import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';

export interface BaseStackProps extends cdk.StackProps {
    environment: string;
    projectName: string;
}

export interface NetworkingStackOutputs {
    vpc: ec2.Vpc;
    privateSubnets: ec2.ISubnet[];
    publicSubnets: ec2.ISubnet[];
    isolatedSubnets: ec2.ISubnet[];
}

export interface StorageStackOutputs {
    table: dynamodb.Table;
    logsBucket: s3.Bucket;
    backupBucket: s3.Bucket;
}

export interface MessagingStackOutputs {
    processingQueue: sqs.Queue;
    dlq: sqs.Queue;
    alertTopic: sns.Topic;
}

export interface ComputeStackOutputs {
    apiLambda: lambda.Function;
    logProcessor: lambda.Function;
    healthMonitor: lambda.Function;
    aiAnalysis: lambda.Function;
    backupProcessor: lambda.Function;
}

export interface ApiStackOutputs {
    api: apigateway.RestApi;
    apiUrl: string;
}

export interface ComputeStackProps extends BaseStackProps {
    vpc: ec2.Vpc;
    table: dynamodb.Table;
    logsBucket: s3.Bucket;
    processingQueue: sqs.Queue;
    dlq: sqs.Queue;
    lambdaRole: iam.Role;
    apiLambdaRole: iam.Role;
}

export interface ApiStackProps extends BaseStackProps {
    apiLambda: lambda.Function;
}

export interface MonitoringStackProps extends BaseStackProps {
    vpc: ec2.Vpc;
    table: dynamodb.Table;
    api: apigateway.RestApi;
    lambdaFunctions: lambda.Function[];
    alertTopic: sns.Topic;
}