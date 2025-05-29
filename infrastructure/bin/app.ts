#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { MonitoringStack } from '../lib/monitoring-stack';
import { PipelineStack } from '../lib/pipeline-stack';

const app = new cdk.App();

const environment = app.node.tryGetContext('environment') || 'dev';
const region = process.env.CDK_DEFAULT_REGION || 'us-east-1';
const account = process.env.CDK_DEFAULT_ACCOUNT;

const env = { region, account };

// Deploy monitoring application
new MonitoringStack(app, `MonitoringStack-${environment}`, {
  env,
  environment,
  stackName: `monitoring-app-${environment}`,
  description: `Resilient monitoring application with circuit breakers - ${environment}`
});

// Deploy CI/CD pipeline (only in dev account)
if (environment === 'dev') {
  new PipelineStack(app, 'MonitoringPipeline', {
    env,
    stackName: 'monitoring-app-pipeline',
    description: 'CI/CD pipeline for monitoring application'
  });
}

app.synth();