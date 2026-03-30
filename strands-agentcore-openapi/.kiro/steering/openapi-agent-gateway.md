---
inclusion: auto
---

# OpenAPI Agent Gateway Implementation Guide

This steering document provides implementation guidance for the OpenAPI Agent Gateway project, a serverless AI agent system for OpenAPI-compliant REST APIs.

## Architecture Overview

The system follows this flow:
```
User → API Gateway → Agent Lambda → Cognito JWT validation → AgentCore Gateway → Claude/Bedrock → AgentCore Gateway → WeatherAPI.com (via OpenAPI Target)
```

Key design decisions:
- Uses dynamic OpenAPI specification parsing for tool discovery
- Cognito JWT validation at the AgentCore Gateway level
- Claude/Bedrock for AI-powered tool selection
- Targets OpenAPI-compliant APIs via Gateway OpenAPI targets
- No Interceptor Lambda — Gateway calls external APIs directly with API Key credential injection

## AWS Resource Configuration

### BedrockAgentCore Gateway

```yaml
Type: AWS::BedrockAgentCore::Gateway
Properties:
  AuthorizerType: CUSTOM_JWT
  JwtConfiguration:
    Issuer: !Sub "https://cognito-idp.us-east-1.amazonaws.com/${CognitoUserPoolId}"
    Audience: !Ref CognitoUserPoolClientId
    JwksUri: !Sub "https://cognito-idp.us-east-1.amazonaws.com/${CognitoUserPoolId}/.well-known/jwks.json"
```

### BedrockAgentCore GatewayTarget

Each OpenAPI operation becomes a GatewayTarget:
```yaml
Type: AWS::BedrockAgentCore::GatewayTarget
Properties:
  GatewayId: !Ref AgentCoreGateway
  TargetName: getCurrentWeather
  TargetType: INLINE
  InlinePayload:
    name: getCurrentWeather
    description: "Get current weather for a location"
    inputSchema:
      type: object
      properties:
        location:
          type: string
          description: "City name or coordinates"
      required: [location]
```

## OpenAPI Parsing Patterns

### Tool Name Generation

Use this priority order:
1. `operationId` if present
2. `{method}_{path}` with path segments joined by underscores (e.g., `get_weather_current`)

### Parameter Conversion

OpenAPI parameters map to Claude input schema:
- Path parameters → required properties
- Query parameters → optional properties (unless required: true)
- Request body → nested object in input schema

### Example Conversion

OpenAPI:
```yaml
paths:
  /weather/current:
    get:
      operationId: getCurrentWeather
      parameters:
        - name: location
          in: query
          required: true
          schema:
            type: string
```

Claude Tool Definition:
```json
{
  "name": "getCurrentWeather",
  "description": "Get current weather for a location",
  "input_schema": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "City name or coordinates"
      }
    },
    "required": ["location"]
  }
}
```

## Strands Agents SDK (REQUIRED)

**CRITICAL REQUIREMENT**: The Agent Lambda MUST use the official **Strands Agents SDK** (`pip install strands-agents`) for all agent orchestration. Do NOT implement custom Bedrock `invoke_model` logic.

The Strands Agents SDK is an open-source Python SDK from AWS that provides:

- Automatic agentic loop (reasoning → tool selection → tool execution → repeat → response)
- Native MCP integration via `MCPClient` for connecting to AgentCore Gateway
- Multi-turn tool use and parallel tool calls handled by the SDK
- `BedrockModel` for Amazon Bedrock integration
- `@tool` decorator for custom tools

### Required Packages

```
strands-agents>=1.0.0       # Core SDK: Agent, BedrockModel
mcp>=1.0.0                  # MCP client: streamablehttp_client
```

### Architecture with Strands SDK

```
src/
├── agent/
│   ├── strands_client.py      # create_mcp_client(), create_agent() helpers
│   ├── agent_processor.py     # AgentProcessor — connects MCPClient to Agent
│   ├── gateway_client.py      # (legacy) GatewayClient for direct boto3 operations
│   └── handler.py             # Lambda entry point with JWT validation
└── shared/
    ├── models.py              # Data models (UserContext, AgentRequest, AgentResponse)
    ├── logging_utils.py       # Structured logging (StructuredLogger)
    ├── error_utils.py         # Error handling and retry logic
    └── jwt_utils.py           # JWT validation and user context extraction
```

**Key Architecture Pattern:**
- `handler.py` → validates JWT, extracts UserContext, calls AgentProcessor
- `agent_processor.py` → creates MCPClient + Strands Agent, runs the agentic loop
- `strands_client.py` → factory functions for MCPClient and Agent creation

### How It Works

The Strands SDK's `MCPClient` connects directly to the AgentCore Gateway MCP endpoint using `streamablehttp_client`. The Gateway exposes tools via the MCP protocol — the SDK handles `tools/list` (discovery) and `tools/call` (execution) automatically as part of the agentic loop.

```python
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# 1. Connect to Gateway MCP endpoint with JWT auth
mcp_client = MCPClient(
    lambda: streamablehttp_client(
        url="https://GATEWAY_URL/mcp",
        headers={"Authorization": f"Bearer {jwt_token}"}
    )
)

# 2. Create agent with Bedrock model and MCP tools
# IMPORTANT: Do NOT use `with mcp_client:` — the Agent calls load_tools() → start() internally.
# Using `with` starts the session, then the Agent tries to start() again and raises
# "the client session is currently running" error.
model = BedrockModel(model_id="anthropic.claude-3-sonnet-20240229-v1:0", region_name="us-east-1")

try:
    agent = Agent(model=model, tools=[mcp_client], system_prompt="You are a helpful assistant.")
    result = agent("What's the weather in London?")
    print(result)
finally:
    mcp_client.stop(None, None, None)
```

The SDK handles the entire loop: the model reasons about the prompt, discovers available tools from the Gateway, selects the right tool, executes it via MCP `tools/call`, feeds the result back to the model, and repeats until a final text response is produced.

### Lambda Integration Pattern

For Lambda, create a new MCPClient per invocation (connection lifecycle management):

**CRITICAL**: Do NOT use `with mcp_client:` context manager. The Strands Agent's tool registry calls `load_tools()` which internally calls `start()`. If you've already started the session via `with`, it raises `MCPClientInitializationError("the client session is currently running")`. Instead, pass the MCPClient directly to the Agent and clean up with `stop()` in a `finally` block.

```python
def handler(event, context):
    mcp_client = MCPClient(
        lambda: streamablehttp_client(
            url=gateway_url,
            headers={"Authorization": f"Bearer {jwt_token}"}
        )
    )
    try:
        agent = Agent(model=model, tools=[mcp_client])
        result = agent(prompt)
        return str(result)
    finally:
        try:
            mcp_client.stop(None, None, None)
        except Exception:
            pass
```

### Lambda Layer

AWS provides an official Strands Agents Lambda layer:
```
arn:aws:lambda:{region}:856699698935:layer:strands-agents-py3_12-x86_64:1
```
This includes the base `strands-agents` package. For additional dependencies (like `mcp`), create a custom layer or package them in the deployment zip.

**IMPORTANT**: Do NOT implement custom `invoke_model` logic. The Strands SDK Agent class handles the full agentic loop including tool discovery, selection, execution, and multi-turn reasoning.

## Lambda Implementation Patterns

### Agent Lambda Structure with Strands Agents SDK (REQUIRED PATTERN)

**CRITICAL**: The Agent Lambda MUST use the Strands Agents SDK. Do NOT implement custom `invoke_model` logic.

The Agent Lambda has three layers:
1. **handler.py** — JWT validation, request parsing, response formatting
2. **agent_processor.py** — Creates MCPClient + Strands Agent, runs the agentic loop
3. **strands_client.py** — Factory functions for MCPClient and Agent creation

#### Layer 1: Lambda Handler (handler.py)

