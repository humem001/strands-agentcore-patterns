#!/usr/bin/env python3
"""Create AgentCore Gateway (CUSTOM_JWT -> Cognito) + 6 lambda targets via boto3."""

import argparse
import json
import time

import boto3

REGION = "eu-west-2"

TARGETS = [
    ("glue-catalogue", "GlueCatalogueFnArn", "tools/glue_catalogue_tools.json"),
    ("athena-query", "AthenaQueryFnArn", "tools/athena_query_tools.json"),
    ("sagemaker-ml", "SagemakerMlFnArn", "tools/sagemaker_ml_tools.json"),
    ("pii-classifier", "PiiClassifierFnArn", "tools/pii_classifier_tools.json"),
    ("governance-kb", "GovernanceKbFnArn", "tools/governance_kb_tools.json"),
    ("cloudtrail-audit", "CloudTrailAuditFnArn", "tools/cloudtrail_audit_tools.json"),
]


def stack_outputs(cf, *stacks):
    out = {}
    for s in stacks:
        for o in cf.describe_stacks(StackName=s)["Stacks"][0].get("Outputs", []):
            out[o["OutputKey"]] = o["OutputValue"]
    return out


def ensure_gateway_role(iam, account_id):
    role_name = "demo-gateway-role"
    trust = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    }
    try:
        arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
        print(f"  Gateway role exists: {arn}")
    except iam.exceptions.NoSuchEntityException:
        arn = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust),
        )["Role"]["Arn"]
        print(f"  Created gateway role: {arn}")
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="InvokeLambdaTargets",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": "lambda:InvokeFunction",
                "Resource": f"arn:aws:lambda:{REGION}:{account_id}:function:demo-*",
            }],
        }),
    )
    time.sleep(10)
    return arn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway-name", default="demo-gateway")
    args = parser.parse_args()

    session = boto3.Session(region_name=REGION)
    cf = session.client("cloudformation")
    iam = session.client("iam")
    ac = session.client("bedrock-agentcore-control")
    account_id = session.client("sts").get_caller_identity()["Account"]

    out = stack_outputs(cf, "DwpDemoCognito", "DwpDemoLambdaTargets")
    pool_id = out["UserPoolId"]
    m2m_client_id = out["M2mClientId"]
    discovery_url = f"https://cognito-idp.{REGION}.amazonaws.com/{pool_id}/.well-known/openid-configuration"

    print("Ensuring gateway IAM role...")
    role_arn = ensure_gateway_role(iam, account_id)

    existing = None
    for g in ac.list_gateways().get("items", []):
        if g["name"] == args.gateway_name:
            existing = g["gatewayId"]
            break

    if existing:
        gw = ac.get_gateway(gatewayIdentifier=existing)
        gateway_id = gw["gatewayId"]
        gateway_arn = gw["gatewayArn"]
        gateway_url = gw["gatewayUrl"]
        print(f"  Reusing gateway: {gateway_id}")
        for t in ac.list_gateway_targets(gatewayIdentifier=gateway_id).get("items", []):
            ac.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=t["targetId"])
            print(f"  Deleted stale target: {t['name']}")
        for _ in range(30):
            remaining = ac.list_gateway_targets(gatewayIdentifier=gateway_id).get("items", [])
            if not remaining:
                break
            time.sleep(2)
        print("  All stale targets cleared")
    else:
        print("Creating gateway...")
        gw = ac.create_gateway(
            name=args.gateway_name,
            roleArn=role_arn,
            protocolType="MCP",
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration={
                "customJWTAuthorizer": {
                    "discoveryUrl": discovery_url,
                    "allowedClients": [m2m_client_id],
                }
            },
            protocolConfiguration={
                "mcp": {"searchType": "SEMANTIC"}
            },
            exceptionLevel="DEBUG",
        )
        gateway_id = gw["gatewayId"]
        gateway_arn = gw["gatewayArn"]
        gateway_url = gw["gatewayUrl"]
        print(f"  Gateway ID: {gateway_id}")
        print(f"  Gateway URL: {gateway_url}")

    print("Creating targets...")
    for target_name, arn_key, schema_file in TARGETS:
        lambda_arn = out[arn_key]
        with open(schema_file) as f:
            tools = json.load(f)
        for attempt in range(15):
            try:
                ac.create_gateway_target(
                    gatewayIdentifier=gateway_id,
                    name=target_name,
                    targetConfiguration={
                        "mcp": {
                            "lambda": {
                                "lambdaArn": lambda_arn,
                                "toolSchema": {"inlinePayload": tools},
                            }
                        }
                    },
                    credentialProviderConfigurations=[
                        {"credentialProviderType": "GATEWAY_IAM_ROLE"}
                    ],
                )
                print(f"  ✓ Target created: {target_name} -> {lambda_arn}")
                break
            except ac.exceptions.ConflictException:
                time.sleep(3)
        else:
            raise RuntimeError(f"Could not create target {target_name} (conflict persisted)")

    result = {
        "gateway_id": gateway_id,
        "gateway_arn": gateway_arn,
        "gateway_url": gateway_url,
        "discovery_url": discovery_url,
    }
    with open("gateway-outputs.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\n✓ Gateway deployment complete. Saved to gateway-outputs.json")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
