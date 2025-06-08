# ⏱️ High Latency Response Runbook

## Overview
This runbook addresses high latency issues in the monitoring infrastructure, focusing on API Gateway, Lambda, and DynamoDB performance optimization.

## Severity Levels
- **P1**: Response time > 2000ms affecting all users
- **P2**: Response time > 1000ms affecting significant portion of users  
- **P3**: Response time > 500ms affecting some users
- **P4**: Response time degradation but within SLA

## 🚨 Immediate Response (First 10 minutes)

### 1. Confirm High Latency
```bash
# Check current API performance
curl -w "@curl-format.txt" -o /dev/null -s https://YOUR_API_URL/health

# Create curl timing format file
echo "time_namelookup:  %{time_namelookup}\n
time_connect:     %{time_connect}\n
time_appconnect:  %{time_appconnect}\n
time_pretransfer: %{time_pretransfer}\n
time_redirect:    %{time_redirect}\n
time_starttransfer: %{time_starttransfer}\n
time_total:       %{time_total}\n" > curl-format.txt

# Check CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Latency \
  --dimensions Name=ApiName,Value=monitoring-api \
  --start-time $(date -d '30 minutes ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum
```

### 2. AI-Powered Quick Analysis
```bash
# Trigger AI analysis for performance issues
aws lambda invoke --function-name monitoring-ai-analysis-dev \
  --payload '{
    "analysis_type": "performance_degradation",
    "urgency": "high",
    "time_range_minutes": 30
  }' \
  latency_analysis.json

# Get AI recommendations
cat latency_analysis.json | jq '.recommendations'
```

## 🔍 Investigation Phase

### 3. Component Analysis

#### API Gateway Performance
```bash
# Check API Gateway metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name IntegrationLatency \
  --dimensions Name=ApiName,Value=monitoring-api \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum

# Check cache hit rate
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name CacheHitCount \
  --dimensions Name=ApiName,Value=monitoring-api \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum
```

#### Lambda Function Performance
```bash
# Check Lambda duration metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=monitoring-api-dev \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum,P95

# Check cold starts
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name ConcurrentExecutions \
  --dimensions Name=FunctionName,Value=monitoring-api-dev \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Maximum

# Check Lambda errors
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=monitoring-api-dev \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum
```

#### DynamoDB Performance
```bash
# Check DynamoDB latency
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name SuccessfulRequestLatency \
  --dimensions Name=TableName,Value=ApplicationMetrics-dev Name=Operation,Value=Query \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum

# Check for throttling
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name UserErrors \
  --dimensions Name=TableName,Value=ApplicationMetrics-dev \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum
```

### 4. Circuit Breaker Impact Analysis
```bash
# Check circuit breaker state
curl https://YOUR_API_URL/health | jq '.circuit_breaker'

# Analyze circuit breaker transitions
aws logs start-query \
  --log-group-name /aws/lambda/monitoring-api-dev \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --end-time $(date +%s)000 \
  --query-string 'fields @timestamp, @message | filter @message like /circuit_breaker/ | sort @timestamp desc'
```

## 🛠️ Resolution Actions

### 5. Immediate Optimizations

#### Enable API Gateway Caching
```bash
# Enable caching if not already enabled
aws apigateway update-stage \
  --rest-api-id YOUR_API_ID \
  --stage-name dev \
  --patch-ops op=replace,path=/caching/enabled,value=true \
  --patch-ops op=replace,path=/caching/ttlInSeconds,value=300
```

#### Lambda Optimization
```bash
# Increase Lambda memory for better performance
aws lambda update-function-configuration \
  --function-name monitoring-api-dev \
  --memory-size 1024

# Enable provisioned concurrency to reduce cold starts
aws lambda put-provisioned-concurrency-config \
  --function-name monitoring-api-dev \
  --qualifier \$LATEST \
  --provisioned-concurrency-units 5
```

#### DynamoDB Optimization
```bash
# Scale up DynamoDB capacity if needed
aws dynamodb update-table \
  --table-name ApplicationMetrics-dev \
  --provisioned-throughput ReadCapacityUnits=100,WriteCapacityUnits=50

# Check and optimize GSI capacity
aws dynamodb update-table \
  --table-name ApplicationMetrics-dev \
  --global-secondary-index-updates \
  '[{
    "Update": {
      "IndexName": "ServiceNameIndex",
      "ProvisionedThroughput": {
        "ReadCapacityUnits": 50,
        "WriteCapacityUnits": 25
      }
    }
  }]'
```

### 6. Application-Level Optimizations

#### Connection Pool Tuning
```python
# Optimize DynamoDB client configuration
import boto3
from botocore.config import Config

config = Config(
    max_pool_connections=50,
    retries={'max_attempts': 3, 'mode': 'adaptive'},
    read_timeout=30,
    connect_timeout=10
)

dynamodb = boto3.resource('dynamodb', config=config)
```

#### Query Optimization
```python
# Use efficient query patterns
def get_recent_metrics_optimized(service_name, limit=100):
    response = table.query(
        IndexName='ServiceNameIndex',
        KeyConditionExpression=Key('ServiceName').eq(service_name),
        ScanIndexForward=False,  # Get newest first
        Limit=limit,
        ProjectionExpression='ServiceName, Timestamp, MetricType, #val',
        ExpressionAttributeNames={'#val': 'Value'}
    )
    return response['Items']
```

