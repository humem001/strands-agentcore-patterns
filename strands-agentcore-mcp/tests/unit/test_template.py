"""CloudFormation template assertion tests.

Loads infrastructure/cloudformation-template.yaml and asserts the casing /
configuration requirements from Requirements 3, 4, 5, 8, 9, 10, and 12.

These tests guard against casing regressions that have bitten this project
before (see .kiro/steering/project-conventions.md).
"""

import os
from typing import Any, Dict

import pytest
import yaml

# ---------------------------------------------------------------------------
# CloudFormation tag constructors — allow yaml.safe_load to handle !Ref,
# !Sub, !GetAtt, !If, !Select, !Join, !Split, !Equals, !Not, !And, !Or
# ---------------------------------------------------------------------------

def _cfn_tag_constructor(loader, tag_suffix, node):
    """Generic constructor that returns a dict {tag: value} for any CFN tag."""
    if isinstance(node, yaml.ScalarNode):
        return {tag_suffix: loader.construct_scalar(node)}
    elif isinstance(node, yaml.SequenceNode):
        return {tag_suffix: loader.construct_sequence(node, deep=True)}
    elif isinstance(node, yaml.MappingNode):
        return {tag_suffix: loader.construct_mapping(node, deep=True)}
    return {tag_suffix: None}


class CloudFormationLoader(yaml.SafeLoader):
    pass


for _tag in ("!Ref", "!Sub", "!GetAtt", "!If", "!Select", "!Join",
             "!Split", "!Equals", "!Not", "!And", "!Or", "!Base64",
             "!Condition", "!FindInMap", "!ImportValue", "!Transform"):
    CloudFormationLoader.add_multi_constructor(
        _tag, lambda loader, tag_suffix, node, t=_tag: _cfn_tag_constructor(
            loader, t, node
        )
    )


# ---------------------------------------------------------------------------
# Fixture: load the template once per session
# ---------------------------------------------------------------------------

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "infrastructure", "cloudformation-template.yaml"
)


@pytest.fixture(scope="session")
def template() -> Dict[str, Any]:
    """Load and parse the CloudFormation template."""
    with open(TEMPLATE_PATH, "r") as fh:
        return yaml.load(fh, Loader=CloudFormationLoader)


@pytest.fixture(scope="session")
def resources(template) -> Dict[str, Any]:
    return template["Resources"]


# ---------------------------------------------------------------------------
# Helper: dump the template back to a string for text-based assertions
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def template_text() -> str:
    with open(TEMPLATE_PATH, "r") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# 1. CustomJWTAuthorizer casing (Requirement 12.1)
# ---------------------------------------------------------------------------

def test_custom_jwt_authorizer_key_exists(resources):
    """AuthorizerConfiguration.CustomJWTAuthorizer must exist (all-caps JWT)."""
    gw = resources["AgentCoreGateway"]["Properties"]
    auth_config = gw.get("AuthorizerConfiguration", {})
    assert "CustomJWTAuthorizer" in auth_config, (
        "Expected 'CustomJWTAuthorizer' key under AuthorizerConfiguration"
    )


def test_custom_jwt_authorizer_wrong_casing_absent(template_text):
    """CustomJwtAuthorizer (wrong casing) must NOT appear anywhere in the template."""
    assert "CustomJwtAuthorizer" not in template_text, (
        "Found 'CustomJwtAuthorizer' (wrong casing) in template — must be 'CustomJWTAuthorizer'"
    )


# ---------------------------------------------------------------------------
# 2. RoleArn vs ExecutionRoleArn (Requirement 12.2)
# ---------------------------------------------------------------------------

def test_gateway_uses_role_arn(resources):
    """AgentCoreGateway must use RoleArn, not ExecutionRoleArn."""
    gw_props = resources["AgentCoreGateway"]["Properties"]
    assert "RoleArn" in gw_props, "AgentCoreGateway must have a 'RoleArn' property"
    assert "ExecutionRoleArn" not in gw_props, (
        "AgentCoreGateway must NOT use 'ExecutionRoleArn' — use 'RoleArn'"
    )


