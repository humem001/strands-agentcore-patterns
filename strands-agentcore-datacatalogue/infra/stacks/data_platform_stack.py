# Data platform stack — S3 buckets, Glue database, Athena workgroup (eu-west-2).
from aws_cdk import (
    Aws,
    CfnOutput,
    RemovalPolicy,
    Stack,
    aws_athena as athena,
    aws_glue as glue,
    aws_s3 as s3,
)
from constructs import Construct


class DataPlatformStack(Stack):
    """Provisions the core data-plane resources for the DWP demo catalogue."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.data_bucket = s3.Bucket(
            self,
            "DataBucket",
            bucket_name=f"dwp-demo-data-{Aws.ACCOUNT_ID}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        self.athena_results_bucket = s3.Bucket(
            self,
            "AthenaResultsBucket",
            bucket_name=f"dwp-demo-athena-results-{Aws.ACCOUNT_ID}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        self.kb_source_bucket = s3.Bucket(
            self,
            "KbSourceBucket",
            bucket_name=f"dwp-demo-kb-source-{Aws.ACCOUNT_ID}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        glue_db = glue.CfnDatabase(
            self,
            "GlueDatabase",
            catalog_id=Aws.ACCOUNT_ID,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name="dwp_data_catalogue",
            ),
        )
        self._glue_database_name = "dwp_data_catalogue"

        athena_wg = athena.CfnWorkGroup(
            self,
            "AthenaWorkGroup",
            name="dwp-demo-athena-wg",
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{self.athena_results_bucket.bucket_name}/",
                ),
            ),
        )
        self._athena_workgroup_name = "dwp-demo-athena-wg"

        CfnOutput(self, "GlueDatabaseName", value=self._glue_database_name)
        CfnOutput(self, "AthenaWorkGroupName", value=self._athena_workgroup_name)

    @property
    def glue_database_name(self) -> str:
        return self._glue_database_name

    @property
    def athena_workgroup_name(self) -> str:
        return self._athena_workgroup_name
