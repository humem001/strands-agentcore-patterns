# Tasks — Data Catalogue & Governance Agent

> Source brief: `data_catalogue_governance_agent.md` (v5)
> Requirements: `spec/requirements.md`
> Design: `spec/design.md`
> Status: **DRAFT — awaiting review**
> Date: 2026-07-15

---

## Task Ordering & Dependencies

```
Step 0.5 (GATE) ──▶ Step 1 ──▶ Step 2 ──▶ Step 3 ──▶ Step 4 ──▶ Step 5 ──▶ Step 6
 Streaming spike     Repo +     Data +     ML + KB    Lambda     AgentCore   Frontend +
                     CDK infra  Glue                  targets    layer       deploy scripts
```

**Hard gate:** Step 0.5 must pass before any subsequent work begins.

---

## Step 0: Pre-Build Verification

### T-0.1: Enable Bedrock Model Access

| Field | Value |
|-------|-------|
| Type | Manual (human) |
| Description | Enable Bedrock model access in the eu-west-2 console for Claude Sonnet and Titan Text Embeddings V2 |
| Acceptance | `aws bedrock get-foundation-model --model-identifier anthropic.claude-sonnet-v2 --region eu-west-2` succeeds; same for `amazon.titan-embed-text-v2:0` |
| Depends on | — |

---

## Step 0.5: Streaming Spike (HARD GATE)

### T-0.5.1: Create Spike Agent

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Write a trivial Strands agent (`spike/agent.py`) that yields ~5 fake reasoning events with short delays. Uses Bedrock Claude Sonnet in eu-west-2. Exposes `/invocations` HTTP handler with SSE streaming. |
| Files | `spike/agent.py`, `spike/requirements.txt` |
| Acceptance | Agent code runs locally without error; yields distinct events with measurable gaps |
| Depends on | T-0.1 |

### T-0.5.2: Create Spike agentcore.json

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Write `spike/agentcore.json` defining a minimal AgentCore Runtime (CodeZip, HTTP protocol, eu-west-2). No Gateway needed for the spike. |
| Files | `spike/agentcore.json` |
| Acceptance | Valid JSON; conforms to AgentCore CLI schema |
| Depends on | — |

### T-0.5.3: Deploy Spike via agentcore CLI

| Field | Value |
|-------|-------|
| Type | Deploy |
| Description | Run `agentcore deploy` from the `spike/` directory. Confirm Runtime is created and endpoint is reachable. |
| Acceptance | `agentcore deploy` exits 0; Runtime ARN/endpoint returned |
| Depends on | T-0.5.1, T-0.5.2 |

### T-0.5.4: Write Stream Verification Script

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Write `spike/test_stream.py` that calls `InvokeAgentRuntime` (boto3), consumes the SSE stream, and asserts: (1) first event within 5s, (2) events arrive incrementally (not all at end), (3) at least 3 distinct events. |
| Files | `spike/test_stream.py` |
| Acceptance | Script passes all 3 assertions against the deployed spike |
| Depends on | T-0.5.3 |

### T-0.5.5: Gate Decision

| Field | Value |
|-------|-------|
| Type | Decision |
| Description | Review spike results. If all gate criteria pass → proceed to Step 1. If streaming is buffered → investigate Runtime config or escalate. |
| Gate criteria | (1) Deploy succeeds, (2) SSE stream returns, (3) first event < 5s, (4) events are incremental, (5) ≥ 3 events |
| Depends on | T-0.5.4 |

---

## Step 1: Repo Structure + CDK Data Infrastructure

### T-1.1: Initialise Project Structure

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Create the full directory structure per design §2. Add `.gitignore` (ignore `data/parquet/`, `cdk.out/`, `*.zip`, `__pycache__/`, `.env`, `cdk-outputs.json`). |
| Files | All directories, `.gitignore` |
| Acceptance | Structure matches design; git-clean |
| Depends on | T-0.5.5 (gate passed) |

