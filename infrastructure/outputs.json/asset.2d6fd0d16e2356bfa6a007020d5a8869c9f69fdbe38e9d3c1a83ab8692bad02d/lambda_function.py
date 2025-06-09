import json
import os
import boto3
from datetime import datetime, timedelta
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')
cloudwatch = boto3.client('logs')

def lambda_handler(event, context):
    """AI-powered analysis of system metrics and logs"""
    try:
        # Get recent metrics from DynamoDB
        metrics_data = get_recent_metrics()
        
        # Get recent error logs
        error_logs = get_recent_error_logs()
        
        # Analyze with Bedrock
        analysis = analyze_with_ai(metrics_data, error_logs)
        
        # Store analysis results
        store_analysis_results(analysis)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'AI analysis completed',
                'insights': analysis.get('insights', []),
                'recommendations': analysis.get('recommendations', [])
            })
        }
        
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def get_recent_metrics():
    """Retrieve recent metrics from DynamoDB"""
    table = dynamodb.Table(os.environ['TABLE_NAME'])
    
    # Get metrics from last hour
    one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
    
    try:
        response = table.scan(
            FilterExpression='Timestamp > :timestamp',
            ExpressionAttributeValues={':timestamp': one_hour_ago},
            Limit=100
        )
        return response['Items']
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        return []

def get_recent_error_logs():
    """Get recent error logs from CloudWatch"""
    try:
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(hours=1)).timestamp() * 1000)
        
        response = cloudwatch.start_query(
            logGroupName='/aws/lambda/your-api-function',
            startTime=start_time,
            endTime=end_time,
            queryString='fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20'
        )
        
        # In a real implementation, you'd wait for and retrieve the query results
        # For now, return mock data
        return [
            "ERROR: Database connection timeout",
            "ERROR: API rate limit exceeded", 
            "ERROR: Invalid input validation failed"
        ]
        
    except Exception as e:
        logger.error(f"Failed to get error logs: {e}")
        return []

def analyze_with_ai(metrics_data, error_logs):
    """Use Bedrock to analyze metrics and logs"""
    
    # Prepare context for AI analysis
    context = f"""
System Metrics Analysis Request:

Recent Metrics Data:
{json.dumps(metrics_data[:10], indent=2, default=str)}

Recent Error Logs:
{chr(10).join(error_logs[:10])}

Please analyze this data and provide:
1. Key insights about system health
2. Potential issues or patterns
3. Recommended actions for improvement
4. Risk assessment

Format your response as JSON with keys: insights, issues, recommendations, risk_level
"""

    try:
        # Use Claude model for analysis
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            contentType='application/json',
            accept='application/json',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [
                    {
                        "role": "user",
                        "content": context
                    }
                ]
            })
        )
        
        # Parse response
        response_body = json.loads(response['body'].read())
        ai_content = response_body['content'][0]['text']
        
        # Try to parse as JSON, fallback to text analysis
        try:
            analysis = json.loads(ai_content)
        except json.JSONDecodeError:
            # If AI doesn't return valid JSON, create structured response
            analysis = {
                "insights": ["AI analysis completed but returned unstructured data"],
                "issues": [],
                "recommendations": ["Review AI response format"],
                "risk_level": "medium",
                "raw_analysis": ai_content
            }
        
        return analysis
        
    except Exception as e:
        logger.error(f"Bedrock analysis failed: {e}")
        return {
            "insights": [f"AI analysis failed: {str(e)}"],
            "issues": ["AI service unavailable"],
            "recommendations": ["Fallback to manual analysis"],
            "risk_level": "unknown"
        }

def store_analysis_results(analysis):
    """Store AI analysis results for tracking"""
    table = dynamodb.Table(os.environ['TABLE_NAME'])
    
    try:
        table.put_item(
            Item={
                'ServiceName': 'AIAnalysis',
                'Timestamp': datetime.now().isoformat(),
                'AnalysisType': 'SystemHealth',
                'Insights': analysis.get('insights', []),
                'Recommendations': analysis.get('recommendations', []),
                'RiskLevel': analysis.get('risk_level', 'unknown'),
                'TTL': int((datetime.now() + timedelta(days=30)).timestamp())
            }
        )
    except Exception as e:
        logger.error(f"Failed to store analysis: {e}") 