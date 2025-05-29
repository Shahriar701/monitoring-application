import pytest
import sys
import os
import json
import time
from unittest.mock import patch, MagicMock, Mock
from decimal import Decimal

# Add lambda function paths
sys.path.append(os.path.join(os.path.dirname(__file__), '../src/lambda/api'))

class TestLambdaFunctions:
    """Test suite for Lambda function components"""
    
    def setup_method(self):
        """Setup for each test"""
        # Reset circuit breaker state
        from lambda_function import circuit_breaker
        circuit_breaker['state'] = 'CLOSED'
        circuit_breaker['failures'] = 0
        circuit_breaker['last_failure_time'] = None

    def test_lambda_function_imports(self):
        """Test that all required modules can be imported"""
        try:
            import lambda_function
            assert hasattr(lambda_function, 'lambda_handler')
            assert hasattr(lambda_function, 'handle_health_check')
            assert hasattr(lambda_function, 'handle_get_metrics')
            assert hasattr(lambda_function, 'handle_post_metrics')
            assert hasattr(lambda_function, 'is_circuit_breaker_closed')
            assert hasattr(lambda_function, 'record_circuit_breaker_failure')
            assert hasattr(lambda_function, 'record_circuit_breaker_success')
        except ImportError as e:
            pytest.fail(f"Failed to import lambda_function: {e}")

    def test_circuit_breaker_configuration(self):
        """Test circuit breaker has correct configuration"""
        from lambda_function import circuit_breaker
        
        assert isinstance(circuit_breaker, dict)
        assert 'state' in circuit_breaker
        assert 'failures' in circuit_breaker
        assert 'failure_threshold' in circuit_breaker
        assert 'timeout' in circuit_breaker
        assert 'last_failure_time' in circuit_breaker
        
        # Check default values
        assert circuit_breaker['failure_threshold'] == 5
        assert circuit_breaker['timeout'] == 60

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_handle_health_check_function(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test handle_health_check function directly"""
        from lambda_function import handle_health_check
        
        # Mock successful operations
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {'Items': []}
        mock_sqs.get_queue_attributes.return_value = {'Attributes': {}}
        
        with patch.dict(os.environ, {
            'TABLE_NAME': 'test-table',
            'PROCESSING_QUEUE_URL': 'test-queue',
            'ENVIRONMENT': 'test'
        }):
            event = {'httpMethod': 'GET', 'path': '/health'}
            response = handle_health_check(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['status'] == 'healthy'
            assert body['environment'] == 'test'

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_handle_get_metrics_function(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test handle_get_metrics function directly"""
        from lambda_function import handle_get_metrics
        
        # Mock DynamoDB scan
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {
            'Items': [
                {
                    'ServiceName': 'test-service',
                    'Timestamp': '2023-01-01T00:00:00',
                    'MetricType': 'test_metric',
                    'Value': Decimal('100'),
                    'Source': 'api'
                }
            ],
            'ScannedCount': 1
        }
        
        with patch.dict(os.environ, {'TABLE_NAME': 'test-table'}):
            event = {'httpMethod': 'GET', 'path': '/metrics'}
            response = handle_get_metrics(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert 'metrics' in body
            assert len(body['metrics']) == 1

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_handle_post_metrics_function(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test handle_post_metrics function directly"""
        from lambda_function import handle_post_metrics
        
        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_cloudwatch.put_metric_data.return_value = {}
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
                    'metric_type': 'test_metric',
                    'value': 100
                })
            }
            response = handle_post_metrics(event)
            
            assert response['statusCode'] == 201
            body = json.loads(response['body'])
            assert body['message'] == 'Metric created successfully'

    def test_is_circuit_breaker_closed_function(self):
        """Test is_circuit_breaker_closed function directly"""
        from lambda_function import is_circuit_breaker_closed, circuit_breaker
        
        # Test CLOSED state
        circuit_breaker['state'] = 'CLOSED'
        assert is_circuit_breaker_closed() == True
        
        # Test HALF_OPEN state
        circuit_breaker['state'] = 'HALF_OPEN'
        assert is_circuit_breaker_closed() == True
        
        # Test OPEN state (recent failure)
        circuit_breaker['state'] = 'OPEN'
        circuit_breaker['last_failure_time'] = time.time()
        assert is_circuit_breaker_closed() == False

    def test_record_circuit_breaker_failure_function(self):
        """Test record_circuit_breaker_failure function directly"""
        from lambda_function import record_circuit_breaker_failure, circuit_breaker
        
        initial_failures = circuit_breaker['failures']
        record_circuit_breaker_failure()
        
        assert circuit_breaker['failures'] == initial_failures + 1
        assert circuit_breaker['last_failure_time'] is not None

    def test_record_circuit_breaker_success_function(self):
        """Test record_circuit_breaker_success function directly"""
        from lambda_function import record_circuit_breaker_success, circuit_breaker
        
        # Test success when HALF_OPEN
        circuit_breaker['state'] = 'HALF_OPEN'
        circuit_breaker['failures'] = 3
        
        record_circuit_breaker_success()
        
        assert circuit_breaker['state'] == 'CLOSED'
        assert circuit_breaker['failures'] == 0

    def test_lambda_handler_routing(self):
        """Test lambda_handler routes requests correctly"""
        from lambda_function import lambda_handler
        
        with patch('lambda_function.handle_health_check') as mock_health, \
             patch('lambda_function.handle_get_metrics') as mock_get_metrics, \
             patch('lambda_function.handle_post_metrics') as mock_post_metrics:
            
            mock_health.return_value = {'statusCode': 200, 'body': '{}'}
            mock_get_metrics.return_value = {'statusCode': 200, 'body': '{}'}
            mock_post_metrics.return_value = {'statusCode': 201, 'body': '{}'}
            
            context = MagicMock()
            
            # Test health route
            event = {'httpMethod': 'GET', 'path': '/health'}
            lambda_handler(event, context)
            mock_health.assert_called_once()
            
            # Test GET metrics route
            event = {'httpMethod': 'GET', 'path': '/metrics'}
            lambda_handler(event, context)
            mock_get_metrics.assert_called_once()
            
            # Test POST metrics route
            event = {'httpMethod': 'POST', 'path': '/metrics'}
            lambda_handler(event, context)
            mock_post_metrics.assert_called_once()

    def test_decimal_to_float_conversion(self):
        """Test that Decimal values are properly converted to float for JSON"""
        from lambda_function import handle_get_metrics
        
        with patch('lambda_function.dynamodb') as mock_dynamodb:
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_table.scan.return_value = {
                'Items': [
                    {
                        'ServiceName': 'test',
                        'Value': Decimal('123.45'),
                        'IntValue': Decimal('100')
                    }
                ],
                'ScannedCount': 1
            }
            
            with patch.dict(os.environ, {'TABLE_NAME': 'test-table'}):
                event = {'httpMethod': 'GET', 'path': '/metrics'}
                response = handle_get_metrics(event)
                
                body = json.loads(response['body'])
                metric = body['metrics'][0]
                
                # Verify Decimal values were converted to float
                assert isinstance(metric['Value'], float)
                assert isinstance(metric['IntValue'], float)
                assert metric['Value'] == 123.45
                assert metric['IntValue'] == 100.0

    def test_environment_variable_handling(self):
        """Test proper handling of environment variables"""
        from lambda_function import handle_health_check, handle_post_metrics
        
        # Test missing TABLE_NAME
        with patch.dict(os.environ, {}, clear=True):
            with patch('lambda_function.dynamodb'), \
                 patch('lambda_function.sqs'), \
                 patch('lambda_function.cloudwatch'):
                
                event = {'httpMethod': 'POST', 'path': '/metrics', 'body': '{}'}
                response = handle_post_metrics(event)
                
                assert response['statusCode'] == 500
                body = json.loads(response['body'])
                assert 'TABLE_NAME not configured' in body['error']

    def test_json_error_handling(self):
        """Test JSON parsing error handling"""
        from lambda_function import handle_post_metrics
        
        with patch.dict(os.environ, {'TABLE_NAME': 'test-table'}):
            with patch('lambda_function.dynamodb'), \
                 patch('lambda_function.sqs'), \
                 patch('lambda_function.cloudwatch'):
                
                event = {
                    'httpMethod': 'POST',
                    'path': '/metrics',
                    'body': 'invalid json'
                }
                response = handle_post_metrics(event)
                
                assert response['statusCode'] == 400
                body = json.loads(response['body'])
                assert 'Invalid JSON in request body' in body['error']

    def test_required_field_validation(self):
        """Test required field validation"""
        from lambda_function import handle_post_metrics
        
        with patch.dict(os.environ, {'TABLE_NAME': 'test-table'}):
            with patch('lambda_function.dynamodb'), \
                 patch('lambda_function.sqs'), \
                 patch('lambda_function.cloudwatch'):
                
                # Test missing service_name
                event = {
                    'httpMethod': 'POST',
                    'path': '/metrics',
                    'body': json.dumps({
                        'metric_type': 'test',
                        'value': 100
                    })
                }
                response = handle_post_metrics(event)
                
                assert response['statusCode'] == 400
                body = json.loads(response['body'])
                assert 'Missing required field: service_name' in body['error'] 