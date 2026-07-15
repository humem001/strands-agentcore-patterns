"""DWP Data Intelligence Agent — Streamlit UI (GOV.UK Design System styling)."""

import json
import os
import uuid

import boto3
import streamlit as st

# Inbound auth to the Runtime uses SigV4 via the local AWS credential chain
# (the CLI-deployed runtime is IAM-authenticated). Only the Runtime ARN is needed.
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
REGION = "eu-west-2"

# ---------------------------------------------------------------------------
# GOV.UK Design System styling
# ---------------------------------------------------------------------------
GOVUK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Arial:wght@400;700&display=swap');

/* Hide default Streamlit chrome */
#MainMenu, header[data-testid="stHeader"], footer {visibility: hidden;}
.block-container {padding-top: 0 !important; max-width: 1100px;}

html, body, [class*="css"] {
    font-family: Arial, "Helvetica Neue", Helvetica, sans-serif !important;
    color: #0b0c0c;
}

/* GOV.UK black header bar — aligned to content width */
.govuk-header {
    background: #0b0c0c;
    border-bottom: 10px solid #1d70b8;
    padding: 10px 20px;
    margin: 0 0 0 0;
    display: flex;
    align-items: center;
    gap: 12px;
}
.govuk-header__logo {
    color: #ffffff;
    font-size: 30px;
    font-weight: 700;
    line-height: 1;
}
.govuk-header__service {
    color: #ffffff;
    font-size: 18px;
    font-weight: 700;
    border-left: 1px solid #ffffff;
    padding-left: 12px;
}

/* Phase banner (ALPHA) */
.govuk-phase-banner {
    border-bottom: 1px solid #b1b4b6;
    padding: 10px 0;
    margin-bottom: 20px;
    font-size: 15px;
}
.govuk-tag {
    background: #1d70b8;
    color: #fff;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 3px 8px;
    font-size: 12px;
    margin-right: 10px;
}

