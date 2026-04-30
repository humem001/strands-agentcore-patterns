# Implementation Plan: strands-agentcore-mcp

## Overview

This plan converts the design into sequenced coding tasks for a Python 3.12 serverless AI agent that uses AWS Bedrock AgentCore Gateway with an MCP target. Each task references specific requirements (from `requirements.md`) and, where applicable, a correctness property (from the Correctness Properties section of `design.md`).

Foundational pieces come first (project scaffolding, reused modules), then the MCP server Lambda, then the CloudFormation template, then the deploy script, and finally the full test pyramid (property-based, unit, template assertions, deploy-script lints, integration, smoke). Integration is the last concern so that all earlier pieces can be exercised in isolation.

Conventions honored throughout (see `.kiro/steering/project-conventions.md`):

- Two-step `pip3 install` for Lambda packaging (`--only-binary=:all:` first, then `--no-deps` pure-Python)
- CloudFormation casing (`CustomJWTAuthorizer`, `RoleArn`, `AllowedAudience`, `CredentialProviderConfigurations` as array, `DiscoveryUrl` ending in `/.well-known/openid-configuration`)
- `$$`-based PID temp files (not `mktemp` suffix templates)
- Case-insensitive `DOES_NOT_EXIST` matching for stack create-vs-update
- `pip3` only, never `pip`
- `src/` prefix preserved inside Lambda zips
- `.dist-info` directories retained
- `us-east-1` region, Claude 3 Sonnet model

## Tasks

- [x] 1. Scaffold project structure and dependencies
  - Create the directory tree: `infrastructure/`, `scripts/`, `src/agent/`, `src/mcp_server/`, `src/shared/`, `tests/unit/`, `tests/property/`, `tests/integration/`
  - Add empty `__init__.py` files under `src/`, `src/agent/`, `src/mcp_server/`, `src/shared/`, `tests/`, `tests/unit/`, `tests/property/`, `tests/integration/`
  - Create `requirements.txt` pinning `strands-agents>=1.0.0`, `mcp>=1.0.0`, `requests>=2.31.0`, `PyJWT[crypto]>=2.8.0`, `boto3`, `jsonschema`
  - Create `requirements-dev.txt` pinning `pytest`, `hypothesis`, `moto[dynamodb]`, `pyyaml` (for template assertion tests), `cfn-lint` (optional, for local template sanity)
  - Create a top-level `README.md` stub pointing at `deploy.sh` and `test.sh`
  - _Requirements: 11.4_

- [x] 2. Copy reused agent and shared modules from strands-agentcore-smithy
  - [x] 2.1 Copy `src/shared/` modules verbatim
    - Copy `models.py`, `jwt_utils.py`, `error_utils.py`, `logging_utils.py` from the prior project without modification
    - Confirm `jwt_utils.py` still accepts `token_use ∈ {access, id}`, passes `verify_aud=False`, and reads `cognito:username`
    - _Requirements: 1.3, 1.4, 1.5, 1.6, 2.9, 14.1_

  - [x] 2.2 Copy `src/agent/` modules verbatim
    - Copy `handler.py`, `agent_processor.py`, `strands_client.py` from the prior project without modification (other than the SYSTEM_PROMPT update in the next sub-task)
    - Confirm handler path resolves as `src.agent.handler.lambda_handler`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.9_

  - [x] 2.3 Update `SYSTEM_PROMPT` in `src/agent/agent_processor.py`
    - Replace the prior project's Bedrock-Runtime-Converse wording with the MCP product-tool wording from the design (mentions `list_products`, `get_product`, `put_product` and instructs conversational responses)
    - This is the ONLY change allowed in `src/agent/`
    - _Requirements: 2.7, 2.9_

