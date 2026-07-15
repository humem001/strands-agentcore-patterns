"""CDK stack: 5 Lambda target functions with least-privilege IAM roles."""

import aws_cdk as cdk
from aws_cdk import (
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_s3 as s3,
)
from constructs import Construct


class LambdaTargetsStack(cdk.Stack):
    """Five Lambda targets for AgentCore Gateway."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        data_bucket: s3.IBucket,
        athena_results_bucket: s3.IBucket,
        glue_database_name: str,
        athena_workgroup_name: str,
        kb_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        enable_write_back = self.node.try_get_context("enable_write_back") or False

        # --- glue-catalogue target ---
        glue_role = iam.Role(
            self, "GlueTargetRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )
        glue_role.add_to_policy(iam.PolicyStatement(
            actions=["glue:GetTable", "glue:GetTables", "glue:SearchTables", "glue:GetDatabase"],
            resources=["*"],
        ))
        if enable_write_back:
            glue_role.add_to_policy(iam.PolicyStatement(
                actions=["glue:UpdateTable"],
                resources=["*"],
            ))

        self.glue_catalogue_fn = _lambda.Function(
            self, "GlueCatalogueFn",
            function_name="dwp-demo-glue-target",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=_lambda.Code.from_asset("../targets/glue_catalogue"),
            role=glue_role,
            timeout=cdk.Duration.seconds(30),
            memory_size=256,
            environment={"GLUE_DATABASE": glue_database_name},
        )

        # --- athena-query target ---
        athena_role = iam.Role(
            self, "AthenaTargetRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )
        athena_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "athena:StartQueryExecution",
                "athena:GetQueryExecution",
                "athena:GetQueryResults",
            ],
            resources=["*"],
        ))
        athena_role.add_to_policy(iam.PolicyStatement(
            actions=["glue:GetTable", "glue:GetDatabase", "glue:GetTables"],
            resources=["*"],
        ))
        athena_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:GetObject", "s3:GetBucketLocation", "s3:ListBucket"],
            resources=[data_bucket.bucket_arn, f"{data_bucket.bucket_arn}/*"],
        ))
        athena_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:GetObject", "s3:PutObject", "s3:GetBucketLocation", "s3:ListBucket"],
            resources=[athena_results_bucket.bucket_arn, f"{athena_results_bucket.bucket_arn}/*"],
        ))

        self.athena_query_fn = _lambda.Function(
            self, "AthenaQueryFn",
            function_name="dwp-demo-athena-target",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=_lambda.Code.from_asset("../targets/athena_query"),
            role=athena_role,
            timeout=cdk.Duration.seconds(60),
            memory_size=256,
            environment={
                "GLUE_DATABASE": glue_database_name,
                "ATHENA_WORKGROUP": athena_workgroup_name,
                "ATHENA_OUTPUT_LOCATION": f"s3://{athena_results_bucket.bucket_name}/",
            },
        )

        # --- sagemaker-ml target ---
        sagemaker_role = iam.Role(
            self, "SagemakerTargetRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )
        sagemaker_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "sagemaker:ListModelPackageGroups",
                "sagemaker:ListModelPackages",
                "sagemaker:DescribeModelPackage",
                "sagemaker:DescribeModelPackageGroup",
                "sagemaker:ListFeatureGroups",
                "sagemaker:DescribeFeatureGroup",
            ],
            resources=["*"],
        ))

        self.sagemaker_ml_fn = _lambda.Function(
            self, "SagemakerMlFn",
            function_name="dwp-demo-sagemaker-target",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=_lambda.Code.from_asset("../targets/sagemaker_ml"),
            role=sagemaker_role,
            timeout=cdk.Duration.seconds(30),
            memory_size=256,
        )

        # --- pii-classifier target ---
        pii_role = iam.Role(
            self, "PiiTargetRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )
        pii_role.add_to_policy(iam.PolicyStatement(
            actions=["glue:GetTable"],
            resources=["*"],
        ))

        self.pii_classifier_fn = _lambda.Function(
            self, "PiiClassifierFn",
            function_name="dwp-demo-pii-target",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=_lambda.Code.from_asset("../targets/pii_classifier"),
            role=pii_role,
            timeout=cdk.Duration.seconds(15),
            memory_size=128,
            environment={"GLUE_DATABASE": glue_database_name},
        )

        # --- governance-kb target ---
        kb_role = iam.Role(
            self, "KbTargetRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )
        kb_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:Retrieve"],
            resources=[f"arn:aws:bedrock:eu-west-2:{cdk.Aws.ACCOUNT_ID}:knowledge-base/{kb_id}"],
        ))

        self.governance_kb_fn = _lambda.Function(
            self, "GovernanceKbFn",
            function_name="dwp-demo-kb-target",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=_lambda.Code.from_asset("../targets/governance_kb"),
            role=kb_role,
            timeout=cdk.Duration.seconds(30),
            memory_size=256,
            environment={"KNOWLEDGE_BASE_ID": kb_id},
        )

        # --- Outputs ---
        cdk.CfnOutput(self, "GlueCatalogueFnArn", value=self.glue_catalogue_fn.function_arn)
        cdk.CfnOutput(self, "AthenaQueryFnArn", value=self.athena_query_fn.function_arn)
        cdk.CfnOutput(self, "SagemakerMlFnArn", value=self.sagemaker_ml_fn.function_arn)
        cdk.CfnOutput(self, "PiiClassifierFnArn", value=self.pii_classifier_fn.function_arn)
        cdk.CfnOutput(self, "GovernanceKbFnArn", value=self.governance_kb_fn.function_arn)
