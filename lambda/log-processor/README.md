# Log Processor Lambda Function

This Lambda function processes log files uploaded to S3, extracts metrics, and stores them in DynamoDB.

## Function Overview

- **Trigger**: S3 Object Created events
- **Runtime**: Python 3.9
- **Handler**: `lambda_function.lambda_handler`

## Processing Flow

1. Function is triggered when a new log file is uploaded to the S3 bucket
2. The function downloads and reads the log file
3. Each line is parsed as JSON (expecting structured logs)
4. Metrics are extracted from the log data
5. Metrics are stored in the DynamoDB table

## Expected Log Format

The function expects logs in JSON format with the following structure:

```json
{
  "service": "user-service",
  "timestamp": "2023-07-27T15:30:00Z",
  "metrics": {
    "cpu": 35,
    "memory": 612,
    "requests": 120,
    "errors": 2
  },
  "level": "INFO",
  "message": "Service metrics"
}
```

Key fields:
- `service`: Name of the service (required)
- `timestamp`: ISO8601 timestamp (optional, current time used if missing)
- `metrics`: Object containing metric values (optional)

## DynamoDB Storage

Each log entry is stored in DynamoDB with the following attributes:
- `ServiceName`: The service name from the log
- `Timestamp`: The timestamp from the log or current time
- `MetricId`: A generated UUID
- `Metrics`: The metrics object from the log
- `LogFile`: The S3 path to the source log file

## Error Handling

The function includes robust error handling:
- Non-JSON lines are skipped
- Individual line processing errors are caught and logged
- The function continues processing even if some lines fail

## Required Permissions

This Lambda function requires:
- S3 GetObject permission for the logs bucket
- DynamoDB write access to the metrics table
- Basic Lambda execution role permissions

## Local Testing

You can test this function locally using the AWS SAM CLI:

```bash
sam local invoke LogProcessor -e events/s3-put.json
```

Example event files are provided in the `events/` directory.

## Environment Variables

- `TABLE_NAME`: The name of the DynamoDB table that stores metrics 