import json
import os
import boto3


sagemaker = boto3.client("sagemaker")


def list_ml_models(parameters):
    query = parameters.get("query", "").lower()

    model_groups = []
    response = sagemaker.list_model_package_groups()
    for group in response.get("ModelPackageGroupSummaryList", []):
        name = group.get("ModelPackageGroupName", "")
        description = group.get("ModelPackageGroupDescription", "")
        if query and query not in name.lower() and query not in description.lower():
            continue
        model_groups.append({
            "name": name,
            "description": description,
            "creation_time": group.get("CreationTime", "").isoformat() if group.get("CreationTime") else None,
            "status": group.get("ModelPackageGroupStatus", "")
        })

    feature_groups = []
    response = sagemaker.list_feature_groups()
    for fg in response.get("FeatureGroupSummaries", []):
        name = fg.get("FeatureGroupName", "")
        if query and query not in name.lower():
            continue
        feature_groups.append({
            "name": name,
            "creation_time": fg.get("CreationTime", "").isoformat() if fg.get("CreationTime") else None,
            "status": fg.get("FeatureGroupStatus", "")
        })

    return {"models": model_groups, "feature_groups": feature_groups}


def describe_ml_asset(parameters):
    asset_type = parameters["asset_type"]
    asset_name = parameters["asset_name"]

    if asset_type == "model":
        packages_response = sagemaker.list_model_packages(
            ModelPackageGroupName=asset_name,
            SortBy="CreationTime",
            SortOrder="Descending",
            MaxResults=1
        )
        packages = packages_response.get("ModelPackageSummaryList", [])
        if not packages:
            return {"error": f"No model packages found for group '{asset_name}'"}

        latest_arn = packages[0]["ModelPackageArn"]
        detail = sagemaker.describe_model_package(ModelPackageName=latest_arn)

        metrics = detail.get("CustomerMetadataProperties", {})
        inference_spec = detail.get("InferenceSpecification", {})
        data_sources = []
        for channel in detail.get("ModelDataSource", {}).get("S3DataSource", []):
            data_sources.append(channel)
        if not data_sources:
            for channel in detail.get("AdditionalInferenceSpecifications", []):
                pass

        return {
            "name": asset_name,
            "description": detail.get("ModelPackageDescription", ""),
            "creation_time": detail.get("CreationTime", "").isoformat() if detail.get("CreationTime") else None,
            "status": detail.get("ModelPackageStatus", ""),
            "inference_spec": inference_spec,
            "metrics": metrics,
            "data_sources": data_sources
        }

    elif asset_type == "feature_group":
        detail = sagemaker.describe_feature_group(FeatureGroupName=asset_name)

        offline_config = detail.get("OfflineStoreConfig", {})
        s3_uri = offline_config.get("S3StorageConfig", {}).get("S3Uri", "")

        return {
            "name": asset_name,
            "description": detail.get("Description", ""),
            "feature_definitions": detail.get("FeatureDefinitions", []),
            "creation_time": detail.get("CreationTime", "").isoformat() if detail.get("CreationTime") else None,
            "status": detail.get("FeatureGroupStatus", ""),
            "offline_store_s3_uri": s3_uri
        }

    return {"error": f"Unknown asset_type '{asset_type}'"}


TOOLS = {
    "list_ml_models": list_ml_models,
    "describe_ml_asset": describe_ml_asset,
}


def _resolve_tool_name(event, context):
    try:
        return context.client_context.custom["bedrockAgentCoreToolName"].split("___")[-1]
    except Exception:
        return event.get("tool_name", "") if isinstance(event, dict) else ""


def handler(event, context):
    tool_name = _resolve_tool_name(event, context)
    parameters = event.get("parameters", event) if isinstance(event, dict) else {}

    tool_fn = TOOLS.get(tool_name)
    if not tool_fn:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        return tool_fn(parameters)
    except Exception as e:
        return {"error": str(e)}
