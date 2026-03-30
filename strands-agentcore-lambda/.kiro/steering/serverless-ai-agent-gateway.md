# Steering Document: Serverless AI Agent Gateway

## Purpose

This steering document provides implementation guidance, coding standards, and best practices for building the Serverless AI Agent Gateway system. It ensures consistency across all components and helps developers avoid common pitfalls when working with AWS Bedrock, AgentCore Gateway, Strands Framework, and related services.

## Architecture Principles

### 1. User Context Propagation is Mandatory

Every component must maintain and propagate user context through the entire request flow:

```python
# GOOD: Always extract and pass user context
user_context = UserContext.from_jwt_claims(jwt_claims)
logger.info("Processing request", extra={
    "user_id": user_context.user_id,
    "username": user_context.username
})

# BAD: Losing user context
logger.info("Processing request")  # No user attribution
```

### 2. Defense in Depth Security

Validate at every layer, don't assume upstream validation:

```python
# GOOD: Validate even if Gateway already validated
if not user_context or not user_context.user_id:
    logger.warning("Missing user context")
    user_context = UserContext(user_id="unknown", username="unknown", client_id="unknown")

# BAD: Assuming user context is always present
result = process_request(user_context.user_id)  # May crash if None
```

### 3. Fail Gracefully, Never Break the Flow

The Gateway Request Interceptor must never break the request flow:

```python
# GOOD: Return original request on error
def lambda_handler(event, context):
    try:
        return transform_request(event)
    except Exception as e:
        logger.error(f"Interceptor error: {e}")
        return event  # Return unchanged

# BAD: Raising exceptions
def lambda_handler(event, context):
    jwt_token = event['headers']['Authorization']  # May crash
    return transform_request(event)
```

## AWS Service Usage Patterns

### Cognito Access Tokens

**CRITICAL**: Always use Cognito access tokens, not ID tokens:

```python
# GOOD: Validate token_use claim
claims = decode_jwt(token)
if claims.get('token_use') != 'access':
    raise ValueError("Must use access token, not ID token")

# BAD: Accepting any token type
claims = decode_jwt(token)  # No validation of token type
```

### AgentCore Gateway Invocation

Always include JWT in Authorization header:

```python
# GOOD: Include JWT token
response = gateway_client.invoke_tool(
    gatewayId=gateway_id,
    toolName='list-s3-buckets',
    parameters={},
    headers={'Authorization': f'Bearer {jwt_token}'}
)

# BAD: Missing authorization
response = gateway_client.invoke_tool(
    gatewayId=gateway_id,
    toolName='list-s3-buckets',
    parameters={}
)
```

### AgentCore Memory with Session Management

Always associate memory with both user_id and session_id:

```python
# GOOD: User + session scoping
memory_client.put_memory(
    memoryId=memory_id,
    sessionId=session_id,
    userId=user_context.user_id,
    content=conversation_turn
)

# BAD: Missing user or session context
memory_client.put_memory(
    memoryId=memory_id,
    content=conversation_turn
)
```

### Bedrock Model Invocation

Use Claude 3 Sonnet with proper tool definitions:

```python
# GOOD: Pass tool definitions from Gateway
tools = query_gateway_tools(gateway_id, jwt_token)
response = bedrock_client.invoke_model(
    modelId='anthropic.claude-3-sonnet-20240229-v1:0',
    body=json.dumps({
        'messages': messages,
        'tools': tools,
        'max_tokens': 4096
    })
)

# BAD: Hardcoded tools or missing tool definitions
response = bedrock_client.invoke_model(
    modelId='anthropic.claude-3-sonnet-20240229-v1:0',
    body=json.dumps({'messages': messages})
)
```

## Python Code Standards

### Type Hints are Required

All functions must have type hints:

```python
# GOOD: Complete type hints
def validate_jwt(token: str, jwks_url: str) -> dict:
    """Validate JWT token and return claims."""
    pass

# BAD: Missing type hints
def validate_jwt(token, jwks_url):
    pass
```

### Use Dataclasses for Data Models

