# Implementation Plan: Serverless AI Agent Gateway with OpenAPI Targets

## Overview

This implementation plan breaks down the serverless AI agent gateway system into discrete coding tasks. The system enables natural language interaction with external REST APIs through AWS Bedrock AgentCore Gateway using OpenAPI specifications, with complete user context propagation through Gateway Request Interceptors.

The implementation follows an incremental approach: shared utilities → interceptor → agent → infrastructure → testing.

## Tasks

- [ ] 1. Set up project structure and shared utilities
  - Create directory structure for Lambda functions and shared code
  - Implement shared data models (UserContext, AgentRequest, AgentResponse, etc.)
  - Implement JWT utilities for token validation and claim extraction
  - Implement structured logging utilities with user context support
  - Set up Python dependencies (boto3, PyJWT, requests, hypothesis)
  - _Requirements: 3.1, 3.2, 8.6_

- [ ]* 1.1 Write property test for UserContext data model
  - **Property 4: User Context Preservation**
  - **Validates: Requirements 3.2, 3.8**

- [ ] 2. Implement Gateway Request Interceptor Lambda
  - [ ] 2.1 Implement JWT token extraction from Authorization header
    - Extract Bearer token from headers
    - Handle missing or malformed Authorization headers
    - _Requirements: 4.3_
  
  - [ ] 2.2 Implement JWT payload decoding without verification
    - Decode JWT payload to extract claims
    - Handle malformed JWT tokens
    - _Requirements: 4.4_
  
  - [ ] 2.3 Implement user context extraction from JWT claims
    - Extract sub, username, client_id from claims
    - Handle missing claims with fallback to 'unknown'
    - _Requirements: 3.5, 4.4_
  
  - [ ] 2.4 Implement user context header injection
    - Add X-User-Id, X-Username, X-Client-Id headers to request
    - Transform gateway request with user headers
    - _Requirements: 3.6, 4.5, 4.6_
  
  - [ ] 2.5 Implement fail-safe error handling
    - Return original request unchanged on any error
    - Log errors without breaking request flow
    - _Requirements: 4.7, 11.3_
  
  - [ ] 2.6 Implement structured logging for Interceptor
    - Log user extraction and header transformation
    - Include request ID and user context in logs
    - Exclude sensitive JWT information from logs
    - _Requirements: 4.8, 8.4, 10.9_

- [ ]* 2.7 Write property test for Interceptor fail-safe behavior
  - **Property 8: Interceptor Fail-Safe Behavior**
  - **Validates: Requirements 4.7, 11.3, 11.8**

- [ ]* 2.8 Write property test for JWT extraction
  - **Property 9: JWT Token Extraction from Authorization Header**
  - **Validates: Requirements 4.3**

- [ ]* 2.9 Write property test for user context header injection
  - **Property 6: User Context Header Injection**
  - **Validates: Requirements 3.6, 4.5, 6.5**

- [ ]* 2.10 Write property test for Interceptor consistency across targets
  - **Property 38: Interceptor Consistency Across Targets**
  - **Validates: Requirements 12.7**

- [ ] 3. Implement JWT validation utilities for Agent Lambda
  - [ ] 3.1 Implement JWKS fetching and caching
    - Fetch JWKS from Cognito discovery URL
    - Cache JWKS with TTL (1 hour)
    - _Requirements: 1.5, 10.2_
  
  - [ ] 3.2 Implement JWT signature verification
    - Verify JWT signature using JWKS public key
    - Validate token expiration
    - Validate token_use claim equals 'access'
    - _Requirements: 1.4, 1.5, 1.7_
  
  - [ ] 3.3 Implement user context extraction from validated JWT
    - Extract sub, username, client_id from claims
    - Return UserContext object
    - _Requirements: 3.1_

- [ ]* 3.4 Write property test for JWT validation
  - **Property 2: JWT Token Validation**
  - **Validates: Requirements 1.5, 1.7, 10.2**

