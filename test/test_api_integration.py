import pytest
import sys
import os
import json
import time
from unittest.mock import patch, MagicMock, Mock
from decimal import Decimal

# Add the lambda function path
sys.path.append(os.path.join(os.path.dirname(__file__), '../src/lambda/api'))

class TestAPIIntegration:
    """Integration tests for the API Lambda function"""
    
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
    def test_cors_preflight_request(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test CORS preflight OPTIONS request"""
        from lambda_function import lambda_handler
        
        event = {
            'httpMethod': 'OPTIONS',
            'path': '/health'
        }
        context = MagicMock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
        assert 'Access-Control-Allow-Methods' in response['headers']
        assert 'Access-Control-Allow-Headers' in response['headers']
        
        body = json.loads(response['body'])
        assert body['message'] == 'CORS preflight'

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_health_endpoint_integration(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test health endpoint integration"""
        from lambda_function import lambda_handler
        
        # Mock successful services
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {'Items': []}
        mock_sqs.get_queue_attributes.return_value = {'Attributes': {}}
        
        with patch.dict(os.environ, {
            'TABLE_NAME': 'test-table',
            'PROCESSING_QUEUE_URL': 'test-queue',
            'ENVIRONMENT': 'test'
        }):
            event = {
                'httpMethod': 'GET',
                'path': '/health'
            }
            context = MagicMock()
            
            response = lambda_handler(event, context)
            
            assert response['statusCode'] == 200
            assert 'Access-Control-Allow-Origin' in response['headers']
            
            body = json.loads(response['body'])
            assert body['status'] == 'healthy'
            assert body['environment'] == 'test'
            assert body['circuit_breaker'] == 'CLOSED'
            assert 'timestamp' in body

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_post_metrics_integration(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test POST /metrics endpoint integration"""
        from lambda_function import lambda_handler
        
        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        
        # Mock CloudWatch put_metric_data
        mock_cloudwatch.put_metric_data.return_value = {}
        
        # Mock SQS send_message
        mock_sqs.send_message.return_value = {'MessageId': 'test-id'}
        
        with patch.dict(os.environ, {
            'TABLE_NAME': 'test-table',
            'PROCESSING_QUEUE_URL': 'test-queue',
            'ENVIRONMENT': 'test'
        }):
            event = {
                'httpMethod': 'POST',
                'path': '/metrics',
                'body': json.dumps({
                    'service_name': 'test-service',
                    'metric_type': 'response_time',
                    'value': 150.5,
                    'metadata': {'request_count': 100}
                })
            }
            context = MagicMock()
            
            response = lambda_handler(event, context)
            
            assert response['statusCode'] == 201
            assert 'Access-Control-Allow-Origin' in response['headers']
            
            body = json.loads(response['body'])
            assert body['message'] == 'Metric created successfully'
            assert body['service_name'] == 'test-service'
            assert 'timestamp' in body
            
            # Verify DynamoDB was called
            mock_table.put_item.assert_called_once()
            put_item_args = mock_table.put_item.call_args[1]['Item']
            assert put_item_args['ServiceName'] == 'test-service'
            assert put_item_args['MetricType'] == 'response_time'
            assert put_item_args['Value'] == Decimal('150.5')
            assert put_item_args['Source'] == 'api'
            assert put_item_args['Environment'] == 'test'
            
            # Verify CloudWatch was called
            mock_cloudwatch.put_metric_data.assert_called_once()
            
            # Verify SQS was called
            mock_sqs.send_message.assert_called_once()

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_post_metrics_missing_fields(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test POST /metrics with missing required fields"""
        from lambda_function import lambda_handler
        
        with patch.dict(os.environ, {'TABLE_NAME': 'test-table'}):
            event = {
                'httpMethod': 'POST',
                'path': '/metrics',
                'body': json.dumps({
                    'service_name': 'test-service',
                    'metric_type': 'response_time'
                    # Missing 'value' field
                })
            }
            context = MagicMock()
            
            response = lambda_handler(event, context)
            
            assert response['statusCode'] == 400
            body = json.loads(response['body'])
            assert 'Missing required field: value' in body['error']

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_post_metrics_invalid_json(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test POST /metrics with invalid JSON"""
        from lambda_function import lambda_handler
        
        with patch.dict(os.environ, {'TABLE_NAME': 'test-table'}):
            event = {
                'httpMethod': 'POST',
                'path': '/metrics',
                'body': 'invalid json'
            }
            context = MagicMock()
            
            response = lambda_handler(event, context)
            
            assert response['statusCode'] == 400
            body = json.loads(response['body'])
            assert 'Invalid JSON in request body' in body['error']

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_get_metrics_integration(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test GET /metrics endpoint integration"""
        from lambda_function import lambda_handler
        
        # Mock DynamoDB scan response
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {
            'Items': [
                {
                    'ServiceName': 'test-service',
                    'Timestamp': '2023-01-01T00:00:00',
                    'MetricType': 'response_time',
                    'Value': Decimal('150.5'),
                    'Source': 'api',
                    'Environment': 'test'
                }
            ],
            'ScannedCount': 1
        }
        
        with patch.dict(os.environ, {'TABLE_NAME': 'test-table'}):
            event = {
                'httpMethod': 'GET',
                'path': '/metrics'
            }
            context = MagicMock()
            
            response = lambda_handler(event, context)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            assert 'metrics' in body
            assert len(body['metrics']) == 1
            assert body['count'] == 1
            assert body['scanned_count'] == 1
            
            metric = body['metrics'][0]
            assert metric['ServiceName'] == 'test-service'
            assert metric['Value'] == 150.5  # Converted from Decimal

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_get_metrics_with_service_filter(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test GET /metrics with service name filter"""
        from lambda_function import lambda_handler
        
        # Mock DynamoDB query response
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.query.return_value = {
            'Items': [
                {
                    'ServiceName': 'specific-service',
                    'Timestamp': '2023-01-01T00:00:00',
                    'MetricType': 'response_time',
                    'Value': Decimal('100'),
                    'Source': 'api'
                }
            ]
        }
        
        with patch.dict(os.environ, {'TABLE_NAME': 'test-table'}):
            event = {
                'httpMethod': 'GET',
                'path': '/metrics',
                'queryStringParameters': {
                    'service': 'specific-service',
                    'limit': '50'
                }
            }
            context = MagicMock()
            
            response = lambda_handler(event, context)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            # Verify query was called instead of scan
            mock_table.query.assert_called_once()
            query_args = mock_table.query.call_args[1]
            assert query_args['Limit'] == 50

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_unsupported_method(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test unsupported HTTP method"""
        from lambda_function import lambda_handler
        
        event = {
            'httpMethod': 'PUT',
            'path': '/metrics'
        }
        context = MagicMock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 405
        body = json.loads(response['body'])
        assert 'Method not allowed' in body['error']

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_unknown_endpoint(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test unknown endpoint"""
        from lambda_function import lambda_handler
        
        event = {
            'httpMethod': 'GET',
            'path': '/unknown'
        }
        context = MagicMock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'Endpoint not found' in body['error']

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_error_handling(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test error handling returns proper error response"""
        from lambda_function import lambda_handler
        
        # Mock DynamoDB to throw an exception
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.put_item.side_effect = Exception("Database error")
        
        with patch.dict(os.environ, {'TABLE_NAME': 'test-table'}):
            event = {
                'httpMethod': 'POST',
                'path': '/metrics',
                'body': json.dumps({
                    'service_name': 'test-service',
                    'metric_type': 'response_time',
                    'value': 150
                })
            }
            context = MagicMock()
            
            response = lambda_handler(event, context)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert 'error' in body

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_missing_table_name_configuration(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test handling of missing TABLE_NAME configuration"""
        from lambda_function import lambda_handler
        
        with patch.dict(os.environ, {}, clear=True):
            event = {
                'httpMethod': 'POST',
                'path': '/metrics',
                'body': json.dumps({
                    'service_name': 'test-service',
                    'metric_type': 'response_time',
                    'value': 150
                })
            }
            context = MagicMock()
            
            response = lambda_handler(event, context)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert 'TABLE_NAME not configured' in body['error']

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_circuit_breaker_blocks_requests(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test that circuit breaker blocks requests when open"""
        from lambda_function import lambda_handler, circuit_breaker
        
        # Set circuit breaker to OPEN
        circuit_breaker['state'] = 'OPEN'
        circuit_breaker['last_failure_time'] = time.time()
        circuit_breaker['failures'] = 5
        
        event = {
            'httpMethod': 'GET',
            'path': '/metrics'
        }
        context = MagicMock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 503
        body = json.loads(response['body'])
        assert 'Service temporarily unavailable' in body['error']
        assert body['circuit_breaker_state'] == 'OPEN'

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_successful_request_records_success(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test that successful requests record success for circuit breaker"""
        from lambda_function import lambda_handler, circuit_breaker
        
        # Set circuit breaker to HALF_OPEN
        circuit_breaker['state'] = 'HALF_OPEN'
        circuit_breaker['failures'] = 3
        
        # Mock successful operations
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {'Items': []}
        mock_sqs.get_queue_attributes.return_value = {'Attributes': {}}
        
        with patch.dict(os.environ, {
            'TABLE_NAME': 'test-table',
            'PROCESSING_QUEUE_URL': 'test-queue'
        }):
            event = {
                'httpMethod': 'GET',
                'path': '/health'
            }
            context = MagicMock()
            
            response = lambda_handler(event, context)
            
            assert response['statusCode'] == 200
            
            # Verify circuit breaker was closed
            assert circuit_breaker['state'] == 'CLOSED'
            assert circuit_breaker['failures'] == 0