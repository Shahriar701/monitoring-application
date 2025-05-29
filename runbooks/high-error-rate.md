# High API Error Rate Runbook

This runbook provides step-by-step instructions for diagnosing and resolving high API error rates.

## Alert Information

- **Alert Name**: HighErrorRateAlarm
- **Severity**: High
- **Description**: The API is experiencing an unusually high error rate.
- **Threshold**: More than 5 errors within a 5-minute period.

## Initial Assessment

1. **Check CloudWatch Dashboard**
   - Log into AWS Console
   - Go to CloudWatch Dashboards
   - Open the "ServerlessMonitoring" dashboard
   - Review the API Performance graph
   
2. **Verify Alert Status**
   - Check if the alert is still active
   - Review recent metrics to see if the issue is ongoing or was transient

## Investigation Steps

### 1. Check CloudWatch Logs

```bash
# Get the most recent error logs
aws logs start-query \
  --log-group-name "/aws/lambda/MonitoringInfrastructureStack-ApiLambda" \
  --start-time $(date -d "30 minutes ago" +%s) \
  --end-time $(date +%s) \
  --query-string "fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20"
```

Analyze the logs for patterns:
- Are errors concentrated in a specific endpoint?
- Is there a common error type or message?
- Are errors coming from a specific client or IP?

### 2. Check DynamoDB Throttling

```bash
# Check for throttled requests
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ThrottledRequests \
  --start-time $(date -d "1 hour ago" +%s) \
  --end-time $(date +%s) \
  --period 300 \
  --statistics Sum \
  --dimensions Name=TableName,Value=ApplicationMetrics
```

### 3. Check Lambda Execution

```bash
# Check Lambda errors
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --start-time $(date -d "1 hour ago" +%s) \
  --end-time $(date +%s) \
  --period 300 \
  --statistics Sum \
  --dimensions Name=FunctionName,Value=MonitoringInfrastructureStack-ApiLambda
```

## Remediation Steps

Based on the findings, take appropriate action:

### DynamoDB Throttling Issues

If DynamoDB is throttling:
1. Consider increasing capacity or switching to on-demand capacity mode
2. Review access patterns for hot keys
3. Implement exponential backoff in the Lambda function

```bash
# Change to on-demand capacity mode if needed
aws dynamodb update-table \
  --table-name ApplicationMetrics \
  --billing-mode PAY_PER_REQUEST
```

### Lambda Function Errors

If Lambda is failing:
1. Check for memory or timeout issues
2. Review recent deployments or code changes
3. Consider rolling back to a stable version

```bash
# Increase Lambda memory if needed
aws lambda update-function-configuration \
  --function-name MonitoringInfrastructureStack-ApiLambda \
  --memory-size 512
```

### API Gateway Issues

If the issue is with API Gateway:
1. Check for throttling or quota limits
2. Review API Gateway logs
3. Check for invalid requests or authentication issues

## Escalation

If unable to resolve within 30 minutes, escalate to:
1. Primary on-call engineer: [Name] - [Contact]
2. Database team (if DynamoDB related): [Contact]
3. Serverless infrastructure team: [Contact]

## Post-Incident Tasks

After resolving the issue:
1. Document the incident and resolution
2. Update this runbook if needed
3. Create tickets for any long-term fixes
4. Schedule a post-mortem if it was a major incident