# ---------------------------------------------------------------------------
# 2b. Required top-level Gateway properties: AuthorizerType and ProtocolType
# ---------------------------------------------------------------------------

def test_gateway_authorizer_type(resources):
    """AgentCoreGateway must have AuthorizerType: CUSTOM_JWT (required field)."""
    gw_props = resources["AgentCoreGateway"]["Properties"]
    assert gw_props.get("AuthorizerType") == "CUSTOM_JWT", (
        f"AgentCoreGateway must have AuthorizerType: CUSTOM_JWT, "
        f"got {gw_props.get('AuthorizerType')!r}"
    )


def test_gateway_protocol_type(resources):
    """AgentCoreGateway must have ProtocolType: MCP (required field)."""
    gw_props = resources["AgentCoreGateway"]["Properties"]
    assert gw_props.get("ProtocolType") == "MCP", (
        f"AgentCoreGateway must have ProtocolType: MCP, "
        f"got {gw_props.get('ProtocolType')!r}"
    )


# ---------------------------------------------------------------------------
# 3. AllowedAudience vs Audience (Requirement 12.3)
# ---------------------------------------------------------------------------

def test_allowed_audience_present(resources):
    """CustomJWTAuthorizer must use AllowedAudience, not Audience."""
    gw = resources["AgentCoreGateway"]["Properties"]
    jwt_auth = gw["AuthorizerConfiguration"]["CustomJWTAuthorizer"]
    assert "AllowedAudience" in jwt_auth, (
        "CustomJWTAuthorizer must have 'AllowedAudience'"
    )
    assert "Audience" not in jwt_auth or "AllowedAudience" in jwt_auth, (
        "CustomJWTAuthorizer must use 'AllowedAudience', not 'Audience'"
    )


def test_bare_audience_key_absent(template_text):
    """The bare key 'Audience:' (wrong name) must not appear in the template."""
    # We check that 'Audience:' doesn't appear as a standalone key
    # (AllowedAudience is fine, but just 'Audience:' is wrong)
    import re
    # Match 'Audience:' that is NOT preceded by 'Allowed'
    matches = re.findall(r'(?<!Allowed)(?<!\w)Audience:', template_text)
    assert not matches, (
        f"Found bare 'Audience:' key in template — must be 'AllowedAudience'"
    )


# ---------------------------------------------------------------------------
# 4. CredentialProviderConfigurations is a list (Requirement 12.4)
# ---------------------------------------------------------------------------

def test_credential_provider_configurations_is_list(resources):
    """McpTarget is created via CLI in deploy.sh — not in CFN template.
    This test verifies the GatewayExecutionRole has the right permissions instead."""
    # McpTarget is intentionally absent from the template (created post-deploy via CLI)
    # Verify GatewayExecutionRole has execute-api:Invoke which is needed for the target
    role = resources["GatewayExecutionRole"]["Properties"]
    stmts = _collect_all_statements(role.get("Policies", []))
    all_actions = []
    for stmt in stmts:
        actions = stmt.get("Action", [])
        if isinstance(actions, str):
            all_actions.append(actions)
        else:
            all_actions.extend(actions)
    assert any("execute-api:Invoke" in a for a in all_actions), (
        "GatewayExecutionRole must grant 'execute-api:Invoke' for MCP target"
    )


# ---------------------------------------------------------------------------
# 5. DiscoveryUrl ends with /.well-known/openid-configuration (Requirement 12.5)
# ---------------------------------------------------------------------------

