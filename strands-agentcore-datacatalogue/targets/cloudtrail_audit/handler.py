import json
import os
from datetime import datetime, timedelta, timezone

import boto3

cloudtrail = boto3.client("cloudtrail")

MAX_RESULTS = 50


def audit_access(parameters):
    table_name = parameters["table_name"]
    days = min(int(parameters.get("days", 30)), 90)

    start_time = datetime.now(timezone.utc) - timedelta(days=days)
    end_time = datetime.now(timezone.utc)

    athena_events = _lookup_events(
        "athena.amazonaws.com", "StartQueryExecution", start_time, end_time
    )
    athena_matches = []
    for event in athena_events:
        request_params = json.loads(event.get("CloudTrailEvent", "{}")).get("requestParameters", {})
        query_string = request_params.get("queryString", "")
        if table_name.lower() in query_string.lower():
            athena_matches.append({
                "principal": event.get("Username", ""),
                "event_time": event["EventTime"].isoformat() if event.get("EventTime") else "",
                "event_name": event.get("EventName", ""),
                "source_ip": json.loads(event.get("CloudTrailEvent", "{}")).get("sourceIPAddress", ""),
                "query_snippet": query_string[:200],
            })

    glue_events = _lookup_events(
        "glue.amazonaws.com", "GetTable", start_time, end_time
    )
    glue_matches = []
    for event in glue_events:
        request_params = json.loads(event.get("CloudTrailEvent", "{}")).get("requestParameters", {})
        if request_params.get("name", "").lower() == table_name.lower():
            glue_matches.append({
                "principal": event.get("Username", ""),
                "event_time": event["EventTime"].isoformat() if event.get("EventTime") else "",
                "event_name": event.get("EventName", ""),
                "source_ip": json.loads(event.get("CloudTrailEvent", "{}")).get("sourceIPAddress", ""),
            })

    return {
        "table_name": table_name,
        "period_days": days,
        "athena_query_events": athena_matches[:MAX_RESULTS],
        "glue_metadata_access_events": glue_matches[:MAX_RESULTS],
        "total_events": len(athena_matches) + len(glue_matches),
    }


def _lookup_events(event_source, event_name, start_time, end_time):
    events = []
    paginator = cloudtrail.get_paginator("lookup_events")
    page_iterator = paginator.paginate(
        LookupAttributes=[
            {"AttributeKey": "EventSource", "AttributeValue": event_source},
        ],
        StartTime=start_time,
        EndTime=end_time,
        MaxResults=50,
    )
    for page in page_iterator:
        for event in page.get("Events", []):
            if event.get("EventName") == event_name:
                events.append(event)
        if len(events) >= MAX_RESULTS:
            break

    return events


def _resolve_tool_name(event, context):
    try:
        return context.client_context.custom["bedrockAgentCoreToolName"].split("___")[-1]
    except Exception:
        return event.get("tool_name", "") if isinstance(event, dict) else ""


def handler(event, context):
    tool_name = _resolve_tool_name(event, context)
    parameters = event.get("parameters", event) if isinstance(event, dict) else {}

    if tool_name == "audit_access":
        return audit_access(parameters)

    return {"error": f"Unknown tool: {tool_name}"}
