import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as codepipeline from 'aws-cdk-lib/aws-codepipeline';
import * as codepipelineActions from 'aws-cdk-lib/aws-codepipeline-actions';
import * as codebuild from 'aws-cdk-lib/aws-codebuild';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as eventsTargets from 'aws-cdk-lib/aws-events-targets';

export class PipelineStack extends cdk.Stack {
    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // ===========================================
        // SOURCE CONTROL - GITHUB
        // ===========================================

        // GitHub repository configuration
        const githubOwner = 'Shahriar701'; // Replace with your GitHub username
        const githubRepo = 'monitoring-application';
        const githubBranch = 'master';

        // You'll need to create a GitHub connection in AWS Console first
        // Go to: CodePipeline -> Settings -> Connections -> Create connection
        const githubConnectionArn = `arn:aws:codestar-connections:${this.region}:${this.account}:connection/your-connection-id`;

        // ===========================================
        // ARTIFACTS STORAGE
        // ===========================================

        const artifactsBucket = new s3.Bucket(this, 'PipelineArtifacts', {
            encryption: s3.BucketEncryption.S3_MANAGED,
            blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
            lifecycleRules: [{
                id: 'CleanupArtifacts',
                enabled: true,
                expiration: cdk.Duration.days(30)
            }]
        });

        // ===========================================
        // BUILD PROJECTS
        // ===========================================

        // Unit Tests Build Project
        const testProject = new codebuild.Project(this, 'TestProject', {
            projectName: 'monitoring-app-tests',
            source: codebuild.Source.gitHub({
                owner: githubOwner,
                repo: githubRepo
            }),
            environment: {
                buildImage: codebuild.LinuxBuildImage.STANDARD_5_0,
                computeType: codebuild.ComputeType.SMALL
            },
            buildSpec: codebuild.BuildSpec.fromObject({
                version: '0.2',
                phases: {
                    install: {
                        'runtime-versions': {
                            python: '3.9',
                            nodejs: '22'
                        },
                        commands: [
                            'echo "Installing dependencies..."',
                            'pip install --upgrade pip',
                            'pip install pytest boto3 moto requests',
                            'npm install -g aws-cdk@2.70.0'
                        ]
                    },
                    pre_build: {
                        commands: [
                            'echo "Pre-build phase..."',
                            'python --version',
                            'cdk --version',
                            'aws --version'
                        ]
                    },
                    build: {
                        commands: [
                            'echo "Running unit tests..."',
                            'python -m pytest test/test_circuit_breaker.py -v',
                            'python -m pytest test/test_health_checks.py -v',
                            'python -m pytest test/test_lambda_functions.py -v',
                            'python -m pytest test/test_api_integration.py -v',
                            'echo "Validating CDK syntax..."',
                            'cd infrastructure && npm install && cdk synth --context environment=dev'
                        ]
                    },
                    post_build: {
                        commands: [
                            'echo "All tests passed successfully!"'
                        ]
                    }
                },
                reports: {
                    'pytest-reports': {
                        files: ['test/test-results.xml'],
                        'file-format': 'JUNITXML'
                    }
                }
            })
        });

        // Integration Tests Build Project
        const integrationTestProject = new codebuild.Project(this, 'IntegrationTestProject', {
            projectName: 'monitoring-app-integration-tests',
            source: codebuild.Source.gitHub({
                owner: githubOwner,
                repo: githubRepo
            }),
            environment: {
                buildImage: codebuild.LinuxBuildImage.STANDARD_5_0,
                computeType: codebuild.ComputeType.SMALL
            },
            buildSpec: codebuild.BuildSpec.fromObject({
                version: '0.2',
                phases: {
                    install: {
                        'runtime-versions': {
                            python: '3.9'
                        },
                        commands: [
                            'pip install requests boto3 pytest'
                        ]
                    },
                    build: {
                        commands: [
                            'echo "Running integration tests..."',
                            'export API_URL=$(aws cloudformation describe-stacks --stack-name monitoring-app-dev --query "Stacks[0].Outputs[?OutputKey==\'ApiUrl\'].OutputValue" --output text)',
                            'echo "Testing API at: $API_URL"',
                            'python -m pytest test/test_api_integration.py -v'
                        ]
                    }
                }
            })
        });

