# Knowledge Base stack — Bedrock KB with S3 Vectors storage (eu-west-2).
from aws_cdk import (
    Aws,
    CfnOutput,
    Stack,
    aws_bedrock as bedrock,
    aws_iam as iam,
    aws_s3 as s3,
)
from constructs import Construct


class KnowledgeBaseStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        kb_source_bucket: s3.IBucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        embedding_model_arn = (
            "arn:aws:bedrock:eu-west-2::foundation-model/amazon.titan-embed-text-v2:0"
        )

        kb_role = iam.Role(
            self,
            "KbRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            inline_policies={
                "BedrockInvoke": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["bedrock:InvokeModel"],
                            resources=[embedding_model_arn],
                        ),
                    ]
                ),
                "S3Access": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["s3:GetObject", "s3:ListBucket"],
                            resources=[
                                kb_source_bucket.bucket_arn,
                                f"{kb_source_bucket.bucket_arn}/*",
                            ],
                        ),
                    ]
                ),
                "S3Vectors": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "s3vectors:CreateVectorBucket",
                                "s3vectors:CreateVectorIndex",
                                "s3vectors:PutVectors",
                                "s3vectors:QueryVectors",
                                "s3vectors:GetVectors",
                                "s3vectors:DeleteVectors",
                                "s3vectors:ListVectorBuckets",
                                "s3vectors:ListVectorIndexes",
                            ],
                            resources=["*"],
                        ),
                    ]
                ),
            },
        )

        kb = bedrock.CfnKnowledgeBase(
            self,
            "GovernanceKb",
            name="dwp-demo-governance-kb",
            role_arn=kb_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=embedding_model_arn,
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="S3_VECTORS",
                s3_vectors_configuration=bedrock.CfnKnowledgeBase.S3VectorsConfigurationProperty(
                    vector_bucket_arn=f"arn:aws:s3vectors:eu-west-2:{Aws.ACCOUNT_ID}:bucket/dwp-demo-kb-vectors",
                    index_name="dwp-demo-governance-index",
                ),
            ),
        )

        data_source = bedrock.CfnDataSource(
            self,
            "KbDataSource",
            name="dwp-demo-kb-datasource",
            knowledge_base_id=kb.attr_knowledge_base_id,
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=kb_source_bucket.bucket_arn,
                ),
            ),
        )

        self.kb_id = kb.attr_knowledge_base_id
        self.kb_arn = kb.attr_knowledge_base_arn
        self.data_source_id = data_source.attr_data_source_id

        CfnOutput(self, "KnowledgeBaseId", value=self.kb_id)
        CfnOutput(self, "KnowledgeBaseArn", value=self.kb_arn)
        CfnOutput(self, "DataSourceId", value=self.data_source_id)
