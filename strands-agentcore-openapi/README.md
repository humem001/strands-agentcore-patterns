# OpenAPI Agent Gateway

A serverless AI agent system that enables natural language interaction with OpenAPI-compliant REST APIs using AWS Bedrock AgentCore Gateway and Claude 3 Sonnet.

## Overview

The OpenAPI Agent Gateway dynamically discovers and invokes REST API operations from OpenAPI 3.x specifications. Users authenticate via Cognito JWT, submit natural language prompts to an Agent Lambda powered by Claude/Bedrock, which discovers and invokes tools dynamically generated from OpenAPI specifications through the AgentCore Gateway.

## Architecture

- **Agent Lambda** (512MB, 30s timeout): Processes natural language prompts using Claude 3 Sonnet, discovers tools from OpenAPI specifications via the Gateway, and orchestrates tool execution
- **Interceptor Lambda** (128MB, 5s timeout): Extracts user identity from Cognito JWT tokens and injects user context into API requests for complete audit trails
- **Weather API Lambda** (256MB, 10s timeout): Mock Weather API demonstrating the OpenAPI integration pattern with getCurrentWeather and getForecast operations

## Project Structure

```
.
├── src/
│   ├── agent/              # Agent Lambda implementation
│   ├── interceptor/        # Interceptor Lambda implementation
│   ├── weather_api/        # Mock Weather API Lambda implementation
│   ├── shared/             # Shared utilities and data models
│   └── openapi_parser/     # OpenAPI specification parser
├── infrastructure/         # CloudFormation templates
├── tests/
│   ├── unit/              # Unit tests
│   ├── property/          # Property-based tests
│   └── integration/       # Integration tests
├── deployment/            # Deployment scripts and utilities
└── README.md

```

## Requirements

- Python 3.12+
- AWS CLI v2 configured with credentials for `us-east-1`
- AWS Account with access to:
  - AWS Bedrock (Claude 3 Sonnet model access enabled)
  - AWS Lambda
  - AWS Bedrock AgentCore Gateway
  - Amazon Cognito
  - AWS Secrets Manager
  - Amazon S3
  - CloudWatch
- **WeatherAPI.com API Key** (free tier, no credit card required)

## Quick Start

### 1. Clone and Set Up Local Environment

```bash
git clone <repository-url>
cd openapi-agent-gateway

python3 -m venv venv
source venv/bin/activate    # On Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Get a WeatherAPI.com API Key

1. Sign up at [weatherapi.com/signup.aspx](https://www.weatherapi.com/signup.aspx) (free, no credit card)
2. Verify your email and log in to [weatherapi.com/my](https://www.weatherapi.com/my/)
3. Copy your API key from the dashboard

### 3. Store API Key in AWS Secrets Manager

```bash
aws secretsmanager create-secret \
  --name dev-weatherapi-key \
  --description "WeatherAPI.com API key for OpenAPI Agent Gateway" \
  --secret-string "YOUR_API_KEY_HERE" \
  --region us-east-1
```

Replace `YOUR_API_KEY_HERE` with your actual API key.

### 4. Deploy

For the full deployment walkthrough (CloudFormation stack, manual AWS resources, Lambda packaging, and testing), see **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)**.

## Infrastructure

The CloudFormation template (`infrastructure/cloudformation-template.yaml`) creates:

- **Cognito User Pool** with JWT token generation
- **AgentCore Gateway** with CUSTOM_JWT authorizer and REQUEST interceptor
- **Three Lambda Functions**: Agent, Interceptor, and Weather API
- **IAM Roles** with least-privilege permissions
- **CloudWatch Log Groups** with 30-day retention
- **CloudWatch Alarms** for error rates and duration thresholds
- **Gateway Target** for Weather API operations

### Stack Outputs

- `GatewayId`: AgentCore Gateway ID
- `CognitoUserPoolId`: Cognito User Pool ID
- `CognitoClientId`: Cognito User Pool Client ID
- `AgentLambdaArn`: Agent Lambda Function ARN
- `InterceptorLambdaArn`: Interceptor Lambda Function ARN
- `WeatherAPILambdaArn`: Weather API Lambda Function ARN

## Development Status

This project is currently in development. Task 1 (infrastructure foundation) has been completed:

- ✅ Directory structure created
- ✅ CloudFormation template with all required resources
- ✅ Gateway configured with CUSTOM_JWT authorizer
- ✅ Gateway configured with REQUEST interception point
- ✅ Stack outputs defined

## Next Steps

1. Implement shared utilities and data models
2. Implement OpenAPI parser module
3. Implement CloudFormation Gateway Target generator
4. Implement Mock Weather API Lambda
5. Implement Interceptor Lambda
6. Implement Gateway Client
7. Implement Strands Client
8. Implement Agent Lambda orchestration
9. Complete deployment scripts
10. Implement comprehensive test suite

## License

Copyright (c) 2024. All rights reserved.
