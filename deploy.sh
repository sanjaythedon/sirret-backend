#!/bin/bash
set -e

echo "Creating Lambda deployment package..."

# Check current directory
CURRENT_DIR=$(pwd)
echo "Current directory: $CURRENT_DIR"

# Create temporary directory for packaging
TEMP_DIR="$(mktemp -d)"
echo "Created temporary directory: $TEMP_DIR"

# Copy necessary files to temp directory
echo "Copying application files..."
cp main.py lambda_handler.py requirements.txt "$TEMP_DIR/" || { echo "Failed to copy files. Check if they exist in the current directory."; exit 1; }

# Change to the temp directory for all operations
cd "$TEMP_DIR"
echo "Changed to directory: $(pwd)"

# Create a virtual environment for the build
echo "Creating virtual environment and installing dependencies..."
python3 -m venv venv || { echo "Failed to create virtual environment. Check if python3-venv is installed."; exit 1; }
source venv/bin/activate || { echo "Failed to activate virtual environment."; exit 1; }

# Install dependencies into package directory
echo "Installing pip packages..."
pip install --upgrade pip

# Create package directory that will be zipped
mkdir -p package
cp main.py lambda_handler.py package/

# Install dependencies directly to the package directory
pip install -r requirements.txt -t package/ --no-cache-dir || { echo "Failed to install requirements."; exit 1; }
pip install mangum -t package/ --no-cache-dir || { echo "Failed to install mangum."; exit 1; }

# Remove pydantic and install the Lambda-compatible version
echo "Fixing pydantic installation for AWS Lambda..."
cd package
rm -rf pydantic pydantic_core
rm -rf pydantic-* pydantic_core-*
pip install --platform manylinux2014_x86_64 --implementation cp --python-version 3.11 --only-binary=:all: --target . pydantic || { echo "Failed to install pydantic for Lambda."; exit 1; }
cd ..

# Create the deployment package
echo "Creating deployment package..."
cd package
ZIP_PATH="$CURRENT_DIR/deployment-package.zip"
echo "Zip file will be created at: $ZIP_PATH"
zip -r "$ZIP_PATH" . || { echo "Failed to create zip file. Check if zip utility is installed."; exit 1; }

# Return to original directory
cd "$CURRENT_DIR"
echo "Changed back to directory: $(pwd)"

# Verify zip file was created
if [ -f "deployment-package.zip" ]; then
    ZIP_SIZE=$(du -h deployment-package.zip | cut -f1)
    echo "Deployment package created: deployment-package.zip (Size: $ZIP_SIZE)"
else
    echo "ERROR: Zip file was not created. Check for errors above."
    exit 1
fi

# Clean up
echo "Cleaning up temporary files..."
rm -rf "$TEMP_DIR"

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