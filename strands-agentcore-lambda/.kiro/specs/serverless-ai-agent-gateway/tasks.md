# Implementation Plan: Serverless AI Agent Gateway

## Overview

This implementation plan breaks down the Serverless AI Agent Gateway system into discrete, actionable tasks. The system consists of five primary components deployed via CloudFormation:

1. **CloudFormation Infrastructure**: Complete IaC for all AWS resources
2. **Agent Lambda**: Strands Framework-based AI agent with Claude 3 Sonnet
3. **Gateway Request Interceptor Lambda**: JWT claims extraction and user context injection
4. **Tool Lambda**: MCP tool implementation for AWS service operations
5. **Testing Infrastructure**: Property-based and unit tests for all 25 correctness properties

The implementation follows a bottom-up approach: infrastructure first, then core components, then integration, with testing tasks integrated throughout to catch errors early.

## Tasks

- [x] 1. Set up project structure and shared utilities
  - Create directory structure: `src/agent/`, `src/interceptor/`, `src/tool/`, `src/shared/`, `tests/`, `infrastructure/`
  - Create shared data models (UserContext, AgentRequest, AgentResponse, ToolRequest, ToolResponse, ConversationContext)
  - Create shared utilities for JWT validation, logging, error handling
  - Set up Python virtual environment and dependencies (boto3, hypothesis, pytest, strands-framework, pyjwt, requests)
  - _Requirements: 3.1, 3.2, 3.8_

- [x] 2. Implement CloudFormation infrastructure templates
  - [x] 2.1 Create base CloudFormation template with parameters
    - Define parameters: EnvironmentName, Region (default us-east-1)
    - Define outputs: Gateway ID, Memory ID, Cognito User Pool ID, Lambda ARNs
    - _Requirements: 8.1, 8.13_
  
  - [x] 2.2 Define AgentCore Gateway resource with auto-provisioned Cognito
    - Create AWS::BedrockAgent::Gateway resource
    - Configure Cognito auto-provisioning for OAuth2 with access tokens
    - Configure authorization using Cognito access tokens
    - Set up IAM execution role for Gateway
    - _Requirements: 1.1, 8.2, 9.3_
  
  - [x] 2.3 Define AgentCore Memory resource
    - Create AWS::BedrockAgent::Memory resource
    - Configure session timeout policy
    - Configure context size limits
    - Set up IAM permissions for Agent Lambda access
    - _Requirements: 8.3, 12.7, 12.8_
  
  - [x] 2.4 Define Agent Lambda function
    - Create AWS::Lambda::Function resource with Python 3.12 runtime
    - Configure environment variables: COGNITO_JWKS_URL, GATEWAY_ID, MEMORY_ID, BEDROCK_MODEL_ID, AWS_REGION
    - Set timeout to 30 seconds, memory to 512MB
    - Create IAM role with permissions for Bedrock, Gateway, Memory
    - DO NOT attach VPC configuration (enable Cognito JWKS access)
    - _Requirements: 8.8, 8.11_
  
  - [x] 2.5 Define Gateway Request Interceptor Lambda function
    - Create AWS::Lambda::Function resource with Python 3.12 runtime
    - Configure environment variables: LOG_LEVEL, AWS_REGION
    - Set timeout to 5 seconds, memory to 256MB
    - Create IAM role with CloudWatch Logs permissions
    - DO NOT attach VPC configuration
    - _Requirements: 4.1, 8.6_
  
  - [x] 2.6 Define Tool Lambda function
    - Create AWS::Lambda::Function resource with Python 3.12 runtime
    - Configure environment variables: LOG_LEVEL, AWS_REGION
    - Set timeout to 10 seconds, memory to 256MB
    - Create IAM role with S3 read permissions (ListAllMyBuckets, GetBucketLocation)
    - DO NOT attach VPC configuration (enable direct AWS service access)
    - _Requirements: 8.9, 8.12_
  
  - [x] 2.7 Define Gateway Target with inline schema
    - Create AWS::BedrockAgent::GatewayTarget resource for list-s3-buckets tool
    - Define inline schema with tool name, description, parameters (including user_context), and returns
    - Link to Tool Lambda ARN
    - Set target type to LAMBDA
    - _Requirements: 8.4, 8.5_
  
  - [x] 2.8 Attach Gateway Request Interceptor to Gateway
    - Create AWS::BedrockAgent::GatewayInterceptor resource
    - Set interceptor type to REQUEST
    - Link to Gateway and Interceptor Lambda
    - Create Lambda permission for Gateway to invoke Interceptor
    - _Requirements: 4.2, 8.7_
  
  - [x] 2.9 Configure CloudWatch logging and monitoring
    - Create log groups for all Lambda functions with 30-day retention
    - Set up CloudWatch alarms for Lambda errors, duration, throttles
    - Configure structured logging format
    - _Requirements: 7.7, 8.14_
  
  - [ ]* 2.10 Write CloudFormation template validation tests
    - Test template syntax validation
    - Test parameter validation
    - Test resource dependencies
    - _Requirements: 8.15_

