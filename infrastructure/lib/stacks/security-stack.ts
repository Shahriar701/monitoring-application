import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as kms from 'aws-cdk-lib/aws-kms';
import { BaseStackProps } from '../interfaces/stack-interfaces';

export class SecurityStack extends cdk.Stack {
    public readonly lambdaExecutionRole: iam.Role;
    public readonly apiLambdaRole: iam.Role;
    public readonly encryptionKey: kms.Key;

    constructor(scope: Construct, id: string, props: BaseStackProps) {
        super(scope, id, props);

        const { environment, projectName } = props;

        // KMS Encryption Key
        this.encryptionKey = new kms.Key(this, 'EncryptionKey', {
            description: `${projectName} encryption key - ${environment}`,
            enableKeyRotation: true,
            removalPolicy: environment === 'prod' ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY
        });

        // Lambda Execution Role
        this.lambdaExecutionRole = new iam.Role(this, 'LambdaExecutionRole', {
            assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
            roleName: `${projectName}-lambda-execution-${environment}`,
            managedPolicies: [
                iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole')
            ]
        });

        // API Lambda Role (with additional permissions)
        this.apiLambdaRole = new iam.Role(this, 'ApiLambdaRole', {
            assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
            roleName: `${projectName}-api-lambda-${environment}`,
            managedPolicies: [
                iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole')
            ]
        });

        // CloudWatch permissions for custom metrics
        const cloudwatchPolicy = new iam.PolicyStatement({
            actions: [
                'cloudwatch:PutMetricData',
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents'
            ],
            resources: ['*']
        });

        // Bedrock permissions for AI analysis
        const bedrockPolicy = new iam.PolicyStatement({
            actions: [
                'bedrock:InvokeModel'
            ],
            resources: [
                `arn:aws:bedrock:${this.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0`
            ]
        });

        // CloudWatch Logs permissions for AI analysis
        const logsPolicy = new iam.PolicyStatement({
            actions: [
                'logs:StartQuery',
                'logs:GetQueryResults',
                'logs:DescribeLogGroups',
                'logs:DescribeLogStreams'
            ],
            resources: ['*']
        });

        // DynamoDB backup permissions for backup lambda
        const backupPolicy = new iam.PolicyStatement({
            actions: [
                'dynamodb:CreateBackup',
                'dynamodb:DeleteBackup',
                'dynamodb:ListBackups',
                'dynamodb:DescribeBackup',
                'dynamodb:ExportTableToPointInTime'
            ],
            resources: ['*']
        });

        this.lambdaExecutionRole.addToPolicy(cloudwatchPolicy);
        this.lambdaExecutionRole.addToPolicy(backupPolicy);
        this.apiLambdaRole.addToPolicy(cloudwatchPolicy);
        this.apiLambdaRole.addToPolicy(bedrockPolicy);
        this.apiLambdaRole.addToPolicy(logsPolicy);

        // Outputs
        new cdk.CfnOutput(this, 'LambdaExecutionRoleArn', {
            value: this.lambdaExecutionRole.roleArn,
            exportName: `${projectName}-lambda-role-arn-${environment}`
        });

        new cdk.CfnOutput(this, 'EncryptionKeyId', {
            value: this.encryptionKey.keyId,
            exportName: `${projectName}-encryption-key-${environment}`
        });

        // Tags
        cdk.Tags.of(this).add('Environment', environment);
        cdk.Tags.of(this).add('Project', projectName);
        cdk.Tags.of(this).add('StackType', 'Security');
    }
}