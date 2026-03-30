# CloudFormation Gateway Target Generator

This module provides utilities for generating AWS::BedrockAgentCore::GatewayTarget CloudFormation resources from OpenAPI 3.x specifications.

## Overview

The CloudFormation generator parses OpenAPI specifications and creates Gateway Target resources that can be deployed to AWS. Each operation in the OpenAPI spec becomes a separate Gateway Target with:

- **Three-underscore naming format**: `{TargetName}___{ToolName}`
- **Complete tool schema**: Including name, description, input_schema, and output_schema
- **Lambda target configuration**: Pointing to the Lambda function that implements the operation

## Usage

### Basic Usage

```python
from infrastructure.cloudformation_generator import generate_gateway_targets

# Your OpenAPI specification
openapi_spec = {
    "openapi": "3.0.3",
    "paths": {
        "/weather": {
            "get": {
                "operationId": "getCurrentWeather",
                "summary": "Get current weather",
                "parameters": [
                    {
                        "name": "location",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ]
            }
        }
    }
}

# Generate Gateway Target resources
resources = generate_gateway_targets(
    openapi_spec=openapi_spec,
    gateway_id="!Ref AgentCoreGateway",
    lambda_arn="!GetAtt WeatherAPILambda.Arn",
    target_name="weather-api"
)

# Each resource is a dictionary with CloudFormation resource definition
for resource in resources:
    print(f"Resource: {resource['LogicalId']}")
    print(f"Name: {resource['Properties']['Name']}")
```

### Generate CloudFormation YAML

```python
from infrastructure.cloudformation_generator import (
    generate_gateway_targets,
    generate_cloudformation_yaml
)

# Generate resources
resources = generate_gateway_targets(
    openapi_spec=openapi_spec,
    gateway_id="!Ref AgentCoreGateway",
    lambda_arn="!GetAtt WeatherAPILambda.Arn"
)

# Convert to YAML format
yaml_output = generate_cloudformation_yaml(resources)

# Write to file or print
print(yaml_output)
```

### Example Output

The generator produces CloudFormation resources like this:

```yaml
WeatherApiGetCurrentWeatherTarget:
  Type: AWS::BedrockAgentCore::GatewayTarget
  Properties:
    GatewayIdentifier: !Ref AgentCoreGateway
    Name: weather-api___getCurrentWeather
    Description: Get current weather for a location
    TargetConfiguration:
      Mcp:
        Lambda:
          LambdaArn: !GetAtt WeatherAPILambda.Arn
          ToolSchema:
            InlinePayload:
            - Name: getCurrentWeather
              Description: Get current weather for a location
              InputSchema:
                Type: object
                Properties:
                  location:
                    Type: string
                Required:
                - location
              OutputSchema:
                Type: object
```

## API Reference

### `generate_gateway_targets(openapi_spec, gateway_id, lambda_arn, target_name="weather-api")`

Generate CloudFormation Gateway Target resources from OpenAPI specification.

**Parameters:**
- `openapi_spec` (dict): OpenAPI 3.x specification as dictionary
- `gateway_id` (str): AgentCore Gateway identifier (e.g., `!Ref AgentCoreGateway`)
- `lambda_arn` (str): Lambda function ARN (e.g., `!GetAtt WeatherAPILambda.Arn`)
- `target_name` (str, optional): Name prefix for Gateway Targets (default: "weather-api")

**Returns:**
- List[Dict]: List of CloudFormation resource definitions

**Raises:**
- `ValueError`: If OpenAPI spec is invalid or cannot be parsed

### `generate_cloudformation_yaml(resources, indent=2)`

Convert Gateway Target resources to CloudFormation YAML format.

**Parameters:**
- `resources` (List[Dict]): List of Gateway Target resource definitions
- `indent` (int, optional): Number of spaces for indentation (default: 2)

**Returns:**
- str: YAML string for CloudFormation Resources section

## Three-Underscore Naming Format

The generator uses the three-underscore format `{TargetName}___{ToolName}` for Gateway Target names. This format is required by the AgentCore Gateway for tool invocation.

**Examples:**
- `weather-api___getCurrentWeather`
- `weather-api___getForecast`
- `my-api___getUserProfile`

## Schema Conversion

The generator automatically converts OpenAPI schemas to CloudFormation-compatible format:

- **Lowercase to PascalCase**: `type` → `Type`, `properties` → `Properties`
- **Parameter extraction**: Query, path, and header parameters → input schema properties
- **Request body**: Merged into input schema
- **Response schemas**: Extracted from successful responses (200, 201, default)

## Requirements

The generator requires:
- Python 3.8+
- PyYAML (for YAML generation)
- OpenAPI 3.0.x or 3.1.x specifications

## Example Script

Run the example script to see the generator in action:

```bash
python infrastructure/example_usage.py
```

This will generate Gateway Target resources for a sample Weather API and display the CloudFormation YAML output.

## Integration with CloudFormation

To use the generated resources in your CloudFormation template:

1. Generate the resources using the Python API
2. Convert to YAML using `generate_cloudformation_yaml()`
3. Copy the YAML output into your CloudFormation template's Resources section
4. Ensure you have defined the referenced resources (AgentCoreGateway, Lambda functions)
5. Deploy the stack

## Error Handling

The generator validates OpenAPI specifications and provides descriptive error messages:

- **Invalid OpenAPI version**: Only 3.0.x and 3.1.x are supported
- **Missing required fields**: Specification must have `openapi` and `paths` fields
- **No operations found**: At least one operation must be defined
- **Parse errors**: Detailed error messages with operation path and method

## Testing

Run the unit tests to verify the generator:

```bash
pytest tests/unit/test_cloudformation_generator.py -v
```

The test suite includes:
- Single and multiple operation generation
- Three-underscore naming format validation
- Complete tool schema structure verification
- Schema conversion tests
- Error handling tests
- YAML generation tests

## Related Documentation

- [OpenAPI Parser](../src/openapi_parser/README.md)
- [Design Document](../.kiro/specs/openapi-agent-gateway/design.md)
- [Requirements](../.kiro/specs/openapi-agent-gateway/requirements.md)
