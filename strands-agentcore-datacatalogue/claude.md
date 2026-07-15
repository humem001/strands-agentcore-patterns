
# Data Catalogue / Governance Agent — Locked Constraints

These decisions are **fixed and confirmed** (design v5). Do not re-open, re-litigate, or propose alternatives to them. If a task appears to conflict with a constraint, flag the conflict and ask — do not silently deviate.

Source brief: `/claude-demo/data_catalogue_governance_agent.md`

## Platform & Region

- **Region: eu-west-2 (London) only.** All resources, all services. UK data-residency is part of the demo narrative.
- **Agent host: Bedrock AgentCore Runtime** — CodeZip build (Python zipped to S3, no Docker/ARM64 container), HTTP protocol (`/invocations`, SSE streaming). NOT Lambda + API Gateway.
- **Agent framework: Strands SDK.** Streaming via `stream_async` — each reasoning/tool step must stream incrementally to the UI (the live reasoning panel is the demo's core value).
- **LLM: Bedrock Claude Sonnet. Embeddings: Titan Text Embeddings v2.**
- **Tools: AgentCore Gateway** (MCP) with **5 `lambda` targets exposing 10 tools**. Tool discovery is dynamic via `tools/list` (Gateway prefixes tools as `${target_name}___${tool_name}`).

## Architecture Rules

- **The orchestrator owns ALL LLM reasoning — zero exceptions.** Target Lambdas are dumb data accessors: they call AWS APIs and return structured data. They never call Bedrock.
- **Governance KB: Bedrock Knowledge Base on S3 Vectors** (NOT OpenSearch Serverless — avoids standing cost). KB access is **`retrieve` only**; the orchestrator synthesises answers and citations. Never use `retrieve_and_generate`.
- **Glue tables are created directly** (no Crawler). Table definitions AND the Parquet data generator are both driven from a **single YAML manifest** — one reviewable data model, no schema/data drift.
- **`search_catalogue` demo-primary path:** `glue.get_tables()` returning the full catalogue with orchestrator-side semantic filtering (10 tables fit in context). `glue.search_tables` stays in the target as the at-scale story only.
- **`generate_metadata` write-back is DISABLED by default.** Enforced by IAM (no `glue:UpdateTable` on the target role) unless an explicit deploy flag enables it. Never rely on prompt-level guardrails alone.
- **Athena safety is IAM-enforced:** athena-target role gets read-only Glue + read-only S3, a dedicated workgroup with fixed output location. Orchestrator applies `LIMIT 100` and never emits DML/DDL — but IAM is the real guardrail.

## Auth (two boundaries — do not conflate)

- **Inbound (Streamlit → Runtime):** simplified login — single pre-provisioned Cognito app-client token. No hosted UI, no per-user accounts.
- **M2M (agent → Gateway):** Cognito client-credentials via **AgentCore Identity** (`@requires_access_token` with a registered Cognito credential provider). No hand-rolled token exchange.
- **Gateway inbound auth:** CUSTOM_JWT authorizer → Cognito. **Gateway outbound to Lambdas:** `GATEWAY_IAM_ROLE` (SigV4 `lambda:InvokeFunction`).
- **AgentCore Policy (Cedar) is deliberately NOT used** in this build — a single M2M token gives nothing to differentiate on. Do not add it.

## Deploy & Data

- **Split deploy:** AWS CDK (Python) for data-plane infra (S3, Glue, Lambdas, Cognito, KB, SageMaker, IAM) + `@aws/agentcore` CLI with `agentcore.json` for Runtime, Gateway targets, and Identity provider. Orchestrated by `setup.sh`; full cleanup via `teardown.sh` (must include S3 Vectors store, KB, Gateway, Runtime, Cognito pool).
- **One command creates everything:** `./setup.sh`. The human only provides credentials and runs it.
- **Data: 10 synthetic datasets, fully fictional** — no real names, NINOs, or case references. SageMaker assets are metadata-only (no training); Feature Store is **offline-only** (no online store).
- **Frontend: Streamlit, run locally** (`streamlit run app.py`). No frontend hosting infra.

## Build Process

- **Step 0.5 streaming spike is a HARD GATE:** before the full build, deploy a trivial Strands agent via CodeZip and confirm `InvokeAgentRuntime` delivers events incrementally (not buffered) end-to-end. Do not proceed until proven.
- **Testing is demo-level only:** one integration smoke script running the 11 demo scenarios (with one retry + backoff per scenario). No mocked unit tests, no load/perf testing.
- **The 11 demo scenarios in the source brief are the acceptance criteria.**

## Cost Discipline

- No standing-cost services: S3 Vectors (not OpenSearch Serverless), offline-only Feature Store, pay-per-use AgentCore. `teardown.sh` must return the account to zero ongoing charges.