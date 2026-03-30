---
inclusion: auto
---

# Strands Agents SDK Migration Guide

This steering document provides patterns, gotchas, and reference code for migrating Lambda Agents from a manual Strands framework (custom `invoke_model` wrapper) to the official `strands-agents` SDK.

## Required Packages

```
strands-agents>=1.0.0       # Core SDK: Agent, BedrockModel
mcp>=1.0.0                  # MCP client: streamablehttp_client
```

## Migration Overview

Replace:
- Manual `bedrock.invoke_model()` calls → `strands.Agent` with `BedrockModel`
- Manual `tools/list` + `tools/call` JSON-RPC → `MCPClient` with `streamablehttp_client`
- Custom agentic loop (reason → select tool → execute → repeat) → SDK handles automatically
- Manual tool schema conversion → SDK discovers tools via MCP protocol

## Architecture Pattern

```
handler.py          → JWT validation, request parsing, response formatting
agent_processor.py  → Creates MCPClient + Strands Agent, runs the agentic loop
strands_client.py   → Factory functions for MCPClient and Agent creation
```

## Reference Code

### strands_client.py — Factory Functions

```python
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

SYSTEM_PROMPT = """You are a helpful AI assistant that can interact with APIs.
When retrieving information, use the available tools to fetch real data.
Format responses in a clear, human-readable way.
If a tool call fails, explain the error and suggest alternatives."""


def create_mcp_client(gateway_url: str, jwt_token: str) -> MCPClient:
    return MCPClient(
        lambda: streamablehttp_client(
            url=gateway_url,
            headers={"Authorization": f"Bearer {jwt_token}"}
        )
    )


def create_agent(model_id: str, region: str, mcp_client: MCPClient, system_prompt: str = None) -> Agent:
    model = BedrockModel(model_id=model_id, region_name=region, max_tokens=4096)
    return Agent(model=model, tools=[mcp_client], system_prompt=system_prompt or SYSTEM_PROMPT)
```

### agent_processor.py — Lambda Lifecycle Pattern

```python
import uuid, boto3
from .strands_client import create_mcp_client, create_agent

class AgentProcessor:
    def __init__(self, gateway_id, model_id, region, logger):
        self.gateway_id = gateway_id
        self.model_id = model_id
        self.region = region
        self.logger = logger
        self._gateway_url = None

    def process_request(self, prompt, jwt_token, session_id=None):
        if not session_id:
            session_id = str(uuid.uuid4())

        gateway_url = self._get_gateway_url()
        mcp_client = create_mcp_client(gateway_url, jwt_token)

        try:
            agent = create_agent(self.model_id, self.region, mcp_client)
            result = agent(prompt)
            return str(result), session_id
        finally:
            try:
                mcp_client.stop(None, None, None)
            except Exception:
                pass

    def _get_gateway_url(self):
        if self._gateway_url:
            return self._gateway_url
        client = boto3.client("bedrock-agentcore-control", region_name=self.region)
        response = client.get_gateway(gatewayIdentifier=self.gateway_id)
        self._gateway_url = response["gatewayUrl"]
        return self._gateway_url
```

## Critical Gotchas

### 1. Do NOT use `with mcp_client:` context manager

The Strands Agent's tool registry calls `load_tools()` which internally calls `start()`. If you've already started the session via `with`, it raises `MCPClientInitializationError("the client session is currently running")`.

```python
# WRONG — double-starts the session
with mcp_client:
    agent = Agent(model=model, tools=[mcp_client])
    result = agent(prompt)

# CORRECT — let Agent manage the session, clean up in finally
mcp_client = create_mcp_client(url, token)
try:
    agent = Agent(model=model, tools=[mcp_client])
    result = agent(prompt)
finally:
    try:
        mcp_client.stop(None, None, None)
    except Exception:
        pass
```

### 2. Do NOT remove `.dist-info` directories during Lambda packaging

The `opentelemetry` package (a dependency of `strands-agents`) uses `importlib.metadata.entry_points()` to discover its context runtime provider. Without `.dist-info` metadata, `entry_points()` returns an empty iterator and `next(iter(...))` raises `StopIteration` at import time, crashing the Lambda on cold start.