### T-1.2: CDK App Skeleton

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Create CDK Python app (`infra/app.py`, `infra/cdk.json`, `infra/requirements.txt`). Define the 5 stacks (empty classes initially). Region hardcoded to eu-west-2. |
| Files | `infra/app.py`, `infra/cdk.json`, `infra/requirements.txt`, `infra/stacks/__init__.py` |
| Acceptance | `cdk synth` produces valid CloudFormation (empty stacks) |
| Depends on | T-1.1 |

### T-1.3: DataPlatformStack — S3 Buckets

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Create S3 buckets: (1) `dwp-demo-data-{account}` (Parquet datasets), (2) `dwp-demo-athena-results-{account}` (Athena output), (3) `dwp-demo-kb-source-{account}` (governance docs). All with `RemovalPolicy.DESTROY` + `auto_delete_objects=True`. Export ARNs. |
| Files | `infra/stacks/data_platform_stack.py` |
| Acceptance | `cdk synth` produces S3 bucket resources with correct policies |
| Depends on | T-1.2 |

### T-1.4: DataPlatformStack — Glue Database + Athena Workgroup

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Add Glue Database (`dwp_data_catalogue`). Add Athena Workgroup (`dwp-demo-athena-wg`) with fixed `OutputLocation` pointing to the Athena results bucket. Export DB name and workgroup name. |
| Files | `infra/stacks/data_platform_stack.py` |
| Acceptance | Synth includes `AWS::Glue::Database` and `AWS::Athena::WorkGroup` |
| Depends on | T-1.3 |

### T-1.5: CognitoStack

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Create User Pool (`dwp-demo-pool`), Resource Server (`dwp-demo-api` with scopes `runtime/invoke`, `gateway/tools`), two App Clients (inbound + M2M, both `ALLOW_CLIENT_CREDENTIALS`). Export: pool ID, pool ARN, issuer URL, both client IDs and secrets. |
| Files | `infra/stacks/cognito_stack.py` |
| Acceptance | Synth includes Cognito resources; outputs include all required values |
| Depends on | T-1.2 |

### T-1.6: Deploy Step 1

| Field | Value |
|-------|-------|
| Type | Deploy |
| Description | Run `cdk deploy DataPlatformStack CognitoStack` to verify infra creates cleanly. |
| Acceptance | Stacks deploy without error; outputs visible in CloudFormation |
| Depends on | T-1.3, T-1.4, T-1.5 |

---

## Step 2: Synthetic Data + Glue Tables

### T-2.1: Write Data Manifest

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Create `data/manifest.yaml` defining all 10 tables: name, description, classification, owner, steward, PDU, lineage (upstream/downstream/transformation), and full column definitions (name, type, description, PII level). Include generator hints (row counts, seed). |
| Files | `data/manifest.yaml` |
| Acceptance | Valid YAML; covers all 10 tables from the source brief; every column annotated |
| Depends on | T-1.1 |

### T-2.2: Write Parquet Generator

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Create `data/generate_parquet.py` that reads `manifest.yaml` and generates one `.parquet` file per table in `data/parquet/`. Use Faker for realistic fictional data. Seed for reproducibility. All data fully fictional. |
| Files | `data/generate_parquet.py`, `data/requirements.txt` |
| Acceptance | Running `python data/generate_parquet.py` produces 10 Parquet files with correct schemas and row counts |
| Depends on | T-2.1 |

### T-2.3: Write Glue Table Creation Script

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Create `scripts/create_glue_tables.py` that reads `manifest.yaml` and calls `glue.create_table()` for each table. Sets: columns (from manifest), SerDe (Parquet), S3 location, and all custom Parameters (description, classification, owner, steward, pdu, lineage_*). |
| Files | `scripts/create_glue_tables.py` |
| Acceptance | Script creates all 10 tables with correct schemas and properties (verified via `aws glue get-table`) |
| Depends on | T-2.1, T-1.6 (Glue DB exists) |

### T-2.4: Upload Data + Create Tables

