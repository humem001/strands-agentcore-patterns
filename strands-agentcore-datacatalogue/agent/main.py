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

model = BedrockModel(
    model_id="anthropic.claude-sonnet-4-6",
    region_name="eu-west-2",
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
    user_message = payload.get("prompt", "Hello")
    mcp_client = make_mcp_client()
    with mcp_client:
        tools = mcp_client.list_tools_sync()
        agent = Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
        )
        async for event in agent.stream_async(user_message):
            if "data" in event and isinstance(event["data"], str):
                yield event["data"]
            else:
                yield event


if __name__ == "__main__":
    app.run()
