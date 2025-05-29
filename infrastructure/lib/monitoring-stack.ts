import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cloudwatchActions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as events from 'aws-cdk-lib/aws-events';
import * as eventsTargets from 'aws-cdk-lib/aws-events-targets';

export interface MonitoringStackProps extends cdk.StackProps {
  environment?: string;
}

export class MonitoringStack extends cdk.Stack {
  public readonly api: apigateway.RestApi;
  public readonly vpc: ec2.Vpc;
  public readonly table: dynamodb.Table;

  constructor(scope: Construct, id: string, props?: MonitoringStackProps) {
    super(scope, id, props);

    const environment = props?.environment || 'dev';

    // ===========================================
    // NETWORKING (Day 5: High Availability)
    // ===========================================

    this.vpc = new ec2.Vpc(this, 'MonitoringVPC', {
      vpcName: `monitoring-vpc-${environment}`,
      maxAzs: 3, // Multi-AZ for high availability
      cidr: '10.0.0.0/16',
      natGateways: environment === 'prod' ? 3 : 1, // Cost optimization for dev
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
        {
          cidrMask: 24,
          name: 'Isolated',
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
        }
      ]
    });

    // ===========================================
    // DATA LAYER (Day 1-2: Core Services)
    // ===========================================

    // DynamoDB Table with all enhancements
    this.table = new dynamodb.Table(this, 'ApplicationMetrics', {
      tableName: `ApplicationMetrics-${environment}`,
      partitionKey: {
        name: 'ServiceName',
        type: dynamodb.AttributeType.STRING
      },
      sortKey: {
        name: 'Timestamp',
        type: dynamodb.AttributeType.STRING
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: true, // Day 5: Backup and recovery
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES, // Day 5: Change tracking
      removalPolicy: environment === 'prod' ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY
    });

    // Global Secondary Index for queries
    this.table.addGlobalSecondaryIndex({
      indexName: 'TimestampIndex',
      partitionKey: {
        name: 'Timestamp',
        type: dynamodb.AttributeType.STRING
      },
      sortKey: {
        name: 'ServiceName',
        type: dynamodb.AttributeType.STRING
      }
    });

    // ===========================================
    // STORAGE (Day 2: S3 and Storage)
    // ===========================================

    // S3 Bucket for logs
    const logsBucket = new s3.Bucket(this, 'LogsBucket', {
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      lifecycleRules: [{
        id: 'LogLifecycle',
        enabled: true,
        transitions: [{
          storageClass: s3.StorageClass.INFREQUENT_ACCESS,
          transitionAfter: cdk.Duration.days(30)
        }, {
          storageClass: s3.StorageClass.GLACIER,
          transitionAfter: cdk.Duration.days(90)
        }],
        expiration: cdk.Duration.days(365)
      }]
    });

    // ===========================================
    // MESSAGING (Day 5: Resilience)
    // ===========================================

    // Dead Letter Queue
    const dlq = new sqs.Queue(this, 'ProcessingDLQ', {
      queueName: `monitoring-dlq-${environment}`,
      retentionPeriod: cdk.Duration.days(14),
      encryption: sqs.QueueEncryption.SQS_MANAGED
    });

    // Main Processing Queue
    const processingQueue = new sqs.Queue(this, 'ProcessingQueue', {
      queueName: `monitoring-queue-${environment}`,
      visibilityTimeout: cdk.Duration.seconds(300),
      deadLetterQueue: {
        queue: dlq,
        maxReceiveCount: 3
      },
      encryption: sqs.QueueEncryption.SQS_MANAGED
    });

    // ===========================================
    // COMPUTE (Day 3: Serverless + Day 5: Resilience)
    // ===========================================

    // Log Processing Lambda
    const logProcessor = new lambda.Function(this, 'LogProcessor', {
      functionName: `monitoring-log-processor-${environment}`,
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset('../src/lambda/log-processor'),
      environment: {
        TABLE_NAME: this.table.tableName,
        ENVIRONMENT: environment,
        DLQ_URL: dlq.queueUrl
      },
      timeout: cdk.Duration.seconds(30),
      vpc: this.vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS
      }
    });