| Field | Value |
|-------|-------|
| Type | Deploy |
| Description | Run: (1) `python data/generate_parquet.py`, (2) `aws s3 sync data/parquet/ s3://{data-bucket}/`, (3) `python scripts/create_glue_tables.py`. Verify tables queryable via Athena. |
| Acceptance | `SELECT * FROM dwp_data_catalogue.cms_payment_history LIMIT 5` returns rows in Athena |
| Depends on | T-2.2, T-2.3 |

---

## Step 3: ML Assets + Knowledge Base

### T-3.1: Write ML Asset Registration Script

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Create `scripts/register_ml_assets.py` that registers: (1) 3 Model Package Groups with 1 version each (dummy S3 artifact, inference spec, metrics in CustomerMetadataProperties), (2) 1 Feature Group (`cms-payment-features`, offline-only, 5–6 feature definitions). |
| Files | `scripts/register_ml_assets.py` |
| Acceptance | `aws sagemaker list-model-package-groups` returns 3 groups; `describe-feature-group` returns the offline group with features |
| Depends on | T-1.1 |

### T-3.2: KnowledgeBaseStack — CDK

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Add to `infra/stacks/knowledge_base_stack.py`: Bedrock Knowledge Base with S3 Vectors as the vector store, Titan Text Embeddings V2 as the embedding model, and the KB source bucket as the data source. Export KB ID and ARN. Use L1 `CfnKnowledgeBase` or custom resource as needed. |
| Files | `infra/stacks/knowledge_base_stack.py` |
| Acceptance | `cdk synth` includes KB + S3 Vectors resources; KB ID exported |
| Depends on | T-1.3 (KB source bucket) |

### T-3.3: MlAssetsStack — CDK

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Add `infra/stacks/ml_assets_stack.py`: SageMaker Model Package Group (×3) and Feature Group (offline, S3 store pointing to data bucket). Note: actual versions/features registered via script (T-3.1), not CDK — CDK just creates the groups. |
| Files | `infra/stacks/ml_assets_stack.py` |
| Acceptance | `cdk synth` includes SageMaker resources |
| Depends on | T-1.3 |

### T-3.4: Bundle Governance Documents

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Write/bundle 5 markdown files in `data/governance_docs/`: DWP Data Strategy, FAIR Principles, Data Sharing Policy (synthetic), AI Security Policy, Information Management Policy. Content from published gov.uk sources + one synthetic doc. |
| Files | `data/governance_docs/*.md` (5 files) |
| Acceptance | 5 files present with substantive content (≥500 words each) |
| Depends on | T-1.1 |

### T-3.5: Write KB Sync Script

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Create `scripts/sync_knowledge_base.py` that: (1) triggers `bedrock_agent.start_ingestion_job(knowledgeBaseId, dataSourceId)`, (2) polls until status = COMPLETE. |
| Files | `scripts/sync_knowledge_base.py` |
| Acceptance | After upload + sync, `bedrock_agent_runtime.retrieve(knowledgeBaseId, query)` returns chunks |
| Depends on | T-3.2 |

### T-3.6: Deploy Step 3

| Field | Value |
|-------|-------|
| Type | Deploy |
| Description | Deploy KB + ML stacks, upload governance docs, sync KB, register ML assets. |
| Acceptance | KB retrieval returns chunks for "Can I share data with HMRC?"; SageMaker assets listed |
| Depends on | T-3.1, T-3.2, T-3.3, T-3.4, T-3.5 |

---

## Step 4: Lambda Targets (5 Lambdas, 10 Tools)

### T-4.1: glue-catalogue Target

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Write `targets/glue_catalogue/handler.py` — dispatcher on `tool_name` field. Implements: `search_catalogue` (`get_tables` + `search_tables`), `get_dataset_detail` (`get_table`), `show_lineage` (extract `lineage_*` properties), `generate_metadata` (return schema; write-back path gated by IAM), `suggest_joins` (return all table schemas). |
| Files | `targets/glue_catalogue/handler.py`, `targets/glue_catalogue/requirements.txt` |
| Acceptance | Local invocation with test event returns correct structured data for each of the 5 tools |
| Depends on | T-2.4 (tables exist) |

