# API Lambda Function

This Lambda function powers the metrics API, providing endpoints for retrieving and creating application metrics.

## Function Overview

- **Trigger**: API Gateway requests
- **Runtime**: Python 3.9
- **Handler**: `lambda_function.lambda_handler`

## API Endpoints

The function supports the following endpoints:

### 1. GET /metrics

Retrieves metrics from the DynamoDB table with filtering options.

**Query Parameters**:
- `service` (optional): Filter by service name
- `timeRange` (optional): Time range for metrics. Possible values:
  - `1h`: Last hour
  - `6h`: Last 6 hours
  - `24h`: Last 24 hours (default)
  - `7d`: Last 7 days
  - `30d`: Last 30 days

**Example Response**:
```json
{
  "metrics": [
    {
      "ServiceName": "payment-service",
      "Timestamp": "2023-07-27T15:30:00Z",
      "MetricId": "custom-1690467000.123456",
      "Metrics": {
        "cpu": 45,
        "memory": 512,
        "requests": 230
      },
      "Source": "API"
    }
  ],
  "count": 1
}
```

### 2. POST /metrics

Creates a new custom metric in the DynamoDB table.

**Request Body**:
```json
{
  "service": "payment-service",
  "timestamp": "2023-07-27T15:30:00Z",
  "metrics": {
    "cpu": 45,
    "memory": 512,
    "requests": 230
  }
}
```

**Example Response**:
```json
{
  "message": "Metric created successfully"
}
```

### 3. GET /health

Health check endpoint to verify API functionality.

**Example Response**:
```json
{
  "status": "healthy",
  "timestamp": "2023-07-27T15:30:00Z",
  "version": "1.0",
  "checks": {
    "database": "healthy"
  }
}
```

## Custom Metrics

The function sends custom CloudWatch metrics for monitoring API performance:

- `ApiSuccess`: Successful API calls
- `ApiError`: Failed API calls
- `ApiLatency`: Response time in milliseconds

## Required Permissions

This Lambda function requires:
- DynamoDB read/write access to the metrics table
- CloudWatch PutMetricData permission
- Basic Lambda execution role permissions

## Local Testing

You can test this function locally using the AWS SAM CLI:

```bash
sam local invoke ApiLambda -e events/get-metrics.json
sam local invoke ApiLambda -e events/post-metric.json
sam local invoke ApiLambda -e events/health-check.json
```

## Environment Variables

- `TABLE_NAME`: The name of the DynamoDB table that stores metrics 