- [ ]* 3.5 Write property test for JWT token structure
  - **Property 1: JWT Token Structure Validation**
  - **Validates: Requirements 1.3, 1.4**

- [ ]* 3.6 Write property test for user context extraction
  - **Property 3: User Context Extraction**
  - **Validates: Requirements 3.1, 3.5, 10.4**

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement AgentCore Gateway integration utilities
  - [ ] 5.1 Implement Gateway tool query function
    - Query Gateway for available OpenAPI tools
    - Include JWT token in Authorization header
    - Parse tool definitions from Gateway response
    - _Requirements: 2.2, 3.3, 12.4_
  
  - [ ] 5.2 Implement Gateway tool invocation function
    - Invoke OpenAPI tool through Gateway
    - Include JWT token in Authorization header
    - Handle Gateway responses and errors
    - _Requirements: 2.7, 6.1_
  
  - [ ] 5.3 Implement retry logic with exponential backoff
    - Retry transient failures up to configured limit
    - Use exponential backoff strategy
    - Handle rate limiting (429) with special backoff
    - _Requirements: 6.10, 11.4, 11.9_
  
  - [ ] 5.4 Implement timeout handling for Gateway calls
    - Configure timeouts for tool invocations
    - Handle timeout errors gracefully
    - _Requirements: 11.7_

- [ ]* 5.5 Write property test for JWT authorization header inclusion
  - **Property 5: JWT Authorization Header Inclusion**
  - **Validates: Requirements 3.3**

- [ ]* 5.6 Write property test for dynamic tool discovery
  - **Property 15: Dynamic Tool Discovery**
  - **Validates: Requirements 2.2, 12.4**

- [ ]* 5.7 Write property test for tool execution through Gateway
  - **Property 18: Tool Execution Through Gateway**
  - **Validates: Requirements 2.7, 6.1**

- [ ]* 5.8 Write property test for retry with exponential backoff
  - **Property 22: Transient Failure Retry with Exponential Backoff**
  - **Validates: Requirements 6.10, 11.4**

- [ ] 6. Implement AWS Bedrock integration utilities
  - [ ] 6.1 Implement Bedrock model invocation function
    - Invoke Claude 3 Sonnet with messages and tools
    - Configure model parameters (max_tokens, temperature)
    - Parse model response for tool usage or text
    - _Requirements: 2.1_
  
  - [ ] 6.2 Implement tool definition formatting for Claude
    - Convert Gateway tool definitions to Claude format
    - Include operation descriptions from OpenAPI specs
    - _Requirements: 2.3, 14.5_
  
  - [ ] 6.3 Implement Claude response parsing
    - Extract tool usage (name and parameters) from response
    - Extract text response from model
    - Validate response format
    - _Requirements: 2.6_
  
  - [ ] 6.4 Implement timeout handling for Bedrock calls
    - Configure timeout for model invocations
    - Handle timeout errors gracefully
    - _Requirements: 11.7_

- [ ]* 6.5 Write property test for Bedrock model invocation
  - **Property 14: Bedrock Model Invocation**
  - **Validates: Requirements 2.1**

- [ ]* 6.6 Write property test for tool definitions passed to Claude
  - **Property 16: Tool Definitions Passed to Claude**
  - **Validates: Requirements 2.3**

- [ ]* 6.7 Write property test for Claude response validation
  - **Property 17: Claude Response Tool Usage Validation**
  - **Validates: Requirements 2.6**

- [ ]* 6.8 Write property test for tool description inclusion
  - **Property 45: Tool Description Inclusion for Claude**
  - **Validates: Requirements 14.5**

