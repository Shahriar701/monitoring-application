#!/usr/bin/env python3
"""
Create CloudWatch dashboard for pipeline monitoring
"""

import boto3
import json

def create_pipeline_dashboard(region='us-east-1'):
    cloudwatch = boto3.client('cloudwatch', region_name=region)
    
    dashboard_body = {
        "widgets": [
            {
                "type": "metric",
                "x": 0,
                "y": 0,
                "width": 12,
                "height": 6,
                "properties": {
                    "metrics": [
                        ["Pipeline/Monitoring", "PipelineExecution", "PipelineName", "monitoring-application-pipeline", "State", "SUCCEEDED"],
                        [".", ".", ".", ".", ".", "FAILED"],
                        [".", ".", ".", ".", ".", "STARTED"]
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "region": region,
                    "title": "Pipeline Execution Status",
                    "period": 300
                }
            },
            {
                "type": "metric",
                "x": 12,
                "y": 0,
                "width": 12,
                "height": 6,
                "properties": {
                    "metrics": [
                        ["AWS/CodeBuild", "Duration", "ProjectName", "monitoring-app-tests"],
                        [".", ".", ".", "monitoring-app-build"],
                        [".", ".", ".", "monitoring-app-integration-tests"]
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "region": region,
                    "title": "Build Duration",
                    "period": 300
                }
            },
            {
                "type": "metric",
                "x": 0,
                "y": 6,
                "width": 24,
                "height": 6,
                "properties": {
                    "metrics": [
                        ["AWS/CodeBuild", "SucceededBuilds", "ProjectName", "monitoring-app-tests"],
                        [".", "FailedBuilds", ".", "."],
                        [".", "SucceededBuilds", ".", "monitoring-app-build"],
                        [".", "FailedBuilds", ".", "."]
                    ],
                    "view": "timeSeries",
                    "stacked": False,
                    "region": region,
                    "title": "Build Success/Failure Rate",
                    "period": 300
                }
            }
        ]
    }
    
    try:
        cloudwatch.put_dashboard(
            DashboardName='monitoring-pipeline-dashboard',
            DashboardBody=json.dumps(dashboard_body)
        )
        
        print("✅ Pipeline dashboard created successfully")
        print(f"🔗 View at: https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}#dashboards:name=monitoring-pipeline-dashboard")
        
    except Exception as e:
        print(f"❌ Failed to create dashboard: {e}")

if __name__ == "__main__":
    create_pipeline_dashboard()