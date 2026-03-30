# Requirements Document

## Introduction

The OpenAPI Agent Gateway is a serverless AI agent system that enables natural language interaction with OpenAPI-compliant REST APIs. Building on the proven architecture from the strands-reference implementation, this system replaces S3-specific tool targets with dynamic OpenAPI specification parsing and tool generation. Users authenticate via Cognito JWT, submit natural language prompts to an Agent Lambda powered by Claude/Bedrock, which discovers and invokes tools dynamically generated from OpenAPI specifications through the AgentCore Gateway. An interceptor Lambda extracts user context from JWT tokens and injects it into API requests, enabling complete user attribution and audit trails. The system targets a mock Weather API Gateway as the initial OpenAPI endpoint, demonstrating the pattern for any OpenAPI-compliant service.

## Glossary

- **Agent_Lambda**: AWS Lambda function that processes natural language prompts using Claude/Bedrock and orchestrates tool discovery and execution
- **AgentCore_Gateway**: AWS Bedrock AgentCore Gateway that mediates communication between Agent Lambda and target APIs with JWT validation
- **Interceptor_Lambda**: AWS Lambda function that extracts user identity from JWT tokens and injects user context headers into API requests
- **OpenAPI_Parser**: Component that parses OpenAPI 3.x specifications and generates tool definitions for Claude
- **Tool_Definition**: Claude-compatible schema describing an API operation including name, description, parameters, and response format
- **Gateway_Target**: AWS BedrockAgentCore GatewayTarget resource that represents a single API operation from the OpenAPI spec
- **Mock_Weather_API**: Target API Gateway endpoint providing weather data operations defined by an OpenAPI specification
- **User_Context**: User identity information extracted from JWT including user_id, username, and client_id
- **JWT_Token**: JSON Web Token issued by Cognito for authentication and authorization
- **CloudFormation_Stack**: AWS infrastructure as code template defining all resources in us-east-1 region
- **MCP_Protocol**: Model Context Protocol for standardized tool definitions and invocations

## Requirements

### Requirement 1: Infrastructure Deployment

**User Story:** As a DevOps engineer, I want to deploy the complete infrastructure via CloudFormation, so that I can provision all AWS resources consistently in us-east-1.

#### Acceptance Criteria

1. THE CloudFormation_Stack SHALL create all required AWS resources in us-east-1 region
2. THE CloudFormation_Stack SHALL include AWS::BedrockAgentCore::Gateway with CUSTOM_JWT authorizer type
3. THE CloudFormation_Stack SHALL include AWS::BedrockAgentCore::GatewayTarget resources for each OpenAPI operation
4. THE CloudFormation_Stack SHALL include AWS::BedrockAgentCore::Gateway GatewayInterceptorConfiguration with REQUEST interception point
5. THE CloudFormation_Stack SHALL create Cognito User Pool with JWT token generation
6. THE CloudFormation_Stack SHALL create Agent_Lambda with 512MB memory and 30s timeout
7. THE CloudFormation_Stack SHALL create Interceptor_Lambda with 128MB memory and 5s timeout
8. THE CloudFormation_Stack SHALL create IAM roles with least-privilege permissions for all Lambda functions
9. THE CloudFormation_Stack SHALL configure CloudWatch log groups with 30-day retention
10. THE CloudFormation_Stack SHALL output Gateway ID, Cognito User Pool ID, and Lambda ARNs

### Requirement 2: OpenAPI Specification Parsing

**User Story:** As a developer, I want the system to parse OpenAPI 3.x specifications, so that API operations are automatically converted to Claude-compatible tool definitions.

#### Acceptance Criteria

1. WHEN an OpenAPI 3.x specification is provided, THE OpenAPI_Parser SHALL extract all operation definitions
2. WHEN an operation has a summary field, THE OpenAPI_Parser SHALL use it as the tool description
3. WHEN an operation has parameters, THE OpenAPI_Parser SHALL convert them to Claude input schema format
4. WHEN an operation has a requestBody, THE OpenAPI_Parser SHALL include it in the tool input schema
5. WHEN an operation has response schemas, THE OpenAPI_Parser SHALL include them in the tool output schema
6. THE OpenAPI_Parser SHALL generate unique tool names using format: {operationId} or {method}_{path}
7. WHEN an operation has security requirements, THE OpenAPI_Parser SHALL preserve them in tool metadata
8. IF an OpenAPI specification is invalid, THEN THE OpenAPI_Parser SHALL return descriptive validation errors
9. THE OpenAPI_Parser SHALL support OpenAPI 3.0.x and 3.1.x specification versions
10. FOR ALL valid OpenAPI specifications, parsing then serializing SHALL produce semantically equivalent tool definitions (round-trip property)

