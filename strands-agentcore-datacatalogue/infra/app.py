#!/usr/bin/env python3
import aws_cdk as cdk
from stacks import (
    DataPlatformStack,
    CognitoStack,
    LambdaTargetsStack,
    KnowledgeBaseStack,
    MlAssetsStack,
)

app = cdk.App()

env = cdk.Environment(region="eu-west-2")

data_platform = DataPlatformStack(app, "DwpDemoDataPlatform", env=env)
cognito = CognitoStack(app, "DwpDemoCognito", env=env)

knowledge_base = KnowledgeBaseStack(
    app,
    "DwpDemoKnowledgeBase",
    kb_source_bucket=data_platform.kb_source_bucket,
    env=env,
)

ml_assets = MlAssetsStack(
    app,
    "DwpDemoMlAssets",
    data_bucket=data_platform.data_bucket,
    env=env,
)

lambda_targets = LambdaTargetsStack(
    app,
    "DwpDemoLambdaTargets",
    data_bucket=data_platform.data_bucket,
    athena_results_bucket=data_platform.athena_results_bucket,
    glue_database_name=data_platform.glue_database_name,
    athena_workgroup_name=data_platform.athena_workgroup_name,
    kb_id=knowledge_base.kb_id,
    env=env,
)

app.synth()