- [x] 3. Checkpoint - Validate CloudFormation templates
  - Ensure CloudFormation templates pass validation, ask the user if questions arise.

- [x] 4. Implement shared utilities and data models
  - [x] 4.1 Implement UserContext data model
    - Create UserContext dataclass with user_id, username, client_id
    - Implement to_dict() method
    - Implement from_jwt_claims() class method
    - _Requirements: 3.1, 3.2_
  
  - [x] 4.2 Implement JWT validation utility
    - Create validate_jwt() function that fetches JWKS from Cognito
    - Implement JWT signature verification using RSA public key
    - Implement token expiration validation
    - Implement token_use claim validation (must be "access")
    - Cache JWKS with 1-hour TTL
    - _Requirements: 1.5, 1.7, 1.8, 9.2_
  
  - [ ]* 4.3 Write property test for JWT validation (Property 1)
    - **Property 1: JWT Token Validation**
    - **Validates: Requirements 1.4, 1.6, 1.7, 9.2**
    - Generate valid and invalid JWT tokens (expired, malformed, invalid signature)
    - Verify validation succeeds for valid tokens and fails appropriately for invalid tokens
  
  - [ ]* 4.4 Write property test for JWT claims extraction (Property 2)
    - **Property 2: JWT Claims Extraction**
    - **Validates: Requirements 1.3, 3.1, 3.5, 4.4, 9.4**
    - Generate JWTs with various claim combinations
    - Verify UserContext extraction produces correct user_id, username, client_id
  
  - [x] 4.5 Implement logging utility with user context
    - Create structured logger that includes user_id, username, request_id in all log entries
    - Implement log sanitization to prevent sensitive data logging
    - Create log_with_user_context() helper function
    - _Requirements: 7.6, 7.8, 9.10_
  
  - [ ]* 4.6 Write property test for audit logging (Property 14)
    - **Property 14: Audit Logging with User Context**
    - **Validates: Requirements 3.9, 7.1, 7.2, 7.4, 7.5, 7.6**
    - Generate operations at various layers
    - Verify log entries include timestamp, request_id, user_context
  
  - [ ]* 4.7 Write property test for log security (Property 15)
    - **Property 15: Sensitive Information Protection in Logs**
    - **Validates: Requirements 7.8, 9.10**
    - Generate log entries with various data
    - Verify no JWT tokens, passwords, or sensitive data in logs
  
  - [x] 4.8 Implement error handling utilities
    - Create error response formatter
    - Create retry logic with exponential backoff
    - Create timeout wrapper for external service calls
    - _Requirements: 10.4, 10.7_
  
  - [ ]* 4.9 Write property test for retry logic (Property 10)
    - **Property 10: Transient Failure Retry**
    - **Validates: Requirements 5.10, 10.4**
    - Generate transient failures (timeout, throttling)
    - Verify retry attempts up to configured maximum
  
  - [ ]* 4.10 Write property test for timeout enforcement (Property 19)
    - **Property 19: External Service Timeout**
    - **Validates: Requirements 10.7**
    - Generate slow operations
    - Verify timeout enforcement for all external calls

