import json
import os

import boto3

client = boto3.client("bedrock-agent-runtime", region_name="eu-west-2")
KNOWLEDGE_BASE_ID = os.environ["KNOWLEDGE_BASE_ID"]


def _resolve_tool_name(event, context):
    try:
        return context.client_context.custom["bedrockAgentCoreToolName"].split("___")[-1]
    except Exception:
        return event.get("tool_name") if isinstance(event, dict) else None


def handler(event, context):
    tool_name = _resolve_tool_name(event, context)
    parameters = event.get("parameters", event) if isinstance(event, dict) else {}

    if tool_name == "policy_search":
        question = parameters["question"]
        response = client.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={"text": question},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": 5}
            },
        )
        chunks = []
        for result in response["retrievalResults"]:
            chunks.append({
                "text": result["content"]["text"],
                "source": result["location"]["s3Location"]["uri"],
                "score": result["score"],
            })
        return {"question": question, "chunks": chunks}

    return {"error": f"Unknown tool: {tool_name}"}
