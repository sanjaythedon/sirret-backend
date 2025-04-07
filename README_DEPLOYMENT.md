# AWS Lambda and API Gateway Manual Deployment Guide

This guide explains how to deploy the Sirret API to AWS Lambda with API Gateway exposure using the AWS Management Console.

## Prerequisites

1. AWS account with access to Lambda and API Gateway services
2. AWS CLI installed and configured (optional, for AWS CLI commands)
3. Python 3.11 or later
4. Zip utility

## Deployment Steps

### 1. Create Deployment Package

Run the deployment script to create a Lambda deployment package:

```bash
./deploy.sh
```

This script will:
- Create a temporary directory
- Copy application files
- Install dependencies
- Create a deployment-package.zip file

### 2. Create Lambda Function

1. Go to the AWS Lambda Console: https://console.aws.amazon.com/lambda/
2. Click "Create function"
3. Select "Author from scratch"
4. Fill in the basic information:
   - Function name: `sirret-api` (or your preferred name)
   - Runtime: Python 3.11
   - Architecture: x86_64
5. Click "Create function"

### 3. Configure Lambda Function

1. In the function's "Code" tab:
   - Click "Upload from" > ".zip file"
   - Upload the `deployment-package.zip` file
   - Click "Save"

2. In the "Runtime settings" section:
   - Handler: `lambda_handler.handler`
   - Click "Save"

3. In the "Configuration" tab:
   - General configuration:
     - Memory: Set to at least 512 MB
     - Timeout: 30 seconds
   - Environment variables:
     - Key: `OPENAI_API_KEY`
     - Value: Your OpenAI API key

### 4. Create API Gateway

1. Go to the API Gateway Console: https://console.aws.amazon.com/apigateway/
2. Click "Create API"
3. Select "REST API" > "Build"
4. Fill in the API details:
   - API name: `sirret-api` (or your preferred name)
   - Description: "Sirret API for Speech-to-Text"
   - Endpoint Type: Regional
5. Click "Create API"

### 5. Configure Proxy Integration

1. Click "Actions" > "Create Resource":
   - Check "Configure as proxy resource"
   - Resource Path: should be `{proxy+}`
   - Click "Create Resource"

2. For the "ANY" method that gets created:
   - Integration type: Lambda Function
   - Lambda Function: `sirret-api` (or the name you used)
   - Click "Save"
   - When prompted to add permission, click "OK"

3. Create a method on the root resource:
   - Select the root resource (/)
   - Click "Actions" > "Create Method"
   - Select "ANY" > click the checkmark
   - Integration type: Lambda Function
   - Lambda Function: `sirret-api` (or the name you used)
   - Click "Save"
   - When prompted to add permission, click "OK"

### 6. Configure CORS

1. Select the root resource (/)
2. Click "Actions" > "Enable CORS"
3. Configure the following:
   - Access-Control-Allow-Origin: `*`
   - Access-Control-Allow-Headers: `Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Requested-With`
   - Access-Control-Allow-Methods: `GET,POST,PUT,DELETE,OPTIONS`
   - Check "Default 4XX" and "Default 5XX" gateway responses
4. Click "Enable CORS and replace existing CORS headers"

### 7. Configure Binary Media Support

1. In the left sidebar, click on your API name
2. Click "Settings"
3. Scroll down to "Binary Media Types"
4. Click "Add Binary Media Type"
5. Add: `multipart/form-data`
6. Click "Add Binary Media Type" again
7. Add: `audio/*`
8. Click "Save Changes"

### 8. Deploy the API

1. Click "Actions" > "Deploy API"
2. Deployment stage: "New Stage"
3. Stage name: `prod`
4. Stage description: "Production Stage"
5. Click "Deploy"

You will see the "Invoke URL" at the top of the screen. This is your API endpoint.

### 9. Test Your API

Test your API using curl or a similar tool:

```bash
# Test the root endpoint
curl https://your-api-id.execute-api.region.amazonaws.com/prod/

# Test the transcribe endpoint (with a file)
curl -X POST \
  https://your-api-id.execute-api.region.amazonaws.com/prod/transcribe/ \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@/path/to/your/audio/file.mp3'
```

## Troubleshooting

### CORS Issues

If you're experiencing CORS issues:
- Verify that CORS is properly configured in API Gateway
- Check that the OPTIONS method is correctly handled
- Test with a simple curl request using the OPTIONS method

### Lambda Function Errors

To view Lambda function logs:
1. Go to AWS Console > CloudWatch > Log Groups
2. Find the log group for your Lambda function: `/aws/lambda/sirret-api`
3. Check the logs for any errors

### API Gateway Issues

- Make sure binary support is configured correctly for handling audio files
- Check that the Lambda function permissions are set correctly
- Verify the API Gateway deployment was successful 