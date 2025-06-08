# 🗄️ Database Issues Response Runbook

## Overview
This runbook covers DynamoDB-related issues in the monitoring infrastructure, including throttling, capacity planning, and data consistency problems.

## Common DynamoDB Issues

### 1. Read/Write Throttling

**Symptoms:**
- API returns 503 errors intermittently
- High `UserErrors` metric in CloudWatch
- `ProvisionedThroughputExceededException` in logs

**Immediate Actions:**
```bash
# Check current capacity and usage
aws dynamodb describe-table --table-name ApplicationMetrics-dev

# Check throttling metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ReadThrottleEvents \
  --dimensions Name=TableName,Value=ApplicationMetrics-dev \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum

# Check write throttling
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name WriteThrottleEvents \
  --dimensions Name=TableName,Value=ApplicationMetrics-dev \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum
```

**Resolution:**
```bash
# Scale up read capacity (if using provisioned mode)
aws dynamodb update-table \
  --table-name ApplicationMetrics-dev \
  --provisioned-throughput ReadCapacityUnits=50,WriteCapacityUnits=50

# Switch to on-demand if frequent scaling needed
aws dynamodb update-table \
  --table-name ApplicationMetrics-dev \
  --billing-mode PAY_PER_REQUEST
```

### 2. Hot Partition Issues

**Symptoms:**
- Uneven distribution of reads/writes
- Some queries much slower than others
- Throttling despite adequate overall capacity

**Investigation:**
```bash
# Check access patterns
aws dynamodb describe-table --table-name ApplicationMetrics-dev \
  --query 'Table.GlobalSecondaryIndexes[*].{IndexName:IndexName,PartitionKey:KeySchema[0].AttributeName}'

# Analyze query patterns from CloudWatch Insights
aws logs start-query \
  --log-group-name /aws/lambda/monitoring-api-dev \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --end-time $(date +%s)000 \
  --query-string 'fields @timestamp, @message | filter @message like /DynamoDB/ | stats count() by bin(5m)'
```

**Resolution:**
- Implement better partition key distribution
- Use composite partition keys
- Consider write sharding for high-volume items

### 3. GSI Throttling

**Symptoms:**
- Queries on Global Secondary Indexes failing
- High latency for filtered queries
- GSI-specific throttling metrics

**Investigation:**
```bash
# Check GSI capacity and usage
aws dynamodb describe-table --table-name ApplicationMetrics-dev \
  --query 'Table.GlobalSecondaryIndexes[*].{IndexName:IndexName,ReadCapacity:ProvisionedThroughput.ReadCapacityUnits,WriteCapacity:ProvisionedThroughput.WriteCapacityUnits}'

# Check GSI throttling
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ReadThrottledRequests \
  --dimensions Name=TableName,Value=ApplicationMetrics-dev Name=GlobalSecondaryIndexName,Value=ServiceNameIndex \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum
```

**Resolution:**
```bash
# Update GSI capacity
aws dynamodb update-table \
  --table-name ApplicationMetrics-dev \
  --global-secondary-index-updates \
  '[{
    "Update": {
      "IndexName": "ServiceNameIndex",
      "ProvisionedThroughput": {
        "ReadCapacityUnits": 100,
        "WriteCapacityUnits": 100
      }
    }
  }]'
```

### 4. Connection Pool Exhaustion

**Symptoms:**
- Lambda timeouts during DynamoDB operations
- Connection timeout errors
- High memory usage in Lambda functions

**Investigation:**
```bash
# Check Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=monitoring-api-dev \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum

# Check concurrent executions
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name ConcurrentExecutions \
  --dimensions Name=FunctionName,Value=monitoring-api-dev \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Maximum
```

**Resolution:**
- Implement connection pooling in Lambda
- Increase Lambda memory allocation
- Use DynamoDB batch operations
- Implement exponential backoff with jitter

## 🤖 AI-Powered Database Analysis

### Trigger AI Analysis for Database Issues
```bash
# Get AI insights on database performance
aws lambda invoke --function-name monitoring-ai-analysis-dev \
  --payload '{
    "analysis_type": "database_performance",
    "focus": "dynamodb_issues",
    "time_range_hours": 2
  }' \
  db_analysis.json

# Review AI recommendations
cat db_analysis.json | jq '.recommendations'
```

### AI-Suggested Optimizations
The AI analysis can provide:
- Partition key optimization suggestions
- Query pattern improvements
- Capacity planning recommendations
- Cost optimization opportunities

## Performance Optimization

