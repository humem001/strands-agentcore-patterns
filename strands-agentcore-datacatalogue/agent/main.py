"""DWP Data Intelligence Agent — Strands on AgentCore Runtime (CodeZip).

Connects to AgentCore Gateway (MCP) using a Cognito M2M token, discovers the
10 tools via tools/list, and streams reasoning + tool steps back over SSE.
"""

import os
from pathlib import Path

import requests
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.txt").read_text()

GATEWAY_URL = os.environ["GATEWAY_URL"]
TOKEN_ENDPOINT = os.environ["COGNITO_TOKEN_ENDPOINT"]
M2M_CLIENT_ID = os.environ["COGNITO_M2M_CLIENT_ID"]
M2M_CLIENT_SECRET = os.environ["COGNITO_M2M_CLIENT_SECRET"]
M2M_SCOPE = os.environ.get("COGNITO_M2M_SCOPE", "dwp-demo-api/gateway.tools")

GUARDRAIL_ID = os.environ.get("GUARDRAIL_ID", "hf6qyzh9j13b")
GUARDRAIL_VERSION = os.environ.get("GUARDRAIL_VERSION", "DRAFT")

model = BedrockModel(
    model_id="anthropic.claude-sonnet-4-6",
    region_name="eu-west-2",
    guardrail_id=GUARDRAIL_ID,
    guardrail_version=GUARDRAIL_VERSION,
)


def get_gateway_token() -> str:
    resp = requests.post(
        TOKEN_ENDPOINT,
        data={"grant_type": "client_credentials", "scope": M2M_SCOPE},
        auth=(M2M_CLIENT_ID, M2M_CLIENT_SECRET),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def make_mcp_client() -> MCPClient:
    token = get_gateway_token()
    return MCPClient(
        lambda: streamablehttp_client(
            GATEWAY_URL,
            headers={"Authorization": f"Bearer {token}"},
        )
    )


@app.entrypoint
async def invoke(payload, context=None):
    import json as _json

    user_message = payload.get("prompt", "Hello")
    mcp_client = make_mcp_client()
    with mcp_client:
        tools = mcp_client.list_tools_sync()
        agent = Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
        )
        seen_tool_ids = set()
        pending_markers = []
        async for event in agent.stream_async(user_message):
            if not isinstance(event, dict):
                continue

            # Tool use — queue a marker to inject with the next text yield
            tu = event.get("current_tool_use")
            if tu and isinstance(tu, dict):
                tool_id = tu.get("toolUseId", "")
                name = tu.get("name", "")
                inp = tu.get("input")
                if tool_id and name and isinstance(inp, dict) and tool_id not in seen_tool_ids:
                    seen_tool_ids.add(tool_id)
                    pending_markers.append(f"<!--TOOL:{name}|{_json.dumps(inp, default=str)}-->")

            # Text content — prepend any queued tool markers
            if "data" in event and isinstance(event["data"], str):
                if pending_markers:
                    prefix = "\n".join(pending_markers) + "\n"
                    pending_markers.clear()
                    yield prefix + event["data"]
                else:
                    yield event["data"]

        # Flush any remaining markers (tool called at the very end with no text after)
        if pending_markers:
            yield "\n" + "\n".join(pending_markers)


if __name__ == "__main__":
    app.run()
