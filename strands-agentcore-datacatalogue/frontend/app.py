"""DWP Data Intelligence Agent — Streamlit UI with live reasoning panel."""

import json
import os
import time

import boto3
import requests
import streamlit as st

COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
COGNITO_CLIENT_SECRET = os.environ.get("COGNITO_CLIENT_SECRET", "")
COGNITO_TOKEN_ENDPOINT = os.environ.get("COGNITO_TOKEN_ENDPOINT", "")
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
REGION = "eu-west-2"


def get_token():
    if "access_token" in st.session_state and st.session_state.get("token_expiry", 0) > time.time():
        return st.session_state["access_token"]

    response = requests.post(
        COGNITO_TOKEN_ENDPOINT,
        data={"grant_type": "client_credentials", "scope": "dwp-demo-api/runtime.invoke"},
        auth=(COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    response.raise_for_status()
    token_data = response.json()
    st.session_state["access_token"] = token_data["access_token"]
    st.session_state["token_expiry"] = time.time() + token_data.get("expires_in", 3600) - 60
    return token_data["access_token"]


def invoke_agent_streaming(prompt: str, session_id: str):
    client = boto3.client("bedrock-agentcore", region_name=REGION)
    payload = json.dumps({"prompt": prompt}).encode()

    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=session_id,
        payload=payload,
    )
    return response


def main():
    st.set_page_config(page_title="DWP Data Intelligence Agent", layout="wide")
    st.title("DWP Data Intelligence Agent")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = f"session-{int(time.time())}"

    chat_col, reasoning_col = st.columns([3, 2])

    with chat_col:
        st.subheader("Chat")
        for msg in st.session_state["messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        prompt = st.chat_input("Ask a question about DWP data...")

    with reasoning_col:
        st.subheader("Agent Reasoning")
        reasoning_container = st.container()

    if prompt:
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with chat_col:
            with st.chat_message("user"):
                st.markdown(prompt)

        with reasoning_col:
            with reasoning_container:
                reasoning_placeholder = st.empty()
                reasoning_events = []

        try:
            response = invoke_agent_streaming(prompt, st.session_state["session_id"])
            content_type = response.get("contentType", "")

            assistant_text = []

            if "text/event-stream" in content_type:
                for line in response["response"].iter_lines(chunk_size=10):
                    if not line:
                        continue
                    decoded = line.decode("utf-8")
                    if not decoded.startswith("data: "):
                        continue
                    data = decoded[6:]

                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        assistant_text.append(data)
                        continue

                    event_type = event.get("type", "")

                    if event_type in ("contentBlockDelta",):
                        delta = event.get("delta", {})
                        if "text" in delta:
                            assistant_text.append(delta["text"])
                            with chat_col:
                                with st.chat_message("assistant"):
                                    st.markdown("".join(assistant_text))

                    elif event_type in ("toolUse", "contentBlockStart"):
                        tool_info = event.get("toolUse", event.get("start", {}))
                        if tool_info:
                            tool_name = tool_info.get("name", "unknown")
                            tool_input = tool_info.get("input", {})
                            reasoning_events.append(f"🔍 **{tool_name}**({json.dumps(tool_input, default=str)[:100]})")
                            with reasoning_col:
                                reasoning_placeholder.markdown("\n\n".join(reasoning_events))

                    elif event_type == "toolResult":
                        reasoning_events.append("✅ Result received")
                        with reasoning_col:
                            reasoning_placeholder.markdown("\n\n".join(reasoning_events))

            elif response.get("contentType") == "application/json":
                chunks = []
                for chunk in response.get("response", []):
                    chunks.append(chunk.decode("utf-8"))
                result = json.loads("".join(chunks))
                assistant_text.append(str(result))

            final_response = "".join(assistant_text) if assistant_text else "No response received."
            st.session_state["messages"].append({"role": "assistant", "content": final_response})

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            st.session_state["messages"].append({"role": "assistant", "content": error_msg})
            with chat_col:
                with st.chat_message("assistant"):
                    st.error(error_msg)


if __name__ == "__main__":
    main()
