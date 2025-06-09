import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import { ApiStackProps, ApiStackOutputs } from '../interfaces/stack-interfaces';

export class ApiStack extends cdk.Stack implements ApiStackOutputs {
    public readonly api: apigateway.RestApi;
    public readonly apiUrl: string;

    constructor(scope: Construct, id: string, props: ApiStackProps) {
        super(scope, id, props);

        const { environment, projectName, apiLambda } = props;

        this.api = new apigateway.RestApi(this, 'MonitoringApi', {
            restApiName: `${projectName}-api-${environment}`,
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
        const analyticsResource = this.api.root.addResource('analytics');

        // Methods
        metricsResource.addMethod('GET', lambdaIntegration);
        metricsResource.addMethod('POST', lambdaIntegration);
        healthResource.addMethod('GET', lambdaIntegration);
        analyticsResource.addMethod('GET', lambdaIntegration);

        this.apiUrl = this.api.url;

        new cdk.CfnOutput(this, 'ApiUrl', {
            value: this.api.url,
            description: 'API Gateway URL',
            exportName: `${projectName}-api-url-${environment}`
        });

        new cdk.CfnOutput(this, 'ApiId', {
            value: this.api.restApiId,
            exportName: `${projectName}-api-id-${environment}`
        });

        // Tags
        cdk.Tags.of(this).add('Environment', environment);
        cdk.Tags.of(this).add('Project', projectName);
        cdk.Tags.of(this).add('StackType', 'Api');
    }
} 