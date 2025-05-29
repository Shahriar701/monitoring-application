# Serverless Monitoring Infrastructure

A complete serverless monitoring solution built with AWS CDK that includes:
- Metrics collection and storage in DynamoDB
- Log processing with Lambda functions
- API endpoints for accessing metrics
- Comprehensive alerting with runbooks
- Automated incident response

## Architecture

![Architecture](docs/architecture.png)

This solution includes the following components:
- **DynamoDB**: Stores application metrics
- **S3 Bucket**: Stores application logs
- **Lambda Functions**:
  - `LogProcessor`: Processes logs from S3 and extracts metrics
  - `ApiLambda`: Provides REST API access to metrics
  - `RunbookExecutor`: Performs automated incident response
- **API Gateway**: Exposes metrics API endpoints
- **CloudWatch Alarms**: Monitors for issues and triggers alerts
- **SNS Topic**: Delivers notifications
- **SSM Parameter Store**: Stores runbook links

## Getting Started

### Prerequisites

- AWS CDK v2 installed
- Node.js 14+ and npm
- AWS CLI configured with appropriate credentials

### Installation

1. Clone this repository
2. Install dependencies:
```bash
cd monitoring-infrastructure
npm install
```

3. Configure email for alerts:
   - Open `lib/monitoring-stack.ts`
   - Replace `your-email@example.com` with your actual email

4. Deploy the stack:
```bash
cdk deploy
```

5. Confirm the SNS subscription in your email.

## Usage

### Sending Logs

Upload log files to the S3 bucket created by the stack. The logs should be in JSON format with the following structure:

```json
{
  "service": "service-name",
  "timestamp": "2023-07-26T15:30:00Z",
  "metrics": {
    "cpu": 42,
    "memory": 512,
    "requests": 100
  }
}
```

### Accessing Metrics

The API provides the following endpoints:

- `GET /metrics` - Get all metrics (supports query params: service, timeRange)
- `POST /metrics` - Create custom metrics
- `GET /health` - Health check endpoint

Example usage:
```bash
# Get metrics for a specific service in the last hour
curl "https://<api-url>/metrics?service=my-service&timeRange=1h"

# Create custom metrics
curl -X POST "https://<api-url>/metrics" \
  -H "Content-Type: application/json" \
  -d '{"service":"my-service","metrics":{"cpu":50,"memory":1024}}'
```

## Runbooks

The system includes automated and manual runbooks for incident response:

### Automated Runbooks

The `RunbookExecutor` Lambda automatically performs initial investigation when alerts trigger:

1. **High Error Rate Runbook**:
   - Queries recent error logs
   - Checks current error rate
   - Initiates automated investigation

2. **High Latency Runbook**:
   - Monitors API latency metrics
   - Investigates potential performance issues

3. **Lambda Error Runbook**:
   - Analyzes Lambda function failures
   - Checks throttling and timeouts

4. **DynamoDB Throttling Runbook**:
   - Monitors table capacity
   - Checks for hot partitions

### Manual Runbooks

Manual runbook links are provided in alarm notifications and stored in SSM Parameter Store:
- `/runbooks/high-error-rate` - High API error rate runbook

## Customization

### Adding New Alarms

Add new alarms to the `lib/monitoring-stack.ts` file following the existing pattern:

```typescript
const newAlarm = new cloudwatch.Alarm(this, 'NewAlarm', {
  metric: new cloudwatch.Metric({
    namespace: 'YourNamespace',
    metricName: 'YourMetric',
    statistic: 'Sum',
    period: cdk.Duration.minutes(5)
  }),
  threshold: 5,
  evaluationPeriods: 2,
  datapointsToAlarm: 2,
  treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
  alarmDescription: 'Detailed alarm description with runbook link',
  comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
});

// Connect to SNS
newAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));
```

### Adding New Runbooks

1. Add a new function to `lambda/runbook-executor/lambda_function.py`:

```python
def execute_new_runbook():
    """
    Executes automated steps for your new alarm type
    """
    # Your automation code here
    return {
        'statusCode': 200,
        'body': json.dumps('Automated runbook steps initiated')
    }
```

2. Update the main handler to call your new function:

```python
if alarm_name == 'NewAlarm':
    return execute_new_runbook()
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
