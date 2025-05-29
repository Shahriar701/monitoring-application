# Monitoring Infrastructure Architecture

## System Overview

The monitoring infrastructure provides a comprehensive solution for collecting, storing, analyzing, and alerting on application metrics and logs. It follows a serverless architecture pattern using AWS services.

## Architecture Diagram

```
┌───────────────┐     ┌───────────┐     ┌───────────────┐
│               │     │           │     │               │
│  Application  │────▶│  S3 Logs  │────▶│ Log Processor │
│               │     │   Bucket  │     │    Lambda     │
└───────────────┘     └───────────┘     └───────┬───────┘
                                                │
                                                ▼
┌───────────────┐     ┌───────────┐     ┌───────────────┐
│               │     │           │     │               │
│ API Gateway   │◀───▶│    API    │◀───▶│   DynamoDB    │
│               │     │   Lambda  │     │    Table      │
└───────────────┘     └───────────┘     └───────────────┘
        │
        │
        ▼
┌───────────────┐     ┌───────────┐     ┌───────────────┐
│               │     │           │     │               │
│   CloudWatch  │────▶│    SNS    │────▶│    Runbook    │
│    Alarms     │     │   Topic   │     │    Executor   │
│               │     │           │     │               │
└───────────────┘     └───────────┘     └───────────────┘
                          │
                          │
                          ▼
                    ┌───────────────┐
                    │               │
                    │    Email      │
                    │ Notifications │
                    │               │
                    └───────────────┘
```

## Component Details

### Data Flow

1. **Log Collection**:
   - Applications write logs to the S3 bucket
   - S3 event notifications trigger the Log Processor Lambda
   - Log Processor extracts metrics and stores them in DynamoDB

2. **Metrics API**:
   - API Gateway exposes REST endpoints
   - API Lambda handles requests and queries DynamoDB
   - Endpoints for reading and writing metrics

3. **Monitoring and Alerting**:
   - CloudWatch alarms monitor metrics for anomalies
   - When thresholds are breached, alarms transition to ALARM state
   - SNS topic receives alarm notifications
   - Email notifications are sent to on-call personnel
   - Runbook Executor Lambda performs automated response

### Key Components

#### Storage

- **DynamoDB Table (ApplicationMetrics)**:
  - Partition Key: ServiceName
  - Sort Key: Timestamp
  - GSI: TimestampIndex (inverted keys for time-based queries)
  - Stores service metrics with metadata

- **S3 Bucket (LogsBucket)**:
  - Stores application logs
  - Lifecycle rules for cost optimization
  - Event notifications for new objects

#### Compute

- **Log Processor Lambda**:
  - Triggered by S3 events
  - Parses logs and extracts metrics
  - Writes metrics to DynamoDB

- **API Lambda**:
  - Handles API Gateway requests
  - Provides metrics data API
  - Supports filtering and aggregation

- **Runbook Executor Lambda**:
  - Triggered by SNS alerts
  - Performs automated incident response
  - Executes runbook procedures

#### API

- **API Gateway**:
  - RESTful API with CORS support
  - Endpoints: `/metrics` (GET/POST), `/health` (GET)
  - Integrated with API Lambda

#### Monitoring

- **CloudWatch Alarms**:
  - API Error Rate
  - API Latency
  - Lambda Errors
  - DynamoDB Throttling

- **CloudWatch Dashboard**:
  - API Performance
  - Lambda Function Health
  - DynamoDB Performance

#### Alerting

- **SNS Topic**:
  - Delivers alarm notifications
  - Email subscription for on-call personnel
  - Lambda subscription for automated response

- **SSM Parameter Store**:
  - Stores runbook links
  - Referenced in alarm descriptions

## Security

- S3 bucket with encryption and public access blocking
- IAM roles with least privilege
- DynamoDB encryption at rest
- API Gateway with appropriate access controls

## Scaling

- Serverless architecture scales automatically
- DynamoDB on-demand capacity
- Lambda concurrency handles burst traffic

## Cost Optimization

- S3 lifecycle rules for log retention
- DynamoDB on-demand pricing
- Serverless compute (pay per use) 