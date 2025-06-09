import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as eventsTargets from 'aws-cdk-lib/aws-events-targets';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { ComputeStackProps, ComputeStackOutputs } from '../interfaces/stack-interfaces';

export class ComputeStack extends cdk.Stack implements ComputeStackOutputs {
    public readonly apiLambda: lambda.Function;
    public readonly logProcessor: lambda.Function;
    public readonly healthMonitor: lambda.Function;
    public readonly aiAnalysis: lambda.Function;
    public readonly backupProcessor: lambda.Function;

    constructor(scope: Construct, id: string, props: ComputeStackProps) {
        super(scope, id, props);

        const { environment, projectName, vpc, table, logsBucket, processingQueue, dlq, lambdaRole, apiLambdaRole } = props;

        // API Lambda with circuit breaker
        this.apiLambda = new lambda.Function(this, 'ApiLambda', {
            functionName: `${projectName}-api-${environment}`,
            runtime: lambda.Runtime.PYTHON_3_9,
            handler: 'lambda_function.lambda_handler',
            code: lambda.Code.fromAsset('../src/lambda/api'),
            environment: {
                TABLE_NAME: table.tableName,
                PROCESSING_QUEUE_URL: processingQueue.queueUrl,
                ENVIRONMENT: environment
            },
            timeout: cdk.Duration.seconds(30),
            // reservedConcurrentExecutions removed due to account limits
            vpc: vpc,
            vpcSubnets: {
                subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS
            },
            role: apiLambdaRole
        });

        // Log Processing Lambda
        this.logProcessor = new lambda.Function(this, 'LogProcessor', {
            functionName: `${projectName}-log-processor-${environment}`,
            runtime: lambda.Runtime.PYTHON_3_9,
            handler: 'lambda_function.lambda_handler',
            code: lambda.Code.fromAsset('../src/lambda/log-processor'),
            environment: {
                TABLE_NAME: table.tableName,
                ENVIRONMENT: environment,
                DLQ_URL: dlq.queueUrl
            },
            timeout: cdk.Duration.seconds(30),
            vpc: vpc,
            vpcSubnets: {
                subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS
            },
            role: lambdaRole
        });

        // Health Monitor Lambda
        this.healthMonitor = new lambda.Function(this, 'HealthMonitor', {
            functionName: `${projectName}-health-${environment}`,
            runtime: lambda.Runtime.PYTHON_3_9,
            handler: 'lambda_function.lambda_handler',
            code: lambda.Code.fromAsset('../src/lambda/health-monitor'),
            environment: {
                TABLE_NAME: table.tableName,
                ENVIRONMENT: environment,
                // API_URL will be set via a separate custom resource to avoid circular dependency
                API_URL: 'to-be-configured'
            },
            timeout: cdk.Duration.minutes(5),
            role: lambdaRole
        });

        // AI Analysis Lambda for intelligent monitoring
        this.aiAnalysis = new lambda.Function(this, 'AiAnalysis', {
            functionName: `${projectName}-ai-analysis-${environment}`,
            runtime: lambda.Runtime.PYTHON_3_9,
            handler: 'lambda_function.lambda_handler',
            code: lambda.Code.fromAsset('../src/lambda/ai-analysis'),
            environment: {
                TABLE_NAME: table.tableName,
                ENVIRONMENT: environment
            },
            timeout: cdk.Duration.minutes(15), // AI analysis can take longer
            role: apiLambdaRole // Needs Bedrock permissions
        });

        // Backup Processing Lambda for disaster recovery
        this.backupProcessor = new lambda.Function(this, 'BackupProcessor', {
            functionName: `${projectName}-backup-${environment}`,
            runtime: lambda.Runtime.PYTHON_3_9,
            handler: 'lambda_function.lambda_handler',
            code: lambda.Code.fromAsset('../src/lambda/backup'),
            environment: {
                TABLE_NAME: table.tableName,
                ENVIRONMENT: environment
            },
            timeout: cdk.Duration.minutes(10),
            role: lambdaRole
        });

        // DynamoDB permissions
        table.grantReadWriteData(this.apiLambda);
        table.grantWriteData(this.logProcessor);
        table.grantReadData(this.healthMonitor);
        table.grantReadWriteData(this.aiAnalysis);
        table.grantReadData(this.backupProcessor);

        // S3 permissions
        logsBucket.grantRead(this.logProcessor);

        // SQS permissions
        processingQueue.grantSendMessages(this.apiLambda);
        processingQueue.grantConsumeMessages(this.logProcessor);

        // Scheduled health checks every 5 minutes
        const healthCheckRule = new events.Rule(this, 'HealthCheckSchedule', {
            schedule: events.Schedule.rate(cdk.Duration.minutes(5)),
            description: 'Run health checks every 5 minutes'
        });
        healthCheckRule.addTarget(new eventsTargets.LambdaFunction(this.healthMonitor));

        // Scheduled AI analysis every hour
        const aiAnalysisRule = new events.Rule(this, 'AiAnalysisSchedule', {
            schedule: events.Schedule.rate(cdk.Duration.hours(1)),
            description: 'Run AI analysis every hour'
        });
        aiAnalysisRule.addTarget(new eventsTargets.LambdaFunction(this.aiAnalysis));

        // Scheduled backup every day at 2 AM
        const backupRule = new events.Rule(this, 'BackupSchedule', {
            schedule: events.Schedule.cron({ hour: '2', minute: '0' }),
            description: 'Daily backup at 2 AM'
        });
        backupRule.addTarget(new eventsTargets.LambdaFunction(this.backupProcessor));

        new cdk.CfnOutput(this, 'ApiLambdaArn', {
            value: this.apiLambda.functionArn,
            exportName: `${projectName}-api-lambda-arn-${environment}`
        });

        // Tags
        cdk.Tags.of(this).add('Environment', environment);
        cdk.Tags.of(this).add('Project', projectName);
        cdk.Tags.of(this).add('StackType', 'Compute');
    }
}