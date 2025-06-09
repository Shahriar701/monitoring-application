import json
import os
import boto3
from datetime import datetime, timedelta
import urllib3

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
cloudwatch = boto3.client('cloudwatch')
http = urllib3.PoolManager()

def lambda_handler(event, context):
    """
    Scheduled health monitoring and SLO tracking
    """
    
    table_name = os.environ.get('TABLE_NAME')
    api_url = os.environ.get('API_URL', '').rstrip('/')
    environment = os.environ.get('ENVIRONMENT', 'dev')
    
    if not table_name:
        print("TABLE_NAME environment variable not set")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'TABLE_NAME not configured'})
        }
    
    table = dynamodb.Table(table_name)
    timestamp = datetime.utcnow().isoformat()
    health_results = []
    
    try:
        # 1. Test API health endpoint
        api_health = test_api_health(api_url)
        health_results.append(api_health)
        
        # Store API health metric
        table.put_item(
            Item={
                'ServiceName': 'api-gateway',
                'Timestamp': timestamp,
                'MetricType': 'HEALTH_CHECK',
                'Value': 1.0 if api_health['healthy'] else 0.0,
                'Source': 'health-monitor',
                'Environment': environment,
                'Metadata': json.dumps(api_health)
            }
        )
        
        # 2. Test DynamoDB health
        dynamo_health = test_dynamodb_health(table)
        health_results.append(dynamo_health)
        
        # Store DynamoDB health metric
        table.put_item(
            Item={
                'ServiceName': 'dynamodb',
                'Timestamp': timestamp,
                'MetricType': 'HEALTH_CHECK',
                'Value': 1.0 if dynamo_health['healthy'] else 0.0,
                'Source': 'health-monitor',
                'Environment': environment,
                'Metadata': json.dumps(dynamo_health)
            }
        )
        
        # 3. Calculate SLO metrics
        slo_metrics = calculate_slo_metrics(table, environment)
        health_results.append(slo_metrics)
        
        # Store SLO metrics
        table.put_item(
            Item={
                'ServiceName': 'system',
                'Timestamp': timestamp,
                'MetricType': 'SLO_AVAILABILITY',
                'Value': slo_metrics['availability_percentage'],
                'Source': 'health-monitor',
                'Environment': environment,
                'Metadata': json.dumps(slo_metrics)
            }
        )
        
        # 4. Send CloudWatch metrics
        send_cloudwatch_metrics(health_results, environment)
        
        # 5. Check error budget
        error_budget_alert = check_error_budget(slo_metrics)
        if error_budget_alert:
            health_results.append(error_budget_alert)
        
        # Summary
        overall_healthy = all(result.get('healthy', False) for result in health_results if 'healthy' in result)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Health monitoring completed',
                'timestamp': timestamp,
                'overall_healthy': overall_healthy,
                'results': health_results,
                'environment': environment
            }, default=str)
        }
        
    except Exception as e:
        print(f"Health monitoring error: {str(e)}")
        
        # Store error metric
        table.put_item(
            Item={
                'ServiceName': 'health-monitor',
                'Timestamp': timestamp,
                'MetricType': 'ERROR',
                'Value': 1.0,
                'Source': 'health-monitor',
                'Environment': environment,
                'Metadata': json.dumps({'error': str(e)})
            }
        )
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Health monitoring failed',
                'message': str(e),
                'timestamp': timestamp
            })
        }

def test_api_health(api_url):
    """Test API health endpoint"""
    health_result = {
        'service': 'api-gateway',
        'healthy': False,
        'response_time_ms': None,
        'status_code': None,
        'error': None
    }
    
    if not api_url:
        health_result['error'] = 'API_URL not configured'
        return health_result
    
    try:
        start_time = datetime.utcnow()
        
        # Test health endpoint
        response = http.request(
            'GET',
            f"{api_url}/health",
            timeout=10.0
        )
        
        end_time = datetime.utcnow()
        response_time = (end_time - start_time).total_seconds() * 1000
        
        health_result['response_time_ms'] = response_time
        health_result['status_code'] = response.status
        health_result['healthy'] = response.status == 200
        
        if response.status != 200:
            health_result['error'] = f"Non-200 status code: {response.status}"
        
    except Exception as e:
        health_result['error'] = str(e)
    
    return health_result

