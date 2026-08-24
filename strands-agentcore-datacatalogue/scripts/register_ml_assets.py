#!/usr/bin/env python3
"""Register SageMaker Model Package Groups and Feature Group (metadata only)."""

import argparse
import json
import boto3

REGION = "eu-west-2"

MODEL_PACKAGES = [
    {
        "group_name": "cms-compliance-predictor-v3",
        "description": "XGBoost predicting payment non-compliance risk for CMS cases",
        "metrics": {
            "accuracy": "0.87",
            "precision": "0.82",
            "recall": "0.79",
            "f1_score": "0.80",
            "training_dataset": "cms_payment_history",
            "feature_group": "cms-payment-features",
        },
    },
    {
        "group_name": "fraud-detection-v1",
        "description": "Binary fraud referral classifier for UC and CMS",
        "metrics": {
            "accuracy": "0.91",
            "precision": "0.76",
            "recall": "0.84",
            "f1_score": "0.80",
            "training_dataset": "uc_claimant_journal + fraud_referral_outcomes",
        },
    },
    {
        "group_name": "claimant-embedding-model",
        "description": "Text embeddings for claimant journal entries (JCS chatbot)",
        "metrics": {
            "embedding_dim": "768",
            "training_dataset": "uc_claimant_journal + jcs_chatbot_interactions",
        },
    },
]

FEATURE_GROUP = {
    "name": "cms-payment-features",
    "description": "Payment behaviour features for compliance prediction",
    "features": [
        {"FeatureName": "case_id", "FeatureType": "String"},
        {"FeatureName": "event_time", "FeatureType": "String"},
        {"FeatureName": "payment_gap_days", "FeatureType": "Integral"},
        {"FeatureName": "avg_payment_amount", "FeatureType": "Fractional"},
        {"FeatureName": "change_of_circs_count", "FeatureType": "Integral"},
        {"FeatureName": "days_since_last_payment", "FeatureType": "Integral"},
        {"FeatureName": "compliance_rate", "FeatureType": "Fractional"},
    ],
}


def get_data_bucket(outputs: dict) -> str:
    for stack_outputs in outputs.values():
        for key, val in stack_outputs.items():
            if "DataBucket" in key or "databucket" in key.lower():
                if val.startswith("s3://"):
                    return val.replace("s3://", "").rstrip("/")
                return val
    raise ValueError("Could not find data bucket in CDK outputs")


def register_model_packages(sm, bucket_name: str):
    print("Registering model package groups...")
    for model in MODEL_PACKAGES:
        try:
            sm.create_model_package_group(
                ModelPackageGroupName=model["group_name"],
                ModelPackageGroupDescription=model["description"],
            )
            print(f"  ✓ Created group: {model['group_name']}")
        except sm.exceptions.ClientError as e:
            if "already exists" in str(e).lower():
                print(f"  ↻ Exists: {model['group_name']}")
            else:
                raise

        try:
            sm.create_model_package(
                ModelPackageGroupName=model["group_name"],
                ModelPackageDescription=model["description"],
                CustomerMetadataProperties=model["metrics"],
                ModelApprovalStatus="Approved",
            )
            print(f"  ✓ Registered version for: {model['group_name']}")
        except sm.exceptions.ClientError as e:
            if "already exists" in str(e).lower():
                print(f"  ↻ Version exists: {model['group_name']}")
            else:
                raise


def get_or_create_feature_store_role(bucket_name: str) -> str:
    iam = boto3.client("iam")
    role_name = "demo-feature-store-role"
    try:
        resp = iam.get_role(RoleName=role_name)
        return resp["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        pass
    import json as _json
    trust = _json.dumps({
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"Service": "sagemaker.amazonaws.com"}, "Action": "sts:AssumeRole"}],
    })
    resp = iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=trust)
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="S3Access",
        PolicyDocument=_json.dumps({
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Allow", "Action": ["s3:PutObject", "s3:GetObject"], "Resource": f"arn:aws:s3:::{bucket_name}/feature-store/*"}],
        }),
    )
    import time; time.sleep(10)
    return resp["Role"]["Arn"]


def register_feature_group(sm, bucket_name: str):
    print("Registering feature group...")
    role_arn = get_or_create_feature_store_role(bucket_name)
    try:
        sm.create_feature_group(
            FeatureGroupName=FEATURE_GROUP["name"],
            RecordIdentifierFeatureName="case_id",
            EventTimeFeatureName="event_time",
            FeatureDefinitions=FEATURE_GROUP["features"],
            Description=FEATURE_GROUP["description"],
            RoleArn=role_arn,
            OfflineStoreConfig={
                "S3StorageConfig": {
                    "S3Uri": f"s3://{bucket_name}/feature-store/{FEATURE_GROUP['name']}/",
                }
            },
        )
        print(f"  ✓ Created: {FEATURE_GROUP['name']}")
    except sm.exceptions.ResourceInUse:
        print(f"  ↻ Exists: {FEATURE_GROUP['name']}")
    except Exception as e:
        print(f"  ⚠ Feature group creation failed (non-critical): {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outputs", default="cdk-outputs.json")
    parser.add_argument("--bucket", default=None)
    args = parser.parse_args()

    if args.bucket:
        bucket_name = args.bucket
    else:
        with open(args.outputs) as f:
            outputs = json.load(f)
        bucket_name = get_data_bucket(outputs)

    sm = boto3.client("sagemaker", region_name=REGION)
    register_model_packages(sm, bucket_name)
    register_feature_group(sm, bucket_name)
    print("\nDone.")


if __name__ == "__main__":
    main()
