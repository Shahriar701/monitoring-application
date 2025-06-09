import json
import os
import boto3
from datetime import datetime, timedelta
from decimal import Decimal
import time

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')
cloudwatch = boto3.client('cloudwatch')

# Circuit breaker state
circuit_breaker = {
    'failures': 0,
    'last_failure_time': None,
    'state': 'CLOSED',  # CLOSED, OPEN, HALF_OPEN
    'failure_threshold': 5,
    'timeout': 60  # seconds
}

def lambda_handler(event, context):
    """
    Main API handler with circuit breaker pattern
    """
    
    # CORS headers
    cors_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    }
    
    try:
        # Handle preflight requests
        if event['httpMethod'] == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': json.dumps({'message': 'CORS preflight'})
            }
        
        # Check circuit breaker
        if not is_circuit_breaker_closed():
            return {
                'statusCode': 503,
                'headers': cors_headers,
                'body': json.dumps({
                    'error': 'Service temporarily unavailable',
                    'circuit_breaker_state': circuit_breaker['state']
                })
            }
        
        # Route requests
        path = event.get('path', '/')
        method = event.get('httpMethod', 'GET')
        
        if path.startswith('/health'):
            response = handle_health_check(event)
        elif path.startswith('/metrics'):
            if method == 'GET':
                response = handle_get_metrics(event)
            elif method == 'POST':
                response = handle_post_metrics(event)
            else:
                response = {
                    'statusCode': 405,
                    'body': json.dumps({'error': 'Method not allowed'})
                }
        else:
            response = {
                'statusCode': 404,
                'body': json.dumps({'error': 'Endpoint not found'})
            }
        
        # Record successful request
        record_circuit_breaker_success()
        
        # Add CORS headers to response
        response['headers'] = {**response.get('headers', {}), **cors_headers}
        return response
        
    except Exception as e:
        print(f"API Error: {str(e)}")
        
        # Record failure for circuit breaker
        record_circuit_breaker_failure()
        
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e),
                'environment': os.environ.get('ENVIRONMENT', 'dev')
            })
        }

def handle_health_check(event):
    """Health check endpoint"""
    
    table_name = os.environ.get('TABLE_NAME')
    environment = os.environ.get('ENVIRONMENT', 'dev')
    
    # Basic health metrics
    health_data = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'environment': environment,
        'circuit_breaker': circuit_breaker['state'],
        'services': {
            'dynamodb': 'unknown',
            'sqs': 'unknown'
        }
    }
    
    try:
        # Test DynamoDB connection
        if table_name:
            table = dynamodb.Table(table_name)
            table.scan(Limit=1)
            health_data['services']['dynamodb'] = 'healthy'
    except Exception:
        health_data['services']['dynamodb'] = 'unhealthy'
        health_data['status'] = 'degraded'
    
    try:
        # Test SQS connection
        queue_url = os.environ.get('PROCESSING_QUEUE_URL')
        if queue_url:
            sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=['All'])
            health_data['services']['sqs'] = 'healthy'
    except Exception:
        health_data['services']['sqs'] = 'unhealthy'
        health_data['status'] = 'degraded'
    
    status_code = 200 if health_data['status'] == 'healthy' else 503
    
    return {
        'statusCode': status_code,
        'body': json.dumps(health_data, default=str)
    }

def handle_get_metrics(event):
    """Get metrics from DynamoDB"""
    
    table_name = os.environ.get('TABLE_NAME')
    if not table_name:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'TABLE_NAME not configured'})
        }
    
    table = dynamodb.Table(table_name)
    query_params = event.get('queryStringParameters') or {}
    
    try:
        # Get service name filter
        service_name = query_params.get('service')
        limit = min(int(query_params.get('limit', 100)), 1000)
        
        if service_name:
            # Query specific service
            response = table.query(
                KeyConditionExpression='ServiceName = :service',
                ExpressionAttributeValues={':service': service_name},
                Limit=limit,
                ScanIndexForward=False  # Latest first
            )
        else:
            # Scan all items (with limit)
            response = table.scan(Limit=limit)
        
        # Convert Decimal to float for JSON serialization
        items = []
        for item in response.get('Items', []):
            converted_item = {}
            for key, value in item.items():
                if isinstance(value, Decimal):
                    converted_item[key] = float(value)
                else:
                    converted_item[key] = value
            items.append(converted_item)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'metrics': items,
                'count': len(items),
                'scanned_count': response.get('ScannedCount', 0)
            }, default=str)
        }
        
    except Exception as e:
        print(f"Error getting metrics: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def handle_post_metrics(event):
    """Post new metrics"""
    
    table_name = os.environ.get('TABLE_NAME')
    queue_url = os.environ.get('PROCESSING_QUEUE_URL')
    
    if not table_name:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'TABLE_NAME not configured'})
        }
    
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        # Validate required fields
        required_fields = ['service_name', 'metric_type', 'value']
        for field in required_fields:
            if field not in body:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': f'Missing required field: {field}'})
                }
        
        # Prepare metric data
        timestamp = datetime.utcnow().isoformat()
        metric_data = {
            'ServiceName': body['service_name'],
            'Timestamp': timestamp,
            'MetricType': body['metric_type'],
            'Value': Decimal(str(body['value'])),
            'Source': 'api',
            'Environment': os.environ.get('ENVIRONMENT', 'dev')
        }
        
        # Add optional metadata
        if 'metadata' in body:
            metric_data['Metadata'] = json.dumps(body['metadata'])
        
        # Store in DynamoDB
        table = dynamodb.Table(table_name)
        table.put_item(Item=metric_data)
        
        # Send to processing queue for additional processing
        if queue_url:
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(body, default=str)
            )
        
        # Send to CloudWatch
        cloudwatch.put_metric_data(
            Namespace=f'Monitoring/{os.environ.get("ENVIRONMENT", "dev")}',
            MetricData=[
                {
                    'MetricName': body['metric_type'],
                    'Value': float(body['value']),
                    'Unit': 'Count',
                    'Dimensions': [
                        {
                            'Name': 'ServiceName',
                            'Value': body['service_name']
                        }
                    ]
                }
            ]
        )
        
        return {
            'statusCode': 201,
            'body': json.dumps({
                'message': 'Metric created successfully',
                'timestamp': timestamp,
                'service_name': body['service_name']
            })
        }
        
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
    except Exception as e:
        print(f"Error posting metrics: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def is_circuit_breaker_closed():
    """Check if circuit breaker allows requests"""
    current_time = time.time()
    
    if circuit_breaker['state'] == 'OPEN':
        # Check if timeout has passed
        if (current_time - circuit_breaker['last_failure_time']) > circuit_breaker['timeout']:
            circuit_breaker['state'] = 'HALF_OPEN'
            return True
        return False
    
    return True

def record_circuit_breaker_failure():
    """Record a failure for circuit breaker"""
    circuit_breaker['failures'] += 1
    circuit_breaker['last_failure_time'] = time.time()
    
    if circuit_breaker['failures'] >= circuit_breaker['failure_threshold']:
        circuit_breaker['state'] = 'OPEN'
        print(f"Circuit breaker opened after {circuit_breaker['failures']} failures")

def record_circuit_breaker_success():
    """Record a success for circuit breaker"""
    if circuit_breaker['state'] == 'HALF_OPEN':
        circuit_breaker['state'] = 'CLOSED'
        circuit_breaker['failures'] = 0
        print("Circuit breaker closed after successful request")