```python
from shared.jwt_utils import validate_jwt, extract_user_context
from shared.error_utils import ErrorHandler
from .agent_processor import AgentProcessor

def lambda_handler(event, context):
    # 1. Extract + validate JWT
    jwt_token = extract_bearer_token(event)
    claims = validate_jwt(jwt_token, COGNITO_JWKS_URL)
    user_context = extract_user_context(claims)

    # 2. Parse prompt
    body = json.loads(event.get("body", "{}"))
    prompt = body["prompt"]

    # 3. Run agent (Strands SDK handles the full loop)
    processor = AgentProcessor(gateway_id=GATEWAY_ID, model_id=MODEL_ID, region=REGION, logger=logger)
    response_text, session_id = processor.process_request(prompt, jwt_token, body.get("session_id"))

    # 4. Return response
    return AgentResponse(response=response_text, session_id=session_id, user_context=user_context).to_lambda_response()
```

#### Layer 2: Agent Processor (agent_processor.py)

```python
from .strands_client import create_mcp_client, create_agent

class AgentProcessor:
    def process_request(self, prompt, jwt_token, session_id=None):
        gateway_url = self._get_gateway_url()  # boto3 get_gateway() + cache
        mcp_client = create_mcp_client(gateway_url, jwt_token)

        # Do NOT use `with mcp_client:` — Agent.load_tools() calls start() internally
        try:
            agent = create_agent(model_id=self.model_id, region=self.region, mcp_client=mcp_client)
            result = agent(prompt)  # SDK handles: discover tools → reason → call tools → respond
            return str(result), session_id or str(uuid.uuid4())
        finally:
            try:
                mcp_client.stop(None, None, None)
            except Exception:
                pass
```

#### Layer 3: Strands Client (strands_client.py)

```python
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

def create_mcp_client(gateway_url, jwt_token):
    return MCPClient(lambda: streamablehttp_client(
        url=gateway_url,
        headers={"Authorization": f"Bearer {jwt_token}"}
    ))

def create_agent(model_id, region, mcp_client):
    model = BedrockModel(model_id=model_id, region_name=region)
    return Agent(model=model, tools=[mcp_client], system_prompt="You are a helpful assistant.")
```

**Why This Pattern:**
- The SDK handles the entire agentic loop — no manual tool discovery, selection, or execution code needed
- MCPClient connects directly to the Gateway MCP endpoint — no need for separate `list_gateway_targets` / `invoke_tool` calls
- Per-invocation MCPClient creation follows Lambda best practices for connection lifecycle
- JWT is passed as a header to the MCP transport, so the Gateway validates auth on every tool call

### Tool Discovery Pattern with GatewayClient (Legacy — now handled by MCPClient)

The GatewayClient discovers tools by querying the AgentCore Gateway for configured targets. This is the legacy pattern — the Strands SDK's MCPClient now handles tool discovery automatically via the MCP protocol.

**Legacy Implementation Details (kept for reference):**

```python
class GatewayClient:
    """Client for AgentCore Gateway operations"""
    
    def list_tools(self, jwt_token):
        """Query AgentCore Gateway for available tools."""
        
        # 1. List all Gateway Targets
        response = self.client.list_gateway_targets(
            gatewayIdentifier=self.gateway_id,
            maxResults=100
        )
        
        tools = []
        target_summaries = response.get('items', [])
        
        # 2. For each target, get full details including tool schema
        for target_summary in target_summaries:
            target_id = target_summary.get('targetId')
            target_name = target_summary.get('name')
            target_status = target_summary.get('status')
            
            # Skip non-ready targets
            if target_status != 'READY':
                continue
            
            # 3. Get full target details
            target_details = self.client.get_gateway_target(
                gatewayIdentifier=self.gateway_id,
                targetId=target_id
            )
            
            # 4. Extract tool definitions from target configuration
            target_config = target_details.get('targetConfiguration', {})
            mcp_config = target_config.get('mcp', {})
            lambda_config = mcp_config.get('lambda', {})
            tool_schema = lambda_config.get('toolSchema', {})
            inline_tools = tool_schema.get('inlinePayload', [])
            
            # 5. Convert each tool to Claude format
            for tool_def in inline_tools:
                claude_tool = self._convert_to_claude_format(tool_def, target_name)
                if claude_tool:
                    tools.append(claude_tool)
        
        return tools
    
    def _convert_to_claude_format(self, tool_def, target_name):
        """Convert Gateway tool definition to Claude format."""
        name = tool_def.get('name')
        description = tool_def.get('description')
        input_schema = tool_def.get('inputSchema', {})
        
        # Format tool name as {TargetName}___{ToolName} (THREE underscores)
        gateway_tool_name = f"{target_name}___{name}"
        
        return {
            'name': gateway_tool_name,
            'description': description,
            'input_schema': input_schema
        }
```

**Critical Details:**
- Uses `bedrock-agentcore-control` client (not `bedrock-agent-runtime`)
- Calls `list_gateway_targets()` to get target summaries
- Calls `get_gateway_target()` for each target to get full tool schemas
- Tool schemas are in `targetConfiguration.mcp.lambda.toolSchema.inlinePayload`
- Each tool is converted to Claude format with three-underscore naming
- Only READY targets are included

### Shared Data Models (REQUIRED)

Standardized data models in `shared/models.py`:

```python
from dataclasses import dataclass

@dataclass
class UserContext:
    """User identity information from JWT"""
    user_id: str
    username: str
    client_id: str
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'client_id': self.client_id
        }
    
    @classmethod
    def from_jwt_claims(cls, claims):
        return cls(
            user_id=claims['sub'],
            username=claims['username'],
            client_id=claims['client_id']
        )

@dataclass
class AgentRequest:
    """Agent Lambda request"""
    prompt: str
    jwt_token: str
    session_id: Optional[str] = None
    
    @classmethod
    def from_event(cls, event):
        """Parse from Lambda event"""
        headers = event.get('headers', {})
        body = json.loads(event.get('body', '{}'))
        
        auth_header = headers.get('Authorization', '')
        jwt_token = auth_header.replace('Bearer ', '')
        
        return cls(
            prompt=body['prompt'],
            jwt_token=jwt_token,
            session_id=body.get('session_id')
        )

@dataclass
class AgentResponse:
    """Agent Lambda response"""
    response: str
    session_id: str
    user_context: UserContext
    
    def to_lambda_response(self):
        return {
            'statusCode': 200,
            'body': json.dumps({
                'response': self.response,
                'session_id': self.session_id,
                'user_context': self.user_context.to_dict()
            })
        }
```

**IMPORTANT**: Always use these data models for consistency across the codebase.

### Gateway Tool Invocation Pattern with GatewayClient (Legacy — now handled by MCPClient)

The GatewayClient handles tool invocation through the AgentCore Gateway MCP endpoint. This is the legacy pattern — the Strands SDK's MCPClient now handles tool invocation automatically.

**Legacy Implementation Details (kept for reference):**

```python
class GatewayClient:
    """Client for AgentCore Gateway operations"""
    
    def invoke_tool(self, tool_name, tool_input, jwt_token):
        """Invoke tool through AgentCore Gateway via MCP endpoint."""
        
        # 1. Get Gateway MCP endpoint URL
        gateway_url = self._get_gateway_url()  # Calls get_gateway() API
        
        # 2. Format as JSON-RPC 2.0 request
        request_id = str(uuid.uuid4())
        mcp_request = {
            'jsonrpc': '2.0',
            'method': 'tools/call',
            'params': {
                'name': tool_name,  # Format: {TargetName}___{ToolName}
                'arguments': tool_input
            },
            'id': request_id
        }
        
        # 3. Prepare headers with JWT
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {jwt_token}'
        }
        
        # 4. Invoke Gateway via HTTPS POST
        response = requests.post(
            gateway_url,  # Gateway MCP endpoint
            headers=headers,
            json=mcp_request,
            timeout=30
        )
        
        # 5. Parse JSON-RPC response
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
        
        result = response.json()
        
        # 6. Extract result from JSON-RPC response
        if 'result' in result:
            return result['result']
        elif 'error' in result:
            raise Exception(f"Tool execution error: {result['error']}")
        else:
            raise Exception("Malformed tool response")
```

