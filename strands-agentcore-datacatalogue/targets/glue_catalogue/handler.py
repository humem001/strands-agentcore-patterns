import json
import os

import boto3
from botocore.exceptions import ClientError

glue = boto3.client("glue")
sts = boto3.client("sts")

DATABASE = os.environ["GLUE_DATABASE"]


def search_catalogue(parameters):
    query = parameters.get("query", "")
    try:
        response = glue.get_tables(DatabaseName=DATABASE)
        tables = []
        for t in response.get("TableList", []):
            params = t.get("Parameters", {})
            tables.append({
                "name": t["Name"],
                "database": t["DatabaseName"],
                "description": params.get("description", ""),
                "classification": params.get("classification", ""),
                "owner": params.get("owner", ""),
            })
        return tables
    except ClientError:
        account_id = sts.get_caller_identity()["Account"]
        response = glue.search_tables(SearchText=query, CatalogId=account_id)
        tables = []
        for t in response.get("TableList", []):
            params = t.get("Parameters", {})
            tables.append({
                "name": t["Name"],
                "database": t["DatabaseName"],
                "description": params.get("description", ""),
                "classification": params.get("classification", ""),
                "owner": params.get("owner", ""),
            })
        return tables


def get_dataset_detail(parameters):
    database = parameters["database"]
    table_name = parameters["table_name"]
    response = glue.get_table(DatabaseName=database, Name=table_name)
    t = response["Table"]
    params = t.get("Parameters", {})
    columns = [
        {"name": c["Name"], "type": c["Type"], "comment": c.get("Comment", "")}
        for c in t.get("StorageDescriptor", {}).get("Columns", [])
    ]
    return {
        "name": t["Name"],
        "database": t["DatabaseName"],
        "description": params.get("description", ""),
        "classification": params.get("classification", ""),
        "owner": params.get("owner", ""),
        "steward": params.get("steward", ""),
        "columns": columns,
        "s3_location": t.get("StorageDescriptor", {}).get("Location", ""),
        "last_updated": t.get("UpdateTime", "").isoformat() if t.get("UpdateTime") else "",
        "parameters": params,
    }


def show_lineage(parameters):
    database = parameters["database"]
    table_name = parameters["table_name"]
    response = glue.get_table(DatabaseName=database, Name=table_name)
    params = response["Table"].get("Parameters", {})
    upstream = json.loads(params.get("lineage_upstream", "[]"))
    downstream = json.loads(params.get("lineage_downstream", "[]"))
    transformation = params.get("lineage_transformation", "")
    return {
        "upstream": upstream,
        "downstream": downstream,
        "transformation": transformation,
    }


def generate_metadata(parameters):
    database = parameters["database"]
    table_name = parameters["table_name"]
    response = glue.get_table(DatabaseName=database, Name=table_name)
    t = response["Table"]
    params = t.get("Parameters", {})
    columns = [
        {"name": c["Name"], "type": c["Type"], "comment": c.get("Comment", "")}
        for c in t.get("StorageDescriptor", {}).get("Columns", [])
    ]
    result = {"columns": columns, "parameters": params}

    if os.environ.get("ENABLE_WRITE_BACK") == "true" and "metadata" in parameters:
        metadata = parameters["metadata"]
        table_input = {
            "Name": t["Name"],
            "StorageDescriptor": t["StorageDescriptor"],
            "Parameters": {**params, **metadata},
        }
        if "PartitionKeys" in t:
            table_input["PartitionKeys"] = t["PartitionKeys"]
        if "TableType" in t:
            table_input["TableType"] = t["TableType"]
        glue.update_table(DatabaseName=database, TableInput=table_input)
        result["write_back"] = "applied"

    return result


def suggest_joins(parameters):
    response = glue.get_tables(DatabaseName=DATABASE)
    tables = []
    for t in response.get("TableList", []):
        columns = [
            {"name": c["Name"], "type": c["Type"]}
            for c in t.get("StorageDescriptor", {}).get("Columns", [])
        ]
        tables.append({"name": t["Name"], "columns": columns})
    return tables


TOOLS = {
    "search_catalogue": search_catalogue,
    "get_dataset_detail": get_dataset_detail,
    "show_lineage": show_lineage,
    "generate_metadata": generate_metadata,
    "suggest_joins": suggest_joins,
}


def handler(event, context):
    try:
        body = event if isinstance(event, dict) else json.loads(event)
        tool_name = body["tool_name"]
        parameters = body.get("parameters", {})

        if tool_name not in TOOLS:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Unknown tool: {tool_name}"}),
            }

        result = TOOLS[tool_name](parameters)
        return {
            "statusCode": 200,
            "body": json.dumps(result, default=str),
        }
    except ClientError as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
