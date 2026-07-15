import json
import os

import boto3

glue = boto3.client("glue")
DEFAULT_DATABASE = os.environ.get("GLUE_DATABASE", "dwp_data_catalogue")


def handler(event, context):
    tool_name = event.get("tool_name")
    parameters = event.get("parameters", {})

    if tool_name == "classify_pii":
        return classify_pii(parameters)

    return {"statusCode": 400, "body": {"error": f"Unknown tool: {tool_name}"}}


def classify_pii(parameters):
    database = parameters.get("database", DEFAULT_DATABASE)
    table_name = parameters["table_name"]

    response = glue.get_table(DatabaseName=database, Name=table_name)
    table = response["Table"]

    columns = []
    for col in table["StorageDescriptor"]["Columns"]:
        columns.append({
            "name": col["Name"],
            "type": col["Type"],
            "description": col.get("Comment", ""),
        })

    result = {
        "table_name": table_name,
        "database": database,
        "columns": columns,
    }

    pii_samples = table.get("Parameters", {}).get("pii_samples")
    if pii_samples:
        result["pii_samples"] = json.loads(pii_samples)

    return {"statusCode": 200, "body": result}
