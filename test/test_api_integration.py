import requests
import pytest
import time
import json
import argparse

class TestApiIntegration:
    """Integration tests for the monitoring API"""
    
    def __init__(self, api_url):
        self.api_url = api_url.rstrip('/')
    
    def test_health_endpoint(self):
        """Test health endpoint returns proper response"""
        response = requests.get(f"{self.api_url}/health", timeout=10)
        
        assert response.status_code in [200, 503], f"Unexpected status code: {response.status_code}"
        
        data = response.json()
        assert 'status' in data
        assert 'timestamp' in data
        assert 'services' in data
        assert 'circuit_breaker' in data
        
        # Check service health details
        services = data['services']
        assert 'dynamodb' in services
        assert 'sqs' in services
        
        print(f"✅ Health check passed - Status: {data['status']}")
        return True
    
    def test_cors_headers(self):
        """Test CORS headers are present"""
        response = requests.options(f"{self.api_url}/metrics", timeout=10)
        
        assert response.status_code == 200
        assert 'Access-Control-Allow-Origin' in response.headers
        assert response.headers['Access-Control-Allow-Origin'] == '*'
        
        print("✅ CORS headers properly configured")
        return True
    
    def test_post_and_get_metrics(self):
        """Test posting a metric and then retrieving it"""
        # Create test metric
        test_metric = {
            'service_name': f'IntegrationTest-{int(time.time())}',
            'metric_type': 'cpu_utilization',
            'value': 85.5,
            'metadata': {
                'region': 'us-east-1',
                'instance_type': 't3.micro'
            }
        }
        
        # POST metric
        response = requests.post(
            f"{self.api_url}/metrics",
            json=test_metric,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        assert response.status_code == 201, f"POST failed with status {response.status_code}: {response.text}"
        
        post_data = response.json()
        assert 'message' in post_data
        assert 'timestamp' in post_data
        
        # Wait for eventual consistency
        time.sleep(2)
        
        # GET metrics
        response = requests.get(
            f"{self.api_url}/metrics?service={test_metric['service_name']}",
            timeout=10
        )
        
        assert response.status_code == 200, f"GET failed with status {response.status_code}: {response.text}"
        
        get_data = response.json()
        assert 'metrics' in get_data
        assert 'count' in get_data
        
        print(f"✅ POST/GET metrics test passed - Service: {test_metric['service_name']}")
        return True
    
    def test_api_performance(self):
        """Test API meets performance SLO"""
        start_time = time.time()
        
        response = requests.get(f"{self.api_url}/health", timeout=10)
        
        end_time = time.time()
        response_time = (end_time - start_time) * 1000  # milliseconds
        
        # API should respond within 2 seconds (SLO requirement)
        assert response_time < 2000, f"Response time too slow: {response_time}ms"
        assert response.status_code in [200, 503]
        
        print(f"✅ Performance test passed - Response time: {response_time:.2f}ms")
        return True
    
    def test_error_handling(self):
        """Test API error handling"""
        # Test invalid JSON
        response = requests.post(
            f"{self.api_url}/metrics",
            data="invalid json",
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        assert response.status_code == 400
        
        # Test missing required fields
        response = requests.post(
            f"{self.api_url}/metrics",
            json={'value': 50.0},  # Missing service_name and metric_type
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        assert response.status_code == 400
        
        print("✅ Error handling test passed")
        return True
    
    def run_all_tests(self):
        """Run all integration tests"""
        tests = [
            self.test_health_endpoint,
            self.test_cors_headers,
            self.test_post_and_get_metrics,
            self.test_api_performance,
            self.test_error_handling
        ]
        
        passed = 0
        failed = 0
        
        print(f"🚀 Starting integration tests against: {self.api_url}")
        print("-" * 60)
        
        for test in tests:
            print(f"\n🧪 Running {test.__name__}...")
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ {test.__name__} failed: {e}")
                failed += 1
        
        print("\n" + "=" * 60)
        print(f"📊 Integration Test Results:")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   📈 Success Rate: {(passed/(passed+failed)*100):.1f}%")
        
        return failed == 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--api-url', required=True, help='API Gateway URL')
    args = parser.parse_args()
    
    tester = TestApiIntegration(args.api_url)
    success = tester.run_all_tests()
    
    if not success:
        exit(1)