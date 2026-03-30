"""Unit tests for CloudFormation template validation."""

import yaml
import pytest
from pathlib import Path


# Add CloudFormation intrinsic function constructors
def cloudformation_constructor(loader, tag_suffix, node):
    """Handle CloudFormation intrinsic functions like !Ref, !GetAtt, etc."""
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return None


# Register CloudFormation intrinsic functions
yaml.add_multi_constructor('!', cloudformation_constructor, Loader=yaml.SafeLoader)


@pytest.fixture
def cloudformation_template():
    """Load CloudFormation template."""
    template_path = Path(__file__).parent.parent.parent / 'infrastructure' / 'cloudformation-template.yaml'
    with open(template_path, 'r') as f:
        return yaml.safe_load(f)


class TestCloudFormationTemplate:
    """Test CloudFormation template structure and content."""
    
    def test_template_has_required_sections(self, cloudformation_template):
        """Test that template has all required sections."""
        assert 'AWSTemplateFormatVersion' in cloudformation_template
        assert 'Description' in cloudformation_template
        assert 'Parameters' in cloudformation_template
        assert 'Resources' in cloudformation_template
        assert 'Outputs' in cloudformation_template
    
    def test_template_has_lambda_functions(self, cloudformation_template):
        """Test that template defines all Lambda functions."""
        resources = cloudformation_template['Resources']
        
        # Check Lambda functions exist
        assert 'AgentLambda' in resources
        assert 'InterceptorLambda' in resources
        assert 'WeatherAPILambda' in resources
        
        # Check Lambda function types
        assert resources['AgentLambda']['Type'] == 'AWS::Lambda::Function'
        assert resources['InterceptorLambda']['Type'] == 'AWS::Lambda::Function'
        assert resources['WeatherAPILambda']['Type'] == 'AWS::Lambda::Function'
    
    def test_agent_lambda_configuration(self, cloudformation_template):
        """Test Agent Lambda configuration."""
        agent_lambda = cloudformation_template['Resources']['AgentLambda']
        props = agent_lambda['Properties']
        
        # Check memory and timeout
        assert props['MemorySize'] == 512
        assert props['Timeout'] == 30
        
        # Check environment variables
        env_vars = props['Environment']['Variables']
        assert 'COGNITO_JWKS_URL' in env_vars
        assert 'GATEWAY_ID' in env_vars
        assert 'BEDROCK_MODEL_ID' in env_vars
        assert 'AWS_REGION' in env_vars
        assert 'LOG_LEVEL' in env_vars
        
        # Check model ID
        assert env_vars['BEDROCK_MODEL_ID'] == 'anthropic.claude-3-sonnet-20240229-v1:0'
    
    def test_interceptor_lambda_configuration(self, cloudformation_template):
        """Test Interceptor Lambda configuration."""
        interceptor_lambda = cloudformation_template['Resources']['InterceptorLambda']
        props = interceptor_lambda['Properties']
        
        # Check memory and timeout
        assert props['MemorySize'] == 128
        assert props['Timeout'] == 5
        
        # Check environment variables
        env_vars = props['Environment']['Variables']
        assert 'LOG_LEVEL' in env_vars
    
    def test_weather_api_lambda_configuration(self, cloudformation_template):
        """Test Weather API Lambda configuration."""
        weather_lambda = cloudformation_template['Resources']['WeatherAPILambda']
        props = weather_lambda['Properties']
        
        # Check memory and timeout
        assert props['MemorySize'] == 256
        assert props['Timeout'] == 10
        
        # Check environment variables
        env_vars = props['Environment']['Variables']
        assert 'LOG_LEVEL' in env_vars
    
    def test_gateway_target_exists(self, cloudformation_template):
        """Test that WeatherAPITarget Gateway Target exists."""
        resources = cloudformation_template['Resources']
        
        assert 'WeatherAPITarget' in resources
        assert resources['WeatherAPITarget']['Type'] == 'AWS::BedrockAgentCore::GatewayTarget'
    
    def test_gateway_target_has_both_operations(self, cloudformation_template):
        """Test that Gateway Target includes both weather operations."""
        weather_target = cloudformation_template['Resources']['WeatherAPITarget']
        tool_schema = weather_target['Properties']['TargetConfiguration']['Mcp']['Lambda']['ToolSchema']
        inline_payload = tool_schema['InlinePayload']
        
        # Check we have 2 tools
        assert len(inline_payload) == 2
        
        # Check tool names
        tool_names = [tool['Name'] for tool in inline_payload]
        assert 'getCurrentWeather' in tool_names
        assert 'getForecast' in tool_names
    
    def test_get_current_weather_tool_schema(self, cloudformation_template):
        """Test getCurrentWeather tool schema structure."""
        weather_target = cloudformation_template['Resources']['WeatherAPITarget']
        inline_payload = weather_target['Properties']['TargetConfiguration']['Mcp']['Lambda']['ToolSchema']['InlinePayload']
        
        # Find getCurrentWeather tool
        current_weather = next(tool for tool in inline_payload if tool['Name'] == 'getCurrentWeather')
        
        # Check description
        assert current_weather['Description'] == 'Get current weather for a location'
        
        # Check input schema
        input_schema = current_weather['InputSchema']
        assert input_schema['Type'] == 'object'
        assert 'location' in input_schema['Properties']
        assert 'user_context' in input_schema['Properties']
        assert 'location' in input_schema['Required']
        assert 'user_context' in input_schema['Required']
        
        # Check user_context structure
        user_context = input_schema['Properties']['user_context']
        assert user_context['Type'] == 'object'
        assert 'user_id' in user_context['Properties']
        assert 'username' in user_context['Properties']
        assert 'client_id' in user_context['Properties']
        
        # Check output schema
        output_schema = current_weather['OutputSchema']
        assert output_schema['Type'] == 'object'
        assert 'location' in output_schema['Properties']
        assert 'temperature' in output_schema['Properties']
        assert 'conditions' in output_schema['Properties']
        assert 'humidity' in output_schema['Properties']
        assert 'wind_speed' in output_schema['Properties']
        assert 'user_context' in output_schema['Properties']
    
    def test_get_forecast_tool_schema(self, cloudformation_template):
        """Test getForecast tool schema structure."""
        weather_target = cloudformation_template['Resources']['WeatherAPITarget']
        inline_payload = weather_target['Properties']['TargetConfiguration']['Mcp']['Lambda']['ToolSchema']['InlinePayload']
        
        # Find getForecast tool
        forecast = next(tool for tool in inline_payload if tool['Name'] == 'getForecast')
        
        # Check description
        assert forecast['Description'] == 'Get weather forecast for a location'
        
        # Check input schema
        input_schema = forecast['InputSchema']
        assert input_schema['Type'] == 'object'
        assert 'location' in input_schema['Properties']
        assert 'days' in input_schema['Properties']
        assert 'user_context' in input_schema['Properties']
        assert 'location' in input_schema['Required']
        assert 'days' in input_schema['Required']
        assert 'user_context' in input_schema['Required']
        
        # Check days parameter constraints
        days_param = input_schema['Properties']['days']
        assert days_param['Type'] == 'integer'
        assert days_param['Minimum'] == 1
        assert days_param['Maximum'] == 10
        
        # Check output schema
        output_schema = forecast['OutputSchema']
        assert output_schema['Type'] == 'object'
        assert 'location' in output_schema['Properties']
        assert 'days' in output_schema['Properties']
        assert 'forecast' in output_schema['Properties']
        assert 'user_context' in output_schema['Properties']
        
        # Check forecast array structure
        forecast_array = output_schema['Properties']['forecast']
        assert forecast_array['Type'] == 'array'
        assert 'Items' in forecast_array
        assert forecast_array['Items']['Type'] == 'object'
        
        # Check daily forecast properties
        daily_forecast = forecast_array['Items']
        assert 'date' in daily_forecast['Properties']
        assert 'high' in daily_forecast['Properties']
        assert 'low' in daily_forecast['Properties']
        assert 'conditions' in daily_forecast['Properties']
    
    def test_cloudwatch_log_groups(self, cloudformation_template):
        """Test that CloudWatch log groups are configured."""
        resources = cloudformation_template['Resources']
        
        assert 'AgentLambdaLogGroup' in resources
        assert 'InterceptorLambdaLogGroup' in resources
        assert 'WeatherAPILambdaLogGroup' in resources
        
        # Check retention
        for log_group in ['AgentLambdaLogGroup', 'InterceptorLambdaLogGroup', 'WeatherAPILambdaLogGroup']:
            assert resources[log_group]['Properties']['RetentionInDays'] == 30
    
    def test_cloudwatch_alarms(self, cloudformation_template):
        """Test that CloudWatch alarms are configured."""
        resources = cloudformation_template['Resources']
        
        # Check Agent Lambda alarms
        assert 'AgentLambdaErrorAlarm' in resources
        assert 'AgentLambdaDurationAlarm' in resources
        assert 'AgentLambdaThrottleAlarm' in resources
        
        # Check Weather API Lambda alarms
        assert 'WeatherAPILambdaErrorAlarm' in resources
        assert 'WeatherAPILambdaDurationAlarm' in resources
        
        # Check error alarm threshold
        error_alarm = resources['AgentLambdaErrorAlarm']
        assert error_alarm['Properties']['Threshold'] == 5
        
        # Check duration alarm threshold (80% of 30s = 24s = 24000ms)
        duration_alarm = resources['AgentLambdaDurationAlarm']
        assert duration_alarm['Properties']['Threshold'] == 24000
    
    def test_cognito_configuration(self, cloudformation_template):
        """Test Cognito User Pool configuration."""
        resources = cloudformation_template['Resources']
        
        assert 'CognitoUserPool' in resources
        assert 'CognitoUserPoolClient' in resources
        
        # Check User Pool properties
        user_pool = resources['CognitoUserPool']
        assert user_pool['Type'] == 'AWS::Cognito::UserPool'
        
        # Check User Pool Client properties
        client = resources['CognitoUserPoolClient']
        assert client['Type'] == 'AWS::Cognito::UserPoolClient'
        assert 'ALLOW_USER_PASSWORD_AUTH' in client['Properties']['ExplicitAuthFlows']
    
    def test_gateway_configuration(self, cloudformation_template):
        """Test AgentCore Gateway configuration."""
        resources = cloudformation_template['Resources']
        
        assert 'AgentCoreGateway' in resources
        gateway = resources['AgentCoreGateway']
        
        # Check type
        assert gateway['Type'] == 'AWS::BedrockAgentCore::Gateway'
        
        # Check authorizer type
        assert gateway['Properties']['AuthorizerType'] == 'CUSTOM_JWT'
        
        # Check protocol type
        assert gateway['Properties']['ProtocolType'] == 'MCP'
        
        # Check interceptor configuration
        interceptor_configs = gateway['Properties']['InterceptorConfigurations']
        assert len(interceptor_configs) == 1
        assert 'REQUEST' in interceptor_configs[0]['InterceptionPoints']
    
    def test_stack_outputs(self, cloudformation_template):
        """Test that stack outputs are defined."""
        outputs = cloudformation_template['Outputs']
        
        # Check all required outputs exist
        assert 'GatewayId' in outputs
        assert 'CognitoUserPoolId' in outputs
        assert 'CognitoClientId' in outputs
        assert 'AgentLambdaArn' in outputs
        assert 'InterceptorLambdaArn' in outputs
        assert 'WeatherAPILambdaArn' in outputs
