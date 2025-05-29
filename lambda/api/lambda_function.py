import json
import boto3
import os
from decimal import Decimal
from datetime import datetime, timedelta
import time
import boto3.dynamodb.conditions as conditions

# Initialize clients
cloudwatch = boto3.client('cloudwatch')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)

def lambda_handler(event, context):
    start_time = time.time()
    
    try:
        http_method = event['httpMethod']
        path = event['path']
        
        # Log structured request info
        print(json.dumps({
            'timestamp': datetime.now().isoformat(),
            'requestId': context.aws_request_id,
            'method': http_method,
            'path': path,
            'userAgent': event.get('headers', {}).get('User-Agent', 'unknown')
        }))
        
        if http_method == 'GET' and path == '/metrics':
            result = get_metrics(event)
        elif http_method == 'POST' and path == '/metrics':
            result = create_metric(event)
        elif http_method == 'GET' and path.startswith('/health'):
            result = health_check()
        else:
            result = {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Not found'})
            }
            
        # Send custom metrics
        send_custom_metrics('ApiSuccess', 1, http_method, path)
        
        return result
        
    except Exception as e:
        # Log error details
        print(json.dumps({
            'timestamp': datetime.now().isoformat(),
            'requestId': context.aws_request_id,
            'level': 'ERROR',
            'message': str(e),
            'method': event.get('httpMethod', 'unknown'),
            'path': event.get('path', 'unknown')
        }))
        
        # Send error metrics
        send_custom_metrics('ApiError', 1, 
                          event.get('httpMethod', 'unknown'), 
                          event.get('path', 'unknown'))
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Internal server error'})
        }
    finally:
        # Send latency metrics
        duration = (time.time() - start_time) * 1000  # Convert to milliseconds
        send_custom_metrics('ApiLatency', duration, 
                          event.get('httpMethod', 'unknown'), 
                          event.get('path', 'unknown'))

def send_custom_metrics(metric_name, value, method, path):
    try:
        cloudwatch.put_metric_data(
            Namespace='MonitoringAPI',
            MetricData=[
                {
                    'MetricName': metric_name,
                    'Value': value,
                    'Unit': 'Count' if metric_name != 'ApiLatency' else 'Milliseconds',
                    'Dimensions': [
                        {
                            'Name': 'Method',
                            'Value': method
                        },
                        {
                            'Name': 'Path', 
                            'Value': path
                        }
                    ],
                    'Timestamp': datetime.now()
                }
            ]
        )
    except Exception as e:
        print(f"Failed to send metrics: {e}")

def get_metrics(event):
    query_params = event.get('queryStringParameters', {}) or {}
    service_name = query_params.get('service')
    time_range = query_params.get('timeRange', '24h')  # Default to last 24 hours
    
    start_time_exec = time.time()
    
    try:
        # Calculate time filter
        end_time = datetime.now().isoformat()
        if time_range == '1h':
            start_time = (datetime.now() - timedelta(hours=1)).isoformat()
        elif time_range == '6h':
            start_time = (datetime.now() - timedelta(hours=6)).isoformat()
        elif time_range == '7d':
            start_time = (datetime.now() - timedelta(days=7)).isoformat()
        elif time_range == '30d':
            start_time = (datetime.now() - timedelta(days=30)).isoformat()
        else:  # Default to 24h
            start_time = (datetime.now() - timedelta(hours=24)).isoformat()
        
        # Query DynamoDB
        if service_name:
            # Query by service name and time range
            response = table.query(
                KeyConditionExpression=conditions.Key('ServiceName').eq(service_name) & 
                                    conditions.Key('Timestamp').between(start_time, end_time)
            )
        else:
            # Query using GSI to get all services in time range
            response = table.query(
                IndexName='TimestampIndex',
                KeyConditionExpression=conditions.Key('Timestamp').between(start_time, end_time)
            )
        
        # Log query performance
        query_duration = (time.time() - start_time_exec) * 1000
        print(json.dumps({
            'timestamp': datetime.now().isoformat(),
            'level': 'INFO',
            'message': 'Database query completed',
            'queryDuration': query_duration,
            'itemCount': len(response['Items']),
            'service': service_name
        }))
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'metrics': response['Items'],
                'count': len(response['Items'])
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(json.dumps({
            'timestamp': datetime.now().isoformat(),
            'level': 'ERROR',
            'message': 'Database query failed',
            'error': str(e),
            'service': service_name
        }))
        raise

def create_metric(event):
    try:
        body = json.loads(event['body'])
        
        # Validate required fields
        if not body or 'service' not in body:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Service name is required'})
            }
        
        # Extract data
        service_name = body['service']
        timestamp = body.get('timestamp', datetime.now().isoformat())
        metrics = body.get('metrics', {})
        
        # Store in DynamoDB
        item = {
            'ServiceName': service_name,
            'Timestamp': timestamp,
            'MetricId': body.get('metricId', f"custom-{datetime.now().timestamp()}"),
            'Metrics': metrics,
            'Source': 'API'
        }
        
        table.put_item(Item=item)
        
        print(json.dumps({
            'timestamp': datetime.now().isoformat(),
            'level': 'INFO',
            'message': 'Metric created successfully',
            'serviceName': service_name
        }))
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Metric created successfully'})
        }
        
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
    except Exception as e:
        print(json.dumps({
            'timestamp': datetime.now().isoformat(),
            'level': 'ERROR',
            'message': 'Failed to create metric',
            'error': str(e)
        }))
        raise

def health_check():
    # Check DynamoDB health
    try:
        table.scan(Limit=1)
        db_status = 'healthy'
    except Exception:
        db_status = 'unhealthy'
    
    health_data = {
        'status': 'healthy' if db_status == 'healthy' else 'degraded',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0',
        'checks': {
            'database': db_status
        }
    }
    
    status_code = 200 if health_data['status'] == 'healthy' else 503
    
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(health_data)
    }