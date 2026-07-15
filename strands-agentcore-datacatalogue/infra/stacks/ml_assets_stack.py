# ML assets stack — SageMaker Model Package Groups, Feature Group, IAM (eu-west-2).
from aws_cdk import (
    Aws,
    RemovalPolicy,
    Stack,
    aws_iam as iam,
    aws_s3 as s3,
    aws_sagemaker as sagemaker,
)
from constructs import Construct


class MlAssetsStack(Stack):
    """SageMaker model registry and offline feature store for the DWP demo."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        data_bucket: s3.IBucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        sagemaker.CfnModelPackageGroup(
            self,
            "CompliancePredictor",
            model_package_group_name="cms-compliance-predictor-v3",
            model_package_group_description="XGBoost predicting payment non-compliance risk",
        )

        sagemaker.CfnModelPackageGroup(
            self,
            "FraudDetection",
            model_package_group_name="fraud-detection-v1",
            model_package_group_description="Binary fraud referral classifier",
        )

        sagemaker.CfnModelPackageGroup(
            self,
            "ClaimantEmbedding",
            model_package_group_name="claimant-embedding-model",
            model_package_group_description="Text embeddings for claimant journal",
        )

        feature_store_role = iam.Role(
            self,
            "FeatureStoreRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            inline_policies={
                "FeatureStoreS3Access": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["s3:PutObject", "s3:GetObject"],
                            resources=[
                                data_bucket.arn_for_objects("feature-store/cms-payment-features/*"),
                            ],
                        ),
                    ]
                ),
            },
        )

        sagemaker.CfnFeatureGroup(
            self,
            "PaymentFeatures",
            feature_group_name="cms-payment-features",
            description="Payment behaviour features for compliance prediction",
            record_identifier_feature_name="case_id",
            event_time_feature_name="event_time",
            feature_definitions=[
                sagemaker.CfnFeatureGroup.FeatureDefinitionProperty(
                    feature_name="case_id", feature_type="String",
                ),
                sagemaker.CfnFeatureGroup.FeatureDefinitionProperty(
                    feature_name="event_time", feature_type="String",
                ),
                sagemaker.CfnFeatureGroup.FeatureDefinitionProperty(
                    feature_name="payment_gap_days", feature_type="Integral",
                ),
                sagemaker.CfnFeatureGroup.FeatureDefinitionProperty(
                    feature_name="avg_payment_amount", feature_type="Fractional",
                ),
                sagemaker.CfnFeatureGroup.FeatureDefinitionProperty(
                    feature_name="change_of_circs_count", feature_type="Integral",
                ),
                sagemaker.CfnFeatureGroup.FeatureDefinitionProperty(
                    feature_name="days_since_last_payment", feature_type="Integral",
                ),
                sagemaker.CfnFeatureGroup.FeatureDefinitionProperty(
                    feature_name="compliance_rate", feature_type="Fractional",
                ),
            ],
            offline_store_config=sagemaker.CfnFeatureGroup.OfflineStoreConfigProperty(
                s3_storage_config=sagemaker.CfnFeatureGroup.S3StorageConfigProperty(
                    s3_uri=f"s3://{data_bucket.bucket_name}/feature-store/cms-payment-features/",
                ),
                disable_glue_table_creation=False,
            ),
            role_arn=feature_store_role.role_arn,
        )
