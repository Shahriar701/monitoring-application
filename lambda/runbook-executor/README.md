# Runbook Executor Lambda

This Lambda function implements automated runbook procedures for handling CloudWatch alarm events. When alarms trigger, this function performs initial triage and remediation steps.

## Function Overview

- **Trigger**: SNS messages from CloudWatch alarms
- **Runtime**: Python 3.9
- **Handler**: `lambda_function.lambda_handler`

## Implemented Runbooks

The Lambda function contains the following automated runbooks:

### 1. High Error Rate Runbook

Handles high API error rates by:
- Querying CloudWatch Logs for recent errors
- Checking current error rate metrics
- Reporting findings for further investigation

### 2. High Latency Runbook

Investigates API latency issues by:
- Analyzing recent latency patterns
- Checking for concurrent resource usage
- Identifying potential bottlenecks

### 3. Lambda Error Runbook

Diagnoses Lambda function errors by:
- Analyzing recent error logs
- Checking for throttling or timeouts
- Verifying resource configurations

### 4. DynamoDB Throttling Runbook

Responds to DynamoDB throttling events by:
- Checking consumed capacity
- Identifying hot partitions
- Monitoring throughput patterns

## Testing

You can test this function locally using the AWS SAM CLI:

```bash
sam local invoke RunbookExecutor -e events/error-alarm.json
```

Example event files are provided in the `events/` directory.

## Adding New Runbooks

To add a new runbook:

1. Create a new function in `lambda_function.py`
2. Add logic to handle the specific alarm type
3. Update the main handler to route to your new function

Example:

```python
def execute_new_alarm_runbook():
    """
    Handles a new type of alarm
    """
    # Your runbook logic here
    return {
        'statusCode': 200,
        'body': json.dumps('New runbook executed')
    }

# Then in lambda_handler:
if alarm_name == 'NewAlarmName':
    return execute_new_alarm_runbook()
```

## Required Permissions

This Lambda function requires the following permissions:
- `logs:StartQuery`
- `logs:GetQueryResults`
- `cloudwatch:GetMetricStatistics`
- Basic Lambda execution role permissions 