### T-4.2: athena-query Target

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Write `targets/athena_query/handler.py` — accepts `sql`, `database`, `table_name`; runs `start_query_execution` on the dedicated workgroup; polls `get_query_execution`; returns results via `get_query_results`. Timeout handling (max 30s poll). |
| Files | `targets/athena_query/handler.py`, `targets/athena_query/requirements.txt` |
| Acceptance | Invoking with a valid SELECT returns rows from Athena |
| Depends on | T-2.4 (data queryable) |

### T-4.3: sagemaker-ml Target

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Write `targets/sagemaker_ml/handler.py` — `list_ml_models`: calls `list_model_package_groups` + `list_feature_groups`; `describe_ml_asset`: calls `describe_model_package` or `describe_feature_group` based on `asset_type`. |
| Files | `targets/sagemaker_ml/handler.py`, `targets/sagemaker_ml/requirements.txt` |
| Acceptance | Returns model/feature group metadata matching registered assets |
| Depends on | T-3.6 (ML assets registered) |

### T-4.4: pii-classifier Target

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Write `targets/pii_classifier/handler.py` — calls `glue.get_table()`, returns column names, types, descriptions, and sample values (from table parameters or hardcoded representative samples). NO Bedrock calls. |
| Files | `targets/pii_classifier/handler.py`, `targets/pii_classifier/requirements.txt` |
| Acceptance | Returns structured column info for any table in the catalogue |
| Depends on | T-2.4 |

### T-4.5: governance-kb Target

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Write `targets/governance_kb/handler.py` — calls `bedrock_agent_runtime.retrieve(knowledgeBaseId, retrievalQuery={text: question})`. Returns ranked chunks with text + source metadata. NO `retrieve_and_generate`. KB ID from environment variable. |
| Files | `targets/governance_kb/handler.py`, `targets/governance_kb/requirements.txt` |
| Acceptance | Returns relevant chunks for governance questions; source metadata present |
| Depends on | T-3.6 (KB synced) |

### T-4.6: LambdaTargetsStack — CDK (IAM + Functions)

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Implement `infra/stacks/lambda_targets_stack.py`: 5 Lambda functions (Python 3.11 runtime), each with a least-privilege IAM role per design §7.2. Environment variables: DB name, workgroup, KB ID, bucket names (from cross-stack imports). Export all 5 Lambda ARNs. Conditionally add `glue:UpdateTable` to glue-target role only if context variable `enable_write_back` is true. |
| Files | `infra/stacks/lambda_targets_stack.py` |
| Acceptance | `cdk synth` produces 5 Lambda + 5 role resources with correct permissions; ARNs exported |
| Depends on | T-4.1–T-4.5 (code written), T-1.3, T-1.4, T-1.5, T-3.2 |

### T-4.7: Deploy Step 4

| Field | Value |
|-------|-------|
| Type | Deploy |
| Description | `cdk deploy LambdaTargetsStack`. Test each Lambda via `aws lambda invoke` with sample events. |
| Acceptance | All 5 Lambdas return correct data for test inputs |
| Depends on | T-4.6 |

---

## Step 5: AgentCore Layer

### T-5.1: Write agentcore.json Template

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Create `agentcore.json` with placeholders for: 5 Lambda ARNs, Cognito issuer URL, M2M client ID. Define Gateway (CUSTOM_JWT auth, 5 targets with full inline tool schemas for all 10 tools), Identity credential provider (Cognito), and Runtime (CodeZip, HTTP/SSE, eu-west-2). |
| Files | `agentcore.json` |
| Acceptance | Valid JSON; all 10 tool schemas present; placeholder format consistent |
| Depends on | — |

### T-5.2: Write agentcore.json Populator Script

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Create `scripts/populate_agentcore_json.py` that reads `cdk-outputs.json` and replaces placeholders in `agentcore.json` with actual ARNs/URLs. |
| Files | `scripts/populate_agentcore_json.py` |
| Acceptance | After running, `agentcore.json` contains real ARNs (no `{...}` placeholders remain) |
| Depends on | T-5.1, T-4.7 (CDK outputs exist) |

