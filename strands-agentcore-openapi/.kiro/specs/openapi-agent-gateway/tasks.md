# Implementation Plan: OpenAPI Agent Gateway

## Overview

This implementation plan converts the OpenAPI Agent Gateway design into actionable coding tasks. The system extends the Strands Framework architecture to dynamically discover and invoke REST API operations from OpenAPI 3.x specifications. Implementation follows a bottom-up approach: infrastructure first, then shared utilities, core components, and finally integration and testing.

The implementation reuses proven components from strands-reference (strands_client.py, gateway_client.py, shared utilities) and builds new components for OpenAPI parsing, CloudFormation generation, and the mock Weather API.

## Tasks

- [x] 1. Set up project structure and infrastructure foundation
  - Create directory structure: src/{agent,interceptor,weather_api,shared,openapi_parser}, infrastructure/, tests/{unit,property,integration}, deployment/
  - Create CloudFormation template with Cognito User Pool, AgentCore Gateway with CUSTOM_JWT authorizer, IAM roles, CloudWatch log groups
  - Configure Gateway with GatewayInterceptorConfiguration for REQUEST interception point
  - Add stack outputs: GatewayId, CognitoUserPoolId, CognitoClientId, AgentLambdaArn, InterceptorLambdaArn, WeatherAPILambdaArn
  - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.8, 1.9, 1.10_

- [ ] 2. Implement shared utilities and data models
  - [x] 2.1 Copy and adapt shared utilities from strands-reference
    - Copy src/shared/models.py, logging_utils.py, error_utils.py, jwt_utils.py from strands-reference
    - Add UserContext, AgentRequest, AgentResponse, ToolDefinition, WeatherData, ForecastData dataclasses to models.py
    - Adapt logging_utils.py to include request_id correlation in all log messages
    - Adapt error_utils.py to return appropriate HTTP status codes (400, 401, 500)
    - _Requirements: 6.4, 6.5, 6.6, 8.9, 8.10_
  
  - [ ]* 2.2 Write property test for UserContext extraction
    - **Property 7: JWT User Context Extraction**
    - **Validates: Requirements 6.3, 6.4, 6.5, 6.6**
  
  - [ ]* 2.3 Write unit tests for shared utilities
    - Test logging_utils request_id correlation
    - Test error_utils HTTP status code mapping
    - Test jwt_utils JWT decoding and validation
    - _Requirements: 8.9, 8.10_

- [ ] 3. Implement OpenAPI parser module
  - [x] 3.1 Create OpenAPI parser with specification validation
    - Implement parse_openapi_spec(spec_dict) to validate OpenAPI 3.0.x and 3.1.x versions
    - Implement extract_operation_tool(path, method, operation) to convert operations to ToolDefinition
    - Extract operationId or generate from method + path for tool name
    - Extract summary for tool description
    - Convert parameters and requestBody to input_schema using convert_to_json_schema()
    - Convert responses to output_schema using convert_to_json_schema()
    - Preserve security requirements in tool metadata
    - Return descriptive validation errors for invalid specifications
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9_
  
  - [ ]* 3.2 Write property test for operation extraction completeness
    - **Property 1: OpenAPI Operation Extraction Completeness**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**
  
  - [ ]* 3.3 Write property test for tool name uniqueness
    - **Property 2: OpenAPI Tool Name Uniqueness**
    - **Validates: Requirements 2.6**
  
  - [ ]* 3.4 Write property test for security preservation
    - **Property 3: OpenAPI Security Preservation**
    - **Validates: Requirements 2.7**
  
  - [ ]* 3.5 Write property test for parsing error handling
    - **Property 4: OpenAPI Parsing Error Handling**
    - **Validates: Requirements 2.8**
  
  - [ ]* 3.6 Write property test for round-trip consistency
    - **Property 5: OpenAPI Parsing Round-Trip**
    - **Validates: Requirements 2.10**
  
  - [ ]* 3.7 Write unit tests for OpenAPI parser edge cases
    - Test minimal valid OpenAPI spec
    - Test spec with no operations
    - Test operation with no parameters, requestBody, or responses
    - Test missing operationId (generate from method + path)
    - _Requirements: 2.1, 2.6, 2.8_

