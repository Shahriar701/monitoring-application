import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { BaseStackProps, NetworkingStackOutputs } from '../interfaces/stack-interfaces';
import { Construct } from 'constructs';

export class NetworkingStack extends cdk.Stack implements NetworkingStackOutputs {
    public readonly vpc: ec2.Vpc;
    public readonly privateSubnets: ec2.ISubnet[];
    public readonly publicSubnets: ec2.ISubnet[];
    public readonly isolatedSubnets: ec2.ISubnet[];

    constructor(scope: Construct, id: string, props: BaseStackProps) {
        super(scope, id, props);

        const { environment, projectName } = props;

        // vpc configuration
        this.vpc = new ec2.Vpc(this, 'MonitoringVPC', {
            vpcName: `${projectName}-vpc-${environment}`,
            maxAzs: 3,
            ipAddresses: ec2.IpAddresses.cidr('10.0.0.0/16'),
            natGateways: environment === 'prod' ? 0 : 1, // No NAT for prod due to EIP limits
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
            ],
            enableDnsHostnames: true,
            enableDnsSupport: true,
        });

        // Store subnet references
        this.privateSubnets = this.vpc.privateSubnets;
        this.publicSubnets = this.vpc.publicSubnets;
        this.isolatedSubnets = this.vpc.isolatedSubnets;

        // Security groups 
        const lambdaSg = new ec2.SecurityGroup(this, 'LambdaSecurityGroup', {
            vpc: this.vpc,
            description: 'Security group for Lambda functions',
            allowAllOutbound: true,
        });

        // Gateway endpoints (free)
        this.vpc.addGatewayEndpoint('DynamoDBEndpoint', {
            service: ec2.GatewayVpcEndpointAwsService.DYNAMODB,
            subnets: [{ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }],
        });

        this.vpc.addGatewayEndpoint('S3Endpoint', {
            service: ec2.GatewayVpcEndpointAwsService.S3,
            subnets: [{ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }]
        });

        // Interface endpoints for production (when no NAT gateway)
        if (environment === 'prod') {
            // Lambda service endpoint
            this.vpc.addInterfaceEndpoint('LambdaEndpoint', {
                service: ec2.InterfaceVpcEndpointAwsService.LAMBDA,
                subnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }
            });

            // CloudWatch Logs endpoint
            this.vpc.addInterfaceEndpoint('CloudWatchLogsEndpoint', {
                service: ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
                subnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }
            });

            // SQS endpoint
            this.vpc.addInterfaceEndpoint('SQSEndpoint', {
                service: ec2.InterfaceVpcEndpointAwsService.SQS,
                subnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }
            });

            // SNS endpoint
            this.vpc.addInterfaceEndpoint('SNSEndpoint', {
                service: ec2.InterfaceVpcEndpointAwsService.SNS,
                subnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }
            });
        }

        // Outputs for Cross-Stack References
        new cdk.CfnOutput(this, 'VpcId', {
            value: this.vpc.vpcId,
            exportName: `${projectName}-vpc-id-${environment}`
        });

        new cdk.CfnOutput(this, 'PrivateSubnetIds', {
            value: this.vpc.privateSubnets.map(subnet => subnet.subnetId).join(','),
            exportName: `${projectName}-private-subnet-ids-${environment}`
        });

        // Tags for cost allocation and governance
        cdk.Tags.of(this).add('Environment', environment);
        cdk.Tags.of(this).add('Project', projectName);
        cdk.Tags.of(this).add('StackType', 'Networking');
    }
}
