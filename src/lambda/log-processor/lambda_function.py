import json
import os
import boto3
from datetime import datetime

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    """
    Process log files and extract metrics
    """
    
    table_name = os.environ.get('TABLE_NAME')
    environment = os.environ.get('ENVIRONMENT', 'dev')
    
    if not table_name:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'TABLE_NAME environment variable not set'})
        }
    
    table = dynamodb.Table(table_name)
    
    try:
        # Process each record
        for record in event.get('Records', []):
            if 'eventSource' in record and record['eventSource'] == 'aws:s3':
                # S3 event processing
                bucket = record['s3']['bucket']['name']
                key = record['s3']['object']['key']
                
                print(f"Processing S3 object: {bucket}/{key}")
                
                # Extract metrics from log filename/path
                service_name = extract_service_name(key)
                timestamp = datetime.utcnow().isoformat()
                
                # Store processed log info
                table.put_item(
                    Item={
                        'ServiceName': service_name,
                        'Timestamp': timestamp,
                        'MetricType': 'LOG_PROCESSED',
                        'Value': 1.0,
                        'Source': f"s3://{bucket}/{key}",
                        'Environment': environment
                    }
                )
                
                # Send custom CloudWatch metric
                cloudwatch.put_metric_data(
                    Namespace=f'Monitoring/{environment}',
                    MetricData=[
                        {
                            'MetricName': 'LogsProcessed',
                            'Value': 1,
                            'Unit': 'Count',
                            'Dimensions': [
                                {
                                    'Name': 'ServiceName',
                                    'Value': service_name
                                }
                            ]
                        }
                    ]
                )
            
            elif 'eventSource' in record and record['eventSource'] == 'aws:sqs':
                # SQS message processing
                body = json.loads(record['body'])
                process_metric_data(body, table, environment)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed {len(event.get("Records", []))} records',
                'environment': environment
            })
        }
        
    except Exception as e:
        print(f"Error processing logs: {str(e)}")
        
        # Send to DLQ if configured
        dlq_url = os.environ.get('DLQ_URL')
        if dlq_url:
            sqs = boto3.client('sqs')
            sqs.send_message(
                QueueUrl=dlq_url,
                MessageBody=json.dumps({
                    'error': str(e),
                    'event': event,
                    'timestamp': datetime.utcnow().isoformat()
                })
            )
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Failed to process logs',
                'message': str(e)
            })
        }

def extract_service_name(s3_key):
    """Extract service name from S3 key"""
    # Example: logs/api-service/2024/01/01/logfile.json -> api-service
    parts = s3_key.split('/')
    if len(parts) > 1:
        return parts[1]
    return 'unknown-service'

def process_metric_data(data, table, environment):
    """Process metric data from SQS message"""
    timestamp = datetime.utcnow().isoformat()
    
    table.put_item(
        Item={
            'ServiceName': data.get('service_name', 'unknown'),
            'Timestamp': timestamp,
            'MetricType': data.get('metric_type', 'CUSTOM'),
            'Value': float(data.get('value', 0)),
            'Source': 'sqs',
            'Environment': environment,
            'Metadata': json.dumps(data.get('metadata', {}))
        }
    ) 