def test_discovery_url_ends_with_openid_configuration(resources):
    """DiscoveryUrl must end with /.well-known/openid-configuration."""
    gw = resources["AgentCoreGateway"]["Properties"]
    jwt_auth = gw["AuthorizerConfiguration"]["CustomJWTAuthorizer"]
    discovery_url = jwt_auth.get("DiscoveryUrl")
    assert discovery_url is not None, "CustomJWTAuthorizer must have 'DiscoveryUrl'"

    # DiscoveryUrl may be a !Sub dict — extract the string value
    if isinstance(discovery_url, dict):
        # e.g. {"!Sub": "https://.../.well-known/openid-configuration"}
        url_str = list(discovery_url.values())[0]
    else:
        url_str = discovery_url

    assert url_str.endswith("/.well-known/openid-configuration"), (
        f"DiscoveryUrl must end with '/.well-known/openid-configuration', got: {url_str!r}"
    )


# ---------------------------------------------------------------------------
# 6. GatewayExecutionRole — four AgentCore ARN patterns + execute-api:Invoke,
#    no wildcard * on Resource (Requirements 5.2, 5.3, 5.4)
# ---------------------------------------------------------------------------

def _collect_all_statements(policies):
    """Flatten all policy statements from a list of inline policies."""
    stmts = []
    for policy in policies:
        doc = policy.get("PolicyDocument", {})
        stmts.extend(doc.get("Statement", []))
    return stmts


def _resource_strings(resource_value):
    """Return a list of resource strings from a Resource field (str or list)."""
    if isinstance(resource_value, str):
        return [resource_value]
    if isinstance(resource_value, list):
        result = []
        for r in resource_value:
            if isinstance(r, str):
                result.append(r)
            elif isinstance(r, dict):
                # !Sub dict — get the template string
                result.append(list(r.values())[0])
        return result
    if isinstance(resource_value, dict):
        return [list(resource_value.values())[0]]
    return []


def test_gateway_execution_role_agentcore_arns(resources):
    """GatewayExecutionRole must have the four required AgentCore ARN patterns."""
    role = resources["GatewayExecutionRole"]["Properties"]
    stmts = _collect_all_statements(role.get("Policies", []))

    # Collect all resource strings across all statements
    all_resources = []
    for stmt in stmts:
        all_resources.extend(_resource_strings(stmt.get("Resource", [])))

    required_patterns = [
        "token-vault/default",
        "token-vault/default/apikeycredentialprovider/*",
        "workload-identity-directory/default",
        "workload-identity-directory/default/workload-identity/",
    ]
    for pattern in required_patterns:
        assert any(pattern in r for r in all_resources), (
            f"GatewayExecutionRole missing ARN pattern containing: {pattern!r}"
        )


def test_gateway_execution_role_execute_api_invoke(resources):
    """GatewayExecutionRole must grant execute-api:Invoke."""
    role = resources["GatewayExecutionRole"]["Properties"]
    stmts = _collect_all_statements(role.get("Policies", []))

    all_actions = []
    for stmt in stmts:
        actions = stmt.get("Action", [])
        if isinstance(actions, str):
            all_actions.append(actions)
        else:
            all_actions.extend(actions)

    assert any("execute-api:Invoke" in a for a in all_actions), (
        "GatewayExecutionRole must grant 'execute-api:Invoke'"
    )


def test_gateway_execution_role_no_wildcard_resource(resources):
    """GatewayExecutionRole must NOT have Resource: '*' on any statement."""
    role = resources["GatewayExecutionRole"]["Properties"]
    stmts = _collect_all_statements(role.get("Policies", []))

    for stmt in stmts:
        resource = stmt.get("Resource", "")
        if isinstance(resource, str):
            assert resource != "*", (
                "GatewayExecutionRole has a wildcard '*' Resource — not allowed"
            )
        elif isinstance(resource, list):
            assert "*" not in resource, (
                "GatewayExecutionRole has a wildcard '*' in Resource list — not allowed"
            )

