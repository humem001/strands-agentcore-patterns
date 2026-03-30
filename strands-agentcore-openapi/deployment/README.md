# Deployment Scripts

This directory contains scripts for packaging and deploying the OpenAPI Agent Gateway to AWS.

## Scripts

### 1. package_lambdas.py

Packages all three Lambda functions (Agent, Interceptor, Weather API) with their dependencies into deployment-ready ZIP files.

**Usage:**
```bash
python deployment/package_lambdas.py
```

**Output:**
- `deployment/agent-lambda.zip` - Agent Lambda deployment package
- `deployment/interceptor-lambda.zip` - Interceptor Lambda deployment package
- `deployment/weather-api-lambda.zip` - Weather API Lambda deployment package

**Features:**
- Automatically installs dependencies using pip with Linux x86_64 platform targeting
- Copies source code from `src/` directory
- Cleans up unnecessary files (__pycache__, tests, etc.)
- Verifies package structure
- Shows package sizes

**Requirements:**
- Python 3.9+
- pip
- unzip command (for verification)

### 2. deploy_stack.py

Validates the CloudFormation template and deploys the complete infrastructure stack to AWS.

**Usage:**
```bash
# Basic deployment
python deployment/deploy_stack.py

# Custom stack name
python deployment/deploy_stack.py --stack-name my-agent-gateway

# With S3 bucket for Lambda packages (recommended for large packages)
python deployment/deploy_stack.py --s3-bucket my-deployment-bucket

# Skip template validation
python deployment/deploy_stack.py --skip-validation
```

**Options:**
- `--stack-name` - CloudFormation stack name (default: openapi-agent-gateway)
- `--template` - Path to CloudFormation template (default: infrastructure/cloudformation-template.yaml)
- `--s3-bucket` - S3 bucket for Lambda packages (optional, uses inline deployment if not provided)
- `--skip-validation` - Skip template validation step

**Output:**
- `deployment/stack_outputs.json` - Stack outputs including Gateway ID, Cognito User Pool ID, Lambda ARNs

**Features:**
- Validates CloudFormation template before deployment
- Supports both create and update operations
- Uploads Lambda packages to S3 (if bucket provided) or uses inline deployment
- Waits for stack completion with progress updates
- Shows stack events on failure for debugging
- Saves stack outputs to JSON file

**Requirements:**
- AWS credentials configured (via AWS CLI, environment variables, or IAM role)
- Permissions: CloudFormation, Lambda, IAM, Cognito, Bedrock, S3 (if using S3 bucket)
- Lambda packages must be created first (run package_lambdas.py)

### 3. setup_test_user.py

Creates a test user in the Cognito User Pool and obtains JWT tokens for testing.

**Usage:**
```bash
# Create default test user
python deployment/setup_test_user.py

# Custom username and password
python deployment/setup_test_user.py --username myuser@example.com --password MyPassword123!
```

**Options:**
- `--username` - Username (email) for test user (default: testuser@example.com)
- `--password` - Password for test user (default: TestPassword123!)

**Output:**
- `deployment/test_credentials.json` - Test user credentials and JWT tokens
- `test_credentials.json` - Copy in root directory for backward compatibility

**Features:**
- Creates or recreates test user (deletes existing user if present)
- Sets permanent password (no password change required)
- Authenticates and obtains JWT tokens (access token, ID token, refresh token)
- Decodes and displays ID token claims
- Saves credentials and tokens to JSON file
- Tokens are valid for ~1 hour

**Requirements:**
- AWS credentials configured
- Stack must be deployed first (run deploy_stack.py)
- Permissions: Cognito User Pool administration

## Deployment Workflow

Follow these steps to deploy the complete system:

### Step 1: Package Lambda Functions

```bash
python deployment/package_lambdas.py
```

This creates three ZIP files in the `deployment/` directory.

### Step 2: Deploy CloudFormation Stack

```bash
python deployment/deploy_stack.py
```

This deploys the complete infrastructure to AWS. The deployment takes several minutes.

