# Implementation Plan: Strands SDK Migration

## Overview

Migrate the Agent Lambda from a custom manual Bedrock/Gateway implementation to the official `strands-agents` SDK. This involves rewriting `strands_client.py` as factory functions, simplifying `agent_processor.py` to use the SDK's agentic loop, updating `handler.py` to remove memory references, deleting obsolete modules, updating CloudFormation IAM/resource config, and updating dependencies. All changes are scoped to the Agent Lambda — Gateway, Interceptor, Tool Lambda, and Cognito are untouched.

## Tasks

- [x] 1. Update dependencies and rewrite strands_client.py with SDK factory functions
  - [x] 1.1 Update `agent-requirements.txt`: add `strands-agents>=1.0.0` and `mcp>=1.0.0`, remove `requests`, keep `boto3`, `PyJWT`, `cryptography`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 1.2 Rewrite `src/agent/strands_client.py` with factory functions and system prompt constant
    - Replace the `StrandsAgent` class with two factory functions: `create_mcp_client(gateway_url, jwt_token)` and `create_agent(model_id, region, mcp_client, system_prompt=None)`
    - Define `SYSTEM_PROMPT` constant at module level
    - `create_mcp_client` must use `MCPClient` with `streamablehttp_client` transport, passing the gateway URL and `Authorization: Bearer {jwt_token}` header
    - `create_agent` must instantiate `BedrockModel` with `model_id`, `region_name`, and `max_tokens=4096`, then return `Agent(model=bedrock_model, tools=[mcp_client], system_prompt=system_prompt or SYSTEM_PROMPT)`
    - Remove all manual `boto3 bedrock-runtime invoke_model` calls, `format_messages`, `extract_tool_use`, `extract_text_response`, `format_tool_result` methods
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 2.1, 2.2, 2.5, 2.6, 9.1_

  - [x]* 1.3 Write property test for `create_agent` factory wiring (Property 1)
    - **Property 1: Agent factory wiring**
    - Use Hypothesis to verify that for any valid `model_id`, `region`, mock `MCPClient`, and optional `system_prompt`, `create_agent` returns an `Agent` with correctly configured `BedrockModel` (model_id, region_name, max_tokens=4096), the MCPClient in tool sources, and the correct system prompt (provided value or SYSTEM_PROMPT default)
    - **Validates: Requirements 1.1, 1.2, 1.3**

  - [x]* 1.4 Write property test for `create_mcp_client` transport configuration (Property 2)
    - **Property 2: MCPClient factory transport configuration**
    - Use Hypothesis to verify that for any `gateway_url` and `jwt_token`, `create_mcp_client` returns an `MCPClient` configured with `streamablehttp_client` transport using the given URL and `Authorization: Bearer {jwt_token}` header
    - **Validates: Requirements 2.1, 2.2**

- [x] 2. Rewrite agent_processor.py with simplified SDK-based orchestration
  - [x] 2.1 Rewrite `src/agent/agent_processor.py` with simplified `AgentProcessor` class
    - Remove imports of `StrandsAgent`, `GatewayClient`, `MemoryClient`
    - Import `create_mcp_client` and `create_agent` from `strands_client`
    - Constructor takes `gateway_id`, `model_id`, `region`, `logger` (no `memory_id`)
    - Add `_gateway_url` cache attribute (initially `None`), populated by `_get_gateway_url()` using `boto3 bedrock-agentcore-control get_gateway` API
    - `process()` method: generate session_id if not provided (using `uuid.uuid4()`), call `_get_gateway_url()`, create MCPClient via `create_mcp_client(gateway_url, jwt_token)`, create Agent via `create_agent(model_id, region, mcp_client)`, call `agent(prompt)`, return `(str(result), session_id)`
    - MCPClient cleanup: call `mcp_client.stop(None, None, None)` in a `finally` block; wrap `stop()` in its own `try/except` to suppress cleanup errors
    - Do NOT use `with mcp_client:` context manager pattern
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.5_

  - [x]* 2.2 Write property test for per-request MCPClient lifecycle (Property 3)
    - **Property 3: Per-request MCPClient lifecycle**
    - Use Hypothesis to verify that for any sequence of `process()` calls with different JWT tokens, each call creates a new `MCPClient` instance (never reuses a previous client)
    - **Validates: Requirements 3.1**

  - [x]* 2.3 Write property test for MCPClient cleanup on all paths (Property 4)
    - **Property 4: MCPClient cleanup on all paths**
    - Use Hypothesis to verify that whether the agent succeeds or raises, `mcp_client.stop(None, None, None)` is called exactly once, and if `stop()` itself raises, the original result/error is preserved
    - **Validates: Requirements 3.4, 3.5**

  - [x]* 2.4 Write property test for agent invocation and result conversion (Property 5)
    - **Property 5: Agent invocation and result conversion**
    - Use Hypothesis to verify that for any prompt string and mock agent result, `process()` invokes `agent(prompt)` and returns `str(result)` as the response text
    - **Validates: Requirements 4.1, 4.5**

  - [x]* 2.5 Write property test for Gateway URL caching (Property 6)
    - **Property 6: Gateway URL caching**
    - Use Hypothesis to verify that calling `process()` N times (N ≥ 1) on the same `AgentProcessor` results in exactly one `get_gateway` API call
    - **Validates: Requirements 4.2**

