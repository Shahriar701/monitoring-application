import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cloudwatchActions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as logs from 'aws-cdk-lib/aws-logs';
import { MonitoringStackProps } from '../interfaces/stack-interfaces';

export class MonitoringStack extends cdk.Stack {
  public readonly dashboard: cloudwatch.Dashboard;

  constructor(scope: Construct, id: string, props: MonitoringStackProps) {
    super(scope, id, props);

    const { environment, projectName, vpc, table, api, lambdaFunctions, alertTopic } = props;

    // CloudWatch Dashboard

    this.dashboard = new cloudwatch.Dashboard(this, 'MonitoringDashboard', {
      dashboardName: `${projectName}-dashboard-${environment}`,
      periodOverride: cloudwatch.PeriodOverride.AUTO
    });

    // Dashboard Widgets

    // API Performance Widget
    const apiWidget = new cloudwatch.GraphWidget({
      title: 'API Performance',
      width: 12,
      height: 6,
      left: [
        lambdaFunctions[0].metricInvocations({ label: 'API Invocations' }),
        lambdaFunctions[0].metricErrors({ label: 'API Errors' })
      ],
      right: [
        lambdaFunctions[0].metricDuration({ label: 'API Duration' })
      ]
    });

    // Lambda Functions Overview
    const lambdaWidget = new cloudwatch.GraphWidget({
      title: 'Lambda Functions Overview',
      width: 12,
      height: 6,
      left: lambdaFunctions.map((fn, index) =>
        fn.metricInvocations({ label: `${fn.functionName} Invocations` })
      ),
      right: lambdaFunctions.map((fn, index) =>
        fn.metricErrors({ label: `${fn.functionName} Errors` })
      )
    });

    // DynamoDB Performance Widget
    const dynamoWidget = new cloudwatch.GraphWidget({
      title: 'DynamoDB Performance',
      width: 12,
      height: 6,
      left: [
        table.metricConsumedReadCapacityUnits({ label: 'Read Capacity' }),
        table.metricConsumedWriteCapacityUnits({ label: 'Write Capacity' })
      ],
      right: [
        table.metricThrottledRequests({ label: 'Throttled Requests' })
      ]
    });

    // API Gateway Metrics Widget
    const apiGatewayWidget = new cloudwatch.GraphWidget({
      title: 'API Gateway Metrics',
      width: 12,
      height: 6,
      left: [
        api.metricCount({ label: 'Request Count' }),
        api.metricClientError({ label: '4xx Errors' }),
        api.metricServerError({ label: '5xx Errors' })
      ],
      right: [
        api.metricLatency({ label: 'Latency' }),
        api.metricIntegrationLatency({ label: 'Integration Latency' })
      ]
    });

    // Add widgets to dashboard
    this.dashboard.addWidgets(
      apiWidget,
      lambdaWidget,
      dynamoWidget,
      apiGatewayWidget
    );

    // CloudWatch Alarms

    // High Error Rate Alarm for API Lambda
    const apiErrorAlarm = lambdaFunctions[0].metricErrors().createAlarm(this, 'ApiHighErrorRate', {
      threshold: 5,
      evaluationPeriods: 2,
      alarmDescription: 'High error rate detected in API Lambda',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING
    });
    apiErrorAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // High Duration Alarm for API Lambda
    const apiDurationAlarm = lambdaFunctions[0].metricDuration().createAlarm(this, 'ApiHighDuration', {
      threshold: 10000, // 10 seconds
      evaluationPeriods: 3,
      alarmDescription: 'API Lambda duration too high'
    });
    apiDurationAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // DynamoDB Throttling Alarm
    const throttleAlarm = table.metricThrottledRequests().createAlarm(this, 'DynamoThrottling', {
      threshold: 1,
      evaluationPeriods: 1,
      alarmDescription: 'DynamoDB throttling detected'
    });
    throttleAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // API Gateway 5xx Error Alarm
    const api5xxAlarm = api.metricServerError().createAlarm(this, 'Api5xxErrors', {
      threshold: 10,
      evaluationPeriods: 2,
      alarmDescription: 'High 5xx error rate in API Gateway'
    });
    api5xxAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // API Gateway High Latency Alarm
    const apiLatencyAlarm = api.metricLatency().createAlarm(this, 'ApiHighLatency', {
      threshold: 5000, // 5 seconds
      evaluationPeriods: 3,
      alarmDescription: 'API Gateway latency too high'
    });
    apiLatencyAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // SLO/SLI Monitoring - Error Budget Tracking
    const errorBudgetAlarm = new cloudwatch.Alarm(this, 'ErrorBudgetAlarm', {
      metric: new cloudwatch.MathExpression({
        expression: '(errors/requests) * 100',
        usingMetrics: {
          'errors': api.metricServerError().with({ statistic: 'Sum' }),
          'requests': api.metricCount().with({ statistic: 'Sum' })
        },
        period: cdk.Duration.minutes(5)
      }),
      threshold: 0.1, // 99.9% availability SLO (0.1% error budget)
      evaluationPeriods: 3,
      alarmDescription: 'Error budget exceeded - SLO at risk'
    });
    errorBudgetAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // Note: Lambda functions automatically create their own log groups
    // API Gateway logging can be configured separately if needed

    // Outputs

    new cdk.CfnOutput(this, 'DashboardUrl', {
      value: `https://${this.region}.console.aws.amazon.com/cloudwatch/home?region=${this.region}#dashboards:name=${this.dashboard.dashboardName}`,
      description: 'CloudWatch Dashboard URL'
    });

    new cdk.CfnOutput(this, 'DashboardName', {
      value: this.dashboard.dashboardName,
      exportName: `${projectName}-dashboard-name-${environment}`
    });

    // Tags
    cdk.Tags.of(this).add('Environment', environment);
    cdk.Tags.of(this).add('Project', projectName);
    cdk.Tags.of(this).add('StackType', 'Monitoring');
  }
}