- [x] 5. Implement Gateway Request Interceptor Lambda
  - [x] 5.1 Implement Interceptor Lambda handler
    - Create lambda_handler() function
    - Extract JWT token from Authorization header
    - Decode JWT payload (base64 decode, JSON parse)
    - Extract user claims (sub, username, client_id)
    - Add user_context to tool parameters
    - Return transformed request
    - _Requirements: 4.3, 4.4, 4.5, 4.6_
  
  - [x] 5.2 Implement Interceptor error handling
    - Handle missing Authorization header (return original request)
    - Handle malformed JWT (return original request)
    - Handle missing claims (return request with partial context)
    - Log all errors without throwing exceptions
    - _Requirements: 4.7, 10.3, 10.8_
  
  - [ ]* 5.3 Write property test for Interceptor transformation (Property 4)
    - **Property 4: Gateway Interceptor Parameter Transformation**
    - **Validates: Requirements 3.6, 4.5, 4.6, 5.6**
    - Generate tool requests with valid JWT tokens
    - Verify transformed request includes user_context with correct values
  
  - [ ]* 5.4 Write property test for Interceptor error handling (Property 8)
    - **Property 8: Interceptor Error Handling**
    - **Validates: Requirements 4.7, 10.3, 10.8**
    - Generate error conditions (missing JWT, malformed JWT, missing claims)
    - Verify original request returned unchanged and errors logged
  
  - [ ]* 5.5 Write unit tests for Interceptor
    - Test successful JWT extraction and transformation
    - Test missing Authorization header
    - Test malformed JWT handling
    - Test missing claims handling
    - _Requirements: 4.8, 4.9_

- [x] 6. Implement Tool Lambda (MCP Implementation)
  - [x] 6.1 Implement Tool Lambda handler
    - Create lambda_handler() function
    - Parse ToolRequest from event (tool_name, parameters, user_context)
    - Extract user_context from parameters
    - Route to appropriate tool implementation
    - Format ToolResponse with results and user_context
    - _Requirements: 5.1, 5.8, 5.9_
  
  - [x] 6.2 Implement list-s3-buckets tool
    - Create S3 client using boto3
    - Call ListBuckets API
    - Format bucket list with names and creation dates
    - Include user_context in response
    - Log operation with user_id and username
    - _Requirements: 6.1, 6.2, 6.3, 6.6_
  
  - [ ]* 6.3 Write property test for Tool user context receipt (Property 5)
    - **Property 5: Tool Lambda User Context Receipt**
    - **Validates: Requirements 3.7, 3.10, 5.8, 7.9**
    - Generate Tool Lambda invocations
    - Verify event payload contains user_context with non-empty user_id and username
  
  - [ ]* 6.4 Write property test for user attribution in responses (Property 11)
    - **Property 11: User Attribution in Responses**
    - **Validates: Requirements 6.3, 6.4**
    - Generate tool responses
    - Verify result includes user_context with user_id and username
  
  - [x] 6.3 Implement Tool error handling
    - Handle AWS ClientError exceptions (AccessDenied, Throttling, ServiceUnavailable)
    - Implement retry logic for transient errors
    - Handle missing user_context gracefully
    - Return user-friendly error messages
    - _Requirements: 6.7, 10.5_
  
  - [ ]* 6.4 Write property test for AWS error handling (Property 12)
    - **Property 12: AWS Service Error Handling**
    - **Validates: Requirements 6.7, 10.5**
    - Generate AWS service errors
    - Verify exceptions caught, logged with user context, and descriptive error returned
  
  - [ ]* 6.5 Write property test for MCP tool interface (Property 20)
    - **Property 20: MCP Tool Interface Compliance**
    - **Validates: Requirements 11.2**
    - Generate tool implementations
    - Verify they accept ToolRequest and return ToolResponse following standard interface
  
  - [ ]* 6.6 Write unit tests for Tool Lambda
    - Test S3 ListBuckets execution
    - Test user context extraction
    - Test response formatting
    - Test specific AWS error codes
    - _Requirements: 6.1, 6.2, 6.6_