def test_dynamodb_health(table):
    """Test DynamoDB health"""
    health_result = {
        'service': 'dynamodb',
        'healthy': False,
        'response_time_ms': None,
        'error': None
    }
    
    try:
        start_time = datetime.utcnow()
        
        # Simple scan to test connectivity
        table.scan(Limit=1)
        
        end_time = datetime.utcnow()
        response_time = (end_time - start_time).total_seconds() * 1000
        
        health_result['response_time_ms'] = response_time
        health_result['healthy'] = True
        
    except Exception as e:
        health_result['error'] = str(e)
    
    return health_result

def calculate_slo_metrics(table, environment):
    """Calculate SLO metrics (99.9% availability target)"""
    # Look at last 24 hours of health checks
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)
    
    slo_metrics = {
        'service': 'slo-tracking',
        'target_availability': 99.9,
        'actual_availability': 0.0,
        'availability_percentage': 0.0,
        'error_budget_remaining': 0.0,
        'total_checks': 0,
        'successful_checks': 0,
        'failed_checks': 0
    }
    
    try:
        # Query health check metrics from last 24 hours
        response = table.scan(
            FilterExpression='#ts >= :yesterday AND MetricType = :health_type',
            ExpressionAttributeNames={'#ts': 'Timestamp'},
            ExpressionAttributeValues={
                ':yesterday': yesterday.isoformat(),
                ':health_type': 'HEALTH_CHECK'
            }
        )
        
        total_checks = 0
        successful_checks = 0
        
        for item in response.get('Items', []):
            total_checks += 1
            if float(item.get('Value', 0)) > 0:
                successful_checks += 1
        
        if total_checks > 0:
            availability_percentage = (successful_checks / total_checks) * 100
            error_budget_used = 100 - availability_percentage
            target_error_budget = 100 - slo_metrics['target_availability']
            error_budget_remaining = max(0, target_error_budget - error_budget_used)
            
            slo_metrics.update({
                'actual_availability': availability_percentage,
                'availability_percentage': availability_percentage,
                'error_budget_remaining': error_budget_remaining,
                'total_checks': total_checks,
                'successful_checks': successful_checks,
                'failed_checks': total_checks - successful_checks
            })
        
    except Exception as e:
        slo_metrics['error'] = str(e)
        print(f"Error calculating SLO metrics: {str(e)}")
    
    return slo_metrics

def check_error_budget(slo_metrics):
    """Check if error budget is being consumed too quickly"""
    error_budget_remaining = slo_metrics.get('error_budget_remaining', 100)
    
    # Alert if error budget is below 50%
    if error_budget_remaining < 0.05:  # 50% of 0.1% error budget
        return {
            'service': 'error-budget',
            'alert': True,
            'severity': 'HIGH',
            'message': f'Error budget critically low: {error_budget_remaining:.3f}% remaining',
            'availability': slo_metrics.get('availability_percentage', 0)
        }
    elif error_budget_remaining < 0.075:  # 75% of 0.1% error budget
        return {
            'service': 'error-budget',
            'alert': True,
            'severity': 'MEDIUM',
            'message': f'Error budget warning: {error_budget_remaining:.3f}% remaining',
            'availability': slo_metrics.get('availability_percentage', 0)
        }
    
    return None

def send_cloudwatch_metrics(health_results, environment):
    """Send metrics to CloudWatch"""
    metric_data = []
    
    for result in health_results:
        service = result.get('service', 'unknown')
        
        # Health status metric
        if 'healthy' in result:
            metric_data.append({
                'MetricName': 'ServiceHealth',
                'Value': 1 if result['healthy'] else 0,
                'Unit': 'Count',
                'Dimensions': [
                    {'Name': 'ServiceName', 'Value': service},
                    {'Name': 'Environment', 'Value': environment}
                ]
            })
        
        # Response time metric
        if 'response_time_ms' in result and result['response_time_ms'] is not None:
            metric_data.append({
                'MetricName': 'ResponseTime',
                'Value': result['response_time_ms'],
                'Unit': 'Milliseconds',
                'Dimensions': [
                    {'Name': 'ServiceName', 'Value': service},
                    {'Name': 'Environment', 'Value': environment}
                ]
            })
        
        # SLO availability metric
        if 'availability_percentage' in result:
            metric_data.append({
                'MetricName': 'AvailabilityPercentage',
                'Value': result['availability_percentage'],
                'Unit': 'Percent',
                'Dimensions': [
                    {'Name': 'Environment', 'Value': environment}
                ]
            })
    
    # Send metrics in batches (CloudWatch limit is 20 per call)
    if metric_data:
        for i in range(0, len(metric_data), 20):
            batch = metric_data[i:i+20]
            cloudwatch.put_metric_data(
                Namespace=f'Monitoring/{environment}',
                MetricData=batch
            ) 