- [x] 3. Checkpoint - Verify core SDK migration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Update handler.py and delete obsolete modules
  - [x] 4.1 Update `src/agent/handler.py` to remove memory references
    - Remove `MEMORY_ID = os.environ.get('MEMORY_ID', '')` line
    - Update `AgentProcessor` constructor call in `process_agent_request()`: remove `memory_id=MEMORY_ID` parameter
    - Update the docstring for `process_agent_request()` to remove references to memory storage and conversation context retrieval
    - All JWT validation, request parsing, response formatting, and error handling remain unchanged
    - _Requirements: 9.3_

  - [x] 4.2 Delete `src/agent/gateway_client.py`
    - _Requirements: 4.3, 9.1_

  - [x] 4.3 Delete `src/agent/memory_client.py`
    - _Requirements: 4.4, 9.2_

  - [x]* 4.4 Write unit tests for migration completeness checks
    - Verify `gateway_client.py` and `memory_client.py` do not exist in `src/agent/`
    - Verify `src/agent/handler.py` does not reference `MEMORY_ID`
    - Verify no agent source files contain `invoke_model`, `list_gateway_targets`, `get_gateway_target`, `requests.post`, or JSON-RPC construction patterns
    - Verify `agent-requirements.txt` contains `strands-agents>=1.0.0` and `mcp>=1.0.0`, retains `boto3`/`PyJWT`/`cryptography`, and does not contain `requests`
    - _Requirements: 1.5, 2.3, 2.4, 2.5, 2.6, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 9.1, 9.2, 9.3_

- [x] 5. Update CloudFormation template
  - [x] 5.1 Update Agent Lambda IAM role in `infrastructure/cloudformation-template.yaml`
    - Add `bedrock:Converse` and `bedrock:ConverseStream` actions to the Bedrock model permissions statement (same resource ARN scope)
    - Retain existing `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream` actions
    - Remove `bedrock-agentcore:ListGatewayTargets` and `bedrock-agentcore:GetGatewayTarget` from the AgentCore permissions statement (keep `bedrock-agentcore:GetGateway`)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 9.5_

  - [x] 5.2 Update Agent Lambda resource configuration in `infrastructure/cloudformation-template.yaml`
    - Change `Timeout` from 30 to 120
    - Change `MemorySize` from 512 to 1024
    - Remove `MEMORY_ID` environment variable (note: it's not currently in the template, but verify it stays absent)
    - _Requirements: 7.1, 7.2, 9.4_

  - [x] 5.3 Update Agent Lambda duration alarm threshold in `infrastructure/cloudformation-template.yaml`
    - Change `AgentLambdaDurationAlarm` threshold from 25000 to 100000
    - _Requirements: 7.3_

  - [x]* 5.4 Write unit tests for CloudFormation changes
    - Parse the YAML template and verify: IAM actions include `bedrock:Converse` and `bedrock:ConverseStream`; IAM actions do NOT include `bedrock-agentcore:ListGatewayTargets` or `bedrock-agentcore:GetGatewayTarget`; IAM actions retain `bedrock-agentcore:GetGateway`; Agent Lambda timeout is 120; Agent Lambda memory is 1024; duration alarm threshold is 100000; no `MEMORY_ID` in environment variables
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 9.4, 9.5_

- [x] 6. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The design uses Python, so all code examples and implementations use Python 3.12
- Property tests use Hypothesis with `max_examples=100` and mock SDK dependencies
- All tests go in `tests/` directory: `test_strands_client.py`, `test_agent_processor.py`, `test_migration_checks.py`
- Cognito, AgentCore Gateway, Gateway Targets, Interceptor Lambda, and Tool Lambda are NOT modified
- Memory is intentionally not implemented — the agent operates statelessly