    // API Lambda with circuit breaker
    const apiLambda = new lambda.Function(this, 'ApiLambda', {
      functionName: `monitoring-api-${environment}`,
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset('../src/lambda/api'),
      environment: {
        TABLE_NAME: this.table.tableName,
        PROCESSING_QUEUE_URL: processingQueue.queueUrl,
        ENVIRONMENT: environment
      },
      timeout: cdk.Duration.seconds(30),
      vpc: this.vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS
      }
    });

    // Health Monitor Lambda
    const healthMonitor = new lambda.Function(this, 'HealthMonitor', {
      functionName: `monitoring-health-${environment}`,
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset('../src/lambda/health-monitor'),
      environment: {
        TABLE_NAME: this.table.tableName,
        ENVIRONMENT: environment
      },
      timeout: cdk.Duration.minutes(5)
    });

    // AI Analysis Lambda for intelligent monitoring
    const aiAnalysis = new lambda.Function(this, 'AiAnalysis', {
      functionName: `monitoring-ai-analysis-${environment}`,
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset('../src/lambda/ai-analysis'),
      environment: {
        TABLE_NAME: this.table.tableName,
        ENVIRONMENT: environment
      },
      timeout: cdk.Duration.minutes(15) // AI analysis can take longer
    });

    // ===========================================
    // PERMISSIONS
    // ===========================================

    // DynamoDB permissions
    this.table.grantReadWriteData(apiLambda);
    this.table.grantWriteData(logProcessor);
    this.table.grantReadData(healthMonitor);
    this.table.grantReadWriteData(aiAnalysis); // AI needs to read metrics and write analysis

    // S3 permissions
    logsBucket.grantRead(logProcessor);

    // SQS permissions
    processingQueue.grantSendMessages(apiLambda);
    processingQueue.grantConsumeMessages(logProcessor);

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

    apiLambda.addToRolePolicy(cloudwatchPolicy);
    logProcessor.addToRolePolicy(cloudwatchPolicy);
    healthMonitor.addToRolePolicy(cloudwatchPolicy);
    aiAnalysis.addToRolePolicy(cloudwatchPolicy);
    aiAnalysis.addToRolePolicy(bedrockPolicy);
    aiAnalysis.addToRolePolicy(logsPolicy);

    // ===========================================
    // API LAYER (Day 1-3: API Gateway)
    // ===========================================

    this.api = new apigateway.RestApi(this, 'MonitoringApi', {
      restApiName: `monitoring-api-${environment}`,
      description: `Resilient monitoring API - ${environment}`,
      deployOptions: {
        stageName: environment,
        throttlingBurstLimit: environment === 'prod' ? 200 : 50,
        throttlingRateLimit: environment === 'prod' ? 100 : 25,
        cachingEnabled: environment === 'prod',
        cacheClusterEnabled: environment === 'prod',
        cacheClusterSize: environment === 'prod' ? '0.5' : undefined
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key']
      }
    });

    // Lambda integration
    const lambdaIntegration = new apigateway.LambdaIntegration(apiLambda, {
      proxy: true,
      integrationResponses: [{
        statusCode: '200'
      }]
    });

    // API Resources
    const metricsResource = this.api.root.addResource('metrics');
    const healthResource = this.api.root.addResource('health');

    metricsResource.addMethod('GET', lambdaIntegration);
    metricsResource.addMethod('POST', lambdaIntegration);
    healthResource.addMethod('GET', lambdaIntegration);

    // ===========================================
    // MONITORING (Day 4: CloudWatch)
    // ===========================================

    // SNS Topic for alerts
    const alertTopic = new sns.Topic(this, 'AlertTopic', {
      topicName: `monitoring-alerts-${environment}`,
      displayName: `Monitoring Alerts - ${environment.toUpperCase()}`
    });

    // Email subscription (replace with actual email)
    alertTopic.addSubscription(
      new snsSubscriptions.EmailSubscription('your-email@example.com')
    );

    // CloudWatch Dashboard
    const dashboard = new cloudwatch.Dashboard(this, 'MonitoringDashboard', {
      dashboardName: `monitoring-dashboard-${environment}`,
      periodOverride: cloudwatch.PeriodOverride.AUTO
    });

    // API Performance Widget
    const apiWidget = new cloudwatch.GraphWidget({
      title: 'API Performance',
      width: 12,
      height: 6,
      left: [
        apiLambda.metricInvocations({ label: 'Invocations' }),
        apiLambda.metricErrors({ label: 'Errors' })
      ],
      right: [
        apiLambda.metricDuration({ label: 'Duration' })
      ]
    });

    // DynamoDB Widget
    const dynamoWidget = new cloudwatch.GraphWidget({
      title: 'DynamoDB Performance',
      width: 12,
      height: 6,
      left: [
        this.table.metricConsumedReadCapacityUnits({ label: 'Read Capacity' }),
        this.table.metricConsumedWriteCapacityUnits({ label: 'Write Capacity' })
      ],
      right: [
        this.table.metricThrottledRequests({ label: 'Throttled Requests' })
      ]
    });

    dashboard.addWidgets(apiWidget, dynamoWidget);

    // ===========================================
    // ALARMS (Day 4: Monitoring)
    // ===========================================

    // High Error Rate Alarm
    const errorAlarm = apiLambda.metricErrors().createAlarm(this, 'HighErrorRate', {
      threshold: 5,
      evaluationPeriods: 2,
      alarmDescription: 'High error rate detected',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING
    });

    errorAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // High Duration Alarm
    const durationAlarm = apiLambda.metricDuration().createAlarm(this, 'HighDuration', {
      threshold: 10000, // 10 seconds
      evaluationPeriods: 3,
      alarmDescription: 'Lambda function duration too high'
    });

    durationAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // DynamoDB Throttling Alarm
    const throttleAlarm = this.table.metricThrottledRequests().createAlarm(this, 'DynamoThrottling', {
      threshold: 1,
      evaluationPeriods: 1,
      alarmDescription: 'DynamoDB throttling detected'
    });

    throttleAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // ===========================================
    // AUTOMATION (Day 4: Operational Excellence)
    // ===========================================

    // S3 Event Trigger for log processing
    logsBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(logProcessor)
    );

    // Scheduled health checks
    const healthCheckRule = new events.Rule(this, 'HealthCheckSchedule', {
      schedule: events.Schedule.rate(cdk.Duration.minutes(5)),
      description: 'Run health checks every 5 minutes'
    });

    healthCheckRule.addTarget(new eventsTargets.LambdaFunction(healthMonitor));

    // Scheduled AI analysis
    const aiAnalysisRule = new events.Rule(this, 'AiAnalysisSchedule', {
      schedule: events.Schedule.rate(cdk.Duration.hours(1)),
      description: 'Run AI analysis every hour'
    });

    aiAnalysisRule.addTarget(new eventsTargets.LambdaFunction(aiAnalysis));

    // Update health monitor with API URL after API is created
    healthMonitor.addEnvironment('API_URL', this.api.url);

    // ===========================================
    // OUTPUTS
    // ===========================================

    new cdk.CfnOutput(this, 'ApiUrl', {
      value: this.api.url,
      description: 'API Gateway URL',
      exportName: `monitoring-api-url-${environment}`
    });

    new cdk.CfnOutput(this, 'DashboardUrl', {
      value: `https://${this.region}.console.aws.amazon.com/cloudwatch/home?region=${this.region}#dashboards:name=${dashboard.dashboardName}`,
      description: 'CloudWatch Dashboard URL'
    });

    new cdk.CfnOutput(this, 'TableName', {
      value: this.table.tableName,
      description: 'DynamoDB Table Name',
      exportName: `monitoring-table-name-${environment}`
    });
  }
}