- [ ] 4. Implement CloudFormation Gateway Target generator
  - [x] 4.1 Create CloudFormation resource generator
    - Implement generate_gateway_targets(openapi_spec, gateway_id, lambda_arn) to create Gateway Target resources
    - For each operation, create AWS::BedrockAgentCore::GatewayTarget resource
    - Configure Lambda target with ToolSchema InlinePayload containing name, description, input_schema, output_schema
    - Use three-underscore naming format: {TargetName}___{ToolName}
    - Return list of CloudFormation resource definitions
    - _Requirements: 1.3, 4.5, 9.5, 9.7_
  
  - [ ]* 4.2 Write property test for Gateway Target generation completeness
    - **Property 6: Gateway Target Generation Completeness**
    - **Validates: Requirements 1.3, 9.5**
  
  - [ ]* 4.3 Write unit tests for CloudFormation generator
    - Test generation with single operation
    - Test generation with multiple operations
    - Test three-underscore naming format
    - Test complete tool schema structure
    - _Requirements: 1.3, 4.5, 9.7_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement Mock Weather API Lambda
  - [x] 6.1 Create Weather API OpenAPI specification
    - Write openapi_spec.yaml with OpenAPI 3.0.3 version
    - Define getCurrentWeather operation: GET /weather with location parameter
    - Define getForecast operation: GET /forecast with location and days parameters
    - Include user_context in request schemas for both operations
    - Define response schemas matching WeatherData and ForecastData models
    - Include security requirements for JWT authentication
    - _Requirements: 7.2, 7.3, 7.9_
  
  - [x] 6.2 Implement Weather API Lambda handler
    - Implement lambda_handler(event, context) to route requests to getCurrentWeather or getForecast
    - Implement getCurrentWeather(location, user_context) to validate user_context and return mock weather data
    - Implement getForecast(location, days, user_context) to validate user_context and return mock forecast data
    - Return 400 status with error message when user_context is missing
    - Log user_id from user_context for audit trail
    - Return responses matching OpenAPI specification schemas
    - _Requirements: 7.4, 7.5, 7.6, 7.7, 7.8, 7.9_
  
  - [ ]* 6.3 Write property test for Weather API response schema compliance
    - **Property 15: Weather API Response Schema Compliance**
    - **Validates: Requirements 7.4, 7.5, 7.9**
  
  - [ ]* 6.4 Write property test for user context validation
    - **Property 16: User Context Validation**
    - **Validates: Requirements 7.6**
  
  - [ ]* 6.5 Write unit tests for Weather API
    - Test getCurrentWeather with valid location
    - Test getForecast with valid location and days
    - Test rejection when user_context is missing
    - Test response schema compliance
    - _Requirements: 7.4, 7.5, 7.6, 7.9_

- [ ] 7. Implement Interceptor Lambda
  - [x] 7.1 Copy and adapt Interceptor Lambda from strands-reference
    - Copy src/interceptor/handler.py from strands-reference
    - Implement lambda_handler(event, context) to extract JWT from gatewayRequest headers
    - Decode JWT payload without verification (Gateway already validated)
    - Extract user_id from 'sub' claim, username from 'username' claim, client_id from 'client_id' claim
    - Inject user_context into tool arguments in transformedGatewayRequest
    - Return original request unchanged if extraction fails (graceful degradation)
    - Log original and transformed requests with request_id for correlation
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 8.3_
  
  - [ ]* 7.2 Write property test for user context injection
    - **Property 8: User Context Injection**
    - **Validates: Requirements 6.7, 6.8**
  
  - [ ]* 7.3 Write property test for transformation logging
    - **Property 19: Interceptor Transformation Logging**
    - **Validates: Requirements 8.3**
  
  - [ ]* 7.4 Write unit tests for Interceptor Lambda
    - Test extraction from valid JWT
    - Test handling of JWT with missing claims
    - Test handling of request with no JWT
    - Test graceful degradation on extraction failure
    - _Requirements: 6.3, 6.4, 6.5, 6.6, 6.9_