- [x] 7. Implement Agent Lambda with Strands Framework
  - [x] 7.1 Implement Agent Lambda handler
    - Create lambda_handler() function
    - Parse AgentRequest from event (prompt, JWT token, session_id)
    - Validate JWT token using shared utility
    - Extract UserContext from JWT claims
    - Route to agent processing logic
    - Return AgentResponse with response, session_id, user_context
    - _Requirements: 2.1, 3.1, 3.2_
  
  - [x] 7.2 Implement Strands Framework agent initialization
    - Initialize Strands agent with Claude 3 Sonnet model
    - Configure Bedrock client with model ID
    - Set up agent configuration (temperature, max_tokens)
    - _Requirements: 2.1, 2.2_
  
  - [x] 7.3 Implement Gateway tool discovery
    - Query AgentCore Gateway for available tools using list_tools API
    - Include JWT token in Authorization header
    - Parse tool definitions from Gateway response
    - Pass tool definitions to Claude via Bedrock
    - _Requirements: 2.2, 2.3, 11.4_
  
  - [ ]* 7.4 Write property test for Authorization header propagation (Property 6)
    - **Property 6: Authorization Header Propagation**
    - **Validates: Requirements 3.3, 4.3**
    - Generate Agent Gateway invocations
    - Verify Authorization header includes JWT in "Bearer <token>" format
  
  - [x] 7.5 Implement tool execution through Gateway
    - Call AgentCore Gateway invoke_tool API
    - Include JWT token in Authorization header
    - Format request as JSON-RPC 2.0
    - Parse tool response
    - Handle Gateway errors
    - _Requirements: 2.7, 5.1, 5.2, 5.3_
  
  - [ ]* 7.6 Write property test for MCP protocol formatting (Property 7)
    - **Property 7: MCP Protocol Formatting**
    - **Validates: Requirements 5.2**
    - Generate tool execution requests
    - Verify JSON-RPC 2.0 format with required fields (jsonrpc, method, params, id)
  
  - [ ]* 7.7 Write property test for tool response parsing (Property 9)
    - **Property 9: Tool Response Parsing**
    - **Validates: Requirements 5.9**
    - Generate valid and malformed tool responses
    - Verify parsing extracts result for valid responses and fails gracefully for malformed
  
  - [x] 7.8 Implement conversation context management with AgentCore Memory
    - Generate session_id for new conversations
    - Store conversation turns in AgentCore Memory with session_id and user_id
    - Retrieve conversation context by session_id
    - Limit context size to prevent token overflow
    - _Requirements: 2.8, 12.1, 12.3, 12.8_
  
  - [ ]* 7.9 Write property test for session management (Property 13)
    - **Property 13: Session Management**
    - **Validates: Requirements 2.8, 12.1, 12.3**
    - Generate conversation sequences
    - Verify unique session_id created for new conversations
    - Verify context retrieved for subsequent requests with same session_id
  
  - [ ]* 7.10 Write property test for context size limiting (Property 24)
    - **Property 24: Context Size Limiting**
    - **Validates: Requirements 12.8**
    - Generate large conversation contexts
    - Verify returned context limited to maximum size
  
  - [ ]* 7.11 Write property test for memory multi-tenant isolation (Property 22)
    - **Property 22: Memory Multi-Tenant Isolation**
    - **Validates: Requirements 12.6**
    - Generate multi-user memory operations
    - Verify users can only access their own conversation history
  
  - [x] 7.12 Implement Agent error handling
    - Handle JWT validation errors (return 401 with generic message)
    - Handle Bedrock errors (throttling, timeouts, model errors)
    - Handle Gateway errors (connection, timeout, invalid response)
    - Handle Memory errors (degrade gracefully)
    - Log all errors with user context
    - _Requirements: 10.1, 10.2, 10.6_
  
  - [ ]* 7.13 Write property test for authentication error security (Property 16)
    - **Property 16: Authentication Error Security**
    - **Validates: Requirements 10.1**
    - Generate authentication failures
    - Verify generic error messages without exposing failure details
  
  - [ ]* 7.14 Write property test for Agent error handling (Property 17)
    - **Property 17: Agent Error Handling**
    - **Validates: Requirements 10.2**
    - Generate Agent errors (Bedrock, Gateway, parsing)
    - Verify errors logged with user context and user-friendly messages returned
  
  - [ ]* 7.15 Write property test for Gateway unreachable handling (Property 18)
    - **Property 18: Gateway Unreachable Handling**
    - **Validates: Requirements 10.6**
    - Generate Gateway failures (network, unavailability)
    - Verify exceptions caught, logged, and appropriate error message returned
  
  - [ ]* 7.16 Write unit tests for Agent Lambda
    - Test successful authentication flow
    - Test prompt processing with tool selection
    - Test memory storage and retrieval
    - Test Bedrock API integration
    - Test Gateway API integration
    - _Requirements: 2.1, 2.8, 3.1_