**Note:** For production deployments with large Lambda packages, use an S3 bucket:

```bash
python deployment/deploy_stack.py --s3-bucket my-deployment-bucket
```

### Step 3: Create Test User

```bash
python deployment/setup_test_user.py
```

This creates a test user and obtains JWT tokens for testing.

### Step 4: Verify Deployment

Run integration tests to verify the deployment:

```bash
pytest tests/integration/
```

Or test manually using the credentials in `test_credentials.json`.

## Troubleshooting

### Package Lambda Failures

**Error: "Package not found"**
- Ensure you're running from the project root directory
- Check that `src/` directory exists with agent, interceptor, weather_api, and shared modules

**Error: "Failed to install dependencies"**
- Check internet connection
- Verify pip is installed and up to date
- Try installing dependencies manually: `pip install -r requirements.txt`

### Deploy Stack Failures

**Error: "Template validation failed"**
- Check CloudFormation template syntax
- Run validation manually: `aws cloudformation validate-template --template-body file://infrastructure/cloudformation-template.yaml`

**Error: "Stack outputs not found"**
- Ensure stack deployment completed successfully
- Check `deployment/stack_outputs.json` exists

**Error: "Insufficient permissions"**
- Verify AWS credentials have required permissions
- Check IAM policies for CloudFormation, Lambda, Cognito, Bedrock access

**Stack creation/update hangs or fails:**
- Check CloudWatch Logs for Lambda function errors
- Review stack events in AWS Console: CloudFormation → Stacks → [stack-name] → Events
- Look for resource-specific error messages

### Setup Test User Failures

**Error: "Stack outputs not found"**
- Deploy stack first: `python deployment/deploy_stack.py`

**Error: "No user pool clients found"**
- Check CloudFormation stack created Cognito User Pool and Client
- Verify stack outputs include CognitoUserPoolId

**Error: "Authentication failed"**
- Verify password meets Cognito password policy requirements
- Check User Pool settings in AWS Console

## File Structure

```
deployment/
├── README.md                      # This file
├── package_lambdas.py             # Lambda packaging script
├── deploy_stack.py                # CloudFormation deployment script
├── setup_test_user.py             # Test user creation script
├── agent-lambda.zip               # Generated: Agent Lambda package
├── interceptor-lambda.zip         # Generated: Interceptor Lambda package
├── weather-api-lambda.zip         # Generated: Weather API Lambda package
├── agent-lambda-package/          # Generated: Temporary packaging directory
├── interceptor-lambda-package/    # Generated: Temporary packaging directory
├── weather-api-lambda-package/    # Generated: Temporary packaging directory
├── stack_outputs.json             # Generated: CloudFormation stack outputs
└── test_credentials.json          # Generated: Test user credentials and tokens
```

## Environment Variables

The scripts use the following environment variables (optional):

- `AWS_PROFILE` - AWS CLI profile to use
- `AWS_REGION` - AWS region (default: us-east-1)
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key

## Security Notes

- **Test credentials are for development only** - Do not use in production
- **JWT tokens expire after ~1 hour** - Re-run setup_test_user.py to get fresh tokens
- **Passwords must meet Cognito requirements** - Minimum 8 characters, uppercase, lowercase, numbers, special characters
- **S3 buckets should be private** - Ensure Lambda packages are not publicly accessible
- **IAM roles follow least privilege** - Review and adjust permissions as needed

## Next Steps

After successful deployment:

1. **Run integration tests** to verify end-to-end functionality
2. **Monitor CloudWatch Logs** for Lambda function execution
3. **Test with real prompts** using the Agent Lambda
4. **Add additional OpenAPI specifications** to extend functionality
5. **Configure CloudWatch Alarms** for production monitoring

## Support

For issues or questions:
- Check CloudWatch Logs for detailed error messages
- Review CloudFormation stack events for deployment issues
- Consult the main README.md for architecture and design details
- Check the design document: `.kiro/specs/openapi-agent-gateway/design.md`