### T-5.3: Write Strands Agent

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Write `agent/agent.py`: Strands Agent with BedrockModel (Claude Sonnet, eu-west-2), system prompt from `system_prompt.txt`, `@requires_access_token` for Gateway auth, `stream_async` for SSE streaming, HTTP handler for `/invocations`. |
| Files | `agent/agent.py`, `agent/requirements.txt` |
| Acceptance | Agent code is syntactically valid; imports resolve; system prompt loaded |
| Depends on | T-5.4 |

### T-5.4: Write System Prompt

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Write `agent/system_prompt.txt` instructing Claude to: act as DWP Data Intelligence Agent, use discovered tools, classify PII with reasoning, generate safe SQL (LIMIT 100, no DML/DDL), synthesise governance answers with citations, chain tools for multi-step queries, explain reasoning before acting. |
| Files | `agent/system_prompt.txt` |
| Acceptance | Prompt covers all 10 tools' usage patterns; includes safety rules |
| Depends on | — |

### T-5.5: Deploy AgentCore Layer

| Field | Value |
|-------|-------|
| Type | Deploy |
| Description | Run `scripts/populate_agentcore_json.py` then `agentcore deploy`. Verify: Gateway created with 5 targets, Identity provider registered, Runtime deployed and reachable. |
| Acceptance | `agentcore deploy` exits 0; Runtime endpoint accessible; Gateway `tools/list` returns 10 tools |
| Depends on | T-5.1, T-5.2, T-5.3, T-5.4, T-4.7 |

### T-5.6: End-to-End Agent Smoke Test

| Field | Value |
|-------|-------|
| Type | Test |
| Description | Call `InvokeAgentRuntime` with a simple prompt ("What datasets are available?"). Verify: (1) SSE stream received, (2) agent calls `search_catalogue` via Gateway, (3) returns dataset list. |
| Acceptance | Streaming response includes tool call events and a final answer listing datasets |
| Depends on | T-5.5 |

---

## Step 6: Frontend + Deploy Scripts + Smoke Test

### T-6.1: Streamlit UI

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Write `frontend/app.py`: two-column layout (chat + reasoning panel). On submit: (1) get/refresh Cognito token, (2) call `InvokeAgentRuntime` with streaming, (3) render SSE events in real-time (reasoning panel: tool calls + decisions; chat panel: final text). Session state for conversation history. |
| Files | `frontend/app.py`, `frontend/requirements.txt` |
| Acceptance | `streamlit run frontend/app.py` launches; submitting a question shows streaming reasoning + response |
| Depends on | T-5.5 |

### T-6.2: Streamlit Auth Integration

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Implement Cognito token fetch in Streamlit: read `COGNITO_CLIENT_ID`, `COGNITO_CLIENT_SECRET`, `COGNITO_DOMAIN` from env/`.env`; call token endpoint; cache in `st.session_state`; auto-refresh on expiry. |
| Files | `frontend/app.py` (additions) |
| Acceptance | Token obtained without manual steps; agent callable from Streamlit |
| Depends on | T-6.1, T-1.5 (Cognito deployed) |

### T-6.3: Write setup.sh

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Write `setup.sh` per design §8.1: pre-build checks → CDK deploy → generate/upload data → create Glue tables → register ML assets → upload gov docs → sync KB → populate agentcore.json → agentcore deploy → print instructions. Idempotent where possible. |
| Files | `setup.sh` |
| Acceptance | Fresh account: `./setup.sh` creates everything end-to-end with no manual steps (beyond credentials + model access) |
| Depends on | All previous tasks |

### T-6.4: Write teardown.sh

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Write `teardown.sh` per design §8.2: agentcore destroy → empty S3 buckets → cdk destroy. Must explicitly handle: S3 Vectors store, KB, Gateway, Runtime, Cognito pool. |
| Files | `teardown.sh` |
| Acceptance | After running, `aws cloudformation list-stacks` shows no dwp-demo stacks; no ongoing charges |
| Depends on | T-6.3 |

