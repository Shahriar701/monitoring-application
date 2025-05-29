import json
import boto3
from datetime import datetime

def lambda_handler(event, context):
    codepipeline = boto3.client('codepipeline')
    cloudwatch = boto3.client('cloudwatch')
    
    try:
        # Get pipeline execution details
        detail = event['detail']
        pipeline_name = detail['pipeline']
        execution_id = detail['execution-id']
        state = detail['state']
        
        # Send custom metrics
        cloudwatch.put_metric_data(
            Namespace='Pipeline/Monitoring',
            MetricData=[
                {
                    'MetricName': 'PipelineExecution',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'PipelineName', 'Value': pipeline_name},
                        {'Name': 'State', 'Value': state}
                    ]
                }
            ]
        )
        
        print(f"Pipeline {pipeline_name} execution {execution_id}: {state}")
        
        return {'statusCode': 200}
        
    except Exception as e:
        print(f"Error monitoring pipeline: {e}")
        return {'statusCode': 500} 