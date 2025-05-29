import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.append(os.path.join(os.path.dirname(__file__), '../src/lambda/api'))

@patch.dict(os.environ, {'TABLE_NAME': 'test-table', 'ENVIRONMENT': 'test'})
@patch('lambda_function.dynamodb')
@patch('lambda_function.sqs')
def test_health_check_all_services_healthy(mock_sqs, mock_dynamodb):
    """Test health check when all services are healthy"""
    from lambda_function import handle_health_check
    
    # Mock DynamoDB table scan
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_table.scan.return_value = {'Items': []}
    
    # Mock SQS get_queue_attributes
    mock_sqs.get_queue_attributes.return_value = {'Attributes': {}}
    
    event = {}
    response = handle_health_check(event)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['status'] == 'healthy'
    assert body['services']['dynamodb'] == 'healthy'
    assert body['services']['sqs'] == 'healthy'
    assert body['environment'] == 'test'

@patch.dict(os.environ, {'TABLE_NAME': 'test-table', 'ENVIRONMENT': 'test'})
@patch('lambda_function.dynamodb')
@patch('lambda_function.sqs')
def test_health_check_degraded_service(mock_sqs, mock_dynamodb):
    """Test health check when one service is degraded"""
    from lambda_function import handle_health_check
    
    # Mock DynamoDB failure
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_table.scan.side_effect = Exception("DynamoDB connection failed")
    
    # Mock SQS success
    mock_sqs.get_queue_attributes.return_value = {'Attributes': {}}
    
    event = {}
    response = handle_health_check(event)
    
    assert response['statusCode'] == 503
    body = json.loads(response['body'])
    assert body['status'] == 'degraded'
    assert body['services']['dynamodb'] == 'unhealthy'
    assert body['services']['sqs'] == 'healthy'

def test_cors_preflight_request():
    """Test CORS preflight OPTIONS request"""
    from lambda_function import lambda_handler
    
    event = {
        'httpMethod': 'OPTIONS',
        'path': '/metrics'
    }
    context = MagicMock()
    
    response = lambda_handler(event, context)
    
    assert response['statusCode'] == 200
    assert 'Access-Control-Allow-Origin' in response['headers']
    assert response['headers']['Access-Control-Allow-Origin'] == '*'
    body = json.loads(response['body'])
    assert body['message'] == 'CORS preflight'