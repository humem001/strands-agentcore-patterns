"""Cognito User Pool, Resource Server, and App Clients for demo."""

from aws_cdk import (
    CfnOutput,
    Fn,
    RemovalPolicy,
    Stack,
    aws_cognito as cognito,
)
from constructs import Construct


class CognitoStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="demo-pool",
            self_sign_up_enabled=False,
            mfa=cognito.Mfa.OFF,
            removal_policy=RemovalPolicy.DESTROY,
        )

        domain_prefix = Fn.join("", ["demo-", self.account])

        self.domain = self.user_pool.add_domain(
            "Domain",
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=domain_prefix),
        )

        runtime_invoke_scope = cognito.ResourceServerScope(
            scope_name="runtime.invoke",
            scope_description="Invoke agent runtime",
        )
        gateway_tools_scope = cognito.ResourceServerScope(
            scope_name="gateway.tools",
            scope_description="Access gateway tools",
        )

        resource_server = self.user_pool.add_resource_server(
            "ResourceServer",
            identifier="demo-api",
            user_pool_resource_server_name="demo-api",
            scopes=[runtime_invoke_scope, gateway_tools_scope],
        )

        self.inbound_client = self.user_pool.add_client(
            "InboundClient",
            user_pool_client_name="demo-inbound",
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(client_credentials=True),
                scopes=[
                    cognito.OAuthScope.custom("demo-api/runtime.invoke"),
                ],
            ),
        )
        self.inbound_client.node.add_dependency(resource_server)

        self.m2m_client = self.user_pool.add_client(
            "M2mClient",
            user_pool_client_name="demo-m2m",
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(client_credentials=True),
                scopes=[
                    cognito.OAuthScope.custom("demo-api/gateway.tools"),
                ],
            ),
        )
        self.m2m_client.node.add_dependency(resource_server)

        self.user_pool_id = self.user_pool.user_pool_id
        self.user_pool_arn = self.user_pool.user_pool_arn
        self.issuer_url = Fn.join("", [
            "https://cognito-idp.eu-west-2.amazonaws.com/",
            self.user_pool.user_pool_id,
        ])
        self.inbound_client_id = self.inbound_client.user_pool_client_id
        self.inbound_client_secret = self.inbound_client.user_pool_client_secret
        self.m2m_client_id = self.m2m_client.user_pool_client_id
        self.m2m_client_secret = self.m2m_client.user_pool_client_secret
        self.token_endpoint = Fn.join("", [
            "https://",
            domain_prefix,
            ".auth.eu-west-2.amazoncognito.com/oauth2/token",
        ])

        CfnOutput(self, "UserPoolId", value=self.user_pool_id)
        CfnOutput(self, "UserPoolArn", value=self.user_pool_arn)
        CfnOutput(self, "IssuerUrl", value=self.issuer_url)
        CfnOutput(self, "InboundClientId", value=self.inbound_client_id)
        CfnOutput(
            self,
            "InboundClientSecret",
            value=self.inbound_client_secret.unsafe_unwrap(),
        )
        CfnOutput(self, "M2mClientId", value=self.m2m_client_id)
        CfnOutput(
            self,
            "M2mClientSecret",
            value=self.m2m_client_secret.unsafe_unwrap(),
        )
        CfnOutput(self, "TokenEndpoint", value=self.token_endpoint)