- [x] 8. Checkpoint - Ensure all component tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement integration and end-to-end testing
  - [ ]* 9.1 Write property test for user context preservation (Property 3)
    - **Property 3: User Context Preservation**
    - **Validates: Requirements 3.2, 3.8, 9.8**
    - Generate user contexts and pass through mock layers (Agent → Gateway → Interceptor → Tool)
    - Verify user_id, username, client_id remain unchanged at every layer
  
  - [ ]* 9.2 Write property test for Interceptor target type compatibility (Property 21)
    - **Property 21: Gateway Interceptor Target Type Compatibility**
    - **Validates: Requirements 11.7**
    - Generate different Gateway target types (Lambda, MCP Server, API Gateway)
    - Verify Interceptor successfully extracts JWT and adds user_context for all types
  
  - [ ]* 9.3 Write property test for session timeout (Property 23)
    - **Property 23: Session Timeout**
    - **Validates: Requirements 12.7**
    - Generate expired sessions
    - Verify subsequent requests create new session or return timeout error
  
  - [ ]* 9.4 Write end-to-end integration test
    - Test complete flow: authenticate → submit prompt → Agent processes → Gateway invokes Interceptor → Tool executes → response returned
    - Verify user context at every layer
    - Verify audit logs at every layer
    - _Requirements: 3.8, 7.6, 9.8_
  
  - [ ]* 9.5 Write multi-turn conversation integration test
    - Test conversation flow: start conversation → first prompt → follow-up prompt
    - Verify session_id created and maintained
    - Verify context stored and retrieved
    - Verify conversation coherence
    - _Requirements: 12.1, 12.3, 12.5_
  
  - [ ]* 9.6 Write error scenario integration tests
    - Test invalid JWT → verify 401 response
    - Test expired JWT → verify 401 response
    - Test AWS service error → verify error handling
    - Test Gateway unavailable → verify error handling
    - Test Interceptor error → verify graceful degradation
    - _Requirements: 1.7, 1.8, 10.1, 10.6, 10.8_

- [x] 10. Deploy and validate infrastructure
  - [x] 10.1 Deploy CloudFormation stack to test environment
    - Deploy stack using AWS CLI or Console
    - Verify all resources created successfully
    - Capture outputs (Gateway ID, Memory ID, Cognito User Pool ID)
    - _Requirements: 8.1, 8.15_
  
  - [ ]* 10.2 Write property test for CloudFormation idempotence (Property 25)
    - **Property 25: CloudFormation Idempotence**
    - **Validates: Requirements 8.14**
    - Deploy same template twice
    - Verify same infrastructure state with no changes or only updated resources
  
  - [x] 10.3 Validate Gateway configuration
    - Verify Gateway created with correct name and description
    - Verify Cognito User Pool auto-provisioned
    - Verify Gateway Target registered with inline schema
    - Verify Interceptor attached to Gateway
    - _Requirements: 8.2, 8.4, 8.5, 8.7_
  
  - [x] 10.4 Validate Lambda configurations
    - Verify Agent Lambda has correct environment variables and IAM permissions
    - Verify Interceptor Lambda has correct configuration
    - Verify Tool Lambda has correct S3 permissions
    - Verify no Lambda functions attached to VPC
    - _Requirements: 8.8, 8.9, 8.11, 8.12_
  
  - [x] 10.5 Validate IAM permissions
    - Verify Agent Lambda can invoke Bedrock, Gateway, Memory
    - Verify Gateway can invoke Interceptor and Tool Lambda
    - Verify Tool Lambda can access S3
    - _Requirements: 8.10, 9.5, 9.6, 9.7_
  
  - [x] 10.6 Validate CloudWatch logging
    - Verify log groups created for all Lambda functions
    - Verify structured logging format
    - Verify log retention set to 30 days
    - _Requirements: 7.7, 8.14_