        // Build and Package Project
        const buildProject = new codebuild.Project(this, 'BuildProject', {
            projectName: 'monitoring-app-build',
            source: codebuild.Source.gitHub({
                owner: githubOwner,
                repo: githubRepo
            }),
            environment: {
                buildImage: codebuild.LinuxBuildImage.STANDARD_5_0,
                computeType: codebuild.ComputeType.SMALL
            },
            buildSpec: codebuild.BuildSpec.fromObject({
                version: '0.2',
                phases: {
                    install: {
                        'runtime-versions': {
                            python: '3.9',
                            nodejs: '22'
                        },
                        commands: [
                            'npm install -g aws-cdk@2.70.0'
                        ]
                    },
                    build: {
                        commands: [
                            'echo "Building CDK templates..."',
                            'cd infrastructure && npm install',
                            'cdk synth --context environment=dev',
                            'cdk synth --context environment=prod',
                            'echo "Validating Lambda code..."',
                            'echo "Current directory: $(pwd)"',
                            'echo "Directory contents:"',
                            'ls -la',
                            'echo "Looking for Lambda files..."',
                            'if [ -d "src/lambda" ]; then find src/lambda -name "*.py" -exec python -m py_compile {} \\; && echo "Lambda validation successful"; else echo "No src/lambda directory found"; fi'
                        ]
                    }
                },
                artifacts: {
                    files: ['**/*']
                }
            })
        });

        // ===========================================
        // PERMISSIONS
        // ===========================================

