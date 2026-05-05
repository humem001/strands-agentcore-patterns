# Requirements Document

## Introduction

Migrate the Agent Lambda from a manual Strands framework implementation (custom `invoke_model` wrapper with hand-rolled tool discovery, invocation, and agentic loop) to the official `strands-agents` SDK. The SDK replaces manual Bedrock API calls with `strands.Agent` + `BedrockModel`, replaces manual Gateway tool discovery/invocation with `MCPClient` using `streamablehttp_client`, and eliminates the custom agentic loop entirely. Infrastructure changes include updated IAM permissions, Lambda resource limits, and packaging rules.

## Glossary

- **Agent_Lambda**: The AWS Lambda function that receives user prompts, authenticates via JWT, and orchestrates AI processing with Claude via Bedrock
- **Strands_SDK**: The official `strands-agents` Python package providing `Agent`, `BedrockModel`, and `MCPClient` classes for AI agent orchestration
- **MCPClient**: A `strands.tools.mcp.MCPClient` instance that connects to an MCP-compatible server (AgentCore Gateway) via Streamable HTTP transport for tool discovery and execution
- **BedrockModel**: A `strands.models.bedrock.BedrockModel` instance that wraps Bedrock's Converse/ConverseStream API for model invocation
- **Strands_Agent**: A `strands.Agent` instance that combines a model and tool sources to run an autonomous agentic loop (reason → select tool → execute → repeat)
- **Gateway_URL**: The MCP endpoint URL of the AgentCore Gateway, retrieved via `get_gateway` API call
- **Factory_Function**: A module-level function that creates and returns a configured SDK object (e.g., `create_mcp_client`, `create_agent`)
- **Agent_Processor**: The orchestrator class that wires together MCPClient, Strands Agent, and session management for each request
- **Lambda_Package**: The deployment ZIP artifact containing application code and all pip dependencies, uploaded to S3 for Lambda deployment
- **CloudFormation_Template**: The `infrastructure/cloudformation-template.yaml` file defining all AWS resources for the system

## Requirements

### Requirement 1: Replace Manual Bedrock Invocation with Strands BedrockModel

**User Story:** As a developer, I want the Agent Lambda to use the official Strands SDK's BedrockModel instead of raw `boto3 bedrock-runtime invoke_model` calls, so that the SDK manages the Converse API, streaming, retries, and response parsing automatically.

#### Acceptance Criteria

1. THE Factory_Function `create_agent` SHALL accept `model_id`, `region`, `mcp_client`, and an optional `system_prompt` parameter and return a configured Strands_Agent instance
2. THE Factory_Function `create_agent` SHALL instantiate a BedrockModel with the provided `model_id`, `region_name`, and `max_tokens` of 4096
3. THE Factory_Function `create_agent` SHALL instantiate a Strands_Agent with the BedrockModel, the MCPClient as a tool source, and the system prompt
4. WHEN the Strands_Agent is invoked with a user prompt, THE Strands_SDK SHALL handle the complete agentic loop including model invocation, tool selection, tool execution, and response generation without manual orchestration code
5. WHEN the migration is complete, THE Agent_Lambda SHALL contain zero direct calls to `boto3 bedrock-runtime invoke_model` or `invoke_model_with_response_stream`

### Requirement 2: Replace Manual Tool Discovery and Invocation with MCPClient

**User Story:** As a developer, I want the Agent Lambda to use the Strands SDK's MCPClient with Streamable HTTP transport instead of manual `list_gateway_targets`/`get_gateway_target` API calls and hand-crafted JSON-RPC HTTP requests, so that tool discovery and execution are handled by the SDK via the MCP protocol.

#### Acceptance Criteria

1. THE Factory_Function `create_mcp_client` SHALL accept a `gateway_url` and `jwt_token` parameter and return a configured MCPClient instance
2. THE Factory_Function `create_mcp_client` SHALL use `mcp.client.streamable_http.streamablehttp_client` as the transport, passing the Gateway_URL and an `Authorization: Bearer {jwt_token}` header
3. WHEN the Strands_Agent loads tools, THE MCPClient SHALL discover available tools from the AgentCore Gateway via the MCP protocol without manual `list_gateway_targets` or `get_gateway_target` API calls
4. WHEN the Strands_Agent selects a tool during the agentic loop, THE MCPClient SHALL execute the tool through the AgentCore Gateway via the MCP protocol without manual JSON-RPC HTTP requests
5. WHEN the migration is complete, THE Agent_Lambda SHALL contain zero manual tool discovery code (no `list_gateway_targets`, `get_gateway_target`, or tool schema conversion logic)
6. WHEN the migration is complete, THE Agent_Lambda SHALL contain zero manual tool invocation code (no `requests.post` to Gateway MCP endpoint or JSON-RPC 2.0 request construction)

### Requirement 3: MCPClient Lifecycle Management

**User Story:** As a developer, I want the MCPClient lifecycle to be managed correctly within the Lambda invocation, so that the MCP session is started by the SDK's `load_tools()` and cleaned up reliably after each request.

#### Acceptance Criteria

1. THE Agent_Processor SHALL create a new MCPClient instance for each Lambda invocation (per-request lifecycle)
2. THE Agent_Processor SHALL pass the MCPClient to the Strands_Agent constructor, allowing the Agent's `load_tools()` to call `start()` internally
3. THE Agent_Processor SHALL NOT use a `with mcp_client:` context manager pattern to avoid double-starting the MCP session
4. THE Agent_Processor SHALL call `mcp_client.stop(None, None, None)` in a `finally` block after the Strands_Agent completes processing
5. IF the `mcp_client.stop()` call raises an exception, THEN THE Agent_Processor SHALL catch and suppress the exception to avoid masking the original result or error

