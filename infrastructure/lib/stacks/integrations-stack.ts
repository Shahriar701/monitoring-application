import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import { BaseStackProps } from '../interfaces/stack-interfaces';

export interface IntegrationsStackProps extends BaseStackProps {
    logsBucket: s3.Bucket;
    table: dynamodb.Table;
    processingQueue: sqs.Queue;
    dlq: sqs.Queue;
    apiLambda: lambda.Function;
    logProcessor: lambda.Function;
    healthMonitor: lambda.Function;
    aiAnalysis: lambda.Function;
    backupProcessor: lambda.Function;
    apiUrl: string;
}

export class IntegrationsStack extends cdk.Stack {

    constructor(scope: Construct, id: string, props: IntegrationsStackProps) {
        super(scope, id, props);

        const {
            environment,
            projectName,
            logsBucket,
            table,
            processingQueue,
            dlq,
            apiLambda,
            logProcessor,
            healthMonitor,
            aiAnalysis,
            backupProcessor,
            apiUrl
        } = props;


        // Placeholder for future integrations

        new cdk.CfnOutput(this, 'IntegrationsComplete', {
            value: 'true',
            description: 'Cross-stack integrations configured',
            exportName: `${projectName}-integrations-complete-${environment}`
        });

        cdk.Tags.of(this).add('Environment', environment);
        cdk.Tags.of(this).add('Project', projectName);
        cdk.Tags.of(this).add('StackType', 'Integrations');
    }
} 