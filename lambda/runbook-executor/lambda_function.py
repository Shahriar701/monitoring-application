import json
import boto3
from datetime import datetime, timedelta

def lambda_handler(event, context):
    """
    Automated runbook executor for CloudWatch alarms
    
    This function is triggered by SNS notifications when CloudWatch alarms
    enter the ALARM state. It executes predefined steps based on the alarm type.
    """
    # Parse SNS message
    message = json.loads(event['Records'][0]['Sns']['Message'])
    alarm_name = message['AlarmName']
    
    print(f"Executing automated steps for alarm: {alarm_name}")
    
    if alarm_name == 'HighErrorRateAlarm':
        return execute_error_rate_runbook()
    elif alarm_name == 'HighLatencyAlarm':
        return execute_high_latency_runbook()
    elif alarm_name == 'LambdaErrorAlarm':
        return execute_lambda_error_runbook()
    elif alarm_name == 'DynamoThrottleAlarm':
        return execute_dynamo_throttle_runbook()
    
    return {
        'statusCode': 200,
        'body': json.dumps('No specific runbook found for this alarm')
    }

def execute_error_rate_runbook():
    """
    Executes automated steps for high API error rate alarms
    """
    cloudwatch = boto3.client('cloudwatch')
    logs = boto3.client('logs')
    
    # Automated Step 1: Get recent error logs
    try:
        response = logs.start_query(
            logGroupName='/aws/lambda/MonitoringInfrastructureStack-ApiLambda',
            startTime=int((datetime.now() - timedelta(minutes=30)).timestamp()),
            endTime=int(datetime.now().timestamp()),
            queryString='fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 10'
        )
        
        print(f"Started log query: {response['queryId']}")
        
        # You could wait for results and analyze them
        # For now, just log that we started the investigation
        
    except Exception as e:
        print(f"Failed to start automated investigation: {e}")
    
    # Automated Step 2: Check if the error rate is still high
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=5)
        
        response = cloudwatch.get_metric_statistics(
            Namespace='MonitoringAPI',
            MetricName='ApiError',
            Dimensions=[],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=['Sum']
        )
        
        if len(response['Datapoints']) > 0:
            error_count = response['Datapoints'][0]['Sum']
            print(f"Current error count: {error_count}")
    
    except Exception as e:
        print(f"Failed to check current error rate: {e}")
    
    return {
        'statusCode': 200,
        'body': json.dumps('Automated runbook steps for high error rate initiated')
    }

def execute_high_latency_runbook():
    """
    Executes automated steps for high API latency alarms
    """
    # Placeholder for latency investigation
    print("Executing high latency runbook")
    return {
        'statusCode': 200,
        'body': json.dumps('Automated runbook steps for high latency initiated')
    }

def execute_lambda_error_runbook():
    """
    Executes automated steps for Lambda function error alarms
    """
    # Placeholder for Lambda error investigation
    print("Executing Lambda error runbook")
    return {
        'statusCode': 200,
        'body': json.dumps('Automated runbook steps for Lambda errors initiated')
    }

def execute_dynamo_throttle_runbook():
    """
    Executes automated steps for DynamoDB throttling alarms
    """
    # Placeholder for DynamoDB throttling investigation
    print("Executing DynamoDB throttle runbook")
    return {
        'statusCode': 200,
        'body': json.dumps('Automated runbook steps for DynamoDB throttling initiated')
    } 