#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Environment parameter
ENVIRONMENT=${1:-dev}
PROJECT_NAME=${2:-monitoring-app}

echo -e "${BLUE}🚀 Deploying Modular Monitoring Infrastructure to ${ENVIRONMENT}${NC}"
echo -e "${BLUE}Project: ${PROJECT_NAME}${NC}"
echo ""

# Navigate to infrastructure directory
cd infrastructure

# Build the TypeScript
echo -e "${YELLOW}📦 Building TypeScript...${NC}"
npm run build

# Bootstrap CDK if needed
echo -e "${YELLOW}🔧 Checking CDK bootstrap...${NC}"
cdk bootstrap --context environment=${ENVIRONMENT} --context projectName=${PROJECT_NAME}

# Deploy stacks in correct order to avoid circular dependencies
STACKS=(
    "${PROJECT_NAME}-Networking-${ENVIRONMENT}"
    "${PROJECT_NAME}-Security-${ENVIRONMENT}"
    "${PROJECT_NAME}-Storage-${ENVIRONMENT}"
    "${PROJECT_NAME}-Messaging-${ENVIRONMENT}"
    "${PROJECT_NAME}-Compute-${ENVIRONMENT}"
    "${PROJECT_NAME}-Api-${ENVIRONMENT}"
    "${PROJECT_NAME}-Monitoring-${ENVIRONMENT}"
    "${PROJECT_NAME}-S3Events-${ENVIRONMENT}"
    "${PROJECT_NAME}-PostDeployment-${ENVIRONMENT}"
    "${PROJECT_NAME}-Integrations-${ENVIRONMENT}"
)

echo -e "${BLUE}📋 Deployment Order:${NC}"
for i in "${!STACKS[@]}"; do
    echo -e "${BLUE}  $((i+1)). ${STACKS[$i]}${NC}"
done
echo ""

# Deploy each stack
for STACK in "${STACKS[@]}"; do
    echo -e "${GREEN}🚢 Deploying ${STACK}...${NC}"
    
    cdk deploy ${STACK} \
        --context environment=${ENVIRONMENT} \
        --context projectName=${PROJECT_NAME} \
        --require-approval never \
        --progress events \
        --output outputs.json
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ ${STACK} deployed successfully${NC}"
    else
        echo -e "${RED}❌ Failed to deploy ${STACK}${NC}"
        exit 1
    fi
    echo ""
done

echo -e "${GREEN}🎉 All stacks deployed successfully!${NC}"
echo -e "${BLUE}📊 Stack outputs saved to: infrastructure/outputs.json${NC}"

# Display stack URLs
echo ""
echo -e "${BLUE}🔗 Important URLs:${NC}"
echo -e "${BLUE}  - API Gateway: Check outputs.json for API URL${NC}"
echo -e "${BLUE}  - CloudWatch Dashboards: AWS Console > CloudWatch${NC}"
echo -e "${BLUE}  - DynamoDB Table: ${PROJECT_NAME}-matrics-${ENVIRONMENT}${NC}"

cd .. 