- [ ] 7. Implement AgentCore Memory integration utilities
  - [ ] 7.1 Implement conversation turn storage
    - Store conversation turn in AgentCore Memory
    - Include session_id and user_id for multi-tenant isolation
    - Store user message, agent response, and tool usage
    - _Requirements: 2.8, 13.2_
  
  - [ ] 7.2 Implement conversation context retrieval
    - Retrieve conversation context by session_id and user_id
    - Limit number of turns retrieved (max 10)
    - Handle missing or empty context gracefully
    - _Requirements: 13.3, 13.8_
  
  - [ ] 7.3 Implement session identifier generation
    - Generate unique session ID for new conversations
    - Associate session with user identity
    - _Requirements: 13.1_
  
  - [ ] 7.4 Implement timeout handling for Memory operations
    - Configure timeout for Memory read/write
    - Handle timeout errors gracefully
    - _Requirements: 11.7_

- [ ]* 7.5 Write property test for conversation context storage
  - **Property 19: Conversation Context Storage**
  - **Validates: Requirements 2.8, 13.2**

- [ ]* 7.6 Write property test for conversation context retrieval
  - **Property 40: Conversation Context Retrieval**
  - **Validates: Requirements 13.3**

- [ ]* 7.7 Write property test for multi-tenant isolation
  - **Property 30: Multi-Tenant Isolation**
  - **Validates: Requirements 10.7, 13.6**

- [ ]* 7.8 Write property test for context size limitation
  - **Property 42: Context Size Limitation**
  - **Validates: Requirements 13.8**

- [ ] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement Agent Lambda main handler
  - [ ] 9.1 Implement request parsing and validation
    - Parse API Gateway event
    - Extract JWT token from Authorization header
    - Parse request body (prompt, session_id)
    - Validate input parameters
    - _Requirements: 2.1_
  
  - [ ] 9.2 Implement JWT validation flow
    - Validate JWT token using JWKS
    - Extract user context from validated token
    - Handle authentication failures with generic errors
    - _Requirements: 1.5, 1.7, 11.1_
  
  - [ ] 9.3 Implement conversation context retrieval
    - Retrieve context from Memory if session_id provided
    - Handle missing context gracefully
    - _Requirements: 13.3, 13.5_
  
  - [ ] 9.4 Implement tool discovery and Claude invocation
    - Query Gateway for available tools
    - Format tools for Claude
    - Invoke Bedrock with prompt, context, and tools
    - _Requirements: 2.2, 2.3, 2.1_
  
  - [ ] 9.5 Implement tool execution orchestration
    - Parse Claude response for tool usage
    - Execute selected tool through Gateway
    - Parse tool results
    - Generate natural language response
    - _Requirements: 2.6, 2.7, 2.9, 6.9_
  
  - [ ] 9.6 Implement conversation turn storage
    - Store conversation turn in Memory
    - Include user message, agent response, tool usage
    - Associate with session_id and user_id
    - _Requirements: 2.8_
  
  - [ ] 9.7 Implement error handling and logging
    - Handle all error types gracefully
    - Log errors with user context
    - Return user-friendly error messages
    - Exclude sensitive information from logs
    - _Requirements: 11.2, 8.2, 8.8_
  
  - [ ] 9.8 Implement response formatting
    - Format response with natural language text
    - Include session_id and user_context
    - Return API Gateway response format
    - _Requirements: 2.9_

- [ ]* 9.9 Write property test for natural language response generation
  - **Property 20: Natural Language Response Generation**
  - **Validates: Requirements 2.9**

- [ ]* 9.10 Write property test for multi-turn context usage
  - **Property 41: Multi-Turn Context Usage**
  - **Validates: Requirements 13.5**

- [ ]* 9.11 Write property test for session identifier creation
  - **Property 39: Session Identifier Creation**
  - **Validates: Requirements 13.1**

- [ ]* 9.12 Write property test for agent error handling
  - **Property 32: Agent Error Handling with User Context**
  - **Validates: Requirements 11.2, 7.8**