#### Implement Caching
```python
import functools
import time

# Simple in-memory cache with TTL
cache = {}
CACHE_TTL = 300  # 5 minutes

def cache_with_ttl(ttl_seconds=CACHE_TTL):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            now = time.time()
            
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if now - timestamp < ttl_seconds:
                    return result
            
            result = func(*args, **kwargs)
            cache[cache_key] = (result, now)
            return result
        return wrapper
    return decorator

@cache_with_ttl(300)  # Cache for 5 minutes
def get_metrics(service_name):
    # Expensive database operation
    return query_database(service_name)
```

## 📊 Performance Monitoring

### 7. Real-time Performance Tracking
```bash
# Create performance monitoring script
cat > monitor_performance.sh << 'EOF'
#!/bin/bash
API_URL="https://YOUR_API_URL"

while true; do
    start_time=$(date +%s%N)
    response=$(curl -s -w "%{http_code}" "$API_URL/health")
    end_time=$(date +%s%N)
    
    duration=$((($end_time - $start_time) / 1000000))  # Convert to milliseconds
    http_code="${response: -3}"
    
    echo "$(date): Response time: ${duration}ms, HTTP code: $http_code"
    
    if [ $duration -gt 1000 ]; then
        echo "HIGH LATENCY DETECTED: ${duration}ms"
    fi
    
    sleep 30
done
EOF

chmod +x monitor_performance.sh
./monitor_performance.sh
```

### 8. Performance Alerts Setup
```bash
# Create latency alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "API-HighLatency-P95" \
  --alarm-description "API response time P95 is high" \
  --metric-name Latency \
  --namespace AWS/ApiGateway \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 1000 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=ApiName,Value=monitoring-api

# Create Lambda duration alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "Lambda-HighDuration" \
  --alarm-description "Lambda function duration is high" \
  --metric-name Duration \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 5000 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=monitoring-api-dev
```

## 🧪 Load Testing and Validation

### 9. Performance Testing
```bash
# Install Apache Bench if not available
# sudo apt-get install apache2-utils

# Basic load test
ab -n 1000 -c 10 https://YOUR_API_URL/health

# More comprehensive test with POST requests
cat > load_test.sh << 'EOF'
#!/bin/bash
API_URL="https://YOUR_API_URL"

for i in {1..100}; do
    curl -X POST "$API_URL/metrics" \
      -H "Content-Type: application/json" \
      -d "{\"service_name\": \"load-test-$i\", \"metric_type\": \"test\", \"value\": $i}" \
      -w "%{time_total}\n" \
      -s -o /dev/null &
done
wait
EOF

chmod +x load_test.sh
./load_test.sh
```

## 🤖 AI-Powered Performance Optimization

### 10. Continuous AI Analysis
```bash
# Schedule AI performance analysis
aws events put-rule \
  --name "PerformanceAnalysisSchedule" \
  --schedule-expression "rate(15 minutes)" \
  --description "Trigger AI performance analysis every 15 minutes"

# Add Lambda target
aws events put-targets \
  --rule "PerformanceAnalysisSchedule" \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT:function:monitoring-ai-analysis-dev"
```

### AI Performance Insights
The AI analysis provides:
- **Performance bottleneck identification**
- **Resource utilization optimization**
- **Predictive capacity planning**
- **Cost-performance trade-off analysis**
- **Automated tuning recommendations**

## 📈 Long-term Performance Improvements

### 11. Architecture Optimizations
1. **Implement CDN**: Use CloudFront for static content
2. **Database Read Replicas**: For read-heavy workloads
3. **Async Processing**: Move heavy operations to background
4. **Microservices**: Split monolithic functions
5. **Event-Driven Architecture**: Reduce synchronous dependencies

### 12. Monitoring Enhancements
```bash
# Create custom CloudWatch dashboard
aws cloudwatch put-dashboard \
  --dashboard-name "PerformanceMonitoring" \
  --dashboard-body '{
    "widgets": [
      {
        "type": "metric",
        "properties": {
          "metrics": [
            ["AWS/ApiGateway", "Latency", "ApiName", "monitoring-api"],
            ["AWS/Lambda", "Duration", "FunctionName", "monitoring-api-dev"],
            ["AWS/DynamoDB", "SuccessfulRequestLatency", "TableName", "ApplicationMetrics-dev"]
          ],
          "period": 300,
          "stat": "Average",
          "region": "us-east-1",
          "title": "Latency Overview"
        }
      }
    ]
  }'
```

## ✅ Resolution Validation

### 13. Performance Verification
```bash
# Verify improvements
echo "Testing performance improvements..."

# Before and after comparison
for i in {1..10}; do
    curl -w "Response time: %{time_total}s\n" -o /dev/null -s https://YOUR_API_URL/health
    sleep 1
done

# Check if latency is back to normal
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Latency \
  --dimensions Name=ApiName,Value=monitoring-api \
  --start-time $(date -d '15 minutes ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average
```

## 📋 Post-Incident Actions

### 14. Documentation and Learning
- [ ] Document root cause and resolution steps
- [ ] Update performance baselines
- [ ] Review and adjust alerting thresholds
- [ ] Schedule performance review meeting
- [ ] Update runbook with lessons learned

### 15. Preventive Measures
- Implement automated performance testing
- Set up predictive alerts based on trends
- Regular performance benchmarking
- Capacity planning reviews

## Related Resources
- [Database Issues Runbook](./database-issues.md)
- [System Outage Runbook](./system-outage.md)
- [AWS Performance Best Practices](https://docs.aws.amazon.com/wellarchitected/latest/performance-efficiency-pillar/welcome.html)
- [DynamoDB Performance Guide](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)

---
**Last Updated**: December 2024  
**Next Review**: Monthly or after performance incidents