```python
# GOOD: Structured data with validation
from dataclasses import dataclass

@dataclass
class UserContext:
    user_id: str
    username: str
    client_id: str
    
    def to_dict(self) -> dict:
        return {
            'user_id': self.user_id,
            'username': self.username,
            'client_id': self.client_id
        }

# BAD: Plain dictionaries
user_context = {
    'user_id': user_id,
    'username': username
}
```

### Error Handling Pattern

Always log with context and return user-friendly messages:

```python
# GOOD: Comprehensive error handling
try:
    result = execute_operation()
except ClientError as e:
    error_code = e.response['Error']['Code']
    logger.error(
        f"AWS service error: {error_code}",
        extra={
            "user_id": user_context.user_id,
            "username": user_context.username,
            "error_code": error_code,
            "request_id": context.aws_request_id
        }
    )
    return {
        'statusCode': 500,
        'body': json.dumps({
            'error': get_user_friendly_message(error_code)
        })
    }

# BAD: Generic error handling
try:
    result = execute_operation()
except Exception as e:
    return {'statusCode': 500, 'body': str(e)}
```

### Logging Standards

Use structured logging with user context:

```python
# GOOD: Structured logging with context
logger.info(
    "Tool execution started",
    extra={
        "tool_name": tool_name,
        "user_id": user_context.user_id,
        "username": user_context.username,
        "request_id": request_id,
        "timestamp": datetime.utcnow().isoformat()
    }
)

# BAD: Unstructured logging
logger.info(f"Tool {tool_name} started")
```

**NEVER log sensitive information**:

```python
# GOOD: Log only non-sensitive claims
logger.info("JWT validated", extra={
    "user_id": claims['sub'],
    "username": claims['username']
})

# BAD: Logging full JWT or sensitive data
logger.info(f"JWT token: {jwt_token}")  # NEVER DO THIS
logger.info(f"Claims: {claims}")  # May contain sensitive data
```

## JWT Handling

### JWT Validation Pattern

```python
import jwt
import requests
from jwt.algorithms import RSAAlgorithm

def validate_jwt(token: str, jwks_url: str) -> dict:
    """
    Validate JWT token using JWKS from Cognito.
    
    Args:
        token: JWT access token
        jwks_url: Cognito JWKS URL
        
    Returns:
        Decoded JWT claims
        
    Raises:
        ValueError: If token is invalid
    """
    try:
        # Fetch JWKS
        jwks_response = requests.get(jwks_url, timeout=5)
        jwks_response.raise_for_status()
        jwks = jwks_response.json()
        
        # Get token header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header['kid']
        
        # Find matching key
        key = next((k for k in jwks['keys'] if k['kid'] == kid), None)
        if not key:
            raise ValueError("Key not found in JWKS")
        
        # Construct public key
        public_key = RSAAlgorithm.from_jwk(json.dumps(key))
        
        # Validate token
        claims = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            options={'verify_exp': True}
        )
        
        # Verify token type
        if claims.get('token_use') != 'access':
            raise ValueError("Must use access token")
        
        return claims
        
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}")
    except Exception as e:
        raise ValueError(f"Token validation failed: {e}")
```

### JWT Claims Extraction

```python
def extract_user_context(claims: dict) -> UserContext:
    """
    Extract user context from JWT claims.
    
    Args:
        claims: Decoded JWT claims
        
    Returns:
        UserContext object
        
    Raises:
        ValueError: If required claims are missing
    """
    required_claims = ['sub', 'username', 'client_id']
    missing = [c for c in required_claims if c not in claims]
    
    if missing:
        raise ValueError(f"Missing required claims: {missing}")
    
    return UserContext(
        user_id=claims['sub'],
        username=claims['username'],
        client_id=claims['client_id']
    )
```

## MCP Protocol Implementation

### JSON-RPC 2.0 Format

All MCP tool requests must follow JSON-RPC 2.0:

```python
# GOOD: Proper JSON-RPC 2.0 format
mcp_request = {
    'jsonrpc': '2.0',
    'method': 'tools/call',
    'params': {
        'name': 'list-s3-buckets',
        'arguments': {
            'user_context': user_context.to_dict()
        }
    },
    'id': str(uuid.uuid4())
}

# BAD: Missing required fields
mcp_request = {
    'method': 'list-s3-buckets',
    'params': {}
}
```

### Tool Response Format

```python
# GOOD: Include user context in response
tool_response = {
    'result': {
        'buckets': bucket_list,
        'user_context': {
            'user_id': user_context.user_id,
            'username': user_context.username
        }
    }
}

# BAD: Missing user attribution
tool_response = {
    'result': {
        'buckets': bucket_list
    }
}
```

## CloudFormation Standards

### Resource Naming Convention

Use consistent naming with environment prefix:

```yaml
# GOOD: Consistent naming
AgentLambda:
  Type: AWS::Lambda::Function
  Properties:
    FunctionName: !Sub '${EnvironmentName}-agent-lambda'

ToolLambda:
  Type: AWS::Lambda::Function
  Properties:
    FunctionName: !Sub '${EnvironmentName}-tool-lambda'

# BAD: Inconsistent naming
AgentLambda:
  Type: AWS::Lambda::Function
  Properties:
    FunctionName: 'my-agent-function'
```

### Gateway Target Inline Schema

Always define Gateway Targets with inline schemas:

```yaml
# GOOD: Inline schema with complete definition
S3ListBucketsTarget:
  Type: AWS::BedrockAgent::GatewayTarget
  Properties:
    GatewayId: !Ref AgentCoreGateway
    TargetName: list-s3-buckets
    TargetType: LAMBDA
    LambdaArn: !GetAtt ToolLambda.Arn
    InlineSchema:
      type: object
      properties:
        toolName:
          type: string
          const: list-s3-buckets
        description:
          type: string
          const: Lists all S3 buckets with creation dates
        parameters:
          type: object
          properties:
            user_context:
              type: object
              properties:
                user_id:
                  type: string
                username:
                  type: string
                client_id:
                  type: string

# BAD: External schema reference
S3ListBucketsTarget:
  Type: AWS::BedrockAgent::GatewayTarget
  Properties:
    GatewayId: !Ref AgentCoreGateway
    SchemaS3Uri: s3://bucket/schema.json  # Don't use external schemas
```

### IAM Permissions

Follow least privilege principle:

```yaml
# GOOD: Specific permissions
ToolLambdaRole:
  Type: AWS::IAM::Role
  Properties:
    Policies:
      - PolicyName: S3ReadOnly
        PolicyDocument:
          Statement:
            - Effect: Allow
              Action:
                - s3:ListAllMyBuckets
                - s3:GetBucketLocation
              Resource: '*'

# BAD: Overly broad permissions
ToolLambdaRole:
  Type: AWS::IAM::Role
  Properties:
    ManagedPolicyArns:
      - arn:aws:iam::aws:policy/AdministratorAccess  # Too broad!
```

### Gateway Interceptor Attachment

```yaml
# GOOD: Attach interceptor to gateway
GatewayInterceptor:
  Type: AWS::BedrockAgent::GatewayInterceptor
  Properties:
    GatewayId: !Ref AgentCoreGateway
    InterceptorType: REQUEST
    LambdaArn: !GetAtt InterceptorLambda.Arn

GatewayInterceptorPermission:
  Type: AWS::Lambda::Permission
  Properties:
    FunctionName: !Ref InterceptorLambda
    Action: lambda:InvokeFunction
    Principal: bedrock.amazonaws.com
    SourceArn: !GetAtt AgentCoreGateway.Arn
```

## Testing Guidelines

### Property-Based Testing

Use Hypothesis for property tests:

