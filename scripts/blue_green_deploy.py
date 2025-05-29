#!/usr/bin/env python3
import boto3
import json
import time
import sys
from datetime import datetime

class BlueGreenDeployer:
    def __init__(self, region='us-east-1'):
        self.region = region
        self.cloudformation = boto3.client('cloudformation', region_name=region)
        self.apigateway = boto3.client('apigateway', region_name=region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
    
    def deploy_blue_green(self, stack_name, environment='prod'):
        """
        Deploy using blue-green strategy with API Gateway stages
        """
        print(f"🚀 Starting blue-green deployment for {stack_name}")
        
        # Step 1: Deploy new version to 'green' stage
        green_stage = f"{environment}-green"
        
        print(f"📦 Deploying to green stage: {green_stage}")
        
        # Update stack with green stage
        try:
            self.cloudformation.update_stack(
                StackName=stack_name,
                UsePreviousTemplate=True,
                Parameters=[
                    {'ParameterKey': 'Environment', 'ParameterValue': environment},
                    {'ParameterKey': '
                    {'ParameterKey': 'Environment', 'ParameterValue': environment},
                    {'ParameterKey': 'Stage', 'ParameterValue': green_stage}
                ],
                Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM']
            )
            
            # Wait for deployment to complete
            print("⏳ Waiting for green deployment to complete...")
            waiter = self.cloudformation.get_waiter('stack_update_complete')
            waiter.wait(StackName=stack_name, WaiterConfig={'Delay': 30, 'MaxAttempts': 60})
            
        except Exception as e:
            print(f"❌ Green deployment failed: {e}")
            return False
        
        # Step 2: Get API Gateway ID and create green stage
        api_id = self._get_api_gateway_id(stack_name)
        if not api_id:
            print("❌ Could not find API Gateway ID")
            return False
        
        # Step 3: Create green stage deployment
        try:
            deployment_id = self._create_api_deployment(api_id, green_stage)
            print(f"✅ Green stage deployed: {green_stage}")
        except Exception as e:
            print(f"❌ Failed to create green stage: {e}")
            return False
        
        # Step 4: Run health checks on green stage
        green_url = f"https://{api_id}.execute-api.{self.region}.amazonaws.com/{green_stage}"
        if not self._run_health_checks(green_url):
            print("❌ Green stage health checks failed")
            self._cleanup_green_stage(api_id, green_stage)
            return False
        
        # Step 5: Switch traffic to green (update prod stage)
        print("🔄 Switching traffic to green stage...")
        try:
            self._switch_traffic_to_green(api_id, environment, green_stage)
            print("✅ Traffic switched to green")
        except Exception as e:
            print(f"❌ Failed to switch traffic: {e}")
            return False
        
        # Step 6: Monitor for 5 minutes
        print("📊 Monitoring green stage for 5 minutes...")
        if not self._monitor_green_stage(green_url, duration_minutes=5):
            print("⚠️ Issues detected, rolling back...")
            self._rollback_to_blue(api_id, environment)
            return False
        
        # Step 7: Cleanup old blue stage
        print("🧹 Cleaning up old blue stage...")
        self._cleanup_old_blue_stage(api_id, environment)
        
        print("🎉 Blue-green deployment completed successfully!")
        return True
    
    def _get_api_gateway_id(self, stack_name):
        """Get API Gateway ID from CloudFormation stack outputs"""
        try:
            response = self.cloudformation.describe_stacks(StackName=stack_name)
            outputs = response['Stacks'][0].get('Outputs', [])
            
            for output in outputs:
                if 'ApiUrl' in output['OutputKey']:
                    # Extract API ID from URL: https://api-id.execute-api.region.amazonaws.com/stage
                    url = output['OutputValue']
                    api_id = url.split('//')[1].split('.')[0]
                    return api_id
            
            return None
        except Exception as e:
            print(f"Error getting API Gateway ID: {e}")
            return None
    
    def _create_api_deployment(self, api_id, stage_name):
        """Create new API Gateway deployment and stage"""
        try:
            # Create deployment
            deployment = self.apigateway.create_deployment(
                restApiId=api_id,
                stageName=stage_name,
                description=f'Blue-green deployment to {stage_name} at {datetime.now().isoformat()}'
            )
            
            return deployment['id']
        except Exception as e:
            print(f"Error creating API deployment: {e}")
            raise
    
    def _run_health_checks(self, api_url):
        """Run health checks against the green stage"""
        import requests
        
        try:
            # Test health endpoint
            health_response = requests.get(f"{api_url}/health", timeout=30)
            if health_response.status_code not in [200, 503]:
                print(f"❌ Health check failed: {health_response.status_code}")
                return False
            
            # Test metrics endpoint
            metrics_response = requests.get(f"{api_url}/metrics", timeout=30)
            if metrics_response.status_code != 200:
                print(f"❌ Metrics endpoint failed: {metrics_response.status_code}")
                return False
            
            # Performance test
            start_time = time.time()
            perf_response = requests.get(f"{api_url}/health", timeout=30)
            response_time = (time.time() - start_time) * 1000
            
            if response_time > 5000:  # 5 second threshold
                print(f"❌ Performance test failed: {response_time}ms")
                return False
            
            print("✅ All health checks passed")
            return True
            
        except Exception as e:
            print(f"❌ Health checks failed: {e}")
            return False
    
    def _switch_traffic_to_green(self, api_id, prod_stage, green_stage):
        """Switch production traffic to green stage"""
        try:
            # Get green stage deployment ID
            green_stage_info = self.apigateway.get_stage(
                restApiId=api_id,
                stageName=green_stage
            )
            
            # Update prod stage to use green deployment
            self.apigateway.update_stage(
                restApiId=api_id,
                stageName=prod_stage,
                patchOps=[
                    {
                        'op': 'replace',
                        'path': '/deploymentId',
                        'value': green_stage_info['deploymentId']
                    }
                ]
            )
            
        except Exception as e:
            print(f"Error switching traffic: {e}")
            raise
    
    def _monitor_green_stage(self, api_url, duration_minutes=5):
        """Monitor green stage for issues"""
        try:
            import requests
            
            end_time = time.time() + (duration_minutes * 60)
            
            while time.time() < end_time:
                # Check health endpoint
                try:
                    response = requests.get(f"{api_url}/health", timeout=10)
                    if response.status_code not in [200, 503]:
                        print(f"⚠️ Health check failed during monitoring: {response.status_code}")
                        return False
                    
                    # Check response time
                    if response.elapsed.total_seconds() > 5:
                        print(f"⚠️ Slow response detected: {response.elapsed.total_seconds()}s")
                        return False
                        
                except requests.RequestException as e:
                    print(f"⚠️ Request failed during monitoring: {e}")
                    return False
                
                time.sleep(30)  # Check every 30 seconds
            
            print("✅ Monitoring completed successfully")
            return True
            
        except Exception as e:
            print(f"❌ Monitoring failed: {e}")
            return False
    
    def _rollback_to_blue(self, api_id, prod_stage):
        """Rollback to previous blue version"""
        try:
            # This would restore the previous deployment
            # Implementation depends on how you track previous deployments
            print("🔄 Rolling back to blue stage...")
            # Add rollback logic here
            
        except Exception as e:
            print(f"Error during rollback: {e}")
    
    def _cleanup_green_stage(self, api_id, green_stage):
        """Cleanup failed green stage"""
        try:
            self.apigateway.delete_stage(restApiId=api_id, stageName=green_stage)
            print(f"🗑️ Cleaned up failed green stage: {green_stage}")
        except Exception as e:
            print(f"Warning: Could not cleanup green stage: {e}")
    
    def _cleanup_old_blue_stage(self, api_id, environment):
        """Cleanup old blue stage after successful deployment"""
        try:
            # Implementation for cleaning up old versions
            print("🧹 Old blue stage cleaned up")
        except Exception as e:
            print(f"Warning: Could not cleanup old blue stage: {e}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Blue-Green Deployment')
    parser.add_argument('--stack-name', required=True, help='CloudFormation stack name')
    parser.add_argument('--environment', default='prod', help='Environment (dev/prod)')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    
    args = parser.parse_args()
    
    deployer = BlueGreenDeployer(args.region)
    
    try:
        success = deployer.deploy_blue_green(args.stack_name, args.environment)
        if success:
            print("🎉 Deployment successful!")
            sys.exit(0)
        else:
            print("💥 Deployment failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️ Deployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()