### T-6.5: Write Integration Smoke Test

| Field | Value |
|-------|-------|
| Type | Code |
| Description | Write `smoke_test.py`: runs all 11 demo scenarios against the deployed stack. For each: (1) send prompt to Runtime, (2) collect full response, (3) assert non-empty and sensible (keyword checks). One retry with exponential backoff per scenario (handles Bedrock throttling / Athena cold-start). Report pass/fail per scenario. |
| Files | `smoke_test.py` |
| Acceptance | All 11 scenarios pass against a fully deployed stack |
| Depends on | T-5.5, T-6.3 |

### T-6.6: Full End-to-End Validation

| Field | Value |
|-------|-------|
| Type | Test |
| Description | Run `./setup.sh` on a clean account → `python smoke_test.py` → manually test Streamlit UI (verify reasoning panel streams live) → `./teardown.sh`. |
| Acceptance | (1) All 11 scenarios pass, (2) reasoning panel streams tool calls in real-time, (3) teardown leaves zero resources |
| Depends on | T-6.1–T-6.5 |

---

## Summary: Task Count

| Step | Tasks | Key Output |
|------|-------|-----------|
| 0 | 1 | Model access enabled |
| 0.5 | 5 | Streaming proven (GATE) |
| 1 | 6 | CDK infra deployed (S3, Glue DB, Athena WG, Cognito) |
| 2 | 4 | 10 tables + Parquet data in S3, queryable via Athena |
| 3 | 6 | KB synced + ML assets registered |
| 4 | 7 | 5 Lambdas deployed, all 10 tools functional |
| 5 | 6 | Agent + Gateway + Identity live, agent calls tools |
| 6 | 6 | Frontend, deploy scripts, smoke test — full system |
| **Total** | **41** | |

---

## Critical Path

The longest dependency chain (determines minimum elapsed time):

```
T-0.1 → T-0.5.1 → T-0.5.3 → T-0.5.4 → T-0.5.5 (GATE)
  → T-1.2 → T-1.3 → T-1.4 → T-1.6
    → T-2.1 → T-2.2 → T-2.3 → T-2.4
      → T-4.1 → T-4.6 → T-4.7
        → T-5.2 → T-5.5 → T-5.6
          → T-6.1 → T-6.5 → T-6.6
```

### Parallelisable Work

Within each step, several tasks can run in parallel:

- **Step 1:** T-1.3/T-1.4/T-1.5 can run in parallel (independent stacks)
- **Step 2:** T-2.1 is a prerequisite for T-2.2 and T-2.3, but those two can run in parallel
- **Step 3:** T-3.1, T-3.2, T-3.3, T-3.4 can all run in parallel
- **Step 4:** T-4.1–T-4.5 (Lambda code) can all run in parallel; T-4.6 depends on all of them
- **Step 5:** T-5.1, T-5.4 can run in parallel; T-5.3 depends on T-5.4
- **Step 6:** T-6.3, T-6.4, T-6.5 can run in parallel once T-6.1/T-6.2 are done

---

## Risk Register

| Risk | Impact | Mitigation | Owner |
|------|--------|-----------|-------|
| Streaming buffered (not incremental) | **Blocks entire project** | Step 0.5 spike validates before investment | Agent |
| `agentcore` CLI deploy path unfamiliar | Medium — delays | Spike also validates CLI path | Agent |
| Athena cold-start delays during demo | Low — UX | Reasoning panel shows "running"; optional warm query pre-demo | Human |
| KB sync slow or fails | Medium — blocks governance scenarios | `sync_knowledge_base.py` polls with timeout; docs are small | Agent |
| Bedrock throttling on smoke test | Low | One retry + backoff built into smoke script | Agent |
| S3 Vectors + KB integration issues | Low (GA service) | Well-documented; fallback: adjust chunking params | Agent |

---

*End of task breakdown. Awaiting review before starting implementation.*
