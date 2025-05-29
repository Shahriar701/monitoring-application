import json
import boto3
import time
from datetime import datetime
from decimal import Decimal
import logging
from botocore.exceptions import ClientError
import random

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients with retry configuration
session = boto3.Session()
dynamodb = session.resource('dynamodb', config=boto3.session.Config(
    retries={'max_attempts': 3, 'mode': 'adaptive'}
))
sqs = session.client('sqs')
cloudwatch = session.client('cloudwatch')

# Circuit breaker state
circuit_breaker = {
    'failure_count': 0,
    'last_failure_time': 0,
    'state': 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
}

FAILURE_THRESHOLD = 5
TIMEOUT_DURATION = 60  # seconds

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)

def lambda_handler(event, context):
    start_time = time.time()
    request_id = context.aws_request_id
    
    try:
        # Structured logging
        logger.info(json.dumps({
            'timestamp': datetime.now().isoformat(),
            'requestId': request_id,
            'event': 'request_start',
            'method': event.get('httpMethod'),
            'path': event.get('path')
        }))
        
        # Check circuit breaker
        if is_circuit_open():
            return circuit_breaker_response()
        
        # Route request
        http_method = event['httpMethod']
        path = event['path']
        
        if http_method == 'GET' and path == '/metrics':
            result = get_metrics_with_retry(event, context)
        elif http_method == 'POST' and path == '/metrics':
            result = create_metric_with_queue(event, context)
        elif http_method == 'GET' and path.startswith('/health'):
            result = comprehensive_health_check()
        else:
            result = {
                'statusCode': 404,
                'body': json.dumps({'error': 'Not found'})
            }
        
        # Record success
        record_circuit_breaker_success()
        send_custom_metrics('ApiSuccess', 1, http_method, path)
        
        return result
        
    except Exception as e:
        # Record failure
        record_circuit_breaker_failure()
        
        logger.error(json.dumps({
            'timestamp': datetime.now().isoformat(),
            'requestId': request_id,
            'event': 'request_error',
            'error': str(e),
            'method': event.get('httpMethod'),
            'path': event.get('path')
        }))
        
        send_custom_metrics('ApiError', 1, 
                          event.get('httpMethod', 'unknown'), 
                          event.get('path', 'unknown'))
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'X-Request-ID': request_id
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'requestId': request_id,
                'timestamp': datetime.now().isoformat()
            })
        }
    finally:
        # Always record latency
        duration = (time.time() - start_time) * 1000
        send_custom_metrics('ApiLatency', duration, 
                          event.get('httpMethod', 'unknown'), 
                          event.get('path', 'unknown'))

def is_circuit_open():
    global circuit_breaker
    current_time = time.time()
    
    if circuit_breaker['state'] == 'OPEN':
        if current_time - circuit_breaker['last_failure_time'] > TIMEOUT_DURATION:
            circuit_breaker['state'] = 'HALF_OPEN'
            logger.info("Circuit breaker moving to HALF_OPEN state")
            return False
        return True
    
    return False

def circuit_breaker_response():
    return {
        'statusCode': 503,
        'headers': {
            'Content-Type': 'application/json',
            'Retry-After': '60'
        },
        'body': json.dumps({
            'error': 'Service temporarily unavailable',
            'message': 'Circuit breaker is open. Please try again later.',
            'retryAfter': 60
        })
    }

def record_circuit_breaker_failure():
    global circuit_breaker
    circuit_breaker['failure_count'] += 1
    circuit_breaker['last_failure_time'] = time.time()
    
    if circuit_breaker['failure_count'] >= FAILURE_THRESHOLD:
        circuit_breaker['state'] = 'OPEN'
        logger.warning(f"Circuit breaker OPENED after {circuit_breaker['failure_count']} failures")

def record_circuit_breaker_success():
    global circuit_breaker
    if circuit_breaker['state'] == 'HALF_OPEN':
        circuit_breaker['state'] = 'CLOSED'
        circuit_breaker['failure_count'] = 0
        logger.info("Circuit breaker CLOSED - service recovered")
    elif circuit_breaker['failure_count'] > 0:
        circuit_breaker['failure_count'] = max(0, circuit_breaker['failure_count'] - 1)

