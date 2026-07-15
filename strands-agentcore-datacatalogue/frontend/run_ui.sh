#!/bin/bash
# Launch the DWP Data Intelligence Agent UI locally against the deployed Runtime.
# Requires active AWS credentials (SigV4 inbound auth to the Runtime).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# Runtime ARN — override via env if you redeploy the agent.
export AGENT_RUNTIME_ARN="${AGENT_RUNTIME_ARN:-arn:aws:bedrock-agentcore:eu-west-2:581571671018:runtime/runtimedeploy_Agent-JVlTK9E59Y}"

# Find a Python interpreter that has streamlit; else set one up in a local venv.
find_streamlit() {
  for py in "../../.venv/bin/python" "../.venv/bin/python" ".venv/bin/python"; do
    if [ -x "$py" ] && "$py" -c "import streamlit" 2>/dev/null; then
      echo "$py"; return 0
    fi
  done
  return 1
}

PY="$(find_streamlit || true)"
if [ -z "${PY:-}" ]; then
  echo "No venv with streamlit found — creating .venv and installing requirements..."
  python3 -m venv .venv
  ./.venv/bin/python -m pip install --quiet --upgrade pip
  ./.venv/bin/python -m pip install --quiet -r requirements.txt
  PY="./.venv/bin/python"
fi

echo "Using: $PY"
echo "Runtime: $AGENT_RUNTIME_ARN"
exec "$PY" -m streamlit run app.py
