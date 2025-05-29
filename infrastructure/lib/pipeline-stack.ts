import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as codepipeline from 'aws-cdk-lib/aws-codepipeline';
import * as codepipelineActions from 'aws-cdk-lib/aws-codepipeline-actions';
import * as codecommit from 'aws-cdk-lib/aws-codecommit';
import * as codebuild from 'aws-cdk-lib/aws-codebuild';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';

export class PipelineStack extends cdk.Stack {
    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // Source Repository
        const repository = new codecommit.Repository(this, 'MonitoringRepo', {
            repositoryName: 'monitoring-application',
            description: 'Monitoring application source code'
        });

        // Artifacts Bucket
        const artifactsBucket = new s3.Bucket(this, 'PipelineArtifacts', {
            bucketName: `monitoring-pipeline-artifacts-${this.account}-${this.region}`,
            encryption: s3.BucketEncryption.S3_MANAGED,
            blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
            lifecycleRules: [{
                id: 'CleanupArtifacts',
                enabled: true,
                expiration: cdk.Duration.days(30)
            }]
        });

        // Build Project
        const buildProject = new codebuild.Project(this, 'BuildProject', {
            projectName: 'monitoring-app-build',
            source: codebuild.Source.codeCommit({
                repository: repository
            }),
            environment: {
                buildImage: codebuild.LinuxBuildImage.STANDARD_5_0,
                computeType: codebuild.ComputeType.SMALL,
                privileged: true
            },
            buildSpec: codebuild.BuildSpec.fromObject({
                version: '0.2',
                phases: {
                    install: {
                        'runtime-versions': {
                            python: '3.9',
                            nodejs: '14'
                        },
                        commands: [
                            'npm install -g aws-cdk@latest',
                            'pip install pytest boto3 moto'
                        ]
                    },
                    pre_build: {
                        commands: [
                            'echo "Running tests..."',
                            'python -m pytest tests/unit/ -v',
                            'echo "Validating CDK..."',
                            'cd infrastructure && npm install && cdk synth'
                        ]
                    },
                    build: {
                        commands: [
                            'echo "Building application..."',
                            'cd infrastructure && cdk synth'
                        ]
                    }
                },
                artifacts: {
                    files: ['**/*']
                }
            })
        });

        // Grant permissions to build project
        buildProject.addToRolePolicy(new iam.PolicyStatement({
            actions: [
                'cloudformation:*',
                'iam:*',
                'lambda:*',
                'apigateway:*',
                'dynamodb:*',
                's3:*',
                'logs:*',
                'events:*',
                'sns:*',
                'sqs:*',
                'ec2:*',
                'elasticloadbalancing:*'
            ],
            resources: ['*']
        }));

        // Notifications
        const pipelineNotifications = new sns.Topic(this, 'PipelineNotifications', {
            topicName: 'monitoring-pipeline-notifications'
        });

        pipelineNotifications.addSubscription(
            new snsSubscriptions.EmailSubscription('your-email@example.com')
        );

        // Pipeline
        const pipeline = new codepipeline.Pipeline(this, 'MonitoringPipeline', {
            pipelineName: 'monitoring-application-pipeline',
            artifactBucket: artifactsBucket,
            stages: [
                {
                    stageName: 'Source',
                    actions: [
                        new codepipelineActions.CodeCommitSourceAction({
                            actionName: 'Source',
                            repository: repository,
                            branch: 'main',
                            output: new codepipeline.Artifact('SourceOutput')
                        })
                    ]
                },
                {
                    stageName: 'Build',
                    actions: [
                        new codepipelineActions.CodeBuildAction({
                            actionName: 'Build',
                            project: buildProject,
                            input: new codepipeline.Artifact('SourceOutput'),
                            outputs: [new codepipeline.Artifact('BuildOutput')]
                        })
                    ]
                },
                {
                    stageName: 'DeployDev',
                    actions: [
                        new codepipelineActions.CloudFormationCreateUpdateStackAction({
                            actionName: 'DeployDev',
                            templatePath: new codepipeline.Artifact('BuildOutput').atPath('infrastructure/cdk.out/MonitoringStack-dev.template.json'),
                            stackName: 'MonitoringStack-dev',
                            adminPermissions: true,
                            parameterOverrides: {
                                Environment: 'dev'
                            }
                        })
                    ]
                },
                {
                    stageName: 'ApprovalForProd',
                    actions: [
                        new codepipelineActions.ManualApprovalAction({
                            actionName: 'ApproveForProd',
                            notificationTopic: pipelineNotifications,
                            additionalInformation: 'Please review dev deployment and approve for production'
                        })
                    ]
                },
                {
                    stageName: 'DeployProd',
                    actions: [
                        new codepipelineActions.CloudFormationCreateUpdateStackAction({
                            actionName: 'DeployProd',
                            templatePath: new codepipeline.Artifact('BuildOutput').atPath('infrastructure/cdk.out/MonitoringStack-prod.template.json'),
                            stackName: 'MonitoringStack-prod',
                            adminPermissions: true,
                            parameterOverrides: {
                                Environment: 'prod'
                            }
                        })
                    ]
                }
            ]
        });

        // Outputs
        new cdk.CfnOutput(this, 'RepositoryCloneUrl', {
            value: repository.repositoryCloneUrlHttp,
            description: 'Repository clone URL'
        });

        new cdk.CfnOutput(this, 'PipelineConsoleUrl', {
            value: `https://${this.region}.console.aws.amazon.com/codesuite/codepipeline/pipelines/${pipeline.pipelineName}/view`,
            description: 'Pipeline console URL'
        });
    }
}