- [ ] 10. Implement error handling utilities
  - [ ] 10.1 Implement OpenAPI error response parsing
    - Parse error status codes (4xx, 5xx)
    - Extract error details from response body
    - Map status codes to user-friendly messages
    - _Requirements: 7.1, 7.2, 7.3_
  
  - [ ] 10.2 Implement network failure handling
    - Handle timeouts and connection failures
    - Return appropriate error messages
    - _Requirements: 7.4, 11.5_
  
  - [ ] 10.3 Implement response validation error handling
    - Handle schema validation failures
    - Log validation errors
    - Return generic error messages
    - _Requirements: 7.6_
  
  - [ ] 10.4 Implement Gateway unreachability handling
    - Detect Gateway communication failures
    - Return appropriate error messages
    - _Requirements: 11.6_

- [ ]* 10.5 Write property test for HTTP error status code handling
  - **Property 23: HTTP Error Status Code Handling**
  - **Validates: Requirements 7.1, 7.2**

- [ ]* 10.6 Write property test for error detail extraction
  - **Property 24: OpenAPI Error Detail Extraction**
  - **Validates: Requirements 7.3**

- [ ]* 10.7 Write property test for network failure handling
  - **Property 25: Network Failure Graceful Handling**
  - **Validates: Requirements 7.4, 11.5**

- [ ]* 10.8 Write property test for response validation failure handling
  - **Property 26: Response Validation Failure Handling**
  - **Validates: Requirements 7.6**

- [ ]* 10.9 Write property test for Gateway unreachability handling
  - **Property 35: Gateway Unreachability Handling**
  - **Validates: Requirements 11.6**

- [ ] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Implement CloudFormation infrastructure templates
  - [ ] 12.1 Create main CloudFormation template
    - Define template parameters (environment name, OpenAPI endpoint URLs)
    - Define template outputs (Gateway ID, Memory ID, Cognito details)
    - _Requirements: 9.1, 9.14_
  
  - [ ] 12.2 Define AgentCore Gateway resource
    - Create Gateway with auto-provisioned Cognito
    - Configure Gateway settings
    - Export Gateway ID and Cognito details
    - _Requirements: 9.2, 1.1_
  
  - [ ] 12.3 Define AgentCore Memory resource
    - Create Memory resource
    - Export Memory ID
    - _Requirements: 9.3_
  
  - [ ] 12.4 Define Gateway Request Interceptor Lambda
    - Create Lambda function with Python 3.12 runtime
    - Configure environment variables (LOG_LEVEL)
    - Create IAM execution role
    - Package Lambda code
    - _Requirements: 9.6, 9.8_
  
  - [ ] 12.5 Attach Interceptor to Gateway
    - Create Gateway Interceptor attachment
    - Configure as REQUEST interceptor
    - Grant Gateway permission to invoke Interceptor
    - _Requirements: 9.7, 4.2, 4.9_
  
  - [ ] 12.6 Define Agent Lambda function
    - Create Lambda function with Python 3.12 runtime
    - Configure environment variables (GATEWAY_ID, MEMORY_ID, COGNITO_JWKS_URL, etc.)
    - Create IAM execution role with required permissions
    - Do NOT attach to VPC
    - Package Lambda code with dependencies
    - _Requirements: 9.8, 9.10_
  
  - [ ] 12.7 Define IAM roles and permissions
    - Agent Lambda role: bedrock:InvokeModel, bedrock:InvokeGateway, bedrock:GetMemory, bedrock:PutMemory
    - Interceptor Lambda role: basic execution only
    - Gateway execution role: lambda:InvokeFunction for Interceptor
    - _Requirements: 9.9_
  
  - [ ] 12.8 Define OpenAPI Gateway Targets
    - Create Gateway Target for each OpenAPI endpoint
    - Configure with OpenAPI specification (inline or URL)
    - Configure base URL and authentication
    - _Requirements: 9.4, 9.5, 5.1_
  
  - [ ] 12.9 Define CloudWatch log groups
    - Create log groups for Agent Lambda
    - Create log groups for Interceptor Lambda
    - Configure log retention (30 days)
    - _Requirements: 9.12_
  
  - [ ] 12.10 Add CloudFormation metadata and documentation
    - Add resource descriptions
    - Add parameter descriptions
    - Add deployment instructions
    - _Requirements: 9.1_

