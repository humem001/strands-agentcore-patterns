# AgentCore API Gateway Weather Agent

A serverless AI weather agent built on AWS Bedrock AgentCore. Uses the Strands SDK to orchestrate an LLM (Claude 3 Sonnet) that calls weather tools exposed through an AgentCore Gateway backed by API Gateway and WeatherAPI.com.

## Architecture

```
User → Lambda (Strands SDK + Claude 3 Sonnet)
     → Cognito JWT authentication
     → AgentCore Gateway (MCP protocol, CUSTOM_JWT auth)
     → API Gateway REST API (API key auth via usage plan)
     → WeatherAPI.com
```

The LLM decides which tool to call. AgentCore auto-discovers available tools from the API Gateway's OpenAPI export and presents them to the agent via MCP `tools/list`. When the agent calls a tool, AgentCore routes the request to API Gateway, authenticating with an API key managed by a credential provider.

## Prerequisites

- AWS CLI 2.28+ (required for `bedrock-agentcore-control` commands)
- Python 3.12+
- pip3
- A [WeatherAPI.com](https://www.weatherapi.com/) API key (free tier works)
- An S3 bucket for Lambda deployment packages (if zip exceeds 50MB)
- AWS account with Bedrock and AgentCore enabled in `us-east-1`

## Quick Start

### 1. Deploy

```bash
./scripts/deploy.sh \
  --environment-name dev \
  --weather-api-key YOUR_WEATHERAPI_KEY \
  --region us-east-1 \
  --s3-bucket YOUR_S3_BUCKET
```

The script handles everything in order:
1. Validates the CloudFormation template
2. Creates Secrets Manager secrets (WeatherAPI key + API Gateway key)
3. Deploys the CloudFormation stack (API Gateway, AgentCore Gateway, Cognito, Lambda, IAM)
4. Retrieves the API Gateway key and updates Secrets Manager
5. Creates/updates the AgentCore credential provider via CLI
6. Updates the stack with the credential provider ARN
7. Packages and deploys the Lambda code (two-step pip install for binary + pure Python deps)
8. Creates a test user in Cognito
9. Generates `scripts/test.sh` with baked-in values

### 2. Test

```bash
./scripts/test.sh
./scripts/test.sh 'What is the weather in Liverpool, England?'
```

The test script authenticates via Cognito, gets an ID token, and invokes the Lambda with your prompt.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--environment-name` | Yes | Environment name (e.g. `dev`, `staging`, `prod`). Used for resource namespacing. |
| `--weather-api-key` | Yes | Your WeatherAPI.com API key |
| `--region` | No | AWS region (default: `us-east-1`) |
| `--s3-bucket` | No | S3 bucket for Lambda packages >50MB |


## Project Structure

```
├── infrastructure/
│   └── cloudformation-template.yaml   # Full stack: API GW, AgentCore, Cognito, Lambda, IAM
├── scripts/
│   ├── deploy.sh                      # One-command deployment script
│   └── test.sh                        # Generated after deploy — end-to-end test
├── src/
│   ├── agent/
│   │   ├── handler.py                 # Lambda entry point
│   │   ├── agent_processor.py         # MCP client + Strands Agent lifecycle
│   │   └── strands_client.py          # Factory functions
│   └── shared/
│       ├── models.py                  # UserContext, AgentRequest, AgentResponse
│       ├── jwt_utils.py               # JWT validation (Cognito ID tokens)
│       ├── error_utils.py             # Error handling
│       └── logging_utils.py           # Structured logging
├── tests/
│   ├── unit/
│   │   ├── test_cloudformation_template.py
│   │   ├── test_properties.py         # Property-based tests
│   │   └── conftest.py
│   └── integration/
│       └── test_e2e.py
├── handoff/                           # Reference patterns (do not modify)
├── requirements.txt                   # Lambda dependencies
└── README.md
```

## Teardown

```bash
# Delete credential provider (not managed by CloudFormation)
aws bedrock-agentcore-control delete-api-key-credential-provider \
  --name dev-weather-apigw-key --region us-east-1

# Delete the stack
aws cloudformation delete-stack --stack-name dev-weather-agent --region us-east-1
aws cloudformation wait stack-delete-complete --stack-name dev-weather-agent --region us-east-1

# Delete secrets
aws secretsmanager delete-secret --secret-id "dev/weather-api-key" \
  --force-delete-without-recovery --region us-east-1
aws secretsmanager delete-secret --secret-id "dev/apigw-api-key" \
  --force-delete-without-recovery --region us-east-1
```

Replace `dev` with your environment name if different.

## Running Tests

```bash
# Unit tests
python -m pytest tests/unit/ -v

# Property-based tests
python -m pytest tests/unit/test_properties.py -v
```

## Key Implementation Notes

- **Two separate API keys**: One for AgentCore → API Gateway (managed by credential provider), another for API Gateway → WeatherAPI.com (injected via stage variable from Secrets Manager)
- **Two-step pip install**: `--only-binary=:all:` with `--platform` silently skips pure Python packages. The deploy script runs a second install with `--no-deps` for `requests`, `PyJWT`, etc.
- **JWT validation**: Accepts both access and ID tokens. Audience verification is disabled (AgentCore Gateway handles it via `AllowedAudience`)
- **Credential provider**: Not a CloudFormation resource — managed via CLI. The deploy script auto-detects CLI support and creates/updates it, with fallback to manual instructions
- **Region**: Must be `us-east-1` (AgentCore availability)
