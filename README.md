# 🔍 Monitoring Infrastructure

A comprehensive AWS-based monitoring solution built with CDK, featuring real-time metrics collection, AI-powered analysis, and automated CI/CD pipeline.

## 🏗️ Architecture

This monitoring infrastructure includes:

- **API Gateway** - RESTful API for metrics collection and health checks
- **Lambda Functions** - Serverless processing for API, log processing, health monitoring, and AI analysis
- **DynamoDB** - Scalable metrics storage with GSI for efficient querying
- **CloudWatch** - Dashboards, alarms, and custom metrics
- **SQS** - Reliable message queuing with dead letter queues
- **S3** - Log storage with intelligent lifecycle management
- **SNS** - Multi-channel alerting and notifications
- **EventBridge** - Event-driven automation and scheduling
- **CI/CD Pipeline** - Automated testing, building, and deployment

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ 
- Python 3.9+
- AWS CLI configured
- CDK v2 installed (`npm install -g aws-cdk`)

### Deploy Monitoring Infrastructure

```bash
cd infrastructure
npm install
cdk bootstrap
cdk deploy MonitoringStack
```

### Deploy CI/CD Pipeline

```bash
cdk deploy PipelineStack
```

## 📊 API Endpoints

**Base URL**: `https://YOUR_API_GATEWAY_URL/dev/`

### Health Check
```bash
GET /health
```
Returns service health status and circuit breaker state.

### Submit Metrics
```bash
POST /metrics
Content-Type: application/json

{
  "service_name": "my-service",
  "metric_type": "response_time", 
  "value": 150,
  "metadata": {
    "additional": "data"
  }
}
```

### Get Metrics
```bash
GET /metrics
```
Returns stored metrics with pagination support.

## 🧪 Testing

The infrastructure includes comprehensive testing:

```bash
# API Integration Tests
python test/test_api_integration.py

# Circuit Breaker Tests  
python test/test_circuit_breaker.py

# Health Check Tests
python test/test_health_checks.py
```

## 🔄 CI/CD Pipeline

The pipeline automatically:

1. **Source** - Pulls code from GitHub
2. **Test** - Runs unit and integration tests
3. **Build** - Packages Lambda functions
4. **Deploy Dev** - Deploys to development environment
5. **Integration Test** - Validates deployment
6. **Manual Approval** - Human gate for production
7. **Deploy Prod** - Production deployment
8. **Smoke Test** - Final validation

## 📈 Monitoring Features

- **Circuit Breaker Pattern** - Automatic failure handling
- **Custom CloudWatch Metrics** - Application-specific monitoring
- **Automated Alerting** - SNS notifications for critical events
- **Log Aggregation** - Centralized logging with S3 storage
- **AI-Powered Analysis** - Intelligent insights on metrics patterns
- **Multi-Environment Support** - Dev/Prod environment separation

## 🛠️ Development

### Local Testing
```bash
# Test API endpoints
curl https://YOUR_API_URL/dev/health

# Submit test metrics
curl -X POST https://YOUR_API_URL/dev/metrics \
  -H "Content-Type: application/json" \
  -d '{"service_name": "test", "metric_type": "latency", "value": 100}'
```

### Monitoring Dashboard

Access CloudWatch dashboards through the AWS Console to view:
- API request metrics
- Lambda execution metrics  
- DynamoDB performance
- Custom application metrics

## 📋 Configuration

Key environment variables:
- `ENVIRONMENT` - Target deployment environment (dev/prod)
- `TABLE_NAME` - DynamoDB table name
- `PROCESSING_QUEUE_URL` - SQS queue for async processing

## 🔒 Security

- API throttling and caching
- CORS configuration
- IAM least-privilege access
- VPC isolation for sensitive components
- Encryption at rest and in transit

## 📝 License

MIT License - see LICENSE file for details.
