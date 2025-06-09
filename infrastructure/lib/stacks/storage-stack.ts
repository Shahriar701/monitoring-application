import * as cdk from 'aws-cdk-lib';
import { BaseStackProps, StorageStackOutputs } from '../interfaces/stack-interfaces';
import { Construct } from 'constructs';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';

export class StorageStack extends cdk.Stack implements StorageStackOutputs {
    table: cdk.aws_dynamodb.Table;
    logsBucket: cdk.aws_s3.Bucket;
    backupBucket: cdk.aws_s3.Bucket;

    constructor(scope: Construct, id: string, props: BaseStackProps) {
        super(scope, id, props);

        const { environment, projectName } = props;

        // DynamoDB Table
        this.table = new dynamodb.Table(this, 'ApplicationMetrics', {
            tableName: `${projectName}-matrics-${environment}`,
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
            pointInTimeRecovery: true,
            stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            removalPolicy: environment === 'prod' ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY
        });

        // Global Secondary Index for time-based queries
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

        // S3 Buckets
        this.logsBucket = new s3.Bucket(this, 'LogsBucket', {
            // Let CDK auto-generate bucket name to avoid conflicts
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
            }],
            removalPolicy: environment === 'prod' ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY
        });

        // Cross-region backup bucket (disaster recovery)
        this.backupBucket = new s3.Bucket(this, 'BackupBucket', {
            // Let CDK auto-generate bucket name to avoid conflicts
            versioned: true,
            encryption: s3.BucketEncryption.S3_MANAGED,
            blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
            lifecycleRules: [{
                id: 'BackupLifecycle',
                enabled: true,
                transitions: [{
                    storageClass: s3.StorageClass.GLACIER,
                    transitionAfter: cdk.Duration.days(30)
                }, {
                    storageClass: s3.StorageClass.DEEP_ARCHIVE,
                    transitionAfter: cdk.Duration.days(120) // Must be 90+ days after GLACIER
                }],
                expiration: cdk.Duration.days(2555) // 7 years retention
            }],
            removalPolicy: cdk.RemovalPolicy.RETAIN // Always retain backups
        });


        // Outputs
        new cdk.CfnOutput(this, 'TableName', {
            value: this.table.tableName,
            exportName: `${projectName}-table-name-${environment}`
        });

        new cdk.CfnOutput(this, 'TableArn', {
            value: this.table.tableArn,
            exportName: `${projectName}-table-arn-${environment}`
        });

        new cdk.CfnOutput(this, 'LogsBucketName', {
            value: this.logsBucket.bucketName,
            exportName: `${projectName}-logs-bucket-${environment}`
        });

        // Tags
        cdk.Tags.of(this).add('Environment', environment);
        cdk.Tags.of(this).add('Project', projectName);
        cdk.Tags.of(this).add('StackType', 'Storage');
    }
}