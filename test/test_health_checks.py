import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock, Mock
from decimal import Decimal

sys.path.append(os.path.join(os.path.dirname(__file__), '../src/lambda/api'))

class TestHealthChecks:
    """Test suite for health check functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        # Reset circuit breaker state
        from lambda_function import circuit_breaker
        circuit_breaker['state'] = 'CLOSED'
        circuit_breaker['failures'] = 0
        circuit_breaker['last_failure_time'] = None

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_health_check_all_services_healthy(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test health check when all services are healthy"""
        from lambda_function import handle_health_check
        
        # Mock successful DynamoDB operation
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {'Items': []}
        
        # Mock successful SQS operation
        mock_sqs.get_queue_attributes.return_value = {'Attributes': {'QueueArn': 'test-arn'}}
        
        # Mock environment variables
        with patch.dict(os.environ, {
            'TABLE_NAME': 'test-table',
            'PROCESSING_QUEUE_URL': 'test-queue-url',
            'ENVIRONMENT': 'test'
        }):
            event = {'httpMethod': 'GET', 'path': '/health'}
            response = handle_health_check(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            assert body['status'] == 'healthy'
            assert body['environment'] == 'test'
            assert body['circuit_breaker'] == 'CLOSED'
            assert body['services']['dynamodb'] == 'healthy'
            assert body['services']['sqs'] == 'healthy'
            assert 'timestamp' in body

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_health_check_dynamodb_unhealthy(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test health check when DynamoDB is unhealthy"""
        from lambda_function import handle_health_check
        
        # Mock failed DynamoDB operation
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.side_effect = Exception("DynamoDB error")
        
        # Mock successful SQS operation
        mock_sqs.get_queue_attributes.return_value = {'Attributes': {}}
        
        with patch.dict(os.environ, {
            'TABLE_NAME': 'test-table',
            'PROCESSING_QUEUE_URL': 'test-queue-url'
        }):
            event = {'httpMethod': 'GET', 'path': '/health'}
            response = handle_health_check(event)
            
            assert response['statusCode'] == 503
            body = json.loads(response['body'])
            
            assert body['status'] == 'degraded'
            assert body['services']['dynamodb'] == 'unhealthy'
            assert body['services']['sqs'] == 'healthy'

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_health_check_sqs_unhealthy(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test health check when SQS is unhealthy"""
        from lambda_function import handle_health_check
        
        # Mock successful DynamoDB operation
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {'Items': []}
        
        # Mock failed SQS operation
        mock_sqs.get_queue_attributes.side_effect = Exception("SQS error")
        
        with patch.dict(os.environ, {
            'TABLE_NAME': 'test-table',
            'PROCESSING_QUEUE_URL': 'test-queue-url'
        }):
            event = {'httpMethod': 'GET', 'path': '/health'}
            response = handle_health_check(event)
            
            assert response['statusCode'] == 503
            body = json.loads(response['body'])
            
            assert body['status'] == 'degraded'
            assert body['services']['dynamodb'] == 'healthy'
            assert body['services']['sqs'] == 'unhealthy'

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_health_check_missing_table_name(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test health check when TABLE_NAME is not configured"""
        from lambda_function import handle_health_check
        
        with patch.dict(os.environ, {}, clear=True):
            event = {'httpMethod': 'GET', 'path': '/health'}
            response = handle_health_check(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            # Should still return healthy, but DynamoDB will be unknown
            assert body['services']['dynamodb'] == 'unknown'

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_health_check_missing_queue_url(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test health check when PROCESSING_QUEUE_URL is not configured"""
        from lambda_function import handle_health_check
        
        # Mock successful DynamoDB operation
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {'Items': []}
        
        with patch.dict(os.environ, {'TABLE_NAME': 'test-table'}):
            event = {'httpMethod': 'GET', 'path': '/health'}
            response = handle_health_check(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            assert body['services']['dynamodb'] == 'healthy'
            assert body['services']['sqs'] == 'unknown'

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_health_check_with_circuit_breaker_open(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test health check reflects circuit breaker state"""
        from lambda_function import handle_health_check, circuit_breaker
        
        # Set circuit breaker to OPEN
        circuit_breaker['state'] = 'OPEN'
        
        # Mock successful operations
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {'Items': []}
        mock_sqs.get_queue_attributes.return_value = {'Attributes': {}}
        
        with patch.dict(os.environ, {
            'TABLE_NAME': 'test-table',
            'PROCESSING_QUEUE_URL': 'test-queue-url'
        }):
            event = {'httpMethod': 'GET', 'path': '/health'}
            response = handle_health_check(event)
            
            body = json.loads(response['body'])
            assert body['circuit_breaker'] == 'OPEN'

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_health_check_environment_default(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test health check uses default environment when not set"""
        from lambda_function import handle_health_check
        
        # Mock successful operations
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {'Items': []}
        mock_sqs.get_queue_attributes.return_value = {'Attributes': {}}
        
        with patch.dict(os.environ, {
            'TABLE_NAME': 'test-table',
            'PROCESSING_QUEUE_URL': 'test-queue-url'
        }):
            event = {'httpMethod': 'GET', 'path': '/health'}
            response = handle_health_check(event)
            
            body = json.loads(response['body'])
            assert body['environment'] == 'dev'  # Default value

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_health_check_both_services_unhealthy(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test health check when both services are unhealthy"""
        from lambda_function import handle_health_check
        
        # Mock failed operations
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.side_effect = Exception("DynamoDB error")
        mock_sqs.get_queue_attributes.side_effect = Exception("SQS error")
        
        with patch.dict(os.environ, {
            'TABLE_NAME': 'test-table',
            'PROCESSING_QUEUE_URL': 'test-queue-url'
        }):
            event = {'httpMethod': 'GET', 'path': '/health'}
            response = handle_health_check(event)
            
            assert response['statusCode'] == 503
            body = json.loads(response['body'])
            
            assert body['status'] == 'degraded'
            assert body['services']['dynamodb'] == 'unhealthy'
            assert body['services']['sqs'] == 'unhealthy'

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