- [ ] 8. Implement Gateway Client
  - [x] 8.1 Copy and adapt Gateway Client from strands-reference
    - Copy src/agent/gateway_client.py from strands-reference
    - Implement list_tools(jwt_token) to call list_gateway_targets() API
    - For each target, call get_gateway_target() to retrieve tool schema
    - Convert tool definitions to Claude format with three-underscore naming: {TargetName}___{ToolName}
    - Return list of Claude-compatible tool definitions
    - Implement invoke_tool(tool_name, tool_input, jwt_token) to get Gateway MCP endpoint via get_gateway()
    - Format JSON-RPC 2.0 request: {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": tool_name, "arguments": tool_input}, "id": request_id}
    - Send HTTPS POST to Gateway MCP endpoint with JWT in Authorization header
    - Return tool execution result
    - Retry up to 3 times with exponential backoff on transient errors
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.4, 5.9, 9.7_
  
  - [ ]* 8.2 Write property test for tool naming consistency
    - **Property 9: Tool Naming Consistency**
    - **Validates: Requirements 4.5, 5.4, 9.7**
  
  - [ ]* 8.3 Write property test for tool schema completeness
    - **Property 10: Gateway Tool Schema Completeness**
    - **Validates: Requirements 4.3, 4.10**
  
  - [ ]* 8.4 Write property test for Claude format conversion
    - **Property 11: Claude Tool Format Conversion**
    - **Validates: Requirements 4.4**
  
  - [ ]* 8.5 Write property test for tool discovery completeness
    - **Property 12: Tool Discovery Completeness**
    - **Validates: Requirements 4.8**
  
  - [ ]* 8.6 Write property test for JWT inclusion in tool invocations
    - **Property 14: JWT Inclusion in Tool Invocations**
    - **Validates: Requirements 3.10, 5.9**
  
  - [ ]* 8.7 Write unit tests for Gateway Client
    - Test list_tools with multiple Gateway Targets
    - Test list_tools with empty Gateway Target list
    - Test tool name conversion to three-underscore format
    - Test invoke_tool through Gateway MCP endpoint
    - Test retry logic on transient errors
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.4_

- [ ] 9. Implement Strands Client
  - [x] 9.1 Copy and adapt Strands Client from strands-reference
    - Copy src/agent/strands_client.py from strands-reference
    - Implement invoke_with_tools(messages, tools, system_prompt) to format Claude API request
    - Invoke Bedrock invoke_model() with model ID: anthropic.claude-3-sonnet-20240229-v1:0
    - Return Claude response with tool_use blocks or text response
    - Implement extract_tool_use(response) to extract tool ID, tool name, and tool input from tool_use blocks
    - Retry up to 3 times with exponential backoff on ThrottlingException and ServiceUnavailableException
    - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.6, 5.8, 5.10_
  
  - [ ]* 9.2 Write property test for Claude tool use extraction
    - **Property 13: Claude Tool Use Extraction**
    - **Validates: Requirements 5.3**
  
  - [ ]* 9.3 Write unit tests for Strands Client
    - Test invoke_with_tools with tools
    - Test extract_tool_use from response
    - Test extract text response
    - Test retry logic on transient errors
    - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.8_

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Implement Agent Lambda orchestration
  - [x] 11.1 Copy and adapt Agent Processor from strands-reference
    - Copy src/agent/agent_processor.py from strands-reference
    - Remove memory client integration for MVP (stateless mode)
    - Implement process_request(prompt, jwt_token, session_id) to orchestrate tool discovery, Claude invocation, and tool execution
    - Call gateway_client.list_tools(jwt_token) to discover available tools
    - Call strands_client.invoke_with_tools(messages, tools, system_prompt) to get Claude response
    - If Claude returns tool_use, extract tool name and input, call gateway_client.invoke_tool()
    - Send tool results back to Claude for response formatting
    - Support multi-turn conversations where Claude may select multiple tools sequentially
    - Return final text response when Claude completes
    - Log all interactions including prompt, tool selection, and response with request_id
    - _Requirements: 4.1, 5.1, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 8.2_
  
  - [x] 11.2 Implement Agent Lambda handler
    - Implement lambda_handler(event, context) as entry point
    - Extract JWT token from Authorization header
    - Validate JWT token using jwt_utils (signature, expiration, issuer, audience)
    - Return 401 status if JWT validation fails
    - Extract prompt and session_id from request body
    - Extract user_context from validated JWT token
    - Call agent_processor.process_request(prompt, jwt_token, session_id)
    - Return AgentResponse with response text, session_id, and user_context
    - Log structured request details including user_id, prompt length, timestamp, request_id
    - Handle errors with appropriate HTTP status codes and user-friendly messages
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.8, 3.9, 3.10, 8.1, 8.2, 8.10_
  
  - [ ]* 11.3 Write property test for request logging completeness
    - **Property 18: Request Logging Completeness**
    - **Validates: Requirements 8.2**
  
  - [ ]* 11.4 Write property test for structured error logging
    - **Property 17: Structured Error Logging**
    - **Validates: Requirements 8.1**
  
  - [ ]* 11.5 Write property test for request ID correlation
    - **Property 20: Request ID Correlation**
    - **Validates: Requirements 8.9**
  
  - [ ]* 11.6 Write property test for HTTP status code appropriateness
    - **Property 21: HTTP Status Code Appropriateness**
    - **Validates: Requirements 8.10**
  
  - [ ]* 11.7 Write unit tests for Agent Lambda
    - Test process_request with valid JWT and prompt
    - Test rejection with missing JWT
    - Test rejection with invalid JWT
    - Test handling of empty tool list from Gateway
    - Test handling of Claude text response (no tool use)
    - Test handling of Claude tool use response
    - Test handling of tool execution failure
    - Test multi-turn conversation flow
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.6, 5.5, 5.6, 5.7, 5.8_

- [ ] 12. Complete CloudFormation template with Lambda resources
  - [x] 12.1 Add Lambda function resources to CloudFormation template
    - Add AWS::Lambda::Function for Agent Lambda with 512MB memory, 30s timeout, environment variables (COGNITO_JWKS_URL, GATEWAY_ID, BEDROCK_MODEL_ID, AWS_REGION, LOG_LEVEL)
    - Add AWS::Lambda::Function for Interceptor Lambda with 128MB memory, 5s timeout, environment variable (LOG_LEVEL)
    - Add AWS::Lambda::Function for Weather API Lambda with 256MB memory, 10s timeout, environment variable (LOG_LEVEL)
    - Add IAM execution roles with least-privilege permissions: Agent Lambda needs Bedrock and Gateway access, Interceptor needs CloudWatch Logs, Weather API needs CloudWatch Logs
    - Add Lambda permissions for Gateway to invoke Interceptor and Weather API
    - _Requirements: 1.6, 1.7, 1.8_
  
  - [x] 12.2 Generate and add Gateway Target resources to CloudFormation template
    - Parse Weather API OpenAPI specification using openapi_parser
    - Generate Gateway Target resources using cloudformation_generator
    - Add generated AWS::BedrockAgentCore::GatewayTarget resources to template
    - Configure each target with Lambda ARN and tool schema InlinePayload
    - _Requirements: 1.3, 9.5_
  
  - [ ]* 12.3 Write unit tests for CloudFormation template validation
    - Test template validates with cfn-lint
    - Test all required resources are present
    - Test IAM roles have least-privilege permissions
    - Test Lambda environment variables are configured
    - _Requirements: 1.1, 1.6, 1.7, 1.8_

- [ ] 13. Implement deployment scripts
  - [x] 13.1 Create Lambda packaging scripts
    - Implement package_agent_lambda.py to package Agent Lambda with dependencies (boto3, requests, jwt)
    - Implement package_interceptor_lambda.py to package Interceptor Lambda with dependencies
    - Implement package_weather_api_lambda.py to package Weather API Lambda with dependencies
    - Create deployment packages as ZIP files
    - _Requirements: 1.1_
  
  - [x] 13.2 Create CloudFormation deployment script
    - Implement deploy_stack.py to validate CloudFormation template
    - Upload Lambda packages to S3 or inline in CloudFormation
    - Deploy CloudFormation stack to us-east-1
    - Wait for stack creation to complete
    - Output stack outputs: GatewayId, CognitoUserPoolId, CognitoClientId, Lambda ARNs
    - _Requirements: 1.1, 1.10_
  
  - [x] 13.3 Create Cognito test user setup script
    - Create Cognito user for testing
    - Set permanent password
    - Authenticate and obtain JWT token
    - Output JWT token for testing
    - _Requirements: 1.5, 10.2_
  
  - [ ]* 13.4 Write unit tests for deployment scripts
    - Test Lambda packaging includes all dependencies
    - Test CloudFormation template validation
    - Test stack deployment (dry-run mode)
    - _Requirements: 1.1_

- [x] 14. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. Implement integration tests
  - [ ]* 15.1 Write end-to-end integration test
    - Authenticate with Cognito and obtain JWT token
    - Invoke Agent Lambda with prompt: "What's the weather in Seattle?"
    - Verify Agent Lambda discovers weather API tools from Gateway
    - Verify Claude selects getCurrentWeather tool
    - Verify tool is invoked through Gateway
    - Verify Interceptor adds user_context headers
    - Verify Weather API receives request with user_context
    - Verify response includes weather data formatted by Claude
    - Verify all CloudWatch logs contain user_id for audit trail
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10_
  
  - [ ]* 15.2 Write multi-turn conversation integration test
    - First turn: "What's the weather in Seattle?"
    - Second turn: "What about tomorrow?"
    - Verify session_id is maintained across turns
    - Verify Claude uses context from previous turn
    - _Requirements: 5.7_
  
  - [ ]* 15.3 Write error scenario integration tests
    - Test invalid JWT returns 401
    - Test missing JWT returns 401
    - Test tool execution failure returns user-friendly error
    - Test Gateway unavailable triggers graceful degradation
    - _Requirements: 3.3, 3.4, 5.6, 8.4, 8.10_

- [ ] 16. Final validation and documentation
  - [x] 16.1 Run complete test suite
    - Run all unit tests and verify 80% line coverage, 75% branch coverage
    - Run all property tests with minimum 100 iterations each
    - Run all integration tests against deployed stack
    - Verify all 21 correctness properties pass
    - _Requirements: All requirements_
  
  - [x] 16.2 Deploy and validate production stack
    - Deploy CloudFormation stack to us-east-1
    - Create Cognito test user
    - Run end-to-end validation test
    - Verify CloudWatch logs and alarms are configured
    - Verify all Lambda functions are operational
    - _Requirements: 1.1, 1.9, 8.7, 8.8, 10.1_
  
  - [x] 16.3 Create deployment and extension guide
    - Document deployment process: package Lambdas, deploy CloudFormation, create test user
    - Document how to add new OpenAPI-based APIs: create OpenAPI spec, generate Gateway Targets, update CloudFormation
    - Document environment-specific configuration using stack parameters
    - Document monitoring and troubleshooting using CloudWatch logs and alarms
    - _Requirements: 9.8, 9.9_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at reasonable breaks
- Property tests validate universal correctness properties with minimum 100 iterations
- Unit tests validate specific examples and edge cases
- Integration tests validate complete end-to-end flows
- All code reuses proven components from strands-reference where possible
- Implementation uses Python as specified in the design document
- CloudFormation template deploys all resources to us-east-1 region
- Gateway uses CUSTOM_JWT authorizer with Cognito for authentication
- Interceptor Lambda extracts user context from JWT and injects into tool arguments
- Weather API validates user_context presence and logs user_id for audit trails
