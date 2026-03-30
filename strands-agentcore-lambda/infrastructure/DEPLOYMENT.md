# Deployment Guide

Deploy and validate the Serverless AI Agent Gateway in ~15 minutes.

## Prerequisites

- Python 3.12+
- AWS CLI configured with credentials (`aws sts get-caller-identity` to verify)
- AWS account with Bedrock model access in us-east-1
- `boto3` installed

### Required AWS Permissions

- CloudFormation: create/update/delete stacks
- Lambda: create/update functions, update function code
- IAM: create roles and policies
- CloudWatch Logs: create log groups
- BedrockAgentCore: create Gateway, GatewayTarget
- Cognito: create user pools, manage users
- Bedrock: invoke models

## Quick Start

```bash
python infrastructure/deploy_stack.py    # 1. Deploy infrastructure (~5-10 min)
python deploy_all.py                     # 2. Package and upload Lambda code
python create_cognito_user.py            # 3. Create test user
python test_e2e_flow.py                  # 4. Run end-to-end test
```

Expected: HTTP 200, S3 bucket list returned, user context propagated through all layers.

## Step-by-Step Details

### Step 1: Deploy CloudFormation Stack

```bash
python infrastructure/deploy_stack.py
```

Options:
```bash
python infrastructure/deploy_stack.py --stack-name my-stack --environment prod --region us-west-2
```

This creates all AWS resources:
- Cognito User Pool + App Client
- AgentCore Gateway with CUSTOM_JWT authorizer and REQUEST interceptor
- Agent Lambda (1024MB, 120s timeout)
- Interceptor Lambda (128MB, 5s timeout)
- Tool Lambda (256MB, 10s timeout)
- GatewayTarget for `list-s3-buckets` with inline MCP schema
- IAM roles (least privilege per component)
- CloudWatch Log Groups (30-day retention)
- CloudWatch Alarms (errors, duration, throttles)

Takes ~5-10 minutes. Stack outputs saved to `infrastructure/stack_outputs.json`.

#### Validate Template First (Optional)

```bash
python infrastructure/validate_template.py
```

### Step 2: Package and Upload Lambda Code

CloudFormation deploys placeholder Lambda code. Real code is deployed separately:

```bash
python deploy_all.py
```

This runs 6 scripts sequentially:

| Script | What It Does |
|--------|-------------|
| `package_agent_lambda.py` | Bundles `src/agent/`, `src/shared/`, `agent-lambda-deps/` into zip |
| `package_interceptor_lambda.py` | Bundles `src/interceptor/`, `src/shared/` into zip |
| `package_tool_lambda.py` | Bundles `src/tool/`, `src/shared/` into zip |
| `upload_agent_lambda.py` | Updates Agent Lambda function code via `update_function_code` |
| `upload_interceptor_lambda.py` | Updates Interceptor Lambda function code |
| `upload_tool_lambda.py` | Updates Tool Lambda function code |

#### Lambda Packaging Details

Agent Lambda dependencies (`agent-lambda-deps/`) are pre-built Linux wheels downloaded with:
```bash
pip install --platform manylinux2014_x86_64 --python-version 3.12 --only-binary=:all: -t agent-lambda-deps/ -r agent-requirements.txt
```

This works from macOS — no Docker required. The `agent-requirements.txt` includes:
- `strands-agents` — Strands SDK for agent orchestration
- `mcp` — MCP client library with streamablehttp transport
- `boto3` — AWS SDK
- `PyJWT`, `cryptography` — JWT validation
- `requests` — HTTP client for JWKS fetching

Do not remove `.dist-info` directories from `agent-lambda-deps/` — opentelemetry (a transitive dependency) needs them for `importlib.metadata.entry_points()` discovery.

### Step 3: Create Test User

```bash
python create_cognito_user.py
```

Creates a confirmed user in the Cognito User Pool. Credentials are printed to stdout.

Note: Cognito access tokens use `sub` (UUID) as the username claim, not email. This is expected.

### Step 4: Run End-to-End Test

```bash
python test_e2e_flow.py
```

Validates the complete request flow:
1. Authenticates with Cognito → gets JWT access token
2. Invokes Agent Lambda with prompt "List my S3 buckets"
3. Agent Lambda creates Strands Agent with MCPClient → connects to Gateway
4. Gateway validates JWT → routes MCP request through Interceptor → Tool Lambda
5. Tool Lambda lists S3 buckets with user attribution
6. Verifies response contains bucket data and `user_context`

Expected output: HTTP 200 with bucket list and user context propagated.

### Step 5: Validate Deployment (Optional)

```bash
python infrastructure/validate_deployment.py
```

Checks:
- Gateway created with correct configuration
- Lambda functions have correct environment variables
- IAM permissions properly attached
- CloudWatch logging enabled
- No Lambda functions attached to VPC

## Stack Outputs

After deployment, review outputs:
```bash
cat infrastructure/stack_outputs.json
```

Key outputs:
- `GatewayId` — AgentCore Gateway identifier
- `CognitoUserPoolId` — Cognito User Pool ID
- `AgentLambdaArn` — Agent Lambda ARN
- `InterceptorLambdaArn` — Interceptor Lambda ARN
- `ToolLambdaArn` — Tool Lambda ARN

## Redeployment

### Code Changes Only

After modifying source code:
```bash
python deploy_all.py
```

### Infrastructure Changes

After modifying `cloudformation-template.yaml`:
```bash
python infrastructure/deploy_stack.py
python deploy_all.py  # Re-upload code if Lambda config changed
```

## Teardown

```bash
aws cloudformation delete-stack --stack-name dev-ai-agent-gateway --region us-east-1
aws cloudformation wait stack-delete-complete --stack-name dev-ai-agent-gateway --region us-east-1
```

This permanently deletes all resources including Lambda functions, log groups, IAM roles, Cognito User Pool, and the Gateway.

## Viewing Logs

```bash
aws logs tail /aws/lambda/dev-agent-lambda --follow
aws logs tail /aws/lambda/dev-interceptor-lambda --follow
aws logs tail /aws/lambda/dev-tool-lambda --follow
```

CloudWatch Logs Insights query for user-attributed requests:
```
fields @timestamp, user_id, username, @message
| filter user_id != "unknown"
| sort @timestamp desc
| limit 50
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "Invalid authentication token" | Using ID token instead of access token, or token expired | Verify `token_use` claim is `access`; re-authenticate |
| "No module named 'agent'" | Lambda code not uploaded | Run `python deploy_all.py` |
| Tool Lambda shows `user_id: unknown` | Interceptor not attached or failing | Check Interceptor CloudWatch logs |
| Gateway not found | Stack not deployed or wrong GATEWAY_ID | Check `stack_outputs.json` |
| `bedrock-agentcore-control` API error | Wrong parameter names | Ensure `gatewayIdentifier` (not `gatewayId`) and `gatewayUrl` (not `endpoint`) |
| Agent Lambda timeout | Gateway or Bedrock latency | Increase timeout in CloudFormation (currently 120s) |

## Cost

Estimated ~$10-50/month for light testing. Primary costs: Bedrock model invocations (Claude 3 Sonnet), Lambda duration, CloudWatch Logs. Delete the stack when not in use.