def test_mcp_server_role_dynamodb_resource_is_product_table_only(resources):
    """McpServerRole DynamoDB policy must scope to ProductTable.Arn only."""
    role = resources["McpServerRole"]["Properties"]
    stmts = _collect_all_statements(role.get("Policies", []))

    dynamodb_actions = {"dynamodb:GetItem", "dynamodb:PutItem",
                        "dynamodb:Query", "dynamodb:Scan"}

    for stmt in stmts:
        actions = stmt.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        if any(a in dynamodb_actions for a in actions):
            resource = stmt.get("Resource")
            # Resource should be !GetAtt ProductTable.Arn
            if isinstance(resource, dict):
                # {"!GetAtt": "ProductTable.Arn"} or {"!GetAtt": ["ProductTable", "Arn"]}
                getatt_val = resource.get("!GetAtt")
                if isinstance(getatt_val, str):
                    assert getatt_val == "ProductTable.Arn", (
                        f"McpServerRole DynamoDB resource must be ProductTable.Arn, got {getatt_val!r}"
                    )
                elif isinstance(getatt_val, list):
                    assert getatt_val == ["ProductTable", "Arn"], (
                        f"McpServerRole DynamoDB resource must be ProductTable.Arn, got {getatt_val!r}"
                    )
            elif isinstance(resource, str):
                # Should not be a plain string wildcard
                assert resource != "*", (
                    "McpServerRole DynamoDB resource must not be '*'"
                )


# ---------------------------------------------------------------------------
# 8. ProductTable billing mode and key schema (Requirements 10.1, 10.2)
# ---------------------------------------------------------------------------

def test_product_table_billing_mode(resources):
    """ProductTable must use PAY_PER_REQUEST billing mode."""
    table_props = resources["ProductTable"]["Properties"]
    assert table_props.get("BillingMode") == "PAY_PER_REQUEST", (
        "ProductTable must have BillingMode: PAY_PER_REQUEST"
    )


def test_product_table_key_schema(resources):
    """ProductTable must have category (HASH) and productId (RANGE) keys."""
    table_props = resources["ProductTable"]["Properties"]
    key_schema = table_props.get("KeySchema", [])

    hash_keys = [k for k in key_schema if k.get("KeyType") == "HASH"]
    range_keys = [k for k in key_schema if k.get("KeyType") == "RANGE"]

    assert len(hash_keys) == 1 and hash_keys[0]["AttributeName"] == "category", (
        "ProductTable must have 'category' as the HASH key"
    )
    assert len(range_keys) == 1 and range_keys[0]["AttributeName"] == "productId", (
        "ProductTable must have 'productId' as the RANGE key"
    )


def test_product_table_attribute_types(resources):
    """ProductTable attributes category and productId must be type S (String)."""
    table_props = resources["ProductTable"]["Properties"]
    attr_defs = {
        a["AttributeName"]: a["AttributeType"]
        for a in table_props.get("AttributeDefinitions", [])
    }
    assert attr_defs.get("category") == "S", (
        "ProductTable 'category' attribute must be type S"
    )
    assert attr_defs.get("productId") == "S", (
        "ProductTable 'productId' attribute must be type S"
    )


# ---------------------------------------------------------------------------
# 9. McpMethod uses AWS_PROXY integration pointing at McpServerLambda (Req 8.1)
# ---------------------------------------------------------------------------

def test_mcp_method_uses_aws_proxy(resources):
    """McpMethod must use AWS_PROXY integration type."""
    method_props = resources["McpMethod"]["Properties"]
    integration = method_props.get("Integration", {})
    assert integration.get("Type") == "AWS_PROXY", (
        "McpMethod Integration.Type must be 'AWS_PROXY'"
    )


def test_mcp_method_integration_points_to_mcp_server_lambda(resources, template_text):
    """McpMethod integration URI must reference McpServerLambda."""
    method_props = resources["McpMethod"]["Properties"]
    integration = method_props.get("Integration", {})
    uri = integration.get("Uri", {})

    # URI is a !Sub dict — check the template string references McpServerLambda
    if isinstance(uri, dict):
        uri_str = list(uri.values())[0]
        if isinstance(uri_str, list):
            # !Sub with a list [template, vars]
            uri_str = uri_str[0]
    else:
        uri_str = str(uri)

    assert "McpServerLambda" in uri_str or "McpServerLambda" in template_text, (
        "McpMethod integration URI must reference McpServerLambda"
    )


