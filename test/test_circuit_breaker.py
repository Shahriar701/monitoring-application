import pytest
import sys
import os
import json
import time
from unittest.mock import patch, MagicMock, Mock

# Add the lambda function path
sys.path.append(os.path.join(os.path.dirname(__file__), '../src/lambda/api'))

class TestCircuitBreaker:
    """Test suite for circuit breaker functionality"""
    
    def setup_method(self):
        """Reset circuit breaker state before each test"""
        # Import here to ensure clean state
        from lambda_function import circuit_breaker
        circuit_breaker['state'] = 'CLOSED'
        circuit_breaker['failures'] = 0
        circuit_breaker['last_failure_time'] = None

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker starts in CLOSED state"""
        from lambda_function import circuit_breaker
        
        assert circuit_breaker['state'] == 'CLOSED'
        assert circuit_breaker['failures'] == 0
        assert circuit_breaker['failure_threshold'] == 5
        assert circuit_breaker['timeout'] == 60

    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures"""
        from lambda_function import record_circuit_breaker_failure, circuit_breaker
        
        # Record failures up to threshold
        for i in range(5):
            record_circuit_breaker_failure()
        
        assert circuit_breaker['state'] == 'OPEN'
        assert circuit_breaker['failures'] == 5
        assert circuit_breaker['last_failure_time'] is not None

    def test_circuit_breaker_half_open_after_timeout(self):
        """Test circuit breaker goes to HALF_OPEN after timeout"""
        from lambda_function import is_circuit_breaker_closed, circuit_breaker
        
        # Set circuit breaker to OPEN state in the past
        circuit_breaker['state'] = 'OPEN'
        circuit_breaker['last_failure_time'] = time.time() - 70  # 70 seconds ago
        circuit_breaker['failures'] = 5
        
        # Should transition to HALF_OPEN and return True
        result = is_circuit_breaker_closed()
        assert result == True
        assert circuit_breaker['state'] == 'HALF_OPEN'

    def test_circuit_breaker_stays_open_within_timeout(self):
        """Test circuit breaker stays OPEN within timeout period"""
        from lambda_function import is_circuit_breaker_closed, circuit_breaker
        
        # Set circuit breaker to OPEN state recently
        circuit_breaker['state'] = 'OPEN'
        circuit_breaker['last_failure_time'] = time.time() - 30  # 30 seconds ago (within timeout)
        circuit_breaker['failures'] = 5
        
        # Should stay OPEN and return False
        result = is_circuit_breaker_closed()
        assert result == False
        assert circuit_breaker['state'] == 'OPEN'

    def test_circuit_breaker_closes_on_success(self):
        """Test circuit breaker closes on successful request after HALF_OPEN"""
        from lambda_function import record_circuit_breaker_success, circuit_breaker
        
        # Set to HALF_OPEN state
        circuit_breaker['state'] = 'HALF_OPEN'
        circuit_breaker['failures'] = 3
        
        # Record success
        record_circuit_breaker_success()
        
        assert circuit_breaker['state'] == 'CLOSED'
        assert circuit_breaker['failures'] == 0

    def test_circuit_breaker_success_when_closed_does_nothing(self):
        """Test that recording success when CLOSED doesn't change state"""
        from lambda_function import record_circuit_breaker_success, circuit_breaker
        
        # Ensure CLOSED state
        circuit_breaker['state'] = 'CLOSED'
        circuit_breaker['failures'] = 2
        
        # Record success
        record_circuit_breaker_success()
        
        # Should remain CLOSED, failures unchanged
        assert circuit_breaker['state'] == 'CLOSED'
        assert circuit_breaker['failures'] == 2

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_lambda_handler_with_circuit_breaker_open(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test lambda handler returns 503 when circuit breaker is open"""
        from lambda_function import lambda_handler, circuit_breaker
        
        # Set circuit breaker to OPEN with recent failure time to prevent timeout
        circuit_breaker['state'] = 'OPEN'
        circuit_breaker['last_failure_time'] = time.time()  # Recent failure
        circuit_breaker['failures'] = 5
        
        event = {
            'httpMethod': 'GET',
            'path': '/health'
        }
        context = MagicMock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 503
        body = json.loads(response['body'])
        assert 'Service temporarily unavailable' in body['error']
        assert body['circuit_breaker_state'] == 'OPEN'
        
        # Verify circuit breaker state hasn't changed
        assert circuit_breaker['state'] == 'OPEN'

    @patch('lambda_function.dynamodb')
    @patch('lambda_function.sqs')
    @patch('lambda_function.cloudwatch')
    def test_lambda_handler_with_circuit_breaker_closed(self, mock_cloudwatch, mock_sqs, mock_dynamodb):
        """Test lambda handler works normally when circuit breaker is closed"""
        from lambda_function import lambda_handler, circuit_breaker
        
        # Ensure circuit breaker is CLOSED
        circuit_breaker['state'] = 'CLOSED'
        circuit_breaker['failures'] = 0
        
        # Mock DynamoDB table operations
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {'Items': []}
        
        # Mock SQS operations
        mock_sqs.get_queue_attributes.return_value = {'Attributes': {}}
        
        # Mock environment variables
        with patch.dict(os.environ, {'TABLE_NAME': 'test-table', 'PROCESSING_QUEUE_URL': 'test-queue'}):
            event = {
                'httpMethod': 'GET',
                'path': '/health'
            }
            context = MagicMock()
            
            response = lambda_handler(event, context)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['status'] == 'healthy'
            assert body['circuit_breaker'] == 'CLOSED'

    def test_circuit_breaker_failure_increments_counter(self):
        """Test that recording failures increments the counter correctly"""
        from lambda_function import record_circuit_breaker_failure, circuit_breaker
        
        initial_failures = circuit_breaker['failures']
        
        record_circuit_breaker_failure()
        
        assert circuit_breaker['failures'] == initial_failures + 1
        assert circuit_breaker['last_failure_time'] is not None
        
        # Should still be CLOSED after one failure
        assert circuit_breaker['state'] == 'CLOSED'