"""DWP Data Intelligence Agent — Strands SDK on AgentCore Runtime (CodeZip)."""

import os
from pathlib import Path

from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.txt").read_text()

model = BedrockModel(
    model_id="anthropic.claude-sonnet-4-6",
    region_name="eu-west-2",
)

gateway_url = os.environ.get("GATEWAY_URL", "")

mcp_client = MCPClient(gateway_url) if gateway_url else None

agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[mcp_client] if mcp_client else [],
)


@app.entrypoint
async def invoke(payload):
    """Stream agent response back to caller via SSE."""
    user_message = payload.get("prompt", "Hello")
    stream = agent.stream_async(user_message)
    async for event in stream:
        yield event


if __name__ == "__main__":
    app.run()
