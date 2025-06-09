import * as cdk from 'aws-cdk-lib';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as sns from 'aws-cdk-lib/aws-sns';
import { BaseStackProps, MessagingStackOutputs } from '../interfaces/stack-interfaces';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import { Construct } from 'constructs';

export class MessagingStack extends cdk.Stack implements MessagingStackOutputs {
    public readonly processingQueue: sqs.Queue;
    public readonly dlq: sqs.Queue;
    public readonly alertTopic: sns.Topic;

    constructor(scope: Construct, id: string, props: BaseStackProps) {
        super(scope, id, props);

        const { environment, projectName } = props;

        // Dead Letter Queue
        this.dlq = new sqs.Queue(this, 'DLQ', {
            queueName: `${projectName}-dlq-${environment}`,
            retentionPeriod: cdk.Duration.days(14),
            encryption: sqs.QueueEncryption.SQS_MANAGED
        });

        // Main Processing Queue
        this.processingQueue = new sqs.Queue(this, 'ProcessingQueue', {
            queueName: `${projectName}-queue-${environment}`,
            visibilityTimeout: cdk.Duration.seconds(300),
            deadLetterQueue: {
                queue: this.dlq,
                maxReceiveCount: 3
            },
            encryption: sqs.QueueEncryption.SQS_MANAGED
        });

        // SNS Topics
        this.alertTopic = new sns.Topic(this, 'AlertTopic', {
            topicName: `${projectName}-alerts-${environment}`,
            displayName: `${projectName} Alerts - ${environment.toUpperCase()}`
        });

        // Email subscription for alerts (configurable via context)
        const alertEmail = this.node.tryGetContext('alertEmail') || 'your-email@example.com';
        this.alertTopic.addSubscription(
            new snsSubscriptions.EmailSubscription(alertEmail)
        );

        // Outputs
        new cdk.CfnOutput(this, 'ProcessingQueueUrl', {
            value: this.processingQueue.queueUrl,
            exportName: `${projectName}-queue-url-${environment}`
        });

        new cdk.CfnOutput(this, 'AlertTopicArn', {
            value: this.alertTopic.topicArn,
            exportName: `${projectName}-alert-topic-arn-${environment}`
        });

        // Tags
        cdk.Tags.of(this).add('Environment', environment);
        cdk.Tags.of(this).add('Project', projectName);
        cdk.Tags.of(this).add('StackType', 'Messaging');
    }
} 