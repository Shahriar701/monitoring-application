#!/bin/bash

# Modular CDK Destroy Script
# Usage: ./destroy.sh [environment]

set -e

# Configuration
ENVIRONMENT=${1:-dev}
PROJECT_NAME="monitoring-app"

echo "🗑️  Destroying ${PROJECT_NAME} stacks for ${ENVIRONMENT} environment"

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo "❌ Invalid environment. Use: dev, staging, or prod"
    exit 1
fi

# Confirmation for production
if [ "$ENVIRONMENT" = "prod" ]; then
    echo "⚠️  WARNING: You are about to destroy PRODUCTION environment!"
    read -p "Type 'DESTROY' to confirm: " confirmation
    if [ "$confirmation" != "DESTROY" ]; then
        echo "❌ Destruction cancelled"
        exit 1
    fi
fi

# Set AWS profile based on environment
case $ENVIRONMENT in
    dev)
        export AWS_PROFILE=${AWS_PROFILE:-default}
        ;;
    staging)
        export AWS_PROFILE=${AWS_PROFILE:-staging}
        ;;
    prod)
        export AWS_PROFILE=${AWS_PROFILE:-production}
        ;;
esac

echo "📋 Using AWS Profile: ${AWS_PROFILE}"

# Destroy stacks in reverse dependency order
echo "🗑️  Destroying stacks in reverse dependency order..."

# 1. Pipeline (if exists)
if [ "$ENVIRONMENT" = "dev" ]; then
    echo "🔄 Destroying Pipeline Stack..."
    cdk destroy ${PROJECT_NAME}-Pipeline \
        --context environment=$ENVIRONMENT \
        --context projectName=$PROJECT_NAME \
        --force || echo "⚠️  Pipeline stack not found or already destroyed"
fi

# 2. Integrations (first - has cross-stack dependencies)
echo "🔗 Destroying Integrations Stack..."
cdk destroy ${PROJECT_NAME}-Integrations-${ENVIRONMENT} \
    --context environment=$ENVIRONMENT \
    --context projectName=$PROJECT_NAME \
    --force || echo "⚠️  Integrations stack not found or already destroyed"

# 3. Monitoring
echo "📊 Destroying Monitoring Stack..."
cdk destroy ${PROJECT_NAME}-Monitoring-${ENVIRONMENT} \
    --context environment=$ENVIRONMENT \
    --context projectName=$PROJECT_NAME \
    --force || echo "⚠️  Monitoring stack not found or already destroyed"

# 4. API
echo "🔌 Destroying API Stack..."
cdk destroy ${PROJECT_NAME}-Api-${ENVIRONMENT} \
    --context environment=$ENVIRONMENT \
    --context projectName=$PROJECT_NAME \
    --force || echo "⚠️  API stack not found or already destroyed"

# 5. Compute
echo "⚡ Destroying Compute Stack..."
cdk destroy ${PROJECT_NAME}-Compute-${ENVIRONMENT} \
    --context environment=$ENVIRONMENT \
    --context projectName=$PROJECT_NAME \
    --force || echo "⚠️  Compute stack not found or already destroyed"

# 6. Messaging
echo "📨 Destroying Messaging Stack..."
cdk destroy ${PROJECT_NAME}-Messaging-${ENVIRONMENT} \
    --context environment=$ENVIRONMENT \
    --context projectName=$PROJECT_NAME \
    --force || echo "⚠️  Messaging stack not found or already destroyed"

# 7. Storage (careful with production)
if [ "$ENVIRONMENT" = "prod" ]; then
    echo "⚠️  Skipping Storage Stack destruction in production (contains retained resources)"
    echo "   Manual cleanup required for: DynamoDB tables, S3 buckets"
else
    echo "💾 Destroying Storage Stack..."
    cdk destroy ${PROJECT_NAME}-Storage-${ENVIRONMENT} \
        --context environment=$ENVIRONMENT \
        --context projectName=$PROJECT_NAME \
        --force || echo "⚠️  Storage stack not found or already destroyed"
fi

# 8. Networking
echo "🌐 Destroying Networking Stack..."
cdk destroy ${PROJECT_NAME}-Networking-${ENVIRONMENT} \
    --context environment=$ENVIRONMENT \
    --context projectName=$PROJECT_NAME \
    --force || echo "⚠️  Networking stack not found or already destroyed"

# 9. Security (last)
echo "🔐 Destroying Security Stack..."
cdk destroy ${PROJECT_NAME}-Security-${ENVIRONMENT} \
    --context environment=$ENVIRONMENT \
    --context projectName=$PROJECT_NAME \
    --force || echo "⚠️  Security stack not found or already destroyed"

echo "✅ Destruction completed!"

if [ "$ENVIRONMENT" = "prod" ]; then
    echo ""
    echo "⚠️  PRODUCTION CLEANUP REMINDER:"
    echo "   - DynamoDB tables with RETAIN policy need manual deletion"
    echo "   - S3 buckets with RETAIN policy need manual deletion"
    echo "   - KMS keys with RETAIN policy need manual deletion"
    echo "   - Check CloudWatch logs for any remaining log groups"
fi 