**Critical Details:**
- Gateway URL is retrieved via `get_gateway()` API and cached
- Tool invocation uses JSON-RPC 2.0 protocol over HTTPS
- Method is always `tools/call`
- Tool name uses three-underscore format: `{TargetName}___{ToolName}`
- JWT token is passed in Authorization header
- Gateway validates JWT, then routes to the appropriate OpenAPI Target
- Response is JSON-RPC format with `result` or `error` field

## Mock Weather API Implementation

### OpenAPI Specification

Store as `weather-api-spec.yaml`:
```yaml
openapi: 3.0.0
info:
  title: Weather API
  version: 1.0.0
paths:
  /weather/current:
    get:
      operationId: getCurrentWeather
      summary: Get current weather for a location
      parameters:
        - name: location
          in: query
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Current weather data
          content:
            application/json:
              schema:
                type: object
                properties:
                  location:
                    type: string
                  temperature:
                    type: number
                  conditions:
                    type: string
```

### Lambda Handler with User Context Validation

```python
def lambda_handler(event, context):
    """Mock Weather API with user context validation"""
    
    # Validate user context headers
    required_headers = ['X-User-Id', 'X-Username', 'X-Client-Id']
    headers = event.get('headers', {})
    
    for header in required_headers:
        if header not in headers:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Missing required header: {header}'})
            }
    
    # Log user context for audit
    print(json.dumps({
        'user_id': headers['X-User-Id'],
        'username': headers['X-Username'],
        'client_id': headers['X-Client-Id'],
        'operation': 'getCurrentWeather'
    }))
    
    # Return mock data
    location = event['queryStringParameters'].get('location', 'Unknown')
    return {
        'statusCode': 200,
        'body': json.dumps({
            'location': location,
            'temperature': 72,
            'conditions': 'Sunny'
        })
    }
```

## CloudFormation Best Practices

### Parameter Configuration

```yaml
Parameters:
  OpenAPISpecUrl:
    Type: String
    Description: S3 URL or HTTP URL to OpenAPI specification
    
  CognitoUserPoolName:
    Type: String
    Default: openapi-agent-gateway-users
    
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, staging, prod]
```

### IAM Role Patterns

Agent Lambda needs:
- `bedrock:InvokeModel` for Claude
- `bedrock-agent-runtime:ListGatewayTargets` for tool discovery
- `bedrock-agent-runtime:InvokeGatewayTarget` for tool invocation
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

### Output Values

```yaml
Outputs:
  GatewayId:
    Value: !Ref AgentCoreGateway
    Export:
      Name: !Sub "${AWS::StackName}-GatewayId"
      
  CognitoUserPoolId:
    Value: !Ref CognitoUserPool
    
  AgentLambdaArn:
    Value: !GetAtt AgentLambda.Arn
```

## Testing Patterns

### End-to-End Test Flow

1. Create Cognito user and obtain JWT token
2. Invoke Agent Lambda with natural language prompt
3. Verify tool discovery from Gateway
4. Verify Claude tool selection
5. Verify Gateway tool invocation
6. Verify response formatting by Claude

### Property-Based Testing

Test the OpenAPI parser with property:
```python
@given(valid_openapi_spec())
def test_openapi_roundtrip(spec):
    """Parsing then serializing produces equivalent tool definitions"""
    tools = parse_openapi_spec(spec)
    reconstructed = serialize_tools_to_openapi(tools)
    assert semantically_equivalent(spec, reconstructed)
```

## Reusability Guidelines

To add a new OpenAPI-based API:

1. Create OpenAPI 3.x specification file
2. Upload to S3 or make accessible via HTTPS
3. Update CloudFormation parameter `OpenAPISpecUrl`
4. Deploy stack - GatewayTargets are created automatically
5. Tools are discovered dynamically at runtime

No code changes required in Agent Lambda.

## Core Files

- `src/agent/strands_client.py` — Factory functions: `create_mcp_client()`, `create_agent()`
- `src/agent/agent_processor.py` — `AgentProcessor` using Strands SDK Agent + MCPClient
- `src/agent/handler.py` — Lambda entry point with JWT validation
- `src/shared/` — Models, logging, error handling, JWT utils

## Region Configuration

All resources must be deployed in `us-east-1` region due to BedrockAgentCore service availability.

## Logging and Monitoring

All Lambda functions should use structured logging via `shared/logging_utils.py`:

```python
from shared.logging_utils import get_logger, log_with_user_context

logger = get_logger(__name__)

# Log with user context
log_with_user_context(
    logger,
    'info',
    'Processing agent request',
    user_context=user_context,
    prompt_length=len(prompt),
    tool_count=len(tools)
)
```

Standard log fields:
- Request ID for correlation
- User ID from JWT
- Timestamp
- Operation performed
- Duration
- Success/failure status

CloudWatch alarms should monitor:
- Lambda error rate > 5 per 5 minutes
- Lambda duration > 80% of timeout
- Gateway 4xx/5xx error rates

## Packaging and Deployment

### Lambda Packaging with Strands Agents SDK

The Strands Agents SDK and MCP client must be packaged with the Agent Lambda:

```bash
# Package Agent Lambda with Strands SDK dependencies
python deployment/package_lambdas.py

# This creates a deployment package with:
# - src/agent/ (handler, agent_processor, strands_client)
# - src/shared/ (models, logging, error handling, JWT)
# - strands-agents, mcp, boto3, PyJWT, and other dependencies
```

**CRITICAL: Do NOT remove `.dist-info` directories during packaging cleanup.** The `opentelemetry` package (a dependency of `strands-agents`) uses `importlib.metadata.entry_points()` to discover its context runtime provider. Without `.dist-info` metadata, `entry_points()` returns an empty iterator and `next(iter(...))` raises `StopIteration` at import time, crashing the Lambda on cold start.

```python
# WRONG — causes StopIteration on Lambda import
patterns_to_remove = [
    "**/*.dist-info",  # ❌ opentelemetry needs this
]

# CORRECT — keep .dist-info, only remove .egg-info
patterns_to_remove = [
    "**/*.egg-info",   # ✓ safe to remove
]
```

### Lambda IAM Permissions for Strands SDK

**CRITICAL**: The Strands SDK uses the Bedrock `ConverseStream` API (not `InvokeModel`). The Lambda execution role MUST include these permissions:

```yaml
- Effect: Allow
  Action:
    - bedrock:InvokeModel
    - bedrock:InvokeModelWithResponseStream
    - bedrock:Converse
    - bedrock:ConverseStream
  Resource: '*'
```

Without `ConverseStream`, the Lambda will fail with `AccessDeniedException` on `bedrock:InvokeModelWithResponseStream`.

### Lambda Configuration for Strands SDK

The Strands SDK agentic loop (model reasoning + MCP tool calls) takes longer than simple `InvokeModel` calls. Recommended Lambda settings:

- **Timeout**: 120 seconds (minimum; the agentic loop may involve multiple model calls + tool executions)
- **Memory**: 1024 MB (the SDK + opentelemetry + MCP client have higher memory requirements)

Alternatively, use the official Strands Agents Lambda layer to reduce package size:
```
arn:aws:lambda:us-east-1:856699698935:layer:strands-agents-py3_12-x86_64:1
```
Then only package `mcp` and your application code in the zip.

### Deployment Script Pattern

```python
# deploy_all.py
import subprocess

def deploy_infrastructure():
    """Deploy CloudFormation stack"""
    subprocess.run([
        'aws', 'cloudformation', 'deploy',
        '--template-file', 'infrastructure/cloudformation-template.yaml',
        '--stack-name', 'openapi-agent-gateway',
        '--region', 'us-east-1',
        '--capabilities', 'CAPABILITY_IAM'
    ])

def package_and_upload_lambdas():
    """Package and upload all Lambda functions"""
    subprocess.run(['python', 'package_agent_lambda.py'])
    subprocess.run(['python', 'upload_agent_lambda.py'])

if __name__ == '__main__':
    deploy_infrastructure()
    package_and_upload_lambdas()
```