### Requirement 3: Cognito JWT Authentication

**User Story:** As a security engineer, I want all API requests authenticated via Cognito JWT tokens, so that only authorized users can invoke the agent.

#### Acceptance Criteria

1. WHEN a request includes a valid JWT token, THE AgentCore_Gateway SHALL validate the token signature
2. WHEN a request includes a valid JWT token, THE AgentCore_Gateway SHALL verify token expiration
3. WHEN a request includes an invalid JWT token, THE AgentCore_Gateway SHALL reject the request with 401 status
4. WHEN a request lacks a JWT token, THE AgentCore_Gateway SHALL reject the request with 401 status
5. THE AgentCore_Gateway SHALL use Cognito JWKS URL for token validation
6. THE AgentCore_Gateway SHALL validate JWT issuer matches Cognito User Pool
7. THE AgentCore_Gateway SHALL validate JWT audience matches Cognito Client ID
8. WHEN JWT validation succeeds, THE AgentCore_Gateway SHALL forward the request to Agent_Lambda
9. THE Agent_Lambda SHALL extract user claims from validated JWT tokens
10. THE Agent_Lambda SHALL include JWT token in all Gateway tool invocation requests

### Requirement 4: Dynamic Tool Discovery

**User Story:** As an AI agent, I want to discover available tools from the OpenAPI specification at runtime, so that I can select appropriate operations for user requests.

#### Acceptance Criteria

1. WHEN Agent_Lambda starts processing a request, THE Agent_Lambda SHALL query AgentCore_Gateway for available tools
2. THE Agent_Lambda SHALL call ListGatewayTargets API to retrieve all configured Gateway_Target resources
3. WHEN Gateway_Target resources exist, THE Agent_Lambda SHALL extract tool schemas from inline payloads
4. THE Agent_Lambda SHALL convert Gateway tool definitions to Claude-compatible format
5. THE Agent_Lambda SHALL use naming format: {TargetName}___{ToolName} for Gateway invocation
6. WHEN no Gateway_Target resources exist, THE Agent_Lambda SHALL return an error indicating no tools available
7. THE Agent_Lambda SHALL cache tool definitions for the duration of a single request
8. THE Agent_Lambda SHALL pass all discovered tools to Claude/Bedrock for tool selection
9. WHEN tool discovery fails, THE Agent_Lambda SHALL log the error and return a user-friendly message
10. FOR ALL discovered tools, the tool schema SHALL include name, description, input_schema, and output_schema

### Requirement 5: Claude Tool Selection and Invocation

**User Story:** As an end user, I want Claude to understand my natural language request and automatically select the correct API operation, so that I don't need to know API details.

#### Acceptance Criteria

1. WHEN Agent_Lambda receives a user prompt, THE Agent_Lambda SHALL invoke Claude/Bedrock with the prompt and available tools
2. THE Agent_Lambda SHALL use model ID: anthropic.claude-3-sonnet-20240229-v1:0
3. WHEN Claude selects a tool, THE Agent_Lambda SHALL extract the tool name and input parameters from Claude's response
4. THE Agent_Lambda SHALL invoke the selected tool through AgentCore_Gateway using the three-underscore naming format
5. WHEN tool invocation succeeds, THE Agent_Lambda SHALL send tool results back to Claude for response formatting
6. WHEN tool invocation fails, THE Agent_Lambda SHALL send error details to Claude for user-friendly error message generation
7. THE Agent_Lambda SHALL support multi-turn conversations where Claude may select multiple tools sequentially
8. WHEN Claude's response is final text, THE Agent_Lambda SHALL return the text to the user
9. THE Agent_Lambda SHALL include user context in all tool invocations
10. THE Agent_Lambda SHALL log all Claude interactions including prompt, tool selection, and response

### Requirement 6: User Context Propagation

**User Story:** As a compliance officer, I want complete user attribution for all API operations, so that I can audit who performed which actions.

#### Acceptance Criteria

1. WHEN AgentCore_Gateway receives a tool invocation request, THE AgentCore_Gateway SHALL invoke Interceptor_Lambda before forwarding to the target
2. THE AgentCore_Gateway SHALL pass the JWT token to Interceptor_Lambda in request headers
3. WHEN Interceptor_Lambda receives a request, THE Interceptor_Lambda SHALL decode the JWT token payload
4. THE Interceptor_Lambda SHALL extract user_id from the 'sub' claim
5. THE Interceptor_Lambda SHALL extract username from the 'username' claim
6. THE Interceptor_Lambda SHALL extract client_id from the 'client_id' claim
7. THE Interceptor_Lambda SHALL inject user context as HTTP headers: X-User-Id, X-Username, X-Client-Id
8. WHEN user context extraction succeeds, THE Interceptor_Lambda SHALL return transformed request with added headers
9. WHEN user context extraction fails, THE Interceptor_Lambda SHALL log the error and return the original request unchanged
10. THE Interceptor_Lambda SHALL complete processing within 5 seconds