### Requirement 4: Simplify Agent Processor Architecture

**User Story:** As a developer, I want the Agent Processor to be simplified by removing the manual agentic loop, GatewayClient, and MemoryClient dependencies, so that the codebase is smaller and easier to maintain.

#### Acceptance Criteria

1. THE Agent_Processor SHALL use the Strands_Agent's `__call__` method (i.e., `agent(prompt)`) to process user prompts, replacing the manual multi-step pipeline
2. THE Agent_Processor SHALL retrieve the Gateway_URL via `boto3 bedrock-agentcore-control get_gateway` API and cache the result for subsequent invocations within the same Lambda container
3. WHEN the migration is complete, THE Agent_Lambda source directory SHALL NOT contain a `gateway_client.py` module
4. WHEN the migration is complete, THE Agent_Lambda source directory SHALL NOT contain a `memory_client.py` module
5. THE Agent_Processor SHALL convert the Strands_Agent result to a string using `str(result)` for the Lambda response

### Requirement 5: Update Python Dependencies

**User Story:** As a developer, I want the agent's Python dependencies updated to include the Strands SDK and MCP client packages, so that the new SDK-based code can import and use them at runtime.

#### Acceptance Criteria

1. THE `agent-requirements.txt` file SHALL include `strands-agents>=1.0.0` as a dependency
2. THE `agent-requirements.txt` file SHALL include `mcp>=1.0.0` as a dependency
3. THE `agent-requirements.txt` file SHALL retain `boto3`, `PyJWT`, and `cryptography` as dependencies
4. THE `agent-requirements.txt` file SHALL remove the `requests` dependency (no longer needed after removing manual HTTP tool invocation)

### Requirement 6: Update Lambda IAM Permissions

**User Story:** As a developer, I want the Agent Lambda's IAM role updated with the permissions required by the Strands SDK's BedrockModel, so that the SDK can call the Bedrock Converse and ConverseStream APIs without `AccessDeniedException`.

#### Acceptance Criteria

1. THE CloudFormation_Template SHALL grant the Agent_Lambda IAM role the `bedrock:Converse` action
2. THE CloudFormation_Template SHALL grant the Agent_Lambda IAM role the `bedrock:ConverseStream` action
3. THE CloudFormation_Template SHALL retain the existing `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream` actions on the Agent_Lambda IAM role
4. THE CloudFormation_Template SHALL scope all Bedrock model permissions to the inference profile resource ARN `arn:{Partition}:bedrock:{Region}:{AccountId}:inference-profile/us.anthropic.claude-sonnet-4-6`

### Requirement 7: Update Lambda Resource Configuration

**User Story:** As a developer, I want the Agent Lambda's timeout and memory increased to accommodate the Strands SDK's multi-turn agentic loop, so that the Lambda does not time out or run out of memory during complex tool-using conversations.

#### Acceptance Criteria

1. THE CloudFormation_Template SHALL set the Agent_Lambda timeout to 120 seconds
2. THE CloudFormation_Template SHALL set the Agent_Lambda memory to 1024 MB
3. THE CloudFormation_Template SHALL update the Agent_Lambda duration alarm threshold to 100000 milliseconds (reflecting the increased timeout)

### Requirement 8: Lambda Packaging Rules

**User Story:** As a developer, I want the Lambda packaging process to follow platform-specific rules and preserve metadata directories, so that the deployment artifact works correctly on the Lambda x86_64 Python 3.12 runtime.

#### Acceptance Criteria

1. THE Lambda_Package build process SHALL use `--python-version 3.12` and `--platform manylinux2014_x86_64` and `--only-binary=:all:` flags when installing pip dependencies
2. THE Lambda_Package build process SHALL NOT remove `.dist-info` directories from the installed dependencies (required by opentelemetry's `importlib.metadata.entry_points()` discovery)
3. THE Lambda_Package build process SHALL remove `.egg-info` directories from the installed dependencies
4. WHEN the Lambda_Package ZIP exceeds 50 MB, THE deployment process SHALL upload the ZIP to S3 and update the Lambda code from the S3 location

### Requirement 9: Remove Obsolete Code

**User Story:** As a developer, I want all obsolete manual framework code removed after migration, so that the codebase contains only the SDK-based implementation without dead code.

#### Acceptance Criteria

1. WHEN the migration is complete, THE `strands_client.py` module SHALL contain only the Factory_Functions (`create_mcp_client` and `create_agent`) and the system prompt constant, with zero manual Bedrock API calls
2. WHEN the migration is complete, THE `agent_processor.py` module SHALL contain only the simplified Agent_Processor class that uses Factory_Functions and the Strands_Agent's `__call__` method
3. WHEN the migration is complete, THE `handler.py` module SHALL retain JWT validation, request parsing, and response formatting logic without changes to the authentication flow
4. WHEN the migration is complete, THE CloudFormation_Template SHALL remove the `MEMORY_ID` environment variable from the Agent_Lambda configuration
5. WHEN the migration is complete, THE CloudFormation_Template SHALL remove the `bedrock-agentcore:ListGatewayTargets` and `bedrock-agentcore:GetGatewayTarget` IAM actions from the Agent_Lambda role (tool discovery is now handled by MCPClient via the Gateway MCP endpoint, not the control plane API)
