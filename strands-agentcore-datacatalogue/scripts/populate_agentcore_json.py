#!/usr/bin/env python3
"""Populate agentcore.json template with CDK output values."""

import argparse
import json
import re


PLACEHOLDER_MAP = {
    "{{LAMBDA_ARN_GLUE}}": ["GlueCatalogueFnArn"],
    "{{LAMBDA_ARN_ATHENA}}": ["AthenaQueryFnArn"],
    "{{LAMBDA_ARN_SAGEMAKER}}": ["SagemakerMlFnArn"],
    "{{LAMBDA_ARN_PII}}": ["PiiClassifierFnArn"],
    "{{LAMBDA_ARN_KB}}": ["GovernanceKbFnArn"],
    "{{COGNITO_POOL_ID}}": ["UserPoolId"],
    "{{COGNITO_TOKEN_ENDPOINT}}": ["TokenEndpoint"],
    "{{COGNITO_M2M_CLIENT_ID}}": ["M2mClientId"],
    "{{COGNITO_M2M_CLIENT_SECRET}}": ["M2mClientSecret"],
}


def find_output(outputs: dict, candidates: list) -> str:
    for stack_outputs in outputs.values():
        for key, val in stack_outputs.items():
            for candidate in candidates:
                if candidate.lower() in key.lower():
                    return val
    raise ValueError(f"Could not find output matching any of: {candidates}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outputs", default="cdk-outputs.json")
    parser.add_argument("--template", default="agentcore.json")
    args = parser.parse_args()

    with open(args.outputs) as f:
        outputs = json.load(f)

    with open(args.template) as f:
        content = f.read()

    for placeholder, candidates in PLACEHOLDER_MAP.items():
        value = find_output(outputs, candidates)
        content = content.replace(placeholder, value)

    # Gateway URL is set after agentcore deploy — leave as placeholder or set from agentcore output
    remaining = re.findall(r"\{\{[^}]+\}\}", content)
    if remaining:
        # GATEWAY_URL is expected to remain — it's set post-deploy
        non_gateway = [p for p in remaining if "GATEWAY" not in p]
        if non_gateway:
            print(f"WARNING: Unresolved placeholders: {non_gateway}")

    with open(args.template, "w") as f:
        f.write(content)

    print(f"✓ Populated {args.template} with CDK outputs.")


if __name__ == "__main__":
    main()
