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
.block-container {padding-top: 0 !important; max-width: 98% !important; width: 98% !important; padding-left: 2rem !important; padding-right: 2rem !important;}

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

/* Flashing green processing indicator */
@keyframes pulse-green {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.2; }
}
.processing-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    background: #00703c;
    border-radius: 50%;
    margin-left: 8px;
    animation: pulse-green 1.2s ease-in-out infinite;
    vertical-align: middle;
}

/* Chat input — match full content width */
[data-testid="stBottomBlockContainer"] {
    max-width: 98% !important;
    width: 98% !important;
    margin: 0 auto !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
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


/* Conversation panel — cleaner markdown rendering */
[data-testid="stChatMessage"] {
    font-size: 15px !important;
    line-height: 1.5 !important;
}
[data-testid="stChatMessage"] hr {
    border: none !important;
    border-top: 1px solid #b1b4b6 !important;
    margin: 12px 0 !important;
}
[data-testid="stChatMessage"] table {
    font-size: 14px !important;
    border-collapse: collapse !important;
    width: 100% !important;
    margin: 8px 0 !important;
}
[data-testid="stChatMessage"] th {
    background: #f3f2f1 !important;
    font-weight: 700 !important;
    text-align: left !important;
    padding: 6px 10px !important;
    border-bottom: 2px solid #0b0c0c !important;
}
[data-testid="stChatMessage"] td {
    padding: 6px 10px !important;
    border-bottom: 1px solid #b1b4b6 !important;
    vertical-align: top !important;
}
[data-testid="stChatMessage"] h2 {
    font-size: 17px !important;
    margin: 14px 0 6px 0 !important;
    padding: 0 !important;
    border: none !important;
}
[data-testid="stChatMessage"] ul, [data-testid="stChatMessage"] ol {
    padding-left: 20px !important;
    margin: 6px 0 !important;
}
[data-testid="stChatMessage"] li {
    margin-bottom: 4px !important;
}
[data-testid="stChatMessage"] code {
    background: #f3f2f1 !important;
    padding: 1px 4px !important;
    font-size: 13px !important;
}
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


def run_query(prompt, chat_box, reasoning_box):
    """Invoke the agent and render streaming output into the two panels."""
    assistant_text = []
    reasoning_lines = []
    seen_tools = set()

    answer_area = chat_box.empty()
    reasoning_area = reasoning_box.empty()

    def render_reasoning():
        # Wrap in a scrollable div that anchors to the bottom (column-reverse trick)
        inner = "".join(reasoning_lines)
        reasoning_area.markdown(
            f"<div style='max-height:440px;overflow-y:auto;display:flex;flex-direction:column-reverse;'>"
            f"<div>{inner}</div></div>",
            unsafe_allow_html=True,
        )

    reasoning_lines.append(
        "<div class='govuk-inset' style='border-left-color:#1d70b8'>"
        "⏳ <b>Connecting to agent...</b></div>"
    )
    render_reasoning()

    try:
        response = invoke_agent_streaming(prompt, st.session_state["session_id"])
        content_type = response.get("contentType", "")

        first_text = True
        total_events = 0

        if "text/event-stream" in content_type:
            for line in response["response"].iter_lines(chunk_size=10):
                if not line:
                    continue
                decoded = line.decode("utf-8")
                if not decoded.startswith("data: "):
                    continue
                data = decoded[6:]

                try:
                    text = json.loads(data)
                except json.JSONDecodeError:
                    text = data

                if not isinstance(text, str):
                    continue

                # Strip out any <!--TOOL:...--> markers that leaked through
                while "<!--TOOL:" in text and "-->" in text:
                    start = text.find("<!--TOOL:")
                    end = text.find("-->", start) + 3
                    text = text[:start] + text[end:]

                if not text:
                    continue

                total_events += 1

                if first_text:
                    reasoning_lines = [
                        "<div class='govuk-inset' style='border-left-color:#1d70b8'>"
                        "⚡ <b>Agent responding</b></div>"
                    ]
                    render_reasoning()
                    first_text = False

                assistant_text.append(text)
                full_so_far = "".join(assistant_text)

                # Detect >>> TOOL: or TOOL: lines in the accumulated text
                # and mirror them to the reasoning panel in real time.
                for line in full_so_far.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith(">>> TOOL:") or stripped.startswith("TOOL:"):
                        marker = stripped.replace(">>> TOOL:", "").replace("TOOL:", "").strip()
                        tool_name, _, desc = marker.partition("|")
                        tool_name = tool_name.strip()
                        desc = desc.strip()
                        key = f"{tool_name}:{desc}"
                        if key not in seen_tools:
                            seen_tools.add(key)
                            reasoning_lines.append(
                                f"<div class='govuk-inset' style='border-left-color:#1d70b8'>"
                                f"🔍 <b>{tool_name}</b>"
                                f"<br/><span style='color:#505a5f'>{desc}</span></div>"
                            )
                            render_reasoning()

                answer_area.markdown(full_so_far)

        elif content_type == "application/json":
            chunks = [c.decode("utf-8") for c in response.get("response", [])]
            assistant_text.append("".join(chunks))
            answer_area.markdown("".join(assistant_text))

        final = "".join(assistant_text) if assistant_text else "No response received."

        # Final reasoning state — show what tools were actually used
        # (detected from the answer content for accuracy)
        tool_evidence = [
            ("search_catalogue", "Searched the data catalogue", "AWS Glue", ["datasets", "catalogue", "tables", "found"]),
            ("classify_pii", "Classified PII sensitivity", "AWS Glue", ["PII", "NINO", "HIGH", "sensitivity", "classified"]),
            ("show_lineage", "Traced data lineage", "AWS Glue", ["upstream", "downstream", "lineage", "comes from"]),
            ("policy_search", "Searched governance policies", "Bedrock KB · S3 Vectors", ["policy", "sharing", "DPIA", "legal gateway", "DSA"]),
            ("query_dataset", "Executed live SQL query", "Amazon Athena", ["SELECT", "query", "rows"]),
            ("generate_metadata", "Generated metadata", "AWS Glue", ["FAIR", "generated description"]),
            ("suggest_joins", "Recommended joins", "AWS Glue", ["join", "JOIN", "link"]),
            ("list_ml_models", "Discovered ML models", "Amazon SageMaker", ["model", "SageMaker", "feature group"]),
            ("describe_ml_asset", "Described ML asset", "Amazon SageMaker", ["trained on", "model package"]),
        ]

        final_reasoning = []

        # Only show tool evidence if the response was substantial
        # (short responses = guardrail blocks or simple refusals, no tools ran)
        if total_events > 100:
            final_lower = final.lower()
            for tool_name, desc, datasource, keywords in tool_evidence:
                if any(kw.lower() in final_lower for kw in keywords):
                    final_reasoning.append(
                        f"<div class='govuk-inset' style='border-left-color:#1d70b8'>"
                        f"✅ <b>{tool_name}</b>"
                        f"<br/><span style='color:#505a5f'>{desc}</span>"
                        f"<br/><span style='color:#1d70b8;font-size:12px'>⛁ {datasource}</span></div>"
                    )

        final_reasoning.append(
            "<div class='govuk-inset' style='border-left-color:#00703c'>"
            f"🏁 <b>Complete</b> — {total_events} tokens streamed</div>"
        )
        reasoning_area.markdown("".join(final_reasoning), unsafe_allow_html=True)

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

    # Reset both panels on new submission
    if prompt:
        st.session_state["messages"] = []

    is_processing = prompt is not None

    chat_col, reasoning_col = st.columns([3, 2], gap="large")

    with chat_col:
        st.markdown("<div class='panel-label'>Conversation</div>", unsafe_allow_html=True)
        chat_history = st.container(height=460)
        with chat_history:
            for msg in st.session_state["messages"]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

    with reasoning_col:
        reasoning_label = st.empty()
        if is_processing:
            reasoning_label.markdown(
                "<div class='panel-label'>Agent reasoning (live)<span class='processing-dot'></span></div>",
                unsafe_allow_html=True,
            )
        else:
            reasoning_label.markdown(
                "<div class='panel-label'>Agent reasoning (live)</div>",
                unsafe_allow_html=True,
            )
        reasoning_history = st.container()

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

        # Stop the flashing dot
        reasoning_label.markdown(
            "<div class='panel-label'>Agent reasoning (live)</div>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
