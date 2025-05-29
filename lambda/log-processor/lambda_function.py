import json
import boto3
import os
import datetime
import uuid

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def lambda_handler(event, context):
    """
    Process logs from S3 and store metrics in DynamoDB
    
    This function is triggered by S3 events when new log files are uploaded.
    It parses the logs, extracts metrics, and stores them in DynamoDB.
    """
    try:
        # Get S3 bucket and key from event
        for record in event.get('Records', []):
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']
            
            # Get the log file from S3
            s3 = boto3.client('s3')
            response = s3.get_object(Bucket=bucket, Key=key)
            log_content = response['Body'].read().decode('utf-8')
            
            # Parse logs and extract metrics
            # This is a simplified example - customize based on your log format
            log_lines = log_content.splitlines()
            for line in log_lines:
                try:
                    if not line.strip():
                        continue
                        
                    # Assuming log is in JSON format
                    log_data = json.loads(line)
                    
                    # Extract metrics (customize based on your log structure)
                    service_name = log_data.get('service', 'unknown')
                    timestamp = log_data.get('timestamp', datetime.datetime.now().isoformat())
                    metrics = log_data.get('metrics', {})
                    
                    # Store in DynamoDB
                    table.put_item(
                        Item={
                            'ServiceName': service_name,
                            'Timestamp': timestamp,
                            'MetricId': str(uuid.uuid4()),  # Generate unique ID
                            'Metrics': metrics,
                            'LogFile': f"{bucket}/{key}"
                        }
                    )
                except json.JSONDecodeError:
                    # Handle non-JSON logs
                    print(f"Skipping non-JSON log line: {line[:100]}...")
                except Exception as e:
                    print(f"Error processing log line: {str(e)}")
        
        return {
            'statusCode': 200,
            'body': json.dumps('Log processing completed successfully')
        }
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error processing logs: {str(e)}')
        } 