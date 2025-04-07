#!/bin/bash
set -e

echo "Creating Lambda deployment package using Docker (Amazon Linux)..."

# Check if Docker is installed
which docker > /dev/null || { echo "Docker is not installed. Please install it first."; exit 1; }

# Create a temporary Dockerfile
cat > Dockerfile.lambda <<EOF
FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt main.py lambda_handler.py ./

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir mangum

CMD ["lambda_handler.handler"]
EOF

# Build the Docker image
echo "Building Docker image..."
docker build -t lambda-package -f Dockerfile.lambda .

# Create a temporary container and copy the dependencies
echo "Creating deployment package..."
CONTAINER_ID=$(docker create lambda-package)
mkdir -p lambda-package-docker
docker cp $CONTAINER_ID:/var/task/. lambda-package-docker/
docker rm $CONTAINER_ID

# Create the deployment package
cd lambda-package-docker
zip -r ../deployment-package.zip .
cd ..

# Clean up
echo "Cleaning up..."
rm -rf lambda-package-docker
rm Dockerfile.lambda
docker image rm lambda-package

echo "Deployment package created: deployment-package.zip"
echo ""
echo "Manual deployment steps:"
echo "------------------------"
echo "1. Go to AWS Lambda Console"
echo "2. Create a new Lambda function with Python 3.11 runtime"
echo "3. Upload the deployment-package.zip file"
echo "4. Set the handler to: lambda_handler.handler"
echo "5. Set environment variable OPENAI_API_KEY to your API key"
echo "6. Set memory to at least 512MB and timeout to 30 seconds"
echo "7. Configure API Gateway as a trigger for the Lambda function"
echo ""
echo "See README_DEPLOYMENT.md for detailed instructions" 