- [ ]* 12.11 Write property test for CloudFormation idempotence
  - **Property 47: CloudFormation Deployment Idempotence**
  - **Validates: Requirements 9.13**

- [ ] 13. Implement OpenAPI specification validation
  - [ ] 13.1 Implement OpenAPI spec version validation
    - Validate OpenAPI version is 3.0.x or 3.1.x
    - Reject invalid versions with descriptive errors
    - _Requirements: 5.1, 14.3_
  
  - [ ] 13.2 Implement OpenAPI spec structure validation
    - Validate required fields (openapi, info, paths)
    - Validate spec structure
    - Reject invalid specs with descriptive errors
    - _Requirements: 14.1, 14.2_
  
  - [ ] 13.3 Implement operation metadata extraction
    - Extract operation IDs, summaries, descriptions
    - Extract parameter schemas
    - Extract response schemas
    - _Requirements: 14.4_
  
  - [ ] 13.4 Implement validation error logging
    - Log schema validation errors
    - Include sufficient detail for troubleshooting
    - _Requirements: 14.8_

- [ ]* 13.5 Write property test for OpenAPI specification validation
  - **Property 43: OpenAPI Specification Validation**
  - **Validates: Requirements 14.1, 14.2**

- [ ]* 13.6 Write property test for OpenAPI version support
  - **Property 13: OpenAPI Specification Version Support**
  - **Validates: Requirements 5.1, 14.3**

- [ ]* 13.7 Write property test for operation metadata extraction
  - **Property 44: OpenAPI Operation Metadata Extraction**
  - **Validates: Requirements 14.4**

- [ ]* 13.8 Write property test for schema validation error logging
  - **Property 46: Schema Validation Error Logging**
  - **Validates: Requirements 14.8**

- [ ] 14. Implement comprehensive logging
  - [ ] 14.1 Implement audit logging for all operations
    - Log authentication events
    - Log Agent processing events
    - Log Interceptor transformations
    - Log OpenAPI invocations
    - Include timestamp, request ID, user context in all logs
    - _Requirements: 8.1, 8.2, 8.4, 8.5, 8.6, 8.9_
  
  - [ ] 14.2 Implement sensitive information filtering
    - Exclude JWT tokens from logs
    - Exclude API keys from logs
    - Exclude passwords from logs
    - _Requirements: 8.8, 10.9_

- [ ]* 14.3 Write property test for comprehensive audit logging
  - **Property 27: Comprehensive Audit Logging with User Context**
  - **Validates: Requirements 8.1, 8.2, 8.4, 8.5, 8.6, 8.9**

- [ ]* 14.4 Write property test for sensitive information exclusion
  - **Property 28: Sensitive Information Exclusion from Logs**
  - **Validates: Requirements 8.8, 10.9**

- [ ] 15. Implement security and communication utilities
  - [ ] 15.1 Implement HTTPS enforcement
    - Ensure all external communications use HTTPS
    - Validate HTTPS URLs for OpenAPI endpoints
    - _Requirements: 10.1, 10.5_
  
  - [ ] 15.2 Implement generic authentication error messages
    - Return generic errors for authentication failures
    - Do not expose sensitive information
    - _Requirements: 11.1_
  
  - [ ] 15.3 Implement timeout configuration
    - Configure timeouts for all external calls
    - Document timeout values
    - _Requirements: 11.7_

- [ ]* 15.4 Write property test for HTTPS communication enforcement
  - **Property 29: HTTPS Communication Enforcement**
  - **Validates: Requirements 10.1, 10.5**

- [ ]* 15.5 Write property test for generic authentication error messages
  - **Property 31: Generic Authentication Error Messages**
  - **Validates: Requirements 11.1**