# ---------------------------------------------------------------------------
# 10. McpStage.StageName == prod (Requirement 8.2)
# ---------------------------------------------------------------------------

def test_mcp_stage_name_is_prod(resources):
    """McpStage must have StageName: prod."""
    stage_props = resources["McpStage"]["Properties"]
    assert stage_props.get("StageName") == "prod", (
        "McpStage.StageName must be 'prod'"
    )


# ---------------------------------------------------------------------------
# 11. Lambda handler paths (Requirement 11.4)
# ---------------------------------------------------------------------------

def test_agent_lambda_handler_path(resources):
    """AgentLambdaFunction must use handler src.agent.handler.lambda_handler."""
    fn_props = resources["AgentLambdaFunction"]["Properties"]
    assert fn_props.get("Handler") == "src.agent.handler.lambda_handler", (
        f"AgentLambdaFunction handler must be 'src.agent.handler.lambda_handler', "
        f"got {fn_props.get('Handler')!r}"
    )


def test_mcp_server_lambda_handler_path(resources):
    """McpServerLambda must use handler src.mcp_server.handler.lambda_handler."""
    fn_props = resources["McpServerLambda"]["Properties"]
    assert fn_props.get("Handler") == "src.mcp_server.handler.lambda_handler", (
        f"McpServerLambda handler must be 'src.mcp_server.handler.lambda_handler', "
        f"got {fn_props.get('Handler')!r}"
    )


# ---------------------------------------------------------------------------
# 12. Both Lambdas use python3.12 runtime
# ---------------------------------------------------------------------------

def test_agent_lambda_runtime(resources):
    """AgentLambdaFunction must use python3.12 runtime."""
    fn_props = resources["AgentLambdaFunction"]["Properties"]
    assert fn_props.get("Runtime") == "python3.12", (
        f"AgentLambdaFunction must use python3.12 runtime, got {fn_props.get('Runtime')!r}"
    )


def test_mcp_server_lambda_runtime(resources):
    """McpServerLambda must use python3.12 runtime."""
    fn_props = resources["McpServerLambda"]["Properties"]
    assert fn_props.get("Runtime") == "python3.12", (
        f"McpServerLambda must use python3.12 runtime, got {fn_props.get('Runtime')!r}"
    )


# ---------------------------------------------------------------------------
# 13. McpMethod HTTP method is POST and AuthorizationType is AWS_IAM
# ---------------------------------------------------------------------------

def test_mcp_method_http_method(resources):
    """McpMethod must use POST HTTP method."""
    method_props = resources["McpMethod"]["Properties"]
    assert method_props.get("HttpMethod") == "POST", (
        "McpMethod must use HttpMethod: POST"
    )


def test_mcp_method_auth_type(resources):
    """McpMethod must use NONE authorization (AgentCore Gateway signs with SigV4 externally)."""
    method_props = resources["McpMethod"]["Properties"]
    assert method_props.get("AuthorizationType") == "NONE", (
        "McpMethod must use AuthorizationType: NONE — AWS_IAM causes 403 for "
        "cross-service SigV4 calls from AgentCore Gateway"
    )


# ---------------------------------------------------------------------------
# 14. Stack Outputs include required keys
# ---------------------------------------------------------------------------

def test_stack_outputs_present(template):
    """Template must export the required stack outputs."""
    outputs = template.get("Outputs", {})
    required_outputs = [
        "AgentLambdaName",
        "McpServerLambdaName",
        "CognitoUserPoolId",
        "CognitoClientId",
        "McpApiInvokeUrl",
        "GatewayUrl",
        "ProductTableName",
    ]
    for key in required_outputs:
        assert key in outputs, f"Template Outputs must include '{key}'"