## CRITICAL: Gateway Target Architecture (OpenAPI vs Lambda)

### Understanding Gateway Target Types

AWS BedrockAgentCore Gateway supports different target types for different use cases:

1. **OpenAPI/HTTP Target** - For external HTTP APIs with OpenAPI specifications
2. **Lambda Target** - For AWS Lambda functions with MCP tool schemas
3. **MCP Server Target** - For MCP protocol servers
4. **Smithy Model Target** - For AWS services with Smithy models

### The Correct Pattern for OpenAPI Integration

**IMPORTANT**: When integrating with OpenAPI-compliant APIs, you must use the **OpenAPI/HTTP target type**, NOT the Lambda target type.

#### OpenAPI Target Configuration (CORRECT for HTTP APIs)

```yaml
WeatherAPITarget:
  Type: AWS::BedrockAgentCore::GatewayTarget
  Properties:
    GatewayIdentifier: !Ref AgentCoreGateway
    Name: weather-api
    Description: Weather API operations from OpenAPI specification
    CredentialProviderConfigurations:
      - CredentialProviderType: GATEWAY_IAM_ROLE
    TargetConfiguration:
      Mcp:
        ApiGateway:  # or OpenApi - for HTTP endpoints
          BaseUrl: https://api.open-meteo.com/v1
          OpenApiSchema:
            S3:
              S3BucketName: !Ref OpenAPISpecBucket
              S3ObjectKey: weather-api/openapi-spec.yaml
```

**Key Points:**
- The `BaseUrl` points to the actual HTTP API endpoint
- The `OpenApiSchema` describes the API operations
- The Gateway makes HTTP calls to the BaseUrl based on the OpenAPI spec
- No Lambda function is involved in the target execution

#### Lambda Target Configuration (INCORRECT for OpenAPI APIs)

```yaml
# DO NOT USE THIS PATTERN FOR OPENAPI APIS
WeatherAPITarget:
  Type: AWS::BedrockAgentCore::GatewayTarget
  Properties:
    TargetConfiguration:
      Mcp:
        Lambda:  # This is for Lambda functions, not HTTP APIs
          LambdaArn: !GetAtt WeatherAPILambda.Arn
          ToolSchema:
            S3:
              S3BucketName: !Ref OpenAPISpecBucket
              S3ObjectKey: tool-schema.json  # MCP format, not OpenAPI
```

**Why This is Wrong:**
- Lambda targets expect MCP tool schemas, not OpenAPI specs
- Lambda targets invoke Lambda functions, not HTTP APIs
- You cannot use an OpenAPI spec to describe a Lambda function's interface

### Architecture Decision: HTTP API vs Lambda

For the OpenAPI Agent Gateway project, we have two architectural options:

#### Option A: Pure OpenAPI/HTTP Architecture (RECOMMENDED)

```
Agent Lambda → AgentCore Gateway → [OpenAPI Target] → External HTTP API (e.g., Open-Meteo)
```

**Advantages:**
- True OpenAPI integration pattern
- No Lambda overhead for API calls
- Direct HTTP invocation
- Simpler architecture
- Lower cost (no Lambda invocations for API calls)

**Implementation:**
- Remove Weather API Lambda entirely
- Use real HTTP API (Open-Meteo weather API)
- Configure OpenAPI Gateway Target with BaseUrl and OpenAPI spec
- Gateway makes HTTP calls directly to the API

#### Option B: Lambda Wrapper Architecture (NOT RECOMMENDED)

```
Agent Lambda → AgentCore Gateway → [Lambda Target] → Weather API Lambda → External HTTP API
```

**Disadvantages:**
- Extra Lambda invocation adds latency and cost
- Lambda target requires MCP tool schema, not OpenAPI spec
- More complex architecture
- Defeats the purpose of OpenAPI integration

**When to Use:**
- Only if you need custom logic in the Lambda (auth, transformation, etc.)
- If the external API doesn't have an OpenAPI spec
- If you need to aggregate multiple APIs

### Migration Path: Lambda to OpenAPI Target

To migrate from the current Lambda-based architecture to the correct OpenAPI architecture:

1. **Remove Lambda Components:**
   - Delete `src/weather_api/handler.py`
   - Delete `WeatherAPILambda` from CloudFormation
   - Delete `WeatherAPILambdaRole` from CloudFormation
   - Delete Lambda packaging scripts for Weather API

2. **Create OpenAPI Specification:**
   - Create OpenAPI spec for the target HTTP API (e.g., Open-Meteo)
   - Include all operations you want to expose
   - Store in S3 bucket

3. **Update Gateway Target:**
   - Change from `Lambda` to `ApiGateway` configuration
   - Add `BaseUrl` pointing to the HTTP API
   - Reference OpenAPI spec in S3
   - Remove Lambda ARN reference

4. **Update Tests:**
   - Remove Lambda-specific tests
   - Add HTTP API integration tests
   - Test Gateway's HTTP invocation

### Example: Open-Meteo Weather API Integration

#### OpenAPI Specification for Open-Meteo

```yaml
openapi: 3.0.0
info:
  title: Open-Meteo Weather API
  version: 1.0.0
  description: Free weather API for non-commercial use
servers:
  - url: https://api.open-meteo.com/v1
paths:
  /forecast:
    get:
      operationId: getCurrentWeather
      summary: Get current weather for a location
      description: Returns current weather conditions for specified coordinates
      parameters:
        - name: latitude
          in: query
          required: true
          description: Latitude coordinate
          schema:
            type: number
            example: 51.5074
        - name: longitude
          in: query
          required: true
          description: Longitude coordinate
          schema:
            type: number
            example: -0.1278
        - name: current_weather
          in: query
          required: true
          description: Include current weather data
          schema:
            type: boolean
            default: true
      responses:
        '200':
          description: Current weather data
          content:
            application/json:
              schema:
                type: object
                properties:
                  latitude:
                    type: number
                  longitude:
                    type: number
                  current_weather:
                    type: object
                    properties:
                      temperature:
                        type: number
                        description: Temperature in Celsius
                      windspeed:
                        type: number
                        description: Wind speed in km/h
                      weathercode:
                        type: integer
                        description: WMO weather code
                      time:
                        type: string
                        format: date-time
```

#### CloudFormation Configuration

```yaml
Resources:
  # S3 Bucket for OpenAPI specs
  OpenAPISpecBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub '${AWS::StackName}-openapi-specs'

  # Upload OpenAPI spec to S3 (use Custom Resource)
  UploadOpenAPISpec:
    Type: Custom::UploadSpec
    Properties:
      ServiceToken: !GetAtt UploadSpecFunction.Arn
      BucketName: !Ref OpenAPISpecBucket
      SpecKey: open-meteo/openapi-spec.yaml
      SpecContent: |
        # OpenAPI spec content here

  # Gateway Target for Open-Meteo API
  OpenMeteoTarget:
    Type: AWS::BedrockAgentCore::GatewayTarget
    DependsOn: UploadOpenAPISpec
    Properties:
      GatewayIdentifier: !Ref AgentCoreGateway
      Name: open-meteo-weather
      Description: Open-Meteo Weather API
      CredentialProviderConfigurations:
        - CredentialProviderType: GATEWAY_IAM_ROLE
      TargetConfiguration:
        Mcp:
          ApiGateway:
            BaseUrl: https://api.open-meteo.com/v1
            OpenApiSchema:
              S3:
                S3BucketName: !Ref OpenAPISpecBucket
                S3ObjectKey: open-meteo/openapi-spec.yaml
```

### User Context Propagation

User context (from JWT claims) is validated at the Agent Lambda level. The Gateway handles JWT validation for MCP endpoint access, and the Agent Lambda extracts user context for logging and audit purposes. No interceptor is needed — the Gateway calls external APIs directly via OpenAPI targets with credential injection handled by the API Key Credential Provider.

### Summary: Key Architectural Principles