```python
from hypothesis import given, strategies as st

# GOOD: Property test with clear validation
@given(
    user_id=st.uuids(),
    username=st.text(min_size=1, max_size=50),
    client_id=st.uuids()
)
def test_user_context_preservation(user_id, username, client_id):
    """Property 3: User context should be preserved through all layers."""
    original = UserContext(
        user_id=str(user_id),
        username=username,
        client_id=str(client_id)
    )
    
    # Simulate passing through layers
    after_agent = pass_through_agent(original)
    after_gateway = pass_through_gateway(after_agent)
    after_interceptor = pass_through_interceptor(after_gateway)
    after_tool = pass_through_tool(after_interceptor)
    
    # Verify unchanged
    assert after_tool.user_id == original.user_id
    assert after_tool.username == original.username
    assert after_tool.client_id == original.client_id
```

### Unit Test Structure

```python
# GOOD: Clear test structure with setup and assertions
def test_jwt_validation_with_valid_token():
    """Test JWT validation succeeds with valid token."""
    # Arrange
    valid_token = create_test_jwt(
        claims={'sub': 'user-123', 'username': 'john', 'client_id': 'app-1'},
        expiry=3600
    )
    jwks_url = 'https://cognito-idp.us-east-1.amazonaws.com/pool/.well-known/jwks.json'
    
    # Act
    claims = validate_jwt(valid_token, jwks_url)
    
    # Assert
    assert claims['sub'] == 'user-123'
    assert claims['username'] == 'john'
    assert claims['token_use'] == 'access'

# BAD: Unclear test without structure
def test_jwt():
    token = "some-token"
    result = validate_jwt(token, "url")
    assert result
```

### Integration Test Pattern

```python
# GOOD: End-to-end integration test
def test_complete_flow_with_user_context():
    """Test complete flow from authentication to tool execution."""
    # 1. Authenticate and get JWT
    jwt_token = authenticate_user('testuser', 'password')
    
    # 2. Submit prompt to Agent
    response = invoke_agent_lambda({
        'headers': {'Authorization': f'Bearer {jwt_token}'},
        'body': json.dumps({'prompt': 'List my S3 buckets'})
    })
    
    # 3. Verify response includes user context
    body = json.loads(response['body'])
    assert body['user_context']['user_id'] is not None
    assert body['user_context']['username'] == 'testuser'
    
    # 4. Verify Tool Lambda logs show user attribution
    tool_logs = get_cloudwatch_logs('/aws/lambda/tool-lambda')
    assert any('user_id' in log and 'testuser' in log for log in tool_logs)
```

## Common Pitfalls to Avoid

### 1. VPC Attachment

**DON'T** attach Agent Lambda or Tool Lambda to VPC:

```yaml
# GOOD: No VPC configuration
AgentLambda:
  Type: AWS::Lambda::Function
  Properties:
    FunctionName: agent-lambda
    Runtime: python3.12
    # No VpcConfig

# BAD: VPC attachment blocks Cognito JWKS access
AgentLambda:
  Type: AWS::Lambda::Function
  Properties:
    FunctionName: agent-lambda
    VpcConfig:  # DON'T DO THIS
      SubnetIds: [!Ref Subnet1]
      SecurityGroupIds: [!Ref SecurityGroup]
```

### 2. Token Type Confusion

**DON'T** use ID tokens for API authorization:

```python
# GOOD: Verify access token
if claims.get('token_use') != 'access':
    raise ValueError("Must use access token")

# BAD: Accepting ID tokens
# ID tokens are for user identity, not API authorization
```

### 3. Missing User Context

**DON'T** forget to extract user context from Interceptor-added parameters:

```python
# GOOD: Extract user_context from parameters
def lambda_handler(event, context):
    parameters = event.get('parameters', {})
    user_context_dict = parameters.get('user_context', {})
    user_context = UserContext(
        user_id=user_context_dict.get('user_id', 'unknown'),
        username=user_context_dict.get('username', 'unknown'),
        client_id=user_context_dict.get('client_id', 'unknown')
    )

# BAD: Ignoring user_context
def lambda_handler(event, context):
    # Process without user context
    result = execute_tool()
```

### 4. Hardcoded Tool Definitions

**DON'T** hardcode tool definitions in Agent Lambda:

```python
# GOOD: Query Gateway for tools
tools = query_gateway_tools(gateway_id, jwt_token)

# BAD: Hardcoded tools
tools = [
    {'name': 'list-s3-buckets', 'description': '...'}
]
```

### 5. Synchronous Retry Without Backoff

**DON'T** retry immediately without backoff:

```python
# GOOD: Exponential backoff
import time

def retry_with_backoff(func, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            return func()
        except TransientError:
            if attempt < max_attempts - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(wait_time)
            else:
                raise

# BAD: Immediate retry
for attempt in range(3):
    try:
        return func()
    except TransientError:
        continue  # No backoff
```

## Security Best Practices

### 1. Never Log Sensitive Data

```python
# GOOD: Log only non-sensitive information
logger.info("Request processed", extra={
    "user_id": user_context.user_id,
    "request_id": request_id
})

# BAD: Logging sensitive data
logger.info(f"JWT: {jwt_token}")  # NEVER
logger.info(f"Full claims: {claims}")  # May contain sensitive data
logger.info(f"Password: {password}")  # NEVER
```

### 2. Generic Error Messages

```python
# GOOD: Generic error message
if not authenticate(username, password):
    return {'error': 'Invalid credentials'}

# BAD: Specific error message
if not user_exists(username):
    return {'error': 'User not found'}  # Reveals user existence
if not password_matches(username, password):
    return {'error': 'Invalid password'}  # Reveals username is valid
```

### 3. Validate All Inputs

```python
# GOOD: Input validation
def process_request(prompt: str, session_id: Optional[str]) -> dict:
    if not prompt or len(prompt) > 10000:
        raise ValueError("Invalid prompt length")
    
    if session_id and not is_valid_uuid(session_id):
        raise ValueError("Invalid session ID format")
    
    # Process request

# BAD: No validation
def process_request(prompt, session_id):
    # Directly use inputs without validation
    result = execute(prompt)
```

## Performance Optimization

### 1. Cache JWKS Keys

```python
# GOOD: Cache JWKS with TTL
from functools import lru_cache
import time

@lru_cache(maxsize=1)
def get_jwks_with_cache(jwks_url: str, cache_time: int = 3600):
    """Cache JWKS for 1 hour."""
    jwks = requests.get(jwks_url).json()
    return jwks, time.time()

def get_jwks(jwks_url: str):
    jwks, cached_at = get_jwks_with_cache(jwks_url)
    if time.time() - cached_at > 3600:
        get_jwks_with_cache.cache_clear()
        jwks, _ = get_jwks_with_cache(jwks_url)
    return jwks

# BAD: Fetch JWKS on every request
def get_jwks(jwks_url: str):
    return requests.get(jwks_url).json()
```

### 2. Limit Memory Context Size

```python
# GOOD: Limit context retrieval
def get_conversation_context(session_id: str, user_id: str, max_turns: int = 10):
    """Retrieve limited conversation context."""
    context = memory_client.get_memory(
        memoryId=memory_id,
        sessionId=session_id,
        userId=user_id
    )
    
    # Limit to recent turns
    if len(context['turns']) > max_turns:
        context['turns'] = context['turns'][-max_turns:]
    
    return context

# BAD: Retrieve entire conversation history
def get_conversation_context(session_id: str, user_id: str):
    return memory_client.get_memory(
        memoryId=memory_id,
        sessionId=session_id,
        userId=user_id
    )  # May return thousands of turns
```

### 3. Parallel Tool Execution

```python
# GOOD: Execute independent tools in parallel
import asyncio

async def execute_tools_parallel(tools: List[ToolRequest]):
    tasks = [execute_tool_async(tool) for tool in tools]
    results = await asyncio.gather(*tasks)
    return results

# BAD: Sequential execution
def execute_tools_sequential(tools: List[ToolRequest]):
    results = []
    for tool in tools:
        results.append(execute_tool(tool))  # Slow
    return results
```

## Deployment Checklist

Before deploying to production:

- [ ] All Lambda functions have appropriate timeout values
- [ ] All Lambda functions have appropriate memory allocation
- [ ] CloudWatch log retention is configured (30 days recommended)
- [ ] IAM roles follow least privilege principle
- [ ] Gateway Targets use inline schemas
- [ ] Gateway Interceptor is attached to Gateway
- [ ] Cognito User Pool is configured for access tokens
- [ ] All environment variables are set correctly
- [ ] CloudFormation stack has proper tags
- [ ] Monitoring and alarms are configured
- [ ] Integration tests pass in test environment
- [ ] Property-based tests pass with 1000+ iterations
- [ ] Security scan completed (no high/critical vulnerabilities)
- [ ] Documentation is up to date

## Monitoring and Observability

### CloudWatch Metrics

Track these custom metrics:

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

# Track user requests
cloudwatch.put_metric_data(
    Namespace='ServerlessAIAgent',
    MetricData=[{
        'MetricName': 'UserRequests',
        'Value': 1,
        'Unit': 'Count',
        'Dimensions': [
            {'Name': 'UserId', 'Value': user_context.user_id},
            {'Name': 'Component', 'Value': 'Agent'}
        ]
    }]
)

# Track tool execution time
cloudwatch.put_metric_data(
    Namespace='ServerlessAIAgent',
    MetricData=[{
        'MetricName': 'ToolExecutionTime',
        'Value': execution_time_ms,
        'Unit': 'Milliseconds',
        'Dimensions': [
            {'Name': 'ToolName', 'Value': tool_name},
            {'Name': 'UserId', 'Value': user_context.user_id}
        ]
    }]
)
```

### CloudWatch Alarms

Set up alarms for:

- Lambda error rate > 5%
- Lambda duration > 25 seconds (Agent) or > 8 seconds (Tool)
- Gateway 4xx/5xx error rate > 10%
- JWT validation failures > 20 per minute
- Tool execution failures > 10 per minute

### Log Insights Queries

Useful queries for troubleshooting:

```
# Find all requests for a specific user
fields @timestamp, @message
| filter user_id = "user-123"
| sort @timestamp desc

# Find all errors with user context
fields @timestamp, user_id, username, error
| filter @message like /ERROR/
| sort @timestamp desc

# Track tool execution times
fields @timestamp, tool_name, execution_time_ms, user_id
| filter tool_name = "list-s3-buckets"
| stats avg(execution_time_ms), max(execution_time_ms) by user_id
```

## Troubleshooting Guide

### Issue: "Invalid authentication token"

**Possible causes**:
1. Using ID token instead of access token
2. Token expired
3. JWKS URL incorrect
4. Token signature invalid

**Debug steps**:
```python
# Decode token without verification to inspect
import jwt
claims = jwt.decode(token, options={"verify_signature": False})
print(f"Token type: {claims.get('token_use')}")  # Should be 'access'
print(f"Expiry: {claims.get('exp')}")
print(f"Issuer: {claims.get('iss')}")
```

### Issue: Tool Lambda shows user_id as "unknown"

**Possible causes**:
1. Gateway Interceptor not attached
2. Interceptor failing silently
3. JWT missing from Gateway request

**Debug steps**:
1. Check Interceptor CloudWatch logs
2. Verify Interceptor is attached to Gateway in CloudFormation
3. Verify Agent includes JWT in Authorization header
4. Check Gateway has permission to invoke Interceptor

### Issue: "Service temporarily unavailable"

**Possible causes**:
1. Gateway unreachable
2. Bedrock throttling
3. Lambda timeout
4. Network connectivity

**Debug steps**:
1. Check CloudWatch logs for specific error
2. Verify Gateway endpoint is correct
3. Check Lambda timeout configuration
4. Review retry logic and backoff

## References

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [AgentCore Gateway Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-gateway.html)
- [Strands Framework Documentation](https://github.com/awslabs/strands)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Cognito JWT Validation](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html)
- [Hypothesis Property Testing](https://hypothesis.readthedocs.io/)

---

**Document Version**: 1.0  
**Last Updated**: 2026-02-15  
**Maintained By**: Development Team
