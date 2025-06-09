import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as iam from 'aws-cdk-lib/aws-iam';
import { BaseStackProps } from '../interfaces/stack-interfaces';

export interface PostDeploymentStackProps extends BaseStackProps {
    healthMonitorFunctionName: string;
}

export class PostDeploymentStack extends cdk.Stack {

    constructor(scope: Construct, id: string, props: PostDeploymentStackProps) {
        super(scope, id, props);

        const { environment, projectName, healthMonitorFunctionName } = props;

        // Custom resource to update Health Monitor Lambda with API URL
        const updateHealthMonitor = new cr.AwsCustomResource(this, 'UpdateHealthMonitorApiUrl', {
            onCreate: {
                service: 'Lambda',
                action: 'updateFunctionConfiguration',
                parameters: {
                    FunctionName: healthMonitorFunctionName,
                    Environment: {
                        Variables: {
                            TABLE_NAME: cdk.Fn.importValue(`${projectName}-table-name-${environment}`),
                            ENVIRONMENT: environment,
                            API_URL: cdk.Fn.importValue(`${projectName}-api-url-${environment}`)
                        }
                    }
                },
                physicalResourceId: cr.PhysicalResourceId.of(`health-monitor-config-${healthMonitorFunctionName}`)
            },
            onUpdate: {
                service: 'Lambda',
                action: 'updateFunctionConfiguration',
                parameters: {
                    FunctionName: healthMonitorFunctionName,
                    Environment: {
                        Variables: {
                            TABLE_NAME: cdk.Fn.importValue(`${projectName}-table-name-${environment}`),
                            ENVIRONMENT: environment,
                            API_URL: cdk.Fn.importValue(`${projectName}-api-url-${environment}`)
                        }
                    }
                }
            },
            policy: cr.AwsCustomResourcePolicy.fromStatements([
                new iam.PolicyStatement({
                    effect: iam.Effect.ALLOW,
                    actions: [
                        'lambda:UpdateFunctionConfiguration',
                        'lambda:GetFunctionConfiguration'
                    ],
                    resources: [`arn:aws:lambda:${this.region}:${this.account}:function:${healthMonitorFunctionName}`]
                })
            ])
        });

        new cdk.CfnOutput(this, 'PostDeploymentComplete', {
            value: 'true',
            description: 'Post-deployment configurations applied',
            exportName: `${projectName}-post-deployment-complete-${environment}`
        });

        // Tags
        cdk.Tags.of(this).add('Environment', environment);
        cdk.Tags.of(this).add('Project', projectName);
        cdk.Tags.of(this).add('StackType', 'PostDeployment');
    }
} 