- [x] 11. Perform end-to-end system validation
  - [x] 11.1 Create test user in Cognito
    - Create user in auto-provisioned Cognito User Pool
    - Set user password
    - Verify user can authenticate
    - _Requirements: 1.1, 1.2_
  
  - [x] 11.2 Test authentication flow
    - Authenticate user with Cognito
    - Verify JWT access token received
    - Verify token contains sub, username, client_id claims
    - Verify token_use is "access"
    - _Requirements: 1.2, 1.3, 1.4_
  
  - [x] 11.3 Test "List my S3 buckets" use case
    - Submit prompt "List my S3 buckets" with JWT token
    - Verify Agent processes request
    - Verify Gateway invokes Interceptor
    - Verify Interceptor adds user_context
    - Verify Tool executes S3 ListBuckets
    - Verify response includes bucket list with creation dates
    - Verify response includes user_context
    - _Requirements: 2.1, 3.6, 5.8, 6.1, 6.3_
  
  - [x] 11.4 Verify user context at all layers
    - Check Agent Lambda logs for user_id and username
    - Check Interceptor Lambda logs for user extraction
    - Check Tool Lambda logs for user_id and username (not "unknown")
    - Verify user_context preserved through all layers
    - _Requirements: 3.8, 3.9, 7.2, 7.4, 7.5, 7.9_
  
  - [x] 11.5 Test multi-turn conversation
    - Submit first prompt "List my S3 buckets"
    - Capture session_id from response
    - Submit follow-up prompt "How many buckets do I have?" with same session_id
    - Verify Agent uses conversation context
    - Verify coherent response referencing previous interaction
    - _Requirements: 2.8, 12.1, 12.3, 12.5_
  
  - [x] 11.6 Test error scenarios
    - Test with invalid JWT → verify 401 response
    - Test with expired JWT → verify 401 response
    - Test with missing Authorization header → verify 401 response
    - Verify error messages are generic and don't expose sensitive information
    - _Requirements: 1.7, 1.8, 10.1_

- [-] 12. Implement scalable multi-tool support
  - [ ] 12.1 Research Gateway Target invocation patterns
    - Review AgentCore Gateway documentation for Lambda target invocation
    - Determine if Gateway passes tool name in event payload
    - Identify all available event fields from Gateway
    - Document Gateway event structure for Lambda targets
    - _Requirements: 5.8, 7.9_
  
  - [ ] 12.2 Design and implement solution for tool routing
    - **Option A: Environment Variables** - Configure TOOL_NAME env var per Lambda, create separate Lambda per tool
    - **Option B: Lambda Function Tags** - Use Lambda tags to identify which tool(s) the function handles
    - **Option C: CloudFormation Metadata** - Store tool mapping in CFN template and pass via env vars
    - **Option D: Gateway Event Analysis** - If Gateway provides tool identifier, extract it from event
    - Select and implement the most appropriate solution based on research findings
    - Remove hardcoded tool name fallback from ToolRequest.from_event()
    - _Requirements: 5.1, 5.8, 11.1, 11.2_
  
  - [ ] 12.3 Update CloudFormation template for multi-tool support
    - Modify Tool Lambda resource definition to support chosen solution
    - Add additional Gateway Targets for new tools (if using separate Lambdas)
    - Update IAM permissions for new tools
    - Ensure scalability for adding new tools without code changes
    - _Requirements: 8.4, 11.1, 11.3_
  
  - [ ] 12.4 Test multi-tool routing
    - Add a second tool (e.g., describe-s3-bucket) to test routing
    - Verify Agent can discover both tools from Gateway
    - Verify Agent can invoke both tools correctly
    - Verify Tool Lambda(s) route to correct implementation
    - Verify no hardcoded tool names remain in code
    - _Requirements: 5.8, 6.1, 11.1, 11.4_
  
  - [ ] 12.5 Verify end-to-end multi-tool flow
    - Submit prompts that require different tools
    - Verify Agent selects correct tool based on prompt
    - Verify Gateway routes to correct Lambda/implementation
    - Verify responses include correct tool results
    - Verify user context maintained across all tools
    - _Requirements: 2.7, 5.1, 5.8, 6.1, 11.1_

- [ ] 13. Final checkpoint - System validation complete
  - Ensure all tests pass and system is fully functional, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional testing tasks and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties across all inputs (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows and multi-component interactions
- CloudFormation deployment is idempotent and supports updates
- All Lambda functions use Python 3.12 runtime
- No Lambda functions are attached to VPC to enable direct AWS service access
- Gateway Request Interceptor ensures user context propagation to Tool Lambda
- System uses Cognito access tokens (not ID tokens) for authorization
- Complete audit trail with user attribution at every layer