### 1. Query Optimization
```python
# Efficient query patterns
def get_metrics_optimized(service_name, start_time, end_time):
    response = table.query(
        IndexName='ServiceNameIndex',
        KeyConditionExpression=Key('ServiceName').eq(service_name) & 
                              Key('Timestamp').between(start_time, end_time),
        ScanIndexForward=False,  # Get newest first
        Limit=100,
        ProjectionExpression='ServiceName, Timestamp, MetricType, #val',
        ExpressionAttributeNames={'#val': 'Value'}
    )
    return response['Items']
```

### 2. Batch Operations
```python
# Use batch operations for better efficiency
def batch_write_metrics(metrics_list):
    with table.batch_writer() as batch:
        for metric in metrics_list:
            batch.put_item(Item=metric)
```

### 3. Connection Pool Configuration
```python
import boto3
from botocore.config import Config

# Optimized DynamoDB client
config = Config(
    max_pool_connections=50,
    retries={'max_attempts': 3, 'mode': 'adaptive'}
)

dynamodb = boto3.resource('dynamodb', config=config)
```

## Monitoring and Alerting

### Key Metrics to Monitor
1. **Read/Write Capacity Utilization**: Should stay under 80%
2. **Throttling Events**: Should be zero or minimal
3. **Error Rate**: DynamoDB-related errors in application logs
4. **Latency**: P95/P99 response times for database operations

### CloudWatch Alarms
```bash
# Create throttling alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "DynamoDB-ReadThrottling" \
  --alarm-description "DynamoDB read throttling detected" \
  --metric-name ReadThrottledRequests \
  --namespace AWS/DynamoDB \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --dimensions Name=TableName,Value=ApplicationMetrics-dev

# Create high latency alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "DynamoDB-HighLatency" \
  --alarm-description "DynamoDB operations taking too long" \
  --metric-name SuccessfulRequestLatency \
  --namespace AWS/DynamoDB \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 100 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=TableName,Value=ApplicationMetrics-dev
```

## Data Consistency Issues

### 1. Eventually Consistent Reads
- Default read consistency is eventually consistent
- Use strongly consistent reads only when necessary
- Implement retry logic for critical operations

### 2. Global Secondary Index Consistency
- GSI updates are eventually consistent
- Plan for propagation delays
- Implement data validation checks

## Backup and Recovery

### 1. Point-in-Time Recovery
```bash
# Enable PITR if not already enabled
aws dynamodb update-continuous-backups \
  --table-name ApplicationMetrics-dev \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true

# Check PITR status
aws dynamodb describe-continuous-backups --table-name ApplicationMetrics-dev
```

### 2. On-Demand Backups
```bash
# Create manual backup
aws dynamodb create-backup \
  --table-name ApplicationMetrics-dev \
  --backup-name "ApplicationMetrics-dev-$(date +%Y%m%d-%H%M%S)"

# List existing backups
aws dynamodb list-backups --table-name ApplicationMetrics-dev
```

### 3. Cross-Region Replication
Consider DynamoDB Global Tables for:
- Disaster recovery
- Multi-region deployments
- Read performance optimization

## Cost Optimization

### 1. Capacity Mode Selection
- **On-Demand**: Unpredictable traffic, sporadic usage
- **Provisioned**: Predictable traffic, cost optimization

### 2. Storage Optimization
```bash
# Check table size and item count
aws dynamodb describe-table --table-name ApplicationMetrics-dev \
  --query 'Table.{ItemCount:ItemCount,TableSizeBytes:TableSizeBytes}'

# Implement TTL for automatic cleanup
aws dynamodb update-time-to-live \
  --table-name ApplicationMetrics-dev \
  --time-to-live-specification Enabled=true,AttributeName=TTL
```

## Troubleshooting Checklist

### Before Escalating
- [ ] Check CloudWatch metrics for throttling
- [ ] Review recent application logs for DynamoDB errors
- [ ] Verify table and GSI capacity settings
- [ ] Check AWS service health dashboard
- [ ] Run AI analysis for insights
- [ ] Test with direct AWS CLI commands

### Emergency Procedures
1. **Scale up capacity** immediately if throttling detected
2. **Switch to on-demand** if provisioned capacity insufficient
3. **Implement circuit breaker** to protect against cascading failures
4. **Use read replicas** for read-heavy workloads if available

## Related Documentation
- [AWS DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [DynamoDB Troubleshooting](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Programming.Errors.html)
- [System Outage Runbook](./system-outage.md)
- [Performance Tuning Guide](./performance-tuning.md)

---
**Last Updated**: December 2024  
**Next Review**: Quarterly or after database incidents
