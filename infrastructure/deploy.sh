#!/bin/bash

# Modular CDK Deployment Script
# Usage: ./deploy.sh [environment] [stack-name]

set -e

# Configuration
ENVIRONMENT=${1:-dev}
STACK_NAME=${2:-all}
PROJECT_NAME="monitoring-app"

echo "🚀 Deploying ${PROJECT_NAME} stacks for ${ENVIRONMENT} environment"

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo "❌ Invalid environment. Use: dev, staging, or prod"
    exit 1
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

# Build TypeScript
echo "🔨 Building TypeScript..."
npm run build

# Bootstrap CDK (if needed)
echo "🏗️  Bootstrapping CDK..."
cdk bootstrap --context environment=$ENVIRONMENT --context projectName=$PROJECT_NAME

# Deploy stacks in order
if [ "$STACK_NAME" = "all" ]; then
    echo "📦 Deploying all stacks in dependency order..."
    
    # 1. Security & IAM (first)
    echo "🔐 Deploying Security Stack..."
    cdk deploy ${PROJECT_NAME}-Security-${ENVIRONMENT} \
        --context environment=$ENVIRONMENT \
        --context projectName=$PROJECT_NAME \
        --require-approval never
    
    # 2. Networking
    echo "🌐 Deploying Networking Stack..."
    cdk deploy ${PROJECT_NAME}-Networking-${ENVIRONMENT} \
        --context environment=$ENVIRONMENT \
        --context projectName=$PROJECT_NAME \
        --require-approval never
    
    # 3. Storage
    echo "💾 Deploying Storage Stack..."
    cdk deploy ${PROJECT_NAME}-Storage-${ENVIRONMENT} \
        --context environment=$ENVIRONMENT \
        --context projectName=$PROJECT_NAME \
        --require-approval never
    
    # 4. Messaging
    echo "📨 Deploying Messaging Stack..."
    cdk deploy ${PROJECT_NAME}-Messaging-${ENVIRONMENT} \
        --context environment=$ENVIRONMENT \
        --context projectName=$PROJECT_NAME \
        --require-approval never
    
    # 5. Compute
    echo "⚡ Deploying Compute Stack..."
    cdk deploy ${PROJECT_NAME}-Compute-${ENVIRONMENT} \
        --context environment=$ENVIRONMENT \
        --context projectName=$PROJECT_NAME \
        --require-approval never
    
    # 6. API
    echo "🔌 Deploying API Stack..."
    cdk deploy ${PROJECT_NAME}-Api-${ENVIRONMENT} \
        --context environment=$ENVIRONMENT \
        --context projectName=$PROJECT_NAME \
        --require-approval never
    
    # 7. Monitoring
    echo "📊 Deploying Monitoring Stack..."
    cdk deploy ${PROJECT_NAME}-Monitoring-${ENVIRONMENT} \
        --context environment=$ENVIRONMENT \
        --context projectName=$PROJECT_NAME \
        --require-approval never
    
    # 8. Integrations
    echo "🔗 Deploying Integrations Stack..."
    cdk deploy ${PROJECT_NAME}-Integrations-${ENVIRONMENT} \
        --context environment=$ENVIRONMENT \
        --context projectName=$PROJECT_NAME \
        --require-approval never
    
    # 8. Pipeline (dev only)
    if [ "$ENVIRONMENT" = "dev" ]; then
        echo "🔄 Deploying Pipeline Stack..."
        cdk deploy ${PROJECT_NAME}-Pipeline \
            --context environment=$ENVIRONMENT \
            --context projectName=$PROJECT_NAME \
            --require-approval never
    fi
    
else
    # Deploy specific stack
    echo "📦 Deploying specific stack: $STACK_NAME"
    cdk deploy $STACK_NAME \
        --context environment=$ENVIRONMENT \
        --context projectName=$PROJECT_NAME \
        --require-approval never
fi

echo "✅ Deployment completed successfully!"

# Show outputs
echo "📋 Stack Outputs:"
cdk list --context environment=$ENVIRONMENT --context projectName=$PROJECT_NAME

echo ""
echo "🔗 Useful Commands:"
echo "  View stacks: cdk list --context environment=$ENVIRONMENT"
echo "  View diff: cdk diff --context environment=$ENVIRONMENT"
echo "  Destroy: ./destroy.sh $ENVIRONMENT"
echo ""
echo "📊 Dashboard URL will be available in CloudWatch console" 