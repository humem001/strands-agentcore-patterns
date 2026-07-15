"""Step 0.5 — Streaming spike. Minimal Strands agent to prove SSE is incremental."""

from strands import Agent
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

model = BedrockModel(
    model_id="anthropic.claude-sonnet-4-6",
    region_name="eu-west-2",
)

agent = Agent(
    model=model,
    system_prompt=(
        "You are a test agent. When asked anything, count from 1 to 5 slowly, "
        "explaining each number in a short sentence. This tests streaming."
    ),
)


@app.entrypoint
async def invoke(payload, context=None):
    """Stream agent response back to caller via SSE."""
    user_message = payload.get("prompt", "Count from 1 to 5 for me.")
    stream = agent.stream_async(user_message)
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]
        else:
            yield event


if __name__ == "__main__":
    app.run()