/* Headings */
h1, h2, h3 { color: #0b0c0c !important; font-weight: 700 !important; }
.govuk-heading { font-size: 24px; font-weight: 700; margin-bottom: 4px; border-bottom: 2px solid #1d70b8; padding-bottom: 6px; }

/* Panels */
.panel-label {
    font-size: 19px; font-weight: 700; color: #0b0c0c;
    border-bottom: 3px solid #1d70b8; padding-bottom: 6px; margin-bottom: 10px;
}

/* Chat input — constrain to the same width as header/content */
[data-testid="stBottomBlockContainer"] {
    max-width: 1100px !important;
    margin: 0 auto !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}
[data-testid="stChatInput"] textarea:focus,
.stTextInput input:focus {
    outline: 3px solid #ffdd00 !important;
    box-shadow: inset 0 0 0 2px #0b0c0c !important;
}

/* Buttons — GOV.UK green */
.stButton button, .stFormSubmitButton button {
    background: #00703c !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 2px 0 #002d18 !important;
    border-radius: 0 !important;
    font-weight: 400 !important;
    font-size: 13px !important;
    padding: 4px 12px !important;
    min-height: 0 !important;
    text-align: center !important;
    white-space: nowrap !important;
}
.stButton button:hover, .stFormSubmitButton button:hover { background: #005a30 !important; }
.stButton button:focus, .stFormSubmitButton button:focus {
    outline: 3px solid #ffdd00 !important;
    box-shadow: 0 2px 0 #0b0c0c !important;
}

/* Hide "Press Enter to submit form" helper text */
[data-testid="InputInstructions"] { display: none !important; }

/* Reasoning panel styling */
.reasoning-box {
    background: #f3f2f1;
    border-left: 5px solid #1d70b8;
    padding: 12px 15px;
    font-size: 15px;
}

/* Tool-call inset text */
.govuk-inset { border-left: 5px solid #b1b4b6; padding: 8px 15px; margin: 8px 0; }
</style>
"""

GOVUK_HEADER = """
<div class="govuk-header">
    <span class="govuk-header__logo">GOV.UK</span>
    <span class="govuk-header__service">Data Intelligence Agent</span>
</div>
<div class="govuk-phase-banner">
    <span class="govuk-tag">Alpha</span>
    <span>This is a prototype — Department for Work and Pensions data catalogue &amp; governance agent.</span>
</div>
"""


def invoke_agent_streaming(prompt: str, session_id: str):
    client = boto3.client("bedrock-agentcore", region_name=REGION)
    payload = json.dumps({"prompt": prompt}).encode()
    return client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=session_id,
        payload=payload,
    )


def extract_text(ev):
    """Pull a text delta out of any of the shapes Strands emits."""
    if isinstance(ev, str):
        return ev
    if isinstance(ev, dict):
        if isinstance(ev.get("data"), str):
            return ev["data"]
        delta = ev.get("event", {}).get("contentBlockDelta", {}).get("delta", {})
        if "text" in delta:
            return delta["text"]
    return None


def extract_tool(ev):
    """Pull a tool-use (name, input) out of the event if present."""
    if not isinstance(ev, dict):
        return None
    tu = ev.get("current_tool_use")
    if tu and tu.get("name"):
        return tu.get("name"), tu.get("input", {})
    start = ev.get("event", {}).get("contentBlockStart", {}).get("start", {})
    tu = start.get("toolUse")
    if tu and tu.get("name"):
        return tu.get("name"), tu.get("input", {})
    return None


def run_query(prompt, chat_box, reasoning_box):
    """Invoke the agent and render streaming output into the two panels."""
    assistant_text = []
    seen_tools = set()
    reasoning_lines = []

    answer_area = chat_box.empty()
    reasoning_area = reasoning_box.empty()

    try:
        response = invoke_agent_streaming(prompt, st.session_state["session_id"])
        content_type = response.get("contentType", "")

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
                    event = data

                tool = extract_tool(event)
                if tool:
                    name, inp = tool
                    key = f"{name}:{json.dumps(inp, default=str)}"
                    if key not in seen_tools:
                        seen_tools.add(key)
                        target, _, tool_name = name.partition("___")
                        arg = json.dumps(inp, default=str)[:100] if inp else ""
                        reasoning_lines.append(
                            f"<div class='govuk-inset'>🔍 <b>{tool_name or target}</b>"
                            f"<br/><span style='color:#505a5f'>{target}</span>"
                            f"<br/><code>{arg}</code></div>"
                        )
                        reasoning_area.markdown(
                            "".join(reasoning_lines), unsafe_allow_html=True
                        )

                text = extract_text(event)
                if text:
                    assistant_text.append(text)
                    answer_area.markdown("".join(assistant_text))

        elif content_type == "application/json":
            chunks = [c.decode("utf-8") for c in response.get("response", [])]
            assistant_text.append("".join(chunks))
            answer_area.markdown("".join(assistant_text))

        final = "".join(assistant_text) if assistant_text else "No response received."
        if reasoning_lines:
            reasoning_lines.append(
                "<div class='govuk-inset' style='border-left-color:#00703c'>"
                "✅ <b>Complete</b></div>"
            )
            reasoning_area.markdown("".join(reasoning_lines), unsafe_allow_html=True)
        return final
    except Exception as e:
        answer_area.error(f"Error: {e}")
        return f"Error: {e}"


def main():
    st.set_page_config(page_title="DWP Data Intelligence Agent", layout="wide")
    st.markdown(GOVUK_CSS, unsafe_allow_html=True)
    st.markdown(GOVUK_HEADER, unsafe_allow_html=True)

    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "session_id" not in st.session_state:
        # Runtime requires runtimeSessionId to be at least 33 chars.
        st.session_state["session_id"] = f"dwp-ui-{uuid.uuid4().hex}"

    # Question box — placed at the top, directly under the phase banner.
    with st.form(key="ask_form", clear_on_submit=True):
        q_col, btn_col = st.columns([8, 1], gap="small", vertical_alignment="center")
        with q_col:
            typed = st.text_input(
                "Question",
                key="q",
                label_visibility="collapsed",
                placeholder="Ask a question about your data",
            )
        with btn_col:
            submitted = st.form_submit_button("Search")

    prompt = typed.strip() if (submitted and typed and typed.strip()) else None

    chat_col, reasoning_col = st.columns([3, 2], gap="large")

    with chat_col:
        st.markdown("<div class='panel-label'>Conversation</div>", unsafe_allow_html=True)
        chat_history = st.container(height=460)
        with chat_history:
            for msg in st.session_state["messages"]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

    with reasoning_col:
        st.markdown("<div class='panel-label'>Agent reasoning (live)</div>", unsafe_allow_html=True)
        reasoning_history = st.container(height=460)

    if prompt:
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with chat_history:
            with st.chat_message("user"):
                st.markdown(prompt)
            assistant_box = st.chat_message("assistant")
        with reasoning_history:
            reasoning_box = st.container()

        final = run_query(prompt, assistant_box, reasoning_box)
        st.session_state["messages"].append({"role": "assistant", "content": final})


if __name__ == "__main__":
    main()