        const pipelinePermissions = new iam.PolicyStatement({
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
                'cloudwatch:*'
            ],
            resources: ['*']
        });

        [testProject, integrationTestProject, buildProject].forEach(project => {
            project.addToRolePolicy(pipelinePermissions);
        });

        // ===========================================
        // NOTIFICATIONS
        // ===========================================

        const pipelineNotifications = new sns.Topic(this, 'PipelineNotifications', {
            topicName: 'monitoring-pipeline-notifications',
            displayName: 'Monitoring Pipeline Notifications'
        });

        pipelineNotifications.addSubscription(
            new snsSubscriptions.EmailSubscription('your-email@example.com')
        );

        // ===========================================
        // PIPELINE MONITORING LAMBDA
        // ===========================================

        const pipelineMonitor = new lambda.Function(this, 'PipelineMonitor', {
            functionName: 'monitoring-pipeline-monitor',
            runtime: lambda.Runtime.PYTHON_3_9,
            handler: 'lambda_function.lambda_handler',
            code: lambda.Code.fromAsset('../src/lambda/pipeline-monitor'),
            timeout: cdk.Duration.seconds(60)
        });

        pipelineMonitor.addToRolePolicy(new iam.PolicyStatement({
            actions: ['codepipeline:*', 'cloudwatch:PutMetricData'],
            resources: ['*']
        }));

        // ===========================================
        // MAIN PIPELINE
        // ===========================================

        const pipeline = new codepipeline.Pipeline(this, 'MonitoringPipeline', {
            pipelineName: 'monitoring-application-pipeline',
            artifactBucket: artifactsBucket,
            restartExecutionOnUpdate: true,
            stages: [
                // SOURCE STAGE
                {
                    stageName: 'Source',
                    actions: [
                        new codepipelineActions.GitHubSourceAction({
                            actionName: 'SourceAction',
                            owner: githubOwner,
                            repo: githubRepo,
                            branch: githubBranch,
                            oauthToken: cdk.SecretValue.secretsManager('github-token'), // Store your GitHub token in Secrets Manager
                            output: new codepipeline.Artifact('SourceOutput'),
                            trigger: codepipelineActions.GitHubTrigger.WEBHOOK
                        })
                    ]
                },

                // TEST STAGE
                {
                    stageName: 'Test',
                    actions: [
                        new codepipelineActions.CodeBuildAction({
                            actionName: 'UnitTests',
                            project: testProject,
                            input: new codepipeline.Artifact('SourceOutput'),
                            outputs: [new codepipeline.Artifact('TestOutput')]
                        })
                    ]
                },

                // BUILD STAGE
                {
                    stageName: 'Build',
                    actions: [
                        new codepipelineActions.CodeBuildAction({
                            actionName: 'BuildAndPackage',
                            project: buildProject,
                            input: new codepipeline.Artifact('SourceOutput'),
                            outputs: [new codepipeline.Artifact('BuildOutput')]
                        })
                    ]
                },

                // DEPLOY TO DEV
                {
                    stageName: 'DeployDev',
                    actions: [
                        new codepipelineActions.CloudFormationCreateUpdateStackAction({
                            actionName: 'DeployToDev',
                            templatePath: new codepipeline.Artifact('BuildOutput').atPath('infrastructure/cdk.out/MonitoringStack-dev.template.json'),
                            stackName: 'monitoring-app-dev',
                            adminPermissions: true,
                            replaceOnFailure: true
                        })
                    ]
                },

                // INTEGRATION TESTS
                {
                    stageName: 'IntegrationTest',
                    actions: [
                        new codepipelineActions.CodeBuildAction({
                            actionName: 'IntegrationTests',
                            project: integrationTestProject,
                            input: new codepipeline.Artifact('SourceOutput')
                        })
                    ]
                },

                // MANUAL APPROVAL FOR PRODUCTION
                {
                    stageName: 'ApprovalForProd',
                    actions: [
                        new codepipelineActions.ManualApprovalAction({
                            actionName: 'ManualApproval',
                            notificationTopic: pipelineNotifications,
                            additionalInformation: `
                                🔍 Dev Deployment Complete!
                                📊 Dashboard: https://console.aws.amazon.com/cloudwatch/home#dashboards:name=monitoring-dashboard-dev
                                🏥 Health Check: Please verify all systems are operational
                                📈 SLI/SLO: Check error rates and circuit breaker status
                                ✅ Approve for production deployment when ready
                            `
                        })
                    ]
                },

                // DEPLOY TO PRODUCTION
                {
                    stageName: 'DeployProd',
                    actions: [
                        new codepipelineActions.CloudFormationCreateUpdateStackAction({
                            actionName: 'DeployToProd',
                            templatePath: new codepipeline.Artifact('BuildOutput').atPath('infrastructure/cdk.out/MonitoringStack-prod.template.json'),
                            stackName: 'monitoring-app-prod',
                            adminPermissions: true,
                            replaceOnFailure: false // More conservative for prod
                        })
                    ]
                },

                // PRODUCTION SMOKE TESTS
                {
                    stageName: 'SmokeTestProd',
                    actions: [
                        new codepipelineActions.CodeBuildAction({
                            actionName: 'ProductionSmokeTests',
                            project: new codebuild.Project(this, 'ProdSmokeTestProject', {
                                projectName: 'monitoring-prod-smoke-tests',
                                source: codebuild.Source.gitHub({
                                    owner: githubOwner,
                                    repo: githubRepo
                                }),
                                environment: {
                                    buildImage: codebuild.LinuxBuildImage.STANDARD_5_0,
                                    computeType: codebuild.ComputeType.SMALL,
                                    environmentVariables: {
                                        'PROD_API_URL': {
                                            value: 'https://jczqvn5k31.execute-api.us-east-1.amazonaws.com/prod/'
                                        }
                                    }
                                },
                                role: new iam.Role(this, 'SmokeTestRole', {
                                    assumedBy: new iam.ServicePrincipal('codebuild.amazonaws.com'),
                                    inlinePolicies: {
                                        SmokeTestPolicy: new iam.PolicyDocument({
                                            statements: [
                                                new iam.PolicyStatement({
                                                    actions: [
                                                        'logs:CreateLogGroup',
                                                        'logs:CreateLogStream',
                                                        'logs:PutLogEvents'
                                                    ],
                                                    resources: ['*']
                                                })
                                            ]
                                        })
                                    }
                                }),
                                buildSpec: codebuild.BuildSpec.fromObject({
                                    version: '0.2',
                                    phases: {
                                        install: {
                                            'runtime-versions': { python: '3.9' },
                                            commands: ['pip install requests boto3']
                                        },
                                        build: {
                                            commands: [
                                                'echo "🧪 Running smoke test against production API..."',
                                                'export API_URL=$PROD_API_URL',
                                                'echo "Production API URL: $API_URL"',
                                                'if [ -z "$API_URL" ]; then echo "❌ Production API URL not found, failing smoke test"; exit 1; fi',
                                                'echo ""',
                                                'echo "Testing health endpoint: ${API_URL}health"',
                                                'echo ""',
                                                'http_code=$(curl -s -o /tmp/response.json -w "%{http_code}" "${API_URL}health")',
                                                'echo "HTTP Status Code: $http_code"',
                                                'echo "Response Body:"',
                                                'cat /tmp/response.json || echo "No response body"',
                                                'echo ""',
                                                'if [ "$http_code" = "200" ]; then',
                                                '  echo "✅ Production health check PASSED - API is responding correctly"',
                                                '  if grep -q "healthy" /tmp/response.json && grep -q "circuit_breaker" /tmp/response.json; then',
                                                '    echo "✅ Response content validation PASSED"',
                                                '  else',
                                                '    echo "⚠️  Response content validation FAILED - missing expected fields"',
                                                '    exit 1',
                                                '  fi',
                                                'else',
                                                '  echo "❌ Production health check FAILED with HTTP code: $http_code"',
                                                '  echo "Debug: Full curl response:"',
                                                '  curl -v "${API_URL}health" || true',
                                                '  exit 1',
                                                'fi',
                                                'echo ""',
                                                'echo "🎉 All smoke tests PASSED! Production deployment is healthy."'
                                            ]
                                        }
                                    }
                                })
                            }),
                            input: new codepipeline.Artifact('SourceOutput')
                        })
                    ]
                }
            ]
        });

        // ===========================================
        // PIPELINE MONITORING
        // ===========================================

        // EventBridge rule to monitor pipeline state changes
        const pipelineStateRule = new events.Rule(this, 'PipelineStateRule', {
            eventPattern: {
                source: ['aws.codepipeline'],
                detailType: ['CodePipeline Pipeline Execution State Change'],
                detail: {
                    pipeline: [pipeline.pipelineName]
                }
            }
        });

        pipelineStateRule.addTarget(new eventsTargets.LambdaFunction(pipelineMonitor));
        pipelineStateRule.addTarget(new eventsTargets.SnsTopic(pipelineNotifications));

        // ===========================================
        // OUTPUTS
        // ===========================================

        new cdk.CfnOutput(this, 'GitHubRepository', {
            value: `https://github.com/${githubOwner}/${githubRepo}`,
            description: 'GitHub repository URL'
        });

        new cdk.CfnOutput(this, 'PipelineUrl', {
            value: `https://${this.region}.console.aws.amazon.com/codesuite/codepipeline/pipelines/${pipeline.pipelineName}/view`,
            description: 'CodePipeline console URL'
        });

        new cdk.CfnOutput(this, 'ArtifactsBucket', {
            value: artifactsBucket.bucketName,
            description: 'Pipeline artifacts bucket'
        });
    }
}