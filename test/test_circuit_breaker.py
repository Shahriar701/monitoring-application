import pytest
import sys
import os
import json
from unittest.mock import patch, MagicMock

# Add the lambda function path
sys.path.append(os.path.join(os.path.dirname(__file__), '../src/lambda/api'))

def test_circuit_breaker_initialization():
    """Test circuit breaker starts in CLOSED state"""
    from lambda_function import circuit_breaker
    
    assert circuit_breaker['state'] == 'CLOSED'
    assert circuit_breaker['failures'] == 0
    assert circuit_breaker['failure_threshold'] == 5
    assert circuit_breaker['timeout'] == 60

def test_circuit_breaker_opens_after_failures():
    """Test circuit breaker opens after threshold failures"""
    from lambda_function import record_circuit_breaker_failure, circuit_breaker
    
    # Reset state
    circuit_breaker['state'] = 'CLOSED'
    circuit_breaker['failures'] = 0
    
    # Record failures up to threshold
    for i in range(5):
        record_circuit_breaker_failure()
    
    assert circuit_breaker['state'] == 'OPEN'
    assert circuit_breaker['failures'] == 5

def test_circuit_breaker_half_open_after_timeout():
    """Test circuit breaker goes to HALF_OPEN after timeout"""
    import time
    from lambda_function import is_circuit_breaker_closed, circuit_breaker
    
    # Set circuit breaker to OPEN state in the past
    circuit_breaker['state'] = 'OPEN'
    circuit_breaker['last_failure_time'] = time.time() - 70  # 70 seconds ago
    
    # Should transition to HALF_OPEN
    result = is_circuit_breaker_closed()
    assert result == True
    assert circuit_breaker['state'] == 'HALF_OPEN'

def test_circuit_breaker_closes_on_success():
    """Test circuit breaker closes on successful request after HALF_OPEN"""
    from lambda_function import record_circuit_breaker_success, circuit_breaker
    
    # Set to HALF_OPEN state
    circuit_breaker['state'] = 'HALF_OPEN'
    circuit_breaker['failures'] = 3
    
    # Record success
    record_circuit_breaker_success()
    
    assert circuit_breaker['state'] == 'CLOSED'
    assert circuit_breaker['failures'] == 0

@patch('lambda_function.dynamodb')
@patch('lambda_function.sqs')
def test_lambda_handler_with_circuit_breaker_open(mock_sqs, mock_dynamodb):
    """Test lambda handler returns 503 when circuit breaker is open"""
    from lambda_function import lambda_handler, circuit_breaker
    
    # Set circuit breaker to OPEN
    circuit_breaker['state'] = 'OPEN'
    
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