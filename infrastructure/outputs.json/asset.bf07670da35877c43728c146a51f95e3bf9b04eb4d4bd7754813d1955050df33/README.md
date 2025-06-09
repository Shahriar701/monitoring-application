# Pipeline Monitor Lambda Function

## Purpose
This Lambda function monitors CodePipeline execution state changes and sends custom metrics to CloudWatch for pipeline monitoring and alerting.

## Functionality
- Receives EventBridge events when pipeline state changes occur
- Extracts pipeline execution details (name, execution ID, state)
- Sends custom metrics to CloudWatch under the `Pipeline/Monitoring` namespace
- Logs pipeline execution status for debugging

## Metrics Sent
- **MetricName**: `PipelineExecution`
- **Namespace**: `Pipeline/Monitoring`
- **Dimensions**:
  - `PipelineName`: Name of the pipeline
  - `State`: Current execution state (STARTED, SUCCEEDED, FAILED, etc.)

## Event Source
This function is triggered by EventBridge rules that monitor CodePipeline state changes.

## IAM Permissions Required
- `codepipeline:*` - To access pipeline information
- `cloudwatch:PutMetricData` - To send custom metrics
- Standard Lambda execution permissions

## Environment Variables
None required - all information is extracted from the incoming EventBridge event.

## Error Handling
- Returns HTTP 200 on success
- Returns HTTP 500 on error with error logging
- All exceptions are caught and logged for debugging 