#!/usr/bin/env python3
"""Integration smoke test — runs all 11 demo scenarios with one retry + backoff."""

import json
import os
import sys
import time

import boto3

REGION = "eu-west-2"
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
MAX_RETRIES = 1
BACKOFF_SECONDS = 5

SCENARIOS = [
    {
        "id": 1,
        "name": "Discovery",
        "prompt": "I'm new to the fraud team — what datasets are available?",
        "check_keywords": ["fraud", "dataset"],
    },
    {
        "id": 2,
        "name": "Understanding",
        "prompt": "What columns are in the CMS payment history table?",
        "check_keywords": ["nino", "payment", "column"],
    },
    {
        "id": 3,
        "name": "PII Audit",
        "prompt": "Which datasets contain national identification numbers?",
        "check_keywords": ["nino", "HIGH"],
    },
    {
        "id": 4,
        "name": "Lineage",
        "prompt": "Where does the compliance prediction score come from?",
        "check_keywords": ["cms_payment_history", "upstream"],
    },
    {
        "id": 5,
        "name": "Metadata Generation",
        "prompt": "Generate a description for the jcs_chatbot_interactions table",
        "check_keywords": ["chatbot", "description"],
    },
    {
        "id": 6,
        "name": "Join Recommendation",
        "prompt": "I want to link fraud referrals to payment history — how?",
        "check_keywords": ["join", "nino"],
    },
    {
        "id": 7,
        "name": "Live Query",
        "prompt": "Show me the top 10 cases with the highest non-compliance risk score",
        "check_keywords": ["SELECT", "risk_score"],
    },
    {
        "id": 8,
        "name": "Governance",
        "prompt": "Can I share benefit claimant data with an external agency?",
        "check_keywords": ["share", "external agency"],
    },
    {
        "id": 9,
        "name": "Multi-step",
        "prompt": "Find all HIGH PII datasets, show me their lineage, and tell me who owns them",
        "check_keywords": ["HIGH", "lineage", "owner"],
    },
    {
        "id": 10,
        "name": "ML Discovery",
        "prompt": "What ML models do we have for fraud detection?",
        "check_keywords": ["fraud-detection", "model"],
    },
    {
        "id": 11,
        "name": "ML + Data Lineage",
        "prompt": "What data was the compliance predictor trained on, and where does that come from?",
        "check_keywords": ["cms_payment_history", "compliance"],
    },
]


def invoke_agent(client, prompt: str, session_id: str) -> str:
    payload = json.dumps({"prompt": prompt}).encode()

    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=session_id,
        payload=payload,
    )

    content_type = response.get("contentType", "")
    result_text = []

    if "text/event-stream" in content_type:
        for line in response["response"].iter_lines(chunk_size=10):
            if line:
                decoded = line.decode("utf-8")
                if decoded.startswith("data: "):
                    result_text.append(decoded[6:])
    elif content_type == "application/json":
        for chunk in response.get("response", []):
            result_text.append(chunk.decode("utf-8"))

    return "\n".join(result_text)


def check_response(response: str, keywords: list) -> tuple:
    if not response or len(response.strip()) < 10:
        return False, "Response too short or empty"

    response_lower = response.lower()
    missing = [kw for kw in keywords if kw.lower() not in response_lower]
    if missing:
        return False, f"Missing keywords: {missing}"

    return True, "OK"


def run_scenario(client, scenario: dict) -> bool:
    session_id = f"smoke-test-{scenario['id']}-{int(time.time())}"
    attempt = 0

    while attempt <= MAX_RETRIES:
        try:
            if attempt > 0:
                print(f"    Retry (attempt {attempt + 1})...")
                time.sleep(BACKOFF_SECONDS * attempt)

            response = invoke_agent(client, scenario["prompt"], session_id)
            passed, reason = check_response(response, scenario["check_keywords"])

            if passed:
                return True
            else:
                print(f"    Check failed: {reason}")
                if attempt == MAX_RETRIES:
                    return False
        except Exception as e:
            print(f"    Error: {e}")
            if attempt == MAX_RETRIES:
                return False

        attempt += 1

    return False


def main():
    if not AGENT_RUNTIME_ARN:
        print("ERROR: Set AGENT_RUNTIME_ARN environment variable")
        sys.exit(1)

    client = boto3.client("bedrock-agentcore", region_name=REGION)

    print(f"Running {len(SCENARIOS)} demo scenarios against: {AGENT_RUNTIME_ARN}")
    print("=" * 60)

    results = []
    for scenario in SCENARIOS:
        print(f"\n[{scenario['id']:2d}/11] {scenario['name']}")
        print(f"       Prompt: {scenario['prompt'][:60]}...")
        passed = run_scenario(client, scenario)
        results.append({"scenario": scenario, "passed": passed})
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"       {status}")

    print("\n" + "=" * 60)
    passed_count = sum(1 for r in results if r["passed"])
    print(f"\nResults: {passed_count}/{len(SCENARIOS)} passed")

    if passed_count == len(SCENARIOS):
        print("\n✅ ALL SCENARIOS PASSED — demo ready.")
    else:
        failed = [r["scenario"]["name"] for r in results if not r["passed"]]
        print(f"\n❌ Failed scenarios: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