- [ ]* 15.6 Write property test for external service timeout configuration
  - **Property 33: External Service Timeout Configuration**
  - **Validates: Requirements 11.7**

- [ ] 16. Implement extensibility features
  - [ ] 16.1 Implement OpenAPI target configuration pattern
    - Define standard configuration format
    - Support inline and URL-based OpenAPI specs
    - _Requirements: 12.2, 5.2_
  
  - [ ] 16.2 Ensure Agent code is target-agnostic
    - Agent discovers tools dynamically from Gateway
    - No hardcoded tool definitions in Agent
    - _Requirements: 12.1_

- [ ]* 16.3 Write property test for OpenAPI target extensibility
  - **Property 36: OpenAPI Target Extensibility**
  - **Validates: Requirements 12.1**

- [ ]* 16.4 Write property test for configuration consistency
  - **Property 37: OpenAPI Target Configuration Consistency**
  - **Validates: Requirements 12.2**

- [ ] 17. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 18. Write integration tests
  - [ ]* 18.1 Write end-to-end flow test
    - Test complete flow: authentication → prompt → tool execution → response
    - Verify user context propagation through all layers
    - Verify logs contain user attribution
    - _Requirements: 3.8, 8.6_
  
  - [ ]* 18.2 Write multi-turn conversation test
    - Test conversation with multiple turns
    - Verify context is maintained across turns
    - Verify session management
    - _Requirements: 13.5_
  
  - [ ]* 18.3 Write error handling integration test
    - Test various error scenarios end-to-end
    - Verify error messages are user-friendly
    - Verify errors are logged with user context
    - _Requirements: 11.2_

- [ ] 19. Write infrastructure validation tests
  - [ ] 19.1 Verify CloudFormation resources exist after deployment
    - Verify AgentCore Gateway exists
    - Verify AgentCore Memory exists
    - Verify Gateway Targets exist
    - Verify Interceptor Lambda exists
    - Verify Agent Lambda exists
    - Verify IAM roles exist
    - _Requirements: 9.2, 9.3, 9.4, 9.6, 9.8, 9.9_
  
  - [ ] 19.2 Verify Interceptor is attached to Gateway
    - Verify Gateway Interceptor attachment exists
    - Verify Gateway has permission to invoke Interceptor
    - _Requirements: 9.7, 4.2, 4.9_
  
  - [ ] 19.3 Verify Agent Lambda is not in VPC
    - Verify Lambda VPC configuration is empty
    - _Requirements: 9.10_
  
  - [ ] 19.4 Verify OpenAPI target configurations
    - Verify multiple targets can be configured
    - Verify inline and URL-based specs work
    - _Requirements: 5.2, 5.10, 12.6_

- [ ] 20. Write round-trip property test
  - [ ]* 20.1 Write user context round-trip integrity test
    - **Property 48: User Context Round-Trip Integrity**
    - **Validates: Requirements 3.8**
    - Test that user context extracted from JWT remains identical through Agent → Gateway → Interceptor → OpenAPI headers

- [ ] 21. Write additional property tests for remaining properties
  - [ ]* 21.1 Write property test for OpenAPI response parsing
    - **Property 21: OpenAPI Response Parsing**
    - **Validates: Requirements 6.9**
  
  - [ ]* 21.2 Write property test for rate limiting backoff
    - **Property 34: Rate Limiting Backoff Strategy**
    - **Validates: Requirements 11.9**
  
  - [ ]* 21.3 Write property test for user context in OpenAPI requests
    - **Property 7: User Context in OpenAPI Requests**
    - **Validates: Requirements 3.7, 5.7, 6.11**

- [ ] 22. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 23. Create deployment documentation
  - Document CloudFormation deployment steps
  - Document environment-specific configuration
  - Document testing procedures
  - Document monitoring and troubleshooting

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows
- Infrastructure tests validate CloudFormation deployment
- All property tests must be tagged with feature name and property number
