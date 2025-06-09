#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { NetworkingStack } from '../lib/stacks/networking-stack';
import { StorageStack } from '../lib/stacks/storage-stack';
import { MessagingStack } from '../lib/stacks/messaging-stack';
import { SecurityStack } from '../lib/stacks/security-stack';
import { ComputeStack } from '../lib/stacks/compute-stack';
import { ApiStack } from '../lib/stacks/api-stack';
import { MonitoringStack } from '../lib/stacks/monitoring-stack';
import { S3EventsStack } from '../lib/stacks/s3-events-stack';
import { PostDeploymentStack } from '../lib/stacks/post-deployment-stack';
import { PipelineStack } from '../lib/stacks/pipeline-stack';

const app = new cdk.App();

const environment = app.node.tryGetContext('environment') || 'dev';
const projectName = app.node.tryGetContext('projectName') || 'monitoring-app';
const region = process.env.CDK_DEFAULT_REGION || 'us-east-1';
const account = process.env.CDK_DEFAULT_ACCOUNT;

if (!account) {
  throw new Error('CDK_DEFAULT_ACCOUNT environment variable is required');
}

const env = { region, account };
const baseProps = { env, environment, projectName };

// 1. Networking Foundation
const networkingStack = new NetworkingStack(app, `${projectName}-Networking-${environment}`, {
  ...baseProps,
  stackName: `${projectName}-networking-${environment}`,
  description: `Networking infrastructure - ${environment}`
});

// 2. Security & IAM
const securityStack = new SecurityStack(app, `${projectName}-Security-${environment}`, {
  ...baseProps,
  stackName: `${projectName}-security-${environment}`,
  description: `Security and IAM resources - ${environment}`
});

// 3. Storage Layer
const storageStack = new StorageStack(app, `${projectName}-Storage-${environment}`, {
  ...baseProps,
  stackName: `${projectName}-storage-${environment}`,
  description: `Data storage layer - ${environment}`
});

// 4. Messaging Layer
const messagingStack = new MessagingStack(app, `${projectName}-Messaging-${environment}`, {
  ...baseProps,
  stackName: `${projectName}-messaging-${environment}`,
  description: `Messaging infrastructure - ${environment}`
});

// 5. Compute Layer
const computeStack = new ComputeStack(app, `${projectName}-Compute-${environment}`, {
  ...baseProps,
  stackName: `${projectName}-compute-${environment}`,
  description: `Lambda functions and compute - ${environment}`,
  // Pass dependencies
  vpc: networkingStack.vpc,
  table: storageStack.table,
  logsBucket: storageStack.logsBucket,
  processingQueue: messagingStack.processingQueue,
  dlq: messagingStack.dlq,
  lambdaRole: securityStack.lambdaExecutionRole,
  apiLambdaRole: securityStack.apiLambdaRole
});

// 6. API Layer
const apiStack = new ApiStack(app, `${projectName}-Api-${environment}`, {
  ...baseProps,
  stackName: `${projectName}-api-${environment}`,
  description: `API Gateway and routing - ${environment}`,
  // Pass dependencies
  apiLambda: computeStack.apiLambda
});

// 7. Monitoring & Observability
const monitoringStack = new MonitoringStack(app, `${projectName}-Monitoring-${environment}`, {
  ...baseProps,
  stackName: `${projectName}-monitoring-${environment}`,
  description: `CloudWatch monitoring and alarms - ${environment}`,
  // Pass all dependencies for comprehensive monitoring
  vpc: networkingStack.vpc,
  table: storageStack.table,
  api: apiStack.api,
  lambdaFunctions: [
    computeStack.apiLambda,
    computeStack.logProcessor,
    computeStack.healthMonitor,
    computeStack.aiAnalysis,
    computeStack.backupProcessor
  ],
  alertTopic: messagingStack.alertTopic
});

// 8. S3 Events Stack (after all others to avoid circular dependencies)
const s3EventsStack = new S3EventsStack(app, `${projectName}-S3Events-${environment}`, {
  ...baseProps,
  stackName: `${projectName}-s3events-${environment}`,
  description: `S3 event notifications for log processing - ${environment}`,
  // Use exported values to avoid circular dependencies
  logsBucketName: storageStack.logsBucket.bucketName,
  logProcessorArn: computeStack.logProcessor.functionArn
});

// 9. Post-Deployment Stack (configures cross-stack dependencies after deployment)
const postDeploymentStack = new PostDeploymentStack(app, `${projectName}-PostDeployment-${environment}`, {
  ...baseProps,
  stackName: `${projectName}-post-deployment-${environment}`,
  description: `Post-deployment configurations - ${environment}`,
  healthMonitorFunctionName: computeStack.healthMonitor.functionName
});

if (environment === 'dev') {
  new PipelineStack(app, `${projectName}-Pipeline`, {
    env,
    stackName: `${projectName}-pipeline`,
    description: 'CI/CD pipeline for monitoring application'
  });
}

// Compute stack depends on foundational stacks
computeStack.addDependency(securityStack);
computeStack.addDependency(networkingStack);
computeStack.addDependency(storageStack);
computeStack.addDependency(messagingStack);

// API stack depends on compute
apiStack.addDependency(computeStack);

// Monitoring stack depends on all others
monitoringStack.addDependency(apiStack);
monitoringStack.addDependency(computeStack);
monitoringStack.addDependency(storageStack);
monitoringStack.addDependency(messagingStack);

// S3 Events stack depends on both Storage and Compute stacks
s3EventsStack.addDependency(storageStack);
s3EventsStack.addDependency(computeStack);

// Post-deployment stack depends on API and Compute stacks
postDeploymentStack.addDependency(apiStack);
postDeploymentStack.addDependency(computeStack);
postDeploymentStack.addDependency(storageStack);

app.synth();