def get_metrics_with_retry(event, context, max_retries=3):
    """Get metrics with exponential backoff retry"""
    table = dynamodb.Table(os.environ['TABLE_NAME'])
    
    for attempt in range(max_retries):
        try:
            query_params = event.get('queryStringParameters', {})
            service_name = query_params.get('service') if query_params else None
            
            if service_name:
                response = table.query(
                    KeyConditionExpression='ServiceName = :service',
                    ExpressionAttributeValues={':service': service_name},
                    ScanIndexForward=False,
                    Limit=10
                )
            else:
                response = table.scan(Limit=50)
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Cache-Control': 'max-age=300'  # 5 minutes cache
                },
                'body': json.dumps(response['Items'], cls=DecimalEncoder)
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ProvisionedThroughputExceededException':
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(wait_time)
                    continue
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait_time)
                continue
            raise
    
    raise Exception("Max retries exceeded")

def create_metric_with_queue(event, context):
    """Create metric with SQS fallback for reliability"""
    try:
        body = json.loads(event['body'])
        
        # Validate input
        required_fields = ['serviceName']
        for field in required_fields:
            if field not in body:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': f'Missing required field: {field}'})
                }
        
        # Try direct write first
        try:
            table = dynamodb.Table(os.environ['TABLE_NAME'])
            item = {
                'ServiceName': body['serviceName'],
                'Timestamp': datetime.now().isoformat(),
                'CPUUtilization': body.get('cpuUtilization', 0),
                'MemoryUsage': body.get('memoryUsage', 0),
                'RequestCount': body.get('requestCount', 0)
            }
            
            table.put_item(Item=item)
            
            return {
                'statusCode': 201,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'Metric created successfully'})
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ProvisionedThroughputExceededException':
                # Fallback to SQS for reliable processing
                return queue_metric_for_processing(body)
            raise
            
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }

def queue_metric_for_processing(metric_data):
    """Queue metric for later processing when DynamoDB is overloaded"""
    try:
        message = {
            'action': 'create_metric',
            'data': metric_data,
            'timestamp': datetime.now().isoformat()
        }
        
        sqs.send_message(
            QueueUrl=os.environ['PROCESSING_QUEUE_URL'],
            MessageBody=json.dumps(message)
        )
        
        return {
            'statusCode': 202,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Metric queued for processing',
                'status': 'accepted'
            })
        }
        
    except Exception as e:
        logger.error(f"Failed to queue metric: {e}")
        raise

def comprehensive_health_check():
    """Multi-layer health check"""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0',
        'checks': {}
    }
    
    overall_healthy = True
    
    # Check DynamoDB
    try:
        table = dynamodb.Table(os.environ['TABLE_NAME'])
        table.describe_table()
        health_status['checks']['database'] = {
            'status': 'healthy',
            'responseTime': 0  # Would measure actual response time
        }
    except Exception as e:
        health_status['checks']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        overall_healthy = False
    
    # Check SQS
    try:
        sqs.get_queue_attributes(
            QueueUrl=os.environ['PROCESSING_QUEUE_URL'],
            AttributeNames=['ApproximateNumberOfMessages']
        )
        health_status['checks']['queue'] = {
            'status': 'healthy'
        }
    except Exception as e:
        health_status['checks']['queue'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        overall_healthy = False
    
    # Check circuit breaker state
    health_status['checks']['circuit_breaker'] = {
        'state': circuit_breaker['state'],
        'failure_count': circuit_breaker['failure_count']
    }
    
    if circuit_breaker['state'] == 'OPEN':
        overall_healthy = False
    
    health_status['status'] = 'healthy' if overall_healthy else 'degraded'
    status_code = 200 if overall_healthy else 503
    
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps(health_status)
    }

def send_custom_metrics(metric_name, value, method, path):
    """Send custom metrics to CloudWatch"""
    try:
        cloudwatch.put_metric_data(
            Namespace='MonitoringAPI/Resilient',
            MetricData=[
                {
                    'MetricName': metric_name,
                    'Value': value,
                    'Unit': 'Count' if metric_name != 'ApiLatency' else 'Milliseconds',
                    'Dimensions': [
                        {'Name': 'Method', 'Value': method},
                        {'Name': 'Path', 'Value': path}
                    ],
                    'Timestamp': datetime.now()
                }
            ]
        )
    except Exception as e:
        logger.warning(f"Failed to send metrics: {e}")