```python
# WRONG — causes StopIteration on Lambda import
patterns_to_remove = ["**/*.dist-info"]

# CORRECT — keep .dist-info, only remove .egg-info
patterns_to_remove = ["**/*.egg-info"]
```

### 3. Lambda IAM role needs ConverseStream, not just InvokeModel

The Strands SDK uses the Bedrock `ConverseStream` API internally. Without these permissions, Lambda fails with `AccessDeniedException`.

```yaml
- Effect: Allow
  Action:
    - bedrock:InvokeModel
    - bedrock:InvokeModelWithResponseStream
    - bedrock:Converse
    - bedrock:ConverseStream
  Resource: '*'
```

### 4. Lambda timeout and memory

The agentic loop involves multiple model calls + tool executions. Minimum recommended:
- Timeout: 120 seconds
- Memory: 1024 MB

### 5. Lambda packaging must target Python 3.12 / x86_64

Local Python version may differ from Lambda runtime. Always use:

```bash
pip install -r requirements.txt \
  -t package_dir \
  --platform manylinux2014_x86_64 \
  --python-version 3.12 \
  --only-binary=:all: \
  --upgrade
```

### 6. Packages over 50MB must go via S3

Lambda direct upload limit is 50MB. The Strands SDK package is typically ~62MB zipped. Upload to S3 first, then update Lambda code from S3.

### 7. Gateway execution role needs 4 ARN patterns for GetResourceApiKey

If using API Key credential providers with AgentCore Gateway, the execution role needs:

```yaml
- Sid: GetResourceApiKey
  Effect: Allow
  Action:
    - bedrock-agentcore:GetResourceApiKey
  Resource:
    - !Sub 'arn:aws:bedrock-agentcore:${AWS::Region}:${AWS::AccountId}:token-vault/default'
    - !Sub 'arn:aws:bedrock-agentcore:${AWS::Region}:${AWS::AccountId}:token-vault/default/apikeycredentialprovider/*'
    - !Sub 'arn:aws:bedrock-agentcore:${AWS::Region}:${AWS::AccountId}:workload-identity-directory/default'
    - !Sub 'arn:aws:bedrock-agentcore:${AWS::Region}:${AWS::AccountId}:workload-identity-directory/default/workload-identity/${GatewayName}-*'
```

Missing any of these causes "Internal Error" on `tools/call`.

### 8. OpenAPI targets only support OAUTH and API_KEY credential types

`GATEWAY_IAM_ROLE` is only valid for Lambda targets. OpenAPI/HTTP targets must use `API_KEY` or `OAUTH`.

### 9. API Key Credential Provider cannot be created via CloudFormation

`AWS::Bedrock::AgentCoreCredentialProvider` does not exist. Create manually via AWS Console or boto3, then reference the ARN in your template.

## Strands Lambda Layer (Optional)

AWS provides an official layer with the base `strands-agents` package:

```
arn:aws:lambda:{region}:856699698935:layer:strands-agents-py3_12-x86_64:1
```

You still need to package `mcp` and your application code separately.

## Multiple Tool Sources

The Agent accepts multiple MCPClient instances for combining tools from different sources:

```python
mcp_weather = create_mcp_client(weather_gateway_url, token)
mcp_database = create_mcp_client(database_gateway_url, token)

agent = Agent(model=model, tools=[mcp_weather, mcp_database], system_prompt=prompt)
```

## What to Remove During Migration

- Manual `bedrock_client.invoke_model()` / `converse()` calls
- Custom tool discovery code (`list_gateway_targets` + `get_gateway_target` loops)
- Custom tool invocation code (JSON-RPC `tools/call` HTTP requests)
- Custom agentic loop logic (reason → select → execute → repeat)
- Tool schema conversion code (Gateway format → Claude format)
- Any `GatewayClient` class that wraps these operations

The SDK replaces all of this with: `agent = Agent(model=model, tools=[mcp_client])` then `result = agent(prompt)`.