1. **OpenAPI specs describe HTTP APIs, not Lambda functions**
2. **Use OpenAPI/HTTP targets for external HTTP APIs**
3. **Use Lambda targets only when you need Lambda-specific logic**
4. **Don't wrap HTTP APIs in Lambda unless necessary**
5. **User context propagates via headers for HTTP targets, via arguments for Lambda targets**
6. **The Gateway makes HTTP calls directly to the BaseUrl based on the OpenAPI spec**

### Documentation References

- [AWS BedrockAgentCore Gateway OpenAPI Schema](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-schema-openapi.html)
- [Open-Meteo Weather API](https://open-meteo.com/en/docs)
- [OpenAPI 3.0 Specification](https://swagger.io/specification/)


## CloudFormation Template Fixes and Best Practices

### Critical Issues Resolved

#### Issue 1: Custom Resource Lambda Dependencies

**Problem**: The `UploadOpenAPISpecFunction` Lambda was using `urllib3` which is not available in the Python 3.12 Lambda runtime by default.

**Error**:
```
Runtime.ImportModuleError: Unable to import module 'index': No module named 'urllib3'
```

**Solution**: Use Python's built-in `urllib.request` instead:

```python
# INCORRECT - urllib3 not available
import urllib3
http = urllib3.PoolManager()
http.request('PUT', url, body=data, headers=headers)

# CORRECT - use built-in urllib.request
from urllib.request import Request, urlopen
req = Request(url, data=data, headers=headers)
urlopen(req)
```

**Complete Fixed Lambda Code**:
```python
Code:
  ZipFile: |
    import boto3
    import json
    from urllib.request import Request, urlopen
    
    s3 = boto3.client('s3')
    
    def send_response(event, context, status, data=None):
        """Send CloudFormation custom resource response"""
        response_body = {
            'Status': status,
            'Reason': f'See CloudWatch Log Stream: {context.log_stream_name}',
            'PhysicalResourceId': context.log_stream_name,
            'StackId': event['StackId'],
            'RequestId': event['RequestId'],
            'LogicalResourceId': event['LogicalResourceId'],
            'Data': data or {}
        }
        
        json_response = json.dumps(response_body).encode('utf-8')
        
        try:
            req = Request(event['ResponseURL'], data=json_response, headers={'Content-Type': ''})
            urlopen(req)
            print(f"Response sent: {status}")
        except Exception as e:
            print(f"Failed to send response: {e}")
    
    def handler(event, context):
        try:
            print(f"Event: {json.dumps(event)}")
            bucket = event['ResourceProperties']['BucketName']
            files = event['ResourceProperties'].get('Files', [])
            
            if event['RequestType'] == 'Delete':
                for f in files:
                    try:
                        s3.delete_object(Bucket=bucket, Key=f['Key'])
                        print(f"Deleted {f['Key']}")
                    except Exception as e:
                        print(f"Failed to delete {f['Key']}: {e}")
                send_response(event, context, 'SUCCESS')
                return
            
            for f in files:
                s3.put_object(Bucket=bucket, Key=f['Key'], Body=f['Content'].encode('utf-8'))
                print(f"Uploaded {f['Key']}")
            
            send_response(event, context, 'SUCCESS')
        except Exception as e:
            print(f"Error: {e}")
            send_response(event, context, 'FAILED', {'Error': str(e)})
```

**Key Points**:
- Always use built-in Python libraries for Lambda inline code
- `urllib.request` is available in all Python runtimes
- Custom resource handlers MUST send responses for all request types (Create, Update, Delete)
- Failure to send response causes 1-hour timeout and stack failure

#### Issue 2: Gateway Target S3 Schema Property Format

**Problem**: The `OpenMeteoWeatherTarget` was using incorrect property names for the S3 OpenAPI schema reference.

**Incorrect Configuration**:
```yaml
TargetConfiguration:
  Mcp:
    OpenApiSchema:
      S3:
        S3BucketName: !Ref OpenAPISpecBucket
        S3ObjectKey: open-meteo/openapi-spec.yaml
```

**Correct Configuration**:
```yaml
TargetConfiguration:
  Mcp:
    OpenApiSchema:
      S3:
        Uri: !Sub 's3://${OpenAPISpecBucket}/open-meteo/openapi-spec.yaml'
```

**Key Properties for OpenAPI Schema**:

The `OpenApiSchema` property supports two formats:

1. **S3 Reference** (recommended for production):
```yaml
OpenApiSchema:
  S3:
    Uri: s3://bucket-name/path/to/spec.yaml
```

2. **Inline Payload** (for small specs or testing):
```yaml
OpenApiSchema:
  InlinePayload: |
    openapi: 3.0.0
    info:
      title: My API
    # ... rest of spec
```

**Important**: Use `Uri` property with full S3 URI format, not separate `S3BucketName` and `S3ObjectKey` properties.

### CloudFormation Template Validation Checklist

Before deploying, always validate:

1. **Custom Resource Handlers**:
   - ✅ Use only built-in Python libraries
   - ✅ Send response for ALL request types (Create, Update, Delete)
   - ✅ Handle errors gracefully and send FAILED response
   - ✅ Include proper error logging

2. **Gateway Target Configuration**:
   - ✅ Use correct property format: `S3.Uri` not `S3BucketName`/`S3ObjectKey`
   - ✅ Use `!Sub` for S3 URI construction with bucket reference
   - ✅ Ensure OpenAPI spec is uploaded before target creation (use `DependsOn`)

3. **Lambda Function Configuration**:
   - ✅ Environment variables at function level, not inside `Code` block
   - ✅ Correct component tags for all resources
   - ✅ Proper IAM permissions for all operations

4. **Resource Dependencies**:
   - ✅ Custom resources depend on their Lambda functions
   - ✅ Gateway targets depend on spec upload completion
   - ✅ Lambda permissions granted before Gateway references them

### Stack Cleanup for Failed Deployments

When a stack enters `ROLLBACK_FAILED` or `DELETE_FAILED` state:

1. **Identify Stuck Resources**:
```bash
aws cloudformation describe-stack-resources \
    --stack-name openapi-agent-gateway \
    --region us-east-1 \
    --query 'StackResources[?ResourceStatus==`DELETE_FAILED`]'
```

2. **Force Delete with Resource Retention**:
```bash
aws cloudformation delete-stack \
    --stack-name openapi-agent-gateway \
    --region us-east-1 \
    --retain-resources UploadOpenAPISpec
```

This orphans the problematic custom resource but allows the stack to be deleted.

3. **Clean Up Orphaned Resources Manually**:
- Check CloudWatch Logs for the custom resource Lambda
- Manually delete S3 objects if needed
- Remove any orphaned Lambda functions

### Testing Custom Resources

Before deploying custom resources in CloudFormation:

1. **Test Lambda Function Independently**:
```python
# test_custom_resource.py
import json

def test_create_event():
    event = {
        'RequestType': 'Create',
        'ResponseURL': 'https://cloudformation-response-url',
        'StackId': 'test-stack',
        'RequestId': 'test-request',
        'LogicalResourceId': 'TestResource',
        'ResourceProperties': {
            'BucketName': 'test-bucket',
            'Files': [
                {'Key': 'test.yaml', 'Content': 'test: content'}
            ]
        }
    }
    
    # Mock context
    class Context:
        request_id = 'test-request-id'
        log_stream_name = 'test-log-stream'
    
    result = handler(event, Context())
    print(json.dumps(result, indent=2))
```

2. **Verify Response Sending**:
- Check that `send_response` is called for all code paths
- Verify response format matches CloudFormation requirements
- Test both SUCCESS and FAILED scenarios

3. **Test All Request Types**:
- Create: Initial resource creation
- Update: Resource property changes
- Delete: Stack deletion or resource removal

### Common CloudFormation Pitfalls

1. **Misplaced Properties**:
   - Environment variables inside `Code.ZipFile` block ❌
   - Environment variables at function level ✅

2. **Incorrect Intrinsic Functions**:
   - `!Ref` for resource IDs
   - `!GetAtt` for resource attributes
   - `!Sub` for string substitution with variables

3. **Missing Dependencies**:
   - Always use `DependsOn` for resource ordering
   - Custom resources must depend on their Lambda functions
   - Gateway targets must depend on spec uploads

4. **Timeout Issues**:
   - Custom resources have 1-hour timeout
   - Always send response, even on error
   - Use appropriate Lambda timeout (60s for custom resources)

### Deployment Best Practices

1. **Validate Before Deploy**:
```bash
python infrastructure/validate_template.py
aws cloudformation validate-template \
    --template-body file://infrastructure/cloudformation-template.yaml
```

2. **Use Change Sets for Updates**:
```bash
aws cloudformation create-change-set \
    --stack-name openapi-agent-gateway \
    --template-body file://infrastructure/cloudformation-template.yaml \
    --change-set-name update-$(date +%Y%m%d-%H%M%S)
```

3. **Monitor Deployment**:
```bash
aws cloudformation describe-stack-events \
    --stack-name openapi-agent-gateway \
    --region us-east-1 \
    --max-items 20
```

4. **Check Custom Resource Logs**:
```bash
aws logs tail /aws/lambda/dev-upload-openapi-spec \
    --since 10m \
    --region us-east-1 \
    --follow
```

### Summary of Template Fixes

Two critical fixes were required for successful deployment:

1. **Custom Resource Lambda**: Changed from `urllib3` to `urllib.request` for CloudFormation response handling
2. **Gateway Target S3 Schema**: Changed from `S3BucketName`/`S3ObjectKey` to `S3.Uri` format

These fixes ensure:
- ✅ Custom resources respond properly to CloudFormation
- ✅ Gateway targets correctly reference OpenAPI specs in S3
- ✅ Stack deployments complete successfully without timeouts
- ✅ Stack deletions work properly without getting stuck

Always validate templates and test custom resources independently before deploying to production.


## Gateway Target Credential Provider Configuration

### CRITICAL: OpenAPI Schema Targets Only Support Specific Credential Types

When using `OpenApiSchema` in a Gateway Target's `TargetConfiguration.Mcp`, you MUST NOT use `GATEWAY_IAM_ROLE` as the credential provider type.

**Supported credential provider types for OpenAPI targets:**
- `API_KEY` - For APIs that require API key authentication
- `OAUTH` - For APIs that require OAuth authentication
- **No credentials** - For public APIs (omit `CredentialProviderConfigurations` entirely)

**Example - Public API (no authentication required):**
```yaml
OpenMeteoWeatherTarget:
  Type: AWS::BedrockAgentCore::GatewayTarget
  Properties:
    GatewayIdentifier: !Ref AgentCoreGateway
    Name: open-meteo-weather
    Description: Open-Meteo Weather API
    # No CredentialProviderConfigurations needed for public APIs
    TargetConfiguration:
      Mcp:
        OpenApiSchema:
          InlinePayload: |
            openapi: 3.0.0
            # ... OpenAPI spec
```

**Example - API Key Authentication:**
```yaml
WeatherAPITarget:
  Type: AWS::BedrockAgentCore::GatewayTarget
  Properties:
    GatewayIdentifier: !Ref AgentCoreGateway
    Name: weather-api
    Description: Weather API with API Key
    CredentialProviderConfigurations:
      - CredentialProviderType: API_KEY
        ApiKeyCredentialProvider:
          SecretArn: !Ref WeatherAPIKeySecret
    TargetConfiguration:
      Mcp:
        OpenApiSchema:
          InlinePayload: |
            openapi: 3.0.0
            # ... OpenAPI spec
```

**Error if using GATEWAY_IAM_ROLE:**
```
Resource handler returned message: "Open api schema target only supports OAUTH and API_KEY credential provider type"
```

### Lambda Targets vs OpenAPI Targets

Note that Lambda targets CAN use `GATEWAY_IAM_ROLE`:

```yaml
# Lambda target - GATEWAY_IAM_ROLE is valid
ListS3BucketsTarget:
  Type: AWS::BedrockAgentCore::GatewayTarget
  Properties:
    CredentialProviderConfigurations:
      - CredentialProviderType: GATEWAY_IAM_ROLE  # ✓ Valid for Lambda targets
    TargetConfiguration:
      Mcp:
        Lambda:
          LambdaArn: !GetAtt ToolLambda.Arn
```

```yaml
# OpenAPI target - GATEWAY_IAM_ROLE is NOT valid
OpenAPITarget:
  Type: AWS::BedrockAgentCore::GatewayTarget
  Properties:
    CredentialProviderConfigurations:
      - CredentialProviderType: GATEWAY_IAM_ROLE  # ✗ Invalid for OpenAPI targets
    TargetConfiguration:
      Mcp:
        OpenApiSchema:
          InlinePayload: |
            openapi: 3.0.0
```



## Gateway Target Credential Provider Types

**CRITICAL**: OpenAPI schema targets have specific credential provider requirements:

### Supported Credential Types for OpenAPI Targets
- **API_KEY**: For APIs requiring API key authentication
- **OAUTH**: For APIs using OAuth authentication
- **NO CREDENTIALS**: For public APIs (omit `CredentialProviderConfigurations` entirely)

### NOT Supported for OpenAPI Targets
- ❌ **GATEWAY_IAM_ROLE**: This is ONLY for Lambda targets, NOT for OpenAPI targets
- Using `GATEWAY_IAM_ROLE` with OpenAPI targets will cause deployment failure with error:
  ```
  Open api schema target only supports OAUTH and API_KEY credential provider type
  ```

### Examples

**Public API (No Authentication Required)**:
```yaml
OpenMeteoWeatherTarget:
  Type: AWS::BedrockAgentCore::GatewayTarget
  Properties:
    GatewayIdentifier: !Ref AgentCoreGateway
    Name: open-meteo-weather
    Description: Open-Meteo Weather API
    # NO CredentialProviderConfigurations needed
    TargetConfiguration:
      Mcp:
        OpenApiSchema:
          InlinePayload: |
            openapi: 3.0.0
            ...
```

**API with API Key**:
```yaml
WeatherAPITarget:
  Type: AWS::BedrockAgentCore::GatewayTarget
  Properties:
    GatewayIdentifier: !Ref AgentCoreGateway
    Name: weather-api
    CredentialProviderConfigurations:
      - CredentialProviderType: API_KEY
        ApiKeyConfiguration:
          ApiKeyIdentityArn: !Ref ApiKeyIdentity
    TargetConfiguration:
      Mcp:
        OpenApiSchema:
          InlinePayload: |
            openapi: 3.0.0
            ...
```

**API with OAuth**:
```yaml
GoogleAPITarget:
  Type: AWS::BedrockAgentCore::GatewayTarget
  Properties:
    GatewayIdentifier: !Ref AgentCoreGateway
    Name: google-api
    CredentialProviderConfigurations:
      - CredentialProviderType: OAUTH
        OAuthConfiguration:
          OAuthIdentityArn: !Ref OAuthIdentity
    TargetConfiguration:
      Mcp:
        OpenApiSchema:
          InlinePayload: |
            openapi: 3.0.0
            ...
```

### Lambda Targets (Different Rules)
Lambda targets (not OpenAPI) CAN use `GATEWAY_IAM_ROLE`:
```yaml
ListS3BucketsTarget:
  Type: AWS::BedrockAgentCore::GatewayTarget
  Properties:
    GatewayIdentifier: !Ref AgentCoreGateway
    Name: list-s3-buckets
    CredentialProviderConfigurations:
      - CredentialProviderType: GATEWAY_IAM_ROLE  # ✓ Valid for Lambda targets
    TargetConfiguration:
      Mcp:
        Lambda:
          LambdaArn: !GetAtt ToolLambda.Arn
          ToolSchema:
            InlinePayload:
              - Name: list-s3-buckets
                ...
```



## Open-Meteo Weather API (No Authentication Required)

**Note**: This API is documented here for use in other workspaces where you target it via API Gateway. For direct OpenAPI Gateway Target usage, see WeatherAPI.com below.

### API Details
- **Base URL**: `https://api.open-meteo.com/v1`
- **Authentication**: None required (public API)
- **Rate Limits**: Fair use policy, no hard limits for non-commercial use
- **Documentation**: https://open-meteo.com/en/docs

### Current Weather Endpoint

**Endpoint**: `GET /forecast`

**Query Parameters**:
- `latitude` (required): Latitude coordinate (e.g., 51.5074 for London)
- `longitude` (required): Longitude coordinate (e.g., -0.1278 for London)
- `current_weather` (required): Set to `true` to get current weather data

**Example Request**:
```
GET https://api.open-meteo.com/v1/forecast?latitude=51.5074&longitude=-0.1278&current_weather=true
```

**Example Response**:
```json
{
  "latitude": 51.5,
  "longitude": -0.120000124,
  "generationtime_ms": 0.123,
  "utc_offset_seconds": 0,
  "timezone": "GMT",
  "timezone_abbreviation": "GMT",
  "elevation": 23.0,
  "current_weather": {
    "temperature": 15.3,
    "windspeed": 12.5,
    "winddirection": 230,
    "weathercode": 3,
    "is_day": 1,
    "time": "2026-03-05T10:00"
  }
}
```

### OpenAPI Specification for Open-Meteo

```yaml
openapi: 3.0.0
info:
  title: Open-Meteo Weather API
  version: 1.0.0
  description: Free weather API for non-commercial use
servers:
  - url: https://api.open-meteo.com/v1
paths:
  /forecast:
    get:
      operationId: getCurrentWeather
      summary: Get current weather
      description: Get current weather data for a location
      parameters:
        - name: latitude
          in: query
          required: true
          schema:
            type: number
          description: Latitude coordinate
        - name: longitude
          in: query
          required: true
          schema:
            type: number
          description: Longitude coordinate
        - name: current_weather
          in: query
          required: true
          schema:
            type: boolean
          description: Include current weather data
      responses:
        '200':
          description: Weather data
          content:
            application/json:
              schema:
                type: object
                properties:
                  latitude:
                    type: number
                  longitude:
                    type: number
                  current_weather:
                    type: object
                    properties:
                      temperature:
                        type: number
                        description: Temperature in Celsius
                      windspeed:
                        type: number
                        description: Wind speed in km/h
                      weathercode:
                        type: integer
                        description: WMO weather code
                      time:
                        type: string
                        format: date-time
```

### Using Open-Meteo with API Gateway

Since Open-Meteo doesn't require authentication, you can create an API Gateway REST API as a proxy:

1. Create API Gateway REST API with IAM authentication
2. Create a proxy integration to `https://api.open-meteo.com/v1/forecast`
3. Use the API Gateway as a BedrockAgentCore Gateway Target with `GATEWAY_IAM_ROLE` credentials

This approach allows you to:
- Add authentication/authorization layer
- Implement rate limiting and throttling
- Monitor and log API usage
- Cache responses for better performance



## API Key Credential Provider - CloudFormation Limitation

### CRITICAL: CloudFormation Does Not Support Creating API Key Credential Providers

**Problem**: The CloudFormation resource type `AWS::Bedrock::AgentCoreCredentialProvider` does NOT exist. You cannot create API Key Credential Providers using CloudFormation.

**Error Message**:
```
Unrecognized resource types: [AWS::Bedrock::AgentCoreCredentialProvider]
```

### Solution: Create Credential Provider Manually, Reference by ARN

You must create the API Key Credential Provider outside of CloudFormation, then reference it by ARN in your template.

#### Option 1: AWS Console (Manual)

1. Navigate to: **Amazon Bedrock → AgentCore → Identity & Access → Credential Providers**
   - Direct link: `https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/agentcore/identity`

2. Click **"Create credential provider"**

3. Select **"API Key"** as the credential type

4. Fill in the form:
   - **Name**: `dev-weatherapi-key`
   - **Description**: `WeatherAPI.com API key for OpenAPI Agent Gateway`
   - **API Key Secret ARN**: Your Secrets Manager secret ARN
   - **Credential Location**: `QUERY_PARAMETER` (or `HEADER` depending on API)
   - **Parameter Name**: `key` (the query parameter or header name)
   - **Credential Prefix**: (leave empty unless API requires prefix like "Bearer ")

5. Click **"Create"**

6. **Copy the Provider ARN** from the success message:
   ```
   arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID:token-vault/VAULT_ID/apikeycredentialprovider/PROVIDER_NAME
   ```

#### Option 2: AWS CLI (Automated)

```bash
# Create the API Key Credential Provider
aws bedrock-agent-runtime create-credential-provider \
  --name dev-weatherapi-key \
  --description "WeatherAPI.com API key" \
  --credential-provider-type API_KEY \
  --api-key-credential-provider-config \
    SecretArn=arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:dev-weatherapi-key-XXXXX,\
    CredentialLocation=QUERY_PARAMETER,\
    ParameterName=key \
  --region us-east-1
```

**Note**: The exact CLI command may vary. Check AWS CLI documentation for the correct service name and command structure.

#### Option 3: Python Script (Automated)

```python
import boto3

client = boto3.client('bedrock-agent-runtime', region_name='us-east-1')

response = client.create_credential_provider(
    name='dev-weatherapi-key',
    description='WeatherAPI.com API key',
    credentialProviderType='API_KEY',
    apiKeyCredentialProviderConfig={
        'secretArn': 'arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:dev-weatherapi-key-XXXXX',
        'credentialLocation': 'QUERY_PARAMETER',
        'parameterName': 'key'
    }
)

print(f"Provider ARN: {response['credentialProviderArn']}")
```

### Update CloudFormation Template

After creating the credential provider, update your template:

**REMOVE THIS** (invalid CloudFormation resource):
```yaml
WeatherAPICredentialProvider:
  Type: AWS::Bedrock::AgentCoreCredentialProvider  # ❌ This type doesn't exist
  Properties:
    Name: dev-weatherapi-key
    Description: WeatherAPI.com API key
    CredentialProviderType: API_KEY
    ApiKeyCredentialProviderConfig:
      SecretArn: arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:dev-weatherapi-key-XXXXX
      CredentialLocation: QUERY_PARAMETER
      ParameterName: key
```

**REPLACE WITH** (comment and hardcoded ARN):
```yaml
# Note: API Key Credential Provider created manually outside CloudFormation
# Provider Name: dev-weatherapi-key
# Created via: AWS Console / AWS CLI / Python script
# ARN: arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID:token-vault/VAULT_ID/apikeycredentialprovider/dev-weatherapi-key
```

**UPDATE Gateway Target** to use hardcoded ARN:
```yaml
WeatherAPITarget:
  Type: AWS::BedrockAgentCore::GatewayTarget
  Properties:
    GatewayIdentifier: !Ref AgentCoreGateway
    Name: weatherapi-current-weather
    Description: WeatherAPI.com current weather data
    CredentialProviderConfigurations:
      - CredentialProviderType: API_KEY
        CredentialProvider:
          ApiKeyCredentialProvider:
            # Use the actual ARN from the credential provider you created
            ProviderArn: arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID:token-vault/VAULT_ID/apikeycredentialprovider/dev-weatherapi-key
    TargetConfiguration:
      Mcp:
        OpenApiSchema:
          InlinePayload: |
            openapi: 3.0.0
            # ... OpenAPI spec
```

### Credential Location Options

When creating an API Key Credential Provider, you must specify where the API expects the key:

1. **QUERY_PARAMETER**: API key in URL query string
   - Example: `https://api.example.com/endpoint?key=YOUR_API_KEY`
   - Parameter Name: `key` (or whatever the API expects)

2. **HEADER**: API key in HTTP header
   - Example: `Authorization: Bearer YOUR_API_KEY`
   - Parameter Name: `Authorization` (or `X-API-Key`, etc.)
   - Credential Prefix: `Bearer ` (if required by API)

3. **PATH**: API key in URL path (less common)
   - Example: `https://api.example.com/YOUR_API_KEY/endpoint`

### Secrets Manager Secret Format

The Secrets Manager secret referenced by the credential provider must contain the API key in plain text or as a JSON object:

**Plain text format** (recommended for API keys):
```
c190031598b44b81b27132058260503
```

**JSON format** (if needed):
```json
{
  "apiKey": "c190031598b44b81b27132058260503"
}
```

If using JSON format, you may need to specify the JSON key path in the credential provider configuration.

### Deployment Workflow

The correct deployment workflow when using API Key authentication:

1. **Create Secrets Manager secret** (one-time):
   ```bash
   aws secretsmanager create-secret \
     --name dev-weatherapi-key \
     --secret-string "YOUR_API_KEY" \
     --region us-east-1
   ```

2. **Create API Key Credential Provider** (one-time, outside CloudFormation):
   - Use AWS Console, CLI, or Python script
   - Copy the Provider ARN

3. **Update CloudFormation template**:
   - Remove the invalid `AWS::Bedrock::AgentCoreCredentialProvider` resource
   - Hardcode the Provider ARN in the Gateway Target

4. **Deploy CloudFormation stack**:
   ```bash
   python deployment/deploy_stack.py
   ```

### Why This Limitation Exists

AWS Bedrock AgentCore is a relatively new service, and not all resource types have been added to CloudFormation yet. This is common with new AWS services - they often launch with API/Console support first, and CloudFormation support is added later.

**Workaround**: Create resources outside CloudFormation and reference them by ARN. This is a standard pattern for resources not yet supported by CloudFormation.

### Future Considerations

If AWS adds CloudFormation support for API Key Credential Providers in the future, you can:
1. Create a new CloudFormation resource for the credential provider
2. Update the Gateway Target to use `!GetAtt` or `!Ref` instead of hardcoded ARN
3. Delete the manually created credential provider (after stack update succeeds)

Until then, the manual creation + ARN reference approach is the only option.


## Gateway Execution Role - Required Permissions for API Key Outbound Auth

### CRITICAL: Three Actions, Four Resource Patterns for GetResourceApiKey

Per the [official AWS docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-outbound-auth.html), when using API Key outbound authorization with a custom gateway service role, the role needs three IAM actions. However, the AWS docs only show the credential provider ARN for `GetResourceApiKey` — in practice, the Gateway service evaluates this permission against FOUR different resource ARN patterns:

```yaml
Policies:
  - PolicyName: GatewayOutboundAuth
    PolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Sid: GetWorkloadAccessToken
          Effect: Allow
          Action:
            - bedrock-agentcore:GetWorkloadAccessToken
          Resource:
            - arn:aws:bedrock-agentcore:REGION:ACCOUNT:workload-identity-directory/default
            - arn:aws:bedrock-agentcore:REGION:ACCOUNT:workload-identity-directory/default/workload-identity/GATEWAY_NAME-*
        - Sid: GetResourceApiKey
          Effect: Allow
          Action:
            - bedrock-agentcore:GetResourceApiKey
          Resource:
            # ALL FOUR of these are required (the docs only mention the credential provider ARN):
            - arn:aws:bedrock-agentcore:REGION:ACCOUNT:token-vault/default
            - arn:aws:bedrock-agentcore:REGION:ACCOUNT:token-vault/default/apikeycredentialprovider/*
            - arn:aws:bedrock-agentcore:REGION:ACCOUNT:workload-identity-directory/default
            - arn:aws:bedrock-agentcore:REGION:ACCOUNT:workload-identity-directory/default/workload-identity/GATEWAY_NAME-*
        - Sid: GetSecretValue
          Effect: Allow
          Action:
            - secretsmanager:GetSecretValue
          Resource:
            - arn:aws:secretsmanager:REGION:ACCOUNT:secret:bedrock-agentcore-identity!default/apikey/*
```

Without all four resource patterns on `GetResourceApiKey`, `tools/call` fails with a generic "An internal error occurred" message while `tools/list` continues to work fine. See the [RESOLVED section below](#resolved-openapi-target-toolscall-internal-error) for full diagnosis details.

### Current Deployed Values

- Gateway Name: `dev-openapi-agent-gateway`
- Credential Provider ARN: `arn:aws:bedrock-agentcore:us-east-1:581571671018:token-vault/default/apikeycredentialprovider/resource-provider-api-key-iidhv`
- Managed Secret ARN: `arn:aws:secretsmanager:us-east-1:581571671018:secret:bedrock-agentcore-identity!default/apikey/resource-provider-api-key-iidhv-Q8CPOO`


## RESOLVED: OpenAPI Target tools/call Internal Error

### Status: RESOLVED

### Root Cause

The `GetResourceApiKey` IAM permission requires access to MULTIPLE resource ARN patterns, not just the credential provider ARN. The AWS documentation only shows the credential provider ARN, but the Gateway service internally evaluates the permission against additional resources:

1. `token-vault/default` — the token vault itself
2. `token-vault/default/apikeycredentialprovider/*` — the credential providers
3. `workload-identity-directory/default` — the workload identity directory
4. `workload-identity-directory/default/workload-identity/GATEWAY_NAME-*` — the gateway's workload identity

Without ALL four resource patterns, `tools/call` fails with a generic "An internal error occurred" while `tools/list` works fine (because `tools/list` doesn't need to retrieve credentials).

### How It Was Diagnosed

CloudTrail `lookup_events` revealed `AccessDenied` errors on `GetResourceApiKey` calls. The error messages showed the Gateway was trying to access the workload identity and token vault resources, not just the credential provider ARN. Each time a resource was added, a new `AccessDenied` appeared for a different resource pattern.

### Correct IAM Policy for API Key Outbound Auth

```yaml
Policies:
  - PolicyName: GatewayOutboundAuth
    PolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Sid: GetWorkloadAccessToken
          Effect: Allow
          Action:
            - bedrock-agentcore:GetWorkloadAccessToken
          Resource:
            - !Sub 'arn:aws:bedrock-agentcore:us-east-1:${AWS::AccountId}:workload-identity-directory/default'
            - !Sub 'arn:aws:bedrock-agentcore:us-east-1:${AWS::AccountId}:workload-identity-directory/default/workload-identity/${EnvironmentName}-openapi-agent-gateway-*'
        - Sid: GetResourceApiKey
          Effect: Allow
          Action:
            - bedrock-agentcore:GetResourceApiKey
          Resource:
            # ALL FOUR of these are required:
            - !Sub 'arn:aws:bedrock-agentcore:us-east-1:${AWS::AccountId}:token-vault/default'
            - !Sub 'arn:aws:bedrock-agentcore:us-east-1:${AWS::AccountId}:token-vault/default/apikeycredentialprovider/*'
            - !Sub 'arn:aws:bedrock-agentcore:us-east-1:${AWS::AccountId}:workload-identity-directory/default'
            - !Sub 'arn:aws:bedrock-agentcore:us-east-1:${AWS::AccountId}:workload-identity-directory/default/workload-identity/${EnvironmentName}-openapi-agent-gateway-*'
        - Sid: GetSecretValue
          Effect: Allow
          Action:
            - secretsmanager:GetSecretValue
          Resource:
            - !Sub 'arn:aws:secretsmanager:us-east-1:${AWS::AccountId}:secret:bedrock-agentcore-identity!default/apikey/*'
```

### Key Debugging Technique

When `tools/call` returns "An internal error occurred", check CloudTrail for `GetResourceApiKey` AccessDenied events:

```python
import boto3, json
from datetime import datetime, timedelta, timezone

ct = boto3.client('cloudtrail', region_name='us-east-1')
now = datetime.now(timezone.utc)
events = ct.lookup_events(StartTime=now - timedelta(minutes=5), EndTime=now, MaxResults=50)

for e in events.get('Events', []):
    parsed = json.loads(e['CloudTrailEvent'])
    if 'errorCode' in parsed and parsed.get('eventName') == 'GetResourceApiKey':
        print(f"Error: {parsed['errorMessage']}")
        print(f"Resources: {parsed.get('resources', [])}")
```

The error message will show which resource ARN the permission check is failing on.
