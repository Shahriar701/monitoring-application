import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as iam from 'aws-cdk-lib/aws-iam';
import { BaseStackProps } from '../interfaces/stack-interfaces';

export interface S3EventsStackProps extends BaseStackProps {
    logsBucketName: string;
    logProcessorArn: string;
}

export class S3EventsStack extends cdk.Stack {

    constructor(scope: Construct, id: string, props: S3EventsStackProps) {
        super(scope, id, props);

        const { environment, projectName, logsBucketName, logProcessorArn } = props;

        // Custom resource to configure S3 event notifications
        // This avoids circular dependency between Storage and Compute stacks
        const s3EventCustomResource = new cr.AwsCustomResource(this, 'S3EventNotification', {
            installLatestAwsSdk: true, // Use latest SDK with supported runtime
            onCreate: {
                service: 'S3',
                action: 'putBucketNotificationConfiguration',
                parameters: {
                    Bucket: logsBucketName,
                    NotificationConfiguration: {
                        LambdaConfigurations: [
                            {
                                Id: 'LogProcessorTrigger',
                                LambdaFunctionArn: logProcessorArn,
                                Events: ['s3:ObjectCreated:*'],
                                Filter: {
                                    Key: {
                                        FilterRules: [
                                            {
                                                Name: 'prefix',
                                                Value: 'logs/'
                                            }
                                        ]
                                    }
                                }
                            }
                        ]
                    }
                },
                physicalResourceId: cr.PhysicalResourceId.of(`s3-event-${logsBucketName}`)
            },
            onDelete: {
                service: 'S3',
                action: 'putBucketNotificationConfiguration',
                parameters: {
                    Bucket: logsBucketName,
                    NotificationConfiguration: {}
                }
            },
            policy: cr.AwsCustomResourcePolicy.fromStatements([
                new iam.PolicyStatement({
                    effect: iam.Effect.ALLOW,
                    actions: [
                        's3:PutBucketNotification',
                        's3:GetBucketNotification'
                    ],
                    resources: [`arn:aws:s3:::${logsBucketName}`]
                })
            ])
        });

        // Lambda permission for S3 to invoke the log processor
        const lambdaPermission = new cr.AwsCustomResource(this, 'LambdaS3Permission', {
            installLatestAwsSdk: true, // Use latest SDK with supported runtime
            onCreate: {
                service: 'Lambda',
                action: 'addPermission',
                parameters: {
                    FunctionName: logProcessorArn,
                    StatementId: 'S3InvokePermission',
                    Action: 'lambda:InvokeFunction',
                    Principal: 's3.amazonaws.com',
                    SourceArn: `arn:aws:s3:::${logsBucketName}`
                },
                physicalResourceId: cr.PhysicalResourceId.of(`lambda-permission-${logProcessorArn}`)
            },
            onDelete: {
                service: 'Lambda',
                action: 'removePermission',
                parameters: {
                    FunctionName: logProcessorArn,
                    StatementId: 'S3InvokePermission'
                }
            },
            policy: cr.AwsCustomResourcePolicy.fromStatements([
                new iam.PolicyStatement({
                    effect: iam.Effect.ALLOW,
                    actions: [
                        'lambda:AddPermission',
                        'lambda:RemovePermission'
                    ],
                    resources: [logProcessorArn]
                })
            ])
        });

        // Ensure proper order
        s3EventCustomResource.node.addDependency(lambdaPermission);

        new cdk.CfnOutput(this, 'S3EventConfigured', {
            value: 'true',
            description: 'S3 event notification configured',
            exportName: `${projectName}-s3-events-configured-${environment}`
        });

        // Tags
        cdk.Tags.of(this).add('Environment', environment);
        cdk.Tags.of(this).add('Project', projectName);
        cdk.Tags.of(this).add('StackType', 'S3Events');
    }
} 