- [x] 3. Implement the MCP Server Lambda — DynamoDB client
  - [x] 3.1 Implement `src/mcp_server/dynamodb_client.py`
    - Create a module-level `TABLE` via `boto3.resource('dynamodb').Table(os.environ['PRODUCT_TABLE'])`
    - Implement `list_products(category: str | None)` — `Query` with `KeyConditionExpression` when `category` is provided, else `Scan`; return the `Items` list
    - Implement `get_product(category, productId)` — `GetItem`; return `{"found": False}` when the item is missing, else `{"found": True, "item": <item>}`
    - Implement `put_product(item: dict)` — `PutItem(Item=item)`; return `{"written": True, "item": item}`
    - Let `botocore`/`boto3` exceptions propagate (the handler maps them to `-32603`)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 10.1_

  - [ ]* 3.2 Write property test for `list_products` filtering correctness
    - **Property 8: list_products filtering correctness**
    - **Validates: Requirements 7.1**
    - Use `moto[dynamodb]` fixture to create a `Product_Table` with PK `category` (S) and SK `productId` (S)
    - Generate a list of product items with `hypothesis` (small category alphabet, UUID-shaped productId)
    - Assert: with no `category`, returned set equals all seeded items; with a `category`, returned set equals exactly items with matching `category`
    - `@settings(max_examples=100)` minimum
    - _Requirements: 7.1_

  - [ ]* 3.3 Write property test for put/get round-trip through DynamoDB
    - **Property 9: put/get round-trip**
    - **Validates: Requirements 7.2, 7.4, 7.7**
    - Use `moto[dynamodb]` fixture
    - Generate valid product items with `hypothesis` (`category`, `productId`, `name`, `price` non-negative `Decimal`)
    - Assert: `put_product(p)` followed by `get_product(p.category, p.productId)` returns `{"found": True, "item": p}`
    - `@settings(max_examples=100)` minimum
    - _Requirements: 7.2, 7.4, 7.7_

  - [ ]* 3.4 Write property test for `put_product` overwrite semantics
    - **Property 10: put_product overwrite**
    - **Validates: Requirements 7.5**
    - Use `moto[dynamodb]` fixture
    - Generate two product items `A` and `B` sharing `category` and `productId` but differing in `name`/`price`
    - Assert: `put_product(A)` then `put_product(B)` then `get_product(A.category, A.productId)` returns item equal to `B`
    - `@settings(max_examples=100)` minimum
    - _Requirements: 7.5_

- [x] 4. Implement the MCP Server Lambda — tool registry
  - [x] 4.1 Implement `src/mcp_server/tools.py`
    - Define a `Tool` dataclass / namedtuple with `name`, `description`, `input_schema`, `handler`
    - Declare `LIST_PRODUCTS`, `GET_PRODUCT`, `PUT_PRODUCT` with the exact JSON schemas from the design
    - Build a `TOOLS: dict[str, Tool]` registry keyed by tool name
    - Implement `list_tool_catalog()` returning `{"tools": [{"name": t.name, "description": t.description, "inputSchema": t.input_schema} for t in TOOLS.values()]}`
    - Implement `dispatch(name, arguments)`:
      - Raise `UnknownToolError` (→ `-32601`) if `name` not in `TOOLS`
      - Validate `arguments` against `tool.input_schema` using `jsonschema`; raise `InvalidParamsError` (→ `-32602`) on failure
      - Call `tool.handler(arguments)` and return `{"content": result}`
    - Define `UnknownToolError` and `InvalidParamsError` exception classes
    - _Requirements: 6.2, 6.3, 7.1, 7.2, 7.4, 7.6_

  - [ ]* 4.2 Write unit tests for the tool registry shape
    - Assert `list_tool_catalog()` returns exactly three tools named `list_products`, `get_product`, `put_product`
    - For each tool, assert `name`, `description`, `inputSchema` fields are present and `inputSchema.type == "object"`
    - Assert `get_product` and `put_product` declare their required fields
    - _Requirements: 6.2_

- [x] 5. Implement the MCP Server Lambda — handler
  - [x] 5.1 Implement `src/mcp_server/handler.py`
    - Define `json_rpc_response(id_, result=None, error=None)` returning the API Gateway response envelope: `statusCode=200`, `Content-Type: application/json`, JSON-RPC 2.0 body
    - Implement `lambda_handler(event, context)`:
      - Emit a structured log via `src.shared.logging_utils` with the JSON-RPC `method` and request id
      - Parse `event.get("body")` as JSON-RPC 2.0; on `json.JSONDecodeError` or missing `jsonrpc`/`method`, return `-32700`
      - Dispatch by `method`:
        - `tools/list` → call `tools.list_tool_catalog()`; return success
        - `tools/call` → call `tools.dispatch(params.name, params.arguments)`; catch `UnknownToolError` → `-32601`, `InvalidParamsError` → `-32602`, any other `Exception` → log and return `-32603`
        - other → `-32601`
    - Log the tool `name` on every `tools/call` request
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.6, 14.2, 14.3_

  - [ ]* 5.2 Write property test for registered tool-call dispatch
    - **Property 3: Registered tool-call dispatch**
    - **Validates: Requirements 6.1, 6.3**
    - Generate `tools/call` requests with `hypothesis` where `params.name` is one of the three registered tools and `params.arguments` satisfies the tool's `inputSchema`
    - Mock `dynamodb_client` so handlers return deterministic success values
    - Assert: response body is JSON-RPC 2.0 success with populated `result.content`; `statusCode == 200`
    - _Requirements: 6.1, 6.3_

  - [ ]* 5.3 Write property test for malformed JSON-RPC and unknown-method error codes
    - **Property 4: Malformed JSON-RPC request error codes**
    - **Validates: Requirements 6.4, 6.5**
    - Generator A: invalid bodies (empty string, `"null"`, non-JSON bytes, JSON missing `jsonrpc`, JSON with wrong `jsonrpc` version, array body, missing `method`) → expect `error.code == -32700`
    - Generator B: `tools/call` requests with `params.name` outside the registered set → expect `error.code == -32601`
    - Assert `statusCode == 200` in both cases
    - _Requirements: 6.4, 6.5_

  - [ ]* 5.4 Write property test for invalid tool arguments
    - **Property 5: Invalid tool arguments**
    - **Validates: Requirements 7.6**
    - For each registered tool, generate `params.arguments` that violate the tool's `inputSchema` (missing required field, wrong type, additional property)
    - Assert response is JSON-RPC error with `error.code == -32602`
    - _Requirements: 7.6_

  - [ ]* 5.5 Write property test for the HTTP envelope invariant
    - **Property 6: HTTP envelope invariant**
    - **Validates: Requirements 6.6**
    - Generate a diverse mix of inputs (valid requests, malformed bodies, unknown tools, invalid arguments, tool-handler exceptions via mocked `dynamodb_client` raising)
    - Assert: every response has `statusCode == 200` and `headers["Content-Type"] == "application/json"`, and the body is valid JSON that deserializes to a dict with `jsonrpc == "2.0"`
    - _Requirements: 6.6_

  - [ ]* 5.6 Write property test for JSON-RPC response round-trip
    - **Property 7: JSON-RPC response round-trip**
    - **Validates: Requirements 6.7**
    - Invoke `lambda_handler` across a `hypothesis`-generated mix of requests
    - For each response, assert `json.loads(response["body"]) == json.loads(json.dumps(json.loads(response["body"])))`
    - _Requirements: 6.7_

  - [ ]* 5.7 Write example unit tests for handler edge cases
    - Assert tool-handler exception (mock `dynamodb_client.get_product` to raise `ClientError`) produces `-32603` AND logs the exception
    - Assert CloudWatch log entry (captured via `caplog`) for every request includes the JSON-RPC `method`, and for `tools/call` includes the tool `name`
    - _Requirements: 14.2, 14.3_

- [x] 6. Checkpoint — MCP server Lambda tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Property tests for reused shared modules (JWT)
  - [ ]* 7.1 Set up JWT property-test infrastructure
    - Create `tests/property/conftest.py` with a session-scoped RSA keypair (`cryptography`)
    - Add a `mock_jwks` fixture that returns a JWKS document exposing the public key with a fixed `kid`
    - Add a `make_jwt(claims, *, key=..., kid=..., expired=False, bad_signature=False, alg="RS256")` helper using `PyJWT`
    - Patch `jwt_utils`'s JWKS fetch to return the mock JWKS (via `monkeypatch` or `unittest.mock`)
    - _Requirements: 1.3, 1.4, 1.6_

  - [ ]* 7.2 Write property test for JWT validation positive path
    - **Property 1: JWT validation positive path**
    - **Validates: Requirements 1.3, 1.4, 1.6**
    - Generate claim sets with `hypothesis` where `token_use ∈ {access, id}`, `exp` is in the future, and `cognito:username` is a non-empty string
    - Sign with the test RSA key
    - Assert: `jwt_utils.validate(token)` succeeds and the returned username equals the `cognito:username` claim
    - _Requirements: 1.3, 1.4, 1.6_

  - [ ]* 7.3 Write property test for JWT validation negative path
    - **Property 2: JWT validation negative path**
    - **Validates: Requirements 1.3, 1.4, 1.7**
    - Generate four failure categories: missing token, expired `exp`, signature signed by a different key, `token_use` outside `{access, id}`
    - Assert: `jwt_utils.validate(...)` raises an auth error (or `src.agent.handler.lambda_handler` returns an auth-error response)
    - Assert: no outbound call is made to AgentCore Gateway (monkeypatch `strands_client` MCP client constructor and assert it is never called)
    - _Requirements: 1.3, 1.4, 1.7_

- [x] 8. Author the CloudFormation template
  - [x] 8.1 Create `infrastructure/cloudformation-template.yaml` — identity and data layer
    - `AWSTemplateFormatVersion` and `Description`
    - Parameters: `GatewayName` (default `agentcore-mcp-gateway`), `CognitoUserPoolName`, `ProductTableName` (default `Product_Table`)
    - `CognitoUserPool` with standard username + password policy
    - `CognitoUserPoolClient` with `ExplicitAuthFlows: [ALLOW_USER_PASSWORD_AUTH, ALLOW_REFRESH_TOKEN_AUTH]`
    - `ProductTable` (`AWS::DynamoDB::Table`) — partition key `category` (S), sort key `productId` (S), `BillingMode: PAY_PER_REQUEST`
    - _Requirements: 1.1, 10.1, 10.2_

  - [x] 8.2 Add MCP Server Lambda role and function
    - `McpServerRole` — trusts `lambda.amazonaws.com`; inline policies: DynamoDB (`GetItem`, `PutItem`, `Query`, `Scan`) scoped to `!GetAtt ProductTable.Arn` ONLY; CloudWatch Logs (`CreateLogGroup`, `CreateLogStream`, `PutLogEvents`)
    - `McpServerLambda` — `Runtime: python3.12`, handler `src.mcp_server.handler.lambda_handler`, `Environment.Variables.PRODUCT_TABLE: !Ref ProductTable`, placeholder `Code.ZipFile` (deploy script replaces via `update-function-code`)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 11.4_

  - [x] 8.3 Add API Gateway REST API, resource, method, deployment, stage, and Lambda permission
    - `McpApi` (`AWS::ApiGateway::RestApi`, name `mcp-api`)
    - `McpResource` at path part `mcp` under the root
    - `McpMethod` — `HttpMethod: POST`, `AuthorizationType: AWS_IAM`, `Integration.Type: AWS_PROXY`, `IntegrationHttpMethod: POST`, `Uri` pointing at `McpServerLambda`
    - `McpDeployment` with `DependsOn: McpMethod`
    - `McpStage` with `StageName: prod`
    - `McpApiInvokePermission` (`AWS::Lambda::Permission`) — `Action: lambda:InvokeFunction`, `Principal: apigateway.amazonaws.com`, `SourceArn` scoped to `McpApi`'s `POST /mcp`
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 8.4 Add Gateway execution role, AgentCore Gateway, and MCP Target
    - `GatewayExecutionRole` — trusts `bedrock-agentcore.amazonaws.com`; inline policies:
      - `AgentCoreAccess` — `bedrock-agentcore:*` scoped to the four ARN patterns (`token-vault/default`, `token-vault/default/apikeycredentialprovider/*`, `workload-identity-directory/default`, `workload-identity-directory/default/workload-identity/${GatewayName}-*`)
      - `InvokeMcpApi` — `execute-api:Invoke` on `!Sub 'arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${McpApi}/*/*/*'`
      - NO wildcard `*` on `Resource`
    - `AgentCoreGateway` (`AWS::BedrockAgentCore::Gateway`) with `AuthorizerConfiguration.CustomJWTAuthorizer` (all-caps `JWT`), `DiscoveryUrl` ending in `/.well-known/openid-configuration`, `AllowedAudience` set to `!Ref CognitoUserPoolClient`, `RoleArn: !GetAtt GatewayExecutionRole.Arn` (NOT `ExecutionRoleArn`)
    - `McpTarget` (`AWS::BedrockAgentCore::GatewayTarget`) with `CredentialProviderConfigurations` as a single-element ARRAY of `{CredentialProviderType: GATEWAY_IAM_ROLE}`, `TargetConfiguration.Mcp.McpServer.EndpointUrl: !Sub 'https://${McpApi}.execute-api.${AWS::Region}.amazonaws.com/prod/mcp'`, `GatewayIdentifier: !Ref AgentCoreGateway`
    - Inline YAML comments calling out the casing traps from the conventions doc
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 12.1, 12.2, 12.3, 12.4, 12.5_

  - [x] 8.5 Add Agent Lambda role and function
    - `AgentLambdaRole` — trusts `lambda.amazonaws.com`; inline policies: `bedrock:InvokeModel` on the Claude 3 Sonnet model ARN; `bedrock-agentcore:InvokeGateway` on `!GetAtt AgentCoreGateway.GatewayArn` (or equivalent); CloudWatch Logs
    - `AgentLambdaFunction` — `Runtime: python3.12`, handler `src.agent.handler.lambda_handler`, environment vars for gateway URL, Cognito user pool id, Cognito client id; placeholder `Code.ZipFile`
    - Stack `Outputs`: `AgentLambdaName`, `CognitoUserPoolId`, `CognitoClientId`, `McpApiInvokeUrl`, `GatewayUrl`, `ProductTableName`
    - _Requirements: 2.1, 11.4, 14.1_

  - [ ]* 8.6 Write CloudFormation template assertion tests (`tests/unit/test_template.py`)
    - Load the template with `pyyaml` (use `yaml.SafeLoader` with a CloudFormation tag constructor for `!Ref`, `!Sub`, `!GetAtt`, etc.)
    - Assert `AuthorizerConfiguration.CustomJWTAuthorizer` exists (all caps `JWT`); `CustomJwtAuthorizer` does NOT appear anywhere
    - Assert `RoleArn` present on `AgentCoreGateway`; `ExecutionRoleArn` absent
    - Assert `AllowedAudience` present under `CustomJWTAuthorizer`; `Audience` absent
    - Assert `CredentialProviderConfigurations` on `McpTarget` is a list containing `{CredentialProviderType: GATEWAY_IAM_ROLE}`
    - Assert `DiscoveryUrl` endswith `/.well-known/openid-configuration`
    - Assert `GatewayExecutionRole` policy statements contain the four AgentCore ARN patterns plus `execute-api:Invoke`, and no statement has `Resource: "*"`
    - Assert `McpServerRole` DynamoDB resource equals `{"Fn::GetAtt": ["ProductTable", "Arn"]}` only (no other DynamoDB resources)
    - Assert `ProductTable.BillingMode == PAY_PER_REQUEST` and keys are `category` (S) + `productId` (S)
    - Assert `McpMethod` uses `AWS_PROXY` integration pointing at `McpServerLambda`
    - Assert `McpStage.StageName == prod`
    - Assert Lambda handler paths are `src.agent.handler.lambda_handler` and `src.mcp_server.handler.lambda_handler`
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 5.2, 5.3, 5.4, 8.1, 8.2, 9.2, 9.4, 10.1, 10.2, 11.4, 12.1, 12.2, 12.3, 12.4, 12.5_

- [x] 9. Implement the deploy script
  - [x] 9.1 Create `scripts/deploy.sh` skeleton with validation-first behavior
    - `#!/usr/bin/env bash`, `set -euo pipefail`
    - Region `us-east-1`, stack name `agentcore-mcp`
    - PID-based temp files using `$$` (e.g. `TMP_AGENT_ZIP="/tmp/agentcore-mcp.$$.agent.zip"`); register a `trap` to clean them up on exit
    - Step 1: `aws cloudformation validate-template --template-body file://infrastructure/cloudformation-template.yaml --region us-east-1` — runs BEFORE any other AWS CLI call
    - _Requirements: 13.1, 13.5_

  - [x] 9.2 Implement Lambda packaging function (two-step pip3 install, reused for both Lambdas)
    - Define a `package_lambda()` shell function taking a build dir and an output zip path
    - Step 1: `pip3 install --target "$DIR" --platform manylinux2014_x86_64 --python-version 3.12 --only-binary=:all: -r requirements.txt`
    - Step 2: `pip3 install --target "$DIR" --platform manylinux2014_x86_64 --python-version 3.12 --only-binary=:all: --no-deps requests urllib3 charset-normalizer idna certifi PyJWT cryptography cffi mcp`
    - Copy `src/` into `$DIR/src/` so the zip preserves the `src/` prefix
    - `cd "$DIR" && zip -qr "$OUT_ZIP" .` — never delete `.dist-info` directories
    - Call `package_lambda` twice to produce an Agent Lambda zip and an MCP Server Lambda zip (can share the same build dir content since both need `src/` tree; use separate zips if scoping differs)
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 13.4_

  - [x] 9.3 Implement stack create-vs-update decision logic
    - Call `aws cloudformation describe-stacks --stack-name agentcore-mcp --region us-east-1` capturing both stdout and stderr
    - Match `DOES_NOT_EXIST` with `grep -i` (case-insensitive) to decide create vs update
    - If `StackStatus == ROLLBACK_COMPLETE`: `aws cloudformation delete-stack` + `aws cloudformation wait stack-delete-complete`, then treat as create
    - Create: `aws cloudformation create-stack ... --capabilities CAPABILITY_IAM` + `aws cloudformation wait stack-create-complete`
    - Update: `aws cloudformation update-stack ...` + `aws cloudformation wait stack-update-complete`; tolerate `No updates are to be performed` by inspecting stderr
    - _Requirements: 13.2, 13.3_

  - [x] 9.4 Implement post-create Lambda code update with S3 fallback
    - Read stack outputs (`AgentLambdaName`, `McpApiInvokeUrl`, `CognitoUserPoolId`, `CognitoClientId`, `GatewayUrl`, `ProductTableName`) via `aws cloudformation describe-stacks --query 'Stacks[0].Outputs'`
    - If a zip is ≤ 50 MB: `aws lambda update-function-code --function-name <name> --zip-file fileb://<zip>`
    - If a zip is > 50 MB: upload to `s3://<bucket>/<key>` and use `--s3-bucket <bucket> --s3-key <key>` form (bucket name can be derived from account id + stack name; create if missing)
    - Run for both the Agent Lambda and the MCP Server Lambda (the stack must expose both function names in Outputs, or the script can derive them from a stable naming scheme)
    - _Requirements: 11.5_

  - [x] 9.5 Seed DynamoDB with sample products
    - Issue three `aws dynamodb put-item` calls against `Product_Table` covering at least two categories (`Electronics/ELEC-001`, `Electronics/ELEC-002`, `Books/BOOK-001`)
    - Each item includes `category`, `productId`, `name`, `price` matching the DynamoDB-attribute-value JSON format
    - _Requirements: 10.3_

  - [x] 9.6 Create the Cognito test user
    - `aws cognito-idp admin-create-user` with a known username, email, `MessageAction: SUPPRESS`
    - `aws cognito-idp admin-set-user-password` with `--permanent` to set a known password and confirm the user
    - _Requirements: 1.2_

  - [x] 9.7 Generate `scripts/test.sh` with baked-in literal values
    - Use a single `cat > scripts/test.sh <<'EOF' ... EOF` heredoc and perform literal substitution with `sed` afterwards (NOT nested `echo` emitting JSON)
    - Generated script must:
      - Bake in `USER_POOL_ID`, `CLIENT_ID`, `AGENT_LAMBDA_NAME`, `USERNAME`, `PASSWORD`, `DEFAULT_PROMPT="List all products."`
      - Accept `$1` as an optional prompt, falling back to the default
      - Obtain an ID token via `aws cognito-idp initiate-auth` with `AuthFlow: USER_PASSWORD_AUTH`
      - Invoke the Agent Lambda via `aws lambda invoke` with payload `{"jwt": "<id_token>", "prompt": "<prompt>"}`
      - Print the model's final answer
    - `chmod +x scripts/test.sh`
    - _Requirements: 13.6, 13.7_

  - [ ]* 9.8 Write deploy-script lint tests (`tests/unit/test_deploy_script.py`)
    - Read `scripts/deploy.sh` as text and grep-style assert:
      - Exactly two `pip3 install` invocations both with `--platform manylinux2014_x86_64` and `--python-version 3.12`; second invocation includes `--no-deps` and the nine pure-Python package names
      - No `rm -rf .*dist-info` patterns; no `find .*dist-info.*-delete` patterns
      - A case-insensitive `DOES_NOT_EXIST` match (e.g. `grep -i DOES_NOT_EXIST` appearing in the script)
      - `ROLLBACK_COMPLETE` handling: `aws cloudformation delete-stack` and `aws cloudformation wait stack-delete-complete` both present
      - No bare `pip ` tokens (only `pip3`); regex `\bpip\b(?!3)` must find nothing
      - `$$`-based temp paths (e.g. `/tmp/.*\.\$\$\.`) present; no `mktemp -t` suffix templates
      - `aws cloudformation validate-template` occurs before the first `aws cloudformation create-stack` / `update-stack` / `describe-stacks` call (string position check)
      - Generated test-script heredoc does NOT use nested `echo` emitting JSON
    - _Requirements: 11.1, 11.2, 11.3, 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