### Requirement 7: Mock Weather API Integration

**User Story:** As a developer, I want to test the system against a mock Weather API, so that I can validate the OpenAPI integration pattern without external dependencies.

#### Acceptance Criteria

1. THE CloudFormation_Stack SHALL create an API Gateway for the Mock_Weather_API
2. THE Mock_Weather_API SHALL implement at least two operations: getCurrentWeather and getForecast
3. THE Mock_Weather_API SHALL provide an OpenAPI 3.x specification document
4. WHEN getCurrentWeather is invoked with a location parameter, THE Mock_Weather_API SHALL return current weather data
5. WHEN getForecast is invoked with location and days parameters, THE Mock_Weather_API SHALL return forecast data
6. THE Mock_Weather_API SHALL validate that requests include X-User-Id, X-Username, and X-Client-Id headers
7. THE Mock_Weather_API SHALL log all received user context headers for audit verification
8. WHEN user context headers are missing, THE Mock_Weather_API SHALL return 400 status with error message
9. THE Mock_Weather_API SHALL return responses matching the OpenAPI specification schema
10. THE Mock_Weather_API SHALL be accessible only from the AgentCore_Gateway via IAM authorization

### Requirement 8: Error Handling and Logging

**User Story:** As a site reliability engineer, I want comprehensive error handling and logging, so that I can troubleshoot issues and monitor system health.

#### Acceptance Criteria

1. WHEN any Lambda function encounters an error, THE Lambda SHALL log structured error details to CloudWatch
2. THE Agent_Lambda SHALL log all requests including user_id, prompt length, and timestamp
3. THE Interceptor_Lambda SHALL log all transformations including original and transformed requests
4. WHEN JWT validation fails, THE AgentCore_Gateway SHALL log the failure reason
5. WHEN tool invocation fails, THE Agent_Lambda SHALL log the error and return a user-friendly message
6. WHEN OpenAPI parsing fails, THE OpenAPI_Parser SHALL log validation errors with line numbers
7. THE CloudFormation_Stack SHALL create CloudWatch alarms for Lambda errors exceeding 5 per 5 minutes
8. THE CloudFormation_Stack SHALL create CloudWatch alarms for Lambda duration exceeding 80% of timeout
9. ALL log messages SHALL include request_id for correlation across services
10. WHEN an error occurs, THE system SHALL return appropriate HTTP status codes: 400 for client errors, 401 for auth errors, 500 for server errors

### Requirement 9: Reusable Pattern Architecture

**User Story:** As a solutions architect, I want the OpenAPI integration pattern to be reusable for other APIs, so that I can extend the system to additional services.

#### Acceptance Criteria

1. THE OpenAPI_Parser SHALL be implemented as a standalone module independent of the Weather API
2. THE CloudFormation_Stack SHALL use parameters for OpenAPI specification URL
3. THE Agent_Lambda SHALL discover tools dynamically without hardcoded API-specific logic
4. THE Interceptor_Lambda SHALL inject user context headers without API-specific transformations
5. WHEN a new OpenAPI specification is provided, THE system SHALL generate Gateway_Target resources automatically
6. THE system SHALL support multiple OpenAPI specifications simultaneously
7. THE system SHALL namespace tools by API name to avoid naming conflicts
8. THE documentation SHALL include a guide for adding new OpenAPI-based APIs
9. THE CloudFormation_Stack SHALL support stack parameters for environment-specific configuration
10. THE system architecture SHALL separate concerns: authentication, tool discovery, tool execution, and API invocation

### Requirement 10: End-to-End Testing

**User Story:** As a quality assurance engineer, I want automated end-to-end tests, so that I can verify the complete flow from user prompt to API response.

#### Acceptance Criteria

1. THE test suite SHALL include an end-to-end test script that validates the complete flow
2. THE test SHALL authenticate with Cognito and obtain a valid JWT token
3. THE test SHALL invoke Agent_Lambda with a natural language prompt: "What's the weather in Seattle?"
4. THE test SHALL verify Agent_Lambda discovers weather API tools from the Gateway
5. THE test SHALL verify Claude selects the getCurrentWeather tool
6. THE test SHALL verify the tool is invoked through AgentCore_Gateway
7. THE test SHALL verify Interceptor_Lambda adds user context headers
8. THE test SHALL verify Mock_Weather_API receives the request with user context headers
9. THE test SHALL verify the response includes weather data formatted by Claude
10. THE test SHALL verify all CloudWatch logs contain user_id for audit trail validation
