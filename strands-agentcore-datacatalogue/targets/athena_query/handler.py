import json
import os
import time

import boto3

athena = boto3.client("athena")

GLUE_DATABASE = os.environ.get("GLUE_DATABASE", "dwp_data_catalogue")
ATHENA_WORKGROUP = os.environ.get("ATHENA_WORKGROUP", "dwp-demo-athena-wg")
ATHENA_OUTPUT_LOCATION = os.environ.get("ATHENA_OUTPUT_LOCATION", "")


def query_dataset(parameters):
    sql = parameters["sql"]
    database = parameters.get("database", GLUE_DATABASE)

    execution = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": database},
        WorkGroup=ATHENA_WORKGROUP,
        ResultConfiguration={"OutputLocation": ATHENA_OUTPUT_LOCATION},
    )
    execution_id = execution["QueryExecutionId"]

    elapsed = 0
    while elapsed < 30:
        response = athena.get_query_execution(QueryExecutionId=execution_id)
        state = response["QueryExecution"]["Status"]["State"]
        if state == "SUCCEEDED":
            break
        if state == "FAILED":
            reason = response["QueryExecution"]["Status"].get("StateChangeReason", "Unknown error")
            return {"statusCode": 500, "body": {"error": f"Query failed: {reason}"}}
        time.sleep(1)
        elapsed += 1

    if state != "SUCCEEDED":
        return {"statusCode": 500, "body": {"error": "Query timed out after 30 seconds"}}

    results = athena.get_query_results(QueryExecutionId=execution_id, MaxResults=101)
    columns = [col["Name"] for col in results["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]]
    rows = []
    for row in results["ResultSet"]["Rows"][1:]:
        rows.append({columns[i]: (datum.get("VarCharValue", "") if datum else "") for i, datum in enumerate(row["Data"])})

    return {
        "statusCode": 200,
        "body": {
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        },
    }


def handler(event, context):
    tool_name = event.get("tool_name", "")
    parameters = event.get("parameters", {})

    if tool_name == "query_dataset":
        return query_dataset(parameters)

    return {"statusCode": 400, "body": {"error": f"Unknown tool: {tool_name}"}}