- [x] 10. Checkpoint — template and deploy-script lints pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Integration test harness
  - [x] 11.1 Create `tests/integration/test_end_to_end.py`
    - Reads stack outputs from `aws cloudformation describe-stacks` (skip with a clear message if the stack is not deployed)
    - Test A — happy path: authenticate the test user against Cognito, invoke the Agent Lambda with prompt `"List all products."`, assert the response is a non-empty string that references at least one seeded product name
    - Test B — unauthorized: issue a request without a JWT and assert a 401/403-shaped auth error is returned from the Agent Lambda (NO outbound call to the Gateway should be made; verified via CloudWatch Logs query or by return-payload shape)
    - Test C — MCP discovery: invoke a prompt that requires a `tools/call` (e.g. `"Get product ELEC-001 details"`) and verify via CloudWatch Logs Insights that both `tools/list` and at least one `tools/call` appear in the MCP Server Lambda's log stream during the invocation window
    - _Requirements: 1.2, 1.7, 2.2, 2.3, 2.5, 4.4, 8.4, 14.1, 14.2_

  - [ ]* 11.2 Add post-deploy smoke checks to `scripts/deploy.sh`
    - After a successful deploy, execute three quick checks and fail the script if any fail:
      - `aws cognito-idp admin-get-user` shows the test user with `UserStatus == CONFIRMED`
      - `aws dynamodb scan --table-name Product_Table --select COUNT` returns `Count >= 3` and the items span `>= 2` distinct categories (scan attributes and count unique `category` values)
      - A bare `curl -s -o /dev/null -w "%{http_code}" <McpApiInvokeUrl>` returns `403` (proves API Gateway is up and requires IAM auth)
    - _Requirements: 1.2, 8.1, 10.3_

- [x] 12. Final checkpoint — full test suite passes
  - Ensure all tests pass (property, unit, template-assertion, deploy-script lint, integration), ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional (testing and smoke-check tasks). Core implementation tasks are required.
- Property-based tests use `hypothesis` with `@settings(max_examples=100)` minimum, and each property test is tagged with its property number from the design.
- `moto[dynamodb]` provides the in-process DynamoDB stub for Properties 8, 9, 10 and for any unit tests touching `dynamodb_client`.
- The JWT property tests (Properties 1, 2) operate against `src/shared/jwt_utils.py` as copied in task 2.1 — they validate reused code without modifying it.
- CloudFormation template assertion tests (task 8.6) guard against casing regressions that have bitten this project before.
- Deploy-script lint tests (task 9.8) guard the conventions checklist mechanically.
- This workflow creates design and planning artifacts only. Once tasks.md is complete, begin executing tasks by opening tasks.md and clicking "Start task" next to task items.
