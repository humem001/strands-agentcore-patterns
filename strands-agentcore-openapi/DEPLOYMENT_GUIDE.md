# OpenAPI Agent Gateway - Deployment Guide

## Architecture

```
User → Agent Lambda → Cognito JWT validation → AgentCore Gateway (MCP) → WeatherAPI.com (OpenAPI Target)
                          ↕                         ↕
                    Strands Agents SDK         API Key Credential Provider
                    (Bedrock Claude)           (Token Vault → Secrets Manager)
```

## Getting Started (New Developer Setup)

Before doing anything else, complete these steps to set up your local environment.

### 1. Install Prerequisites

- **Python 3.12+** — [python.org/downloads](https://www.python.org/downloads/)
- **AWS CLI v2** — [docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)
- **Git** — to clone the repository

### 2. Configure AWS Credentials

You need an AWS account with access to the following services:
- AWS Lambda
- Amazon Bedrock (Claude 3 Sonnet model access enabled)
- AWS Bedrock AgentCore Gateway
- Amazon Cognito
- AWS Secrets Manager
- Amazon S3
- AWS CloudFormation
- Amazon CloudWatch

Configure your CLI for the `us-east-1` region (all resources are deployed there):

```bash
aws configure
# AWS Access Key ID: <your-access-key>
# AWS Secret Access Key: <your-secret-key>
# Default region name: us-east-1
# Default output format: json
```

Verify access:

```bash
aws sts get-caller-identity
```

### 3. Clone and Set Up the Project

```bash
git clone <repository-url>
cd openapi-agent-gateway

python3 -m venv venv
source venv/bin/activate    # On Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 4. Get a WeatherAPI.com API Key

This project calls the WeatherAPI.com REST API as its demo OpenAPI target. You need a free API key:

1. Sign up at [weatherapi.com/signup.aspx](https://www.weatherapi.com/signup.aspx) (no credit card required)
2. Verify your email
3. Log in to [weatherapi.com/my](https://www.weatherapi.com/my/) and copy your API key

**Free tier**: 1 million calls/month, current weather + 3-day forecast.

You'll use this key in the "Resources Created Outside CloudFormation" section below when creating the Secrets Manager secret.

---

## Resources Created Outside CloudFormation

> **Note**: If you use `scripts/deploy.sh` (recommended), these are created automatically. This section is only relevant for manual deployments.

### 1. Secrets Manager Secret (WeatherAPI.com API Key)

- **Name**: `{environment}/weatherapi-key`
- **Contains**: Your WeatherAPI.com API key
- **Created by**: `scripts/deploy.sh` automatically, or manually:

```bash
aws secretsmanager create-secret \
  --name dev/weatherapi-key \
  --secret-string "YOUR_WEATHERAPI_KEY_HERE" \
  --region us-east-1
```

### 2. API Key Credential Provider (BedrockAgentCore Token Vault)

- **Purpose**: Injects the WeatherAPI.com API key as a query parameter (`key`) into Gateway requests
- **Created by**: `scripts/deploy.sh` via `aws bedrock-agentcore-control` CLI (requires AWS CLI 2.28+)

If your CLI is older, create manually via AWS Console:
1. Navigate to Amazon Bedrock → AgentCore → Identity & Access → Credential Providers
2. Create credential provider with type "API Key"
3. Enter your WeatherAPI.com API key directly
4. Note down the credential provider ARN for the CloudFormation `CredentialProviderArn` parameter

### 3. S3 Bucket (Lambda Package Storage)

- **Name**: `lambda-packages-<your-account-id>-us-east-1`
- **Purpose**: Stores Lambda deployment packages over 50MB (the agent package is ~62MB)
- **Created by**: `scripts/deploy.sh` automatically on first run — no manual setup needed

## Resources Created by CloudFormation

The `openapi-agent-gateway` stack creates:

| Resource | Type | Name |
|----------|------|------|
| Cognito User Pool | `AWS::Cognito::UserPool` | `dev-openapi-agent-user-pool` |
| Cognito Client | `AWS::Cognito::UserPoolClient` | `dev-openapi-agent-client` |
| Gateway Execution Role | `AWS::IAM::Role` | `dev-gateway-execution-role` |
| AgentCore Gateway | `AWS::BedrockAgentCore::Gateway` | `dev-openapi-agent-gateway` |
| Agent Lambda Role | `AWS::IAM::Role` | `dev-agent-lambda-role` |
| Agent Lambda | `AWS::Lambda::Function` | `dev-agent-lambda` |
| Gateway Target | `AWS::BedrockAgentCore::GatewayTarget` | `weatherapi-current-weather` |
| Log Group | `AWS::Logs::LogGroup` | `/aws/lambda/dev-agent-lambda` |

## Deployment

### Prerequisites

- All steps in **Getting Started** above completed (Python, AWS CLI, venv, dependencies, WeatherAPI key)

### Quick Deploy (Recommended)

A single script handles everything — secrets, CloudFormation stack, credential provider, Lambda packaging, test user, and test script generation:

```bash
./scripts/deploy.sh \
  --environment-name dev \
  --weather-api-key YOUR_WEATHERAPI_KEY
```

That's it. When it finishes, test with:

```bash
./scripts/test.sh
./scripts/test.sh 'What is the weather in Paris, France?'
```

#### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--environment-name` | (required) | Environment prefix for all resources (dev/test/prod) |
| `--weather-api-key` | (required) | Your WeatherAPI.com API key |
| `--region` | `us-east-1` | AWS region |
| `--s3-bucket` | auto-created | S3 bucket for Lambda packages >50MB |

#### What the script does

1. Validates the CloudFormation template
2. Creates/updates the WeatherAPI key in Secrets Manager
3. Deploys the CloudFormation stack (creates Cognito, Gateway, Lambda, etc.)
4. Creates the API Key credential provider via `bedrock-agentcore-control` CLI (with console fallback if CLI is too old)
5. Re-deploys the stack with the credential provider ARN to wire up the Gateway Target
6. Packages and deploys the Lambda code (auto-uploads to S3 if >50MB)
7. Creates a Cognito test user (`testuser@example.com` / `TestPassword123!`)
8. Generates `scripts/test.sh` with baked-in config for one-command testing

#### Credential provider note

The script tries to create the credential provider via `aws bedrock-agentcore-control` CLI (requires AWS CLI 2.28+). If your CLI is older, it prints manual instructions for creating it via the AWS Console.

### End-to-End Test

```python
import boto3, json

with open('deployment/test_credentials.json') as f:
    creds = json.load(f)

lambda_client = boto3.client('lambda', region_name='us-east-1')
response = lambda_client.invoke(
    FunctionName='dev-agent-lambda',
    Payload=json.dumps({
        'headers': {'Authorization': f"Bearer {creds['access_token']}"},
        'body': json.dumps({'prompt': 'What is the weather in London?'})
    })
)
result = json.loads(response['Payload'].read())
print(json.loads(result['body'])['response'])
```

### Manual Deployment (Step-by-Step)

If you prefer to run each step individually:

<details>
<summary>Click to expand manual steps</summary>

#### Step 1: Deploy CloudFormation Stack

```bash
aws cloudformation deploy \
  --template-file infrastructure/cloudformation-template.yaml \
  --stack-name openapi-agent-gateway \
  --region us-east-1 \
  --capabilities CAPABILITY_NAMED_IAM
```

#### Step 2: Save Stack Outputs

```bash
aws cloudformation describe-stacks \
  --stack-name openapi-agent-gateway \
  --region us-east-1 \
  --query 'Stacks[0].Outputs' \
  --output json > deployment/stack_outputs.json
```

#### Step 3: Package Lambda

```bash
python deployment/package_lambdas.py
```

**Critical packaging notes:**
- Do NOT remove `.dist-info` directories — opentelemetry needs `entry_points()` metadata
- Uses `--python-version 3.12 --platform manylinux2014_x86_64 --only-binary=:all:` for Lambda compatibility

#### Step 4: Deploy Lambda Code

```bash
python update_lambda_code.py
```

#### Step 5: Create Test User

```bash
python deployment/setup_test_user.py
```

Creates `testuser@example.com` / `TestPassword123!` in the Cognito User Pool and saves JWT tokens to `deployment/test_credentials.json`.

</details>

## Teardown

### Delete Stack Only (preserves external resources)

```bash
aws cloudformation delete-stack --stack-name openapi-agent-gateway --region us-east-1
aws cloudformation wait stack-delete-complete --stack-name openapi-agent-gateway --region us-east-1
```

After deletion, the credential provider, secrets, and S3 bucket remain intact for redeployment.

### Full Cleanup (delete everything)

1. Delete the CloudFormation stack (above)
2. Delete the credential provider via AWS Console (Bedrock → AgentCore → Credential Providers)
3. Delete secrets:
   ```bash
   aws secretsmanager delete-secret --secret-id dev-weatherapi-key --region us-east-1
   ```
4. Empty and delete the S3 bucket:
   ```bash
   aws s3 rb s3://lambda-packages-<your-account-id>-us-east-1 --force
   ```

## Troubleshooting

### "Internal Error" on tools/call

The Gateway execution role needs 4 resource ARN patterns for `GetResourceApiKey`:
- `token-vault/default`
- `token-vault/default/apikeycredentialprovider/*`
- `workload-identity-directory/default`
- `workload-identity-directory/default/workload-identity/{gateway-name}-*`

### StopIteration on Lambda cold start

`.dist-info` directories were removed during packaging. Opentelemetry needs them for `entry_points()`. Re-run `package_lambdas.py` (it preserves `.dist-info` by default).

### MCPClientInitializationError ("client session is currently running")

Do NOT use `with mcp_client:` context manager. The Strands Agent's `load_tools()` calls `start()` internally. Use `try/finally` with `mcp_client.stop(None, None, None)` instead.

### AccessDeniedException on bedrock:InvokeModelWithResponseStream

The Strands SDK uses `ConverseStream` API. Lambda role needs `bedrock:ConverseStream` and `bedrock:InvokeModelWithResponseStream` permissions (both are in the template).

### Lambda timeout

The Strands SDK agentic loop involves multiple model calls + tool executions. Lambda is configured for 120s timeout and 1024MB memory.
