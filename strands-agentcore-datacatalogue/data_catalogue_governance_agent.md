# Data Catalogue / Governance Agent

> **v5 changelog vs v4 (review feedback):** Added **Step 0.5 integration spike** (Runtime CodeZip streaming fidelity + `agentcore` CLI deploy path — the two riskiest unknowns, validated before the full build). `policy_search` changed from KB `retrieve_and_generate` → **`retrieve` only** (orchestrator synthesises the answer — reasoning rule now has **zero exceptions**, synthesis visible in the panel). `search_catalogue` demo-primary path is now **`get_tables` + orchestrator-side filtering** (Glue keyword search kept as the at-scale story). Glue tables + Parquet generator now driven from a **single YAML manifest** (one place to review the data model; schema and data can't drift). `generate_metadata` **write-back disabled by default** (IAM-gated read-only demo mode). Smoke test gets **one retry with backoff**. Athena first-query latency noted as a demo-pacing point (mitigated by the reasoning panel + optional pre-stage warm query).

> **v4 changelog vs v3:** Orchestrator moved from AWS Lambda to **Bedrock AgentCore Runtime** (Strands agent, containerized, native streaming — no API Gateway/WebSockets needed). Knowledge Base vector store changed from **OpenSearch Serverless → S3 Vectors**. Glue tables now **created directly** (no Crawler). Testing scoped to **demo-level** (scenario smoke tests, not mocked unit tests). Auth clarified into **two Cognito boundaries**. Added `owner`/`steward` metadata. Clarified **where LLM reasoning happens** (orchestrator vs target). Added a **phased build plan** and **pre-build region checks**.

## Deployment Approach

**This project must be fully deployable via code/scripts.** The coding agent (Kiro) writes all code AND creates deployable infrastructure. The human operator should only need to:
1. Provide AWS credentials / assume the correct IAM role
2. Run a single setup/deploy command

**Deploy tooling is split by responsibility** (per the official AgentCore guidance — the old CDK/starter-toolkit path for Runtime+Gateway is deprecated):

**A. AWS CDK (Python) — the data-plane infrastructure:**
- S3 buckets (Parquet data, Athena results, KB source docs, S3 Vectors index)
- Glue Database + Glue table definitions created **directly** (schema + custom properties in one shot — no Crawler)
- Target Lambda functions (5): glue-catalogue, athena-query, sagemaker-ml, pii-classifier, governance-kb
- **Cognito** user pool + two app clients (see Auth section)
- **Bedrock Knowledge Base** backed by **S3 Vectors** (via `@cdklabs/generative-ai-cdk-constructs` L2 / L1 `CfnKnowledgeBase` / boto3 custom resource as needed)
- SageMaker Model Registry (model package group + version) and Feature Store (**offline store only**)
- IAM roles and least-privilege permissions
- **Exports the 5 target Lambda ARNs + Cognito details as CloudFormation outputs** for the AgentCore layer to consume

**B. `@aws/agentcore` CLI + `agentcore.json` — the AgentCore layer:**
- **AgentCore Runtime** hosting the Strands orchestrator agent — **CodeZip build** (Python zipped to S3; no Docker/ARM64 container needed). Protocol: HTTP (`/invocations`, SSE streaming).
- **AgentCore Gateway** (CUSTOM_JWT authorizer → Cognito) with **5 `lambda` targets**, each referencing a target Lambda ARN (from CDK outputs) plus an **inline tool schema** (`toolDefinitions`). Outbound auth = `GATEWAY_IAM_ROLE`.
- **AgentCore Identity** credential provider (Cognito) so the agent obtains its Gateway access token via `@requires_access_token` — no hand-rolled token exchange.

> Note: Gateway exposes tools as `${target_name}___${tool_name}`. The agent discovers them via MCP `tools/list`, so the prefixing is handled automatically.

Include a **`setup.sh`** script that:
1. Runs pre-build region checks (see Pre-Build Verification)
2. `cdk deploy` — data-plane infra (S3, Glue DB, Lambdas, Cognito, KB, SageMaker, IAM)
3. Uploads synthetic Parquet data to S3
4. Creates Glue tables directly (schema + descriptions + lineage + PII + owner/steward)
5. Registers SageMaker model packages and feature groups (metadata only)
6. Uploads bundled governance documents to the KB S3 data source
7. Triggers a Bedrock KB sync and waits for completion
8. `agentcore deploy` — reads `agentcore.json` (populated with CDK-output Lambda ARNs) to create the Gateway + 5 targets, the Identity credential provider, and deploy the Strands agent to Runtime (CodeZip)
9. Outputs the Runtime ARN/endpoint and the Streamlit run command

Include a **`teardown.sh`** that destroys everything, explicitly including the S3 Vectors store, KB, Gateway, Runtime, and Cognito pool.

The goal: **one command (`./setup.sh`) creates everything from scratch.**

## Region — CONFIRMED: eu-west-2 (London)

**Region locked to `eu-west-2` (London).** AgentCore Runtime + Gateway and Bedrock Knowledge Bases with S3 Vectors are both confirmed available in London, so the **UK data-residency claim stands** for the demo narrative.

Still confirm model access is switched on in the console before deploy (one-time, per-account):
- [ ] **Bedrock Claude Sonnet** model access enabled in eu-west-2
- [ ] **Embedding model** (Titan Text Embeddings v2 or Cohere) access enabled in eu-west-2
- [x] AgentCore Runtime + Gateway available in eu-west-2 — confirmed
- [x] Bedrock KB + S3 Vectors available in eu-west-2 — confirmed
- [x] SageMaker, Glue, Athena — available

## Overview

An AI-powered data discovery and governance agent for a fictional government social security agency. Data analysts, case workers, and business users interact with the agency's data catalogue through natural language — finding datasets, understanding content, checking sensitivity, exploring lineage, and querying live data.

## Problem Statement

The agency has 27 petabytes of data across ~20 Programme Delivery Units (PDUs), with 750 data analysts and 9,000 dashboard users. A published Data Strategy 2023–2030 states:

> "A data catalogue with advanced search functions will cut discovery time from sometimes **months** to only **hours**."

Currently:
- Data discovery relies on tribal knowledge, emailing colleagues, or browsing spreadsheets
- There is no intelligent, searchable catalogue with AI-powered metadata
- Understanding a dataset (columns, PII, lineage) requires finding the person who built it
- Non-technical users (case workers, policy teams) cannot self-serve data insights
- Metadata is often missing, incomplete, or out of date

## Solution

A conversational AI agent built with the **Strands SDK**, hosted on **Amazon Bedrock AgentCore Runtime**, using **Bedrock (Claude Sonnet)** for reasoning. It sits on top of the agency's existing data estate (S3 + AWS Glue Data Catalog + Amazon Athena) and provides natural language access to:

1. **Dataset discovery** — search and browse the data catalogue
2. **Dataset understanding** — explain columns, types, and purpose
3. **PII classification** — identify and flag sensitive columns
4. **Data lineage** — show upstream sources and downstream consumers
5. **Metadata generation** — auto-create FAIR-compliant descriptions
6. **Join recommendations** — suggest how to combine datasets
7. **Live data querying** — NL → SQL → Athena → results
8. **Governance Q&A** — answer sharing/access/compliance questions from policy docs
9. **ML asset discovery** — find and describe SageMaker models and feature groups

## Why Build This vs. Amazon DataZone / SageMaker Catalog

**A fair question for any reviewer: doesn't AWS already do this?** Partly, yes — and it's worth being upfront about it. Amazon **DataZone** (now delivered as **Amazon SageMaker Catalog**, which is built on DataZone) is AWS's managed data catalogue and governance product, and it covers a lot of this out of the box:

| Capability | DataZone / SageMaker Catalog | This agent |
|-----------|------------------------------|-----------|
| Dataset search / business catalog | ✅ Native (Glue + Redshift) | ✅ via `search_catalogue` |
| AI-generated descriptions | ✅ GA ("AI recommendations for descriptions") | ✅ via `generate_metadata` |
| ML assets (Feature Groups, Model Package Groups) | ✅ First-class asset types | ✅ via `list_ml_models` / `describe_ml_asset` |
| Governed access / subscriptions | ✅ Automated via Lake Formation | ~ Read-focused for the demo |
| Live query access | ✅ Athena / Redshift integration | ✅ via `query_dataset` |
| PII / sensitivity | ~ Via data quality + Macie/Glue | ✅ Bespoke LLM reasoning (`classify_pii`) |
| Lineage | ~ Via integrations | ✅ From own metadata (`show_lineage`) |
| Governance Q&A over policy documents | ❌ Not a catalog feature | ✅ via `policy_search` (Bedrock KB) |
| Single conversational agent chaining all of the above, with a visible reasoning panel | ❌ | ✅ Core of this build |

**So why build it?** The point of this project is **not** "AWS can't catalogue data" — for a production catalogue, DataZone / SageMaker Catalog is the right choice. The point is to demonstrate the **agentic pattern**: a single natural-language agent that autonomously orchestrates multiple services (Glue, Athena, SageMaker, a governance Knowledge Base) and *shows its reasoning*, using **Bedrock AgentCore + Strands**. Concretely, this build addresses gaps that a managed catalogue doesn't:

- **Cross-service orchestration + transparency** — one chat that chains discovery → PII → lineage → live query → policy Q&A, with a live reasoning panel. DataZone gives a catalog UI and AI descriptions, not an agent that orchestrates and explains its steps.
- **Bespoke governance Q&A** — answers grounded in *your* policy documents with citations (Bedrock Knowledge Base territory, not a catalog feature).
- **Custom PII + lineage logic** — reasoning over your own rules and metadata rather than only what a managed product infers.
- **Region fit** — DataZone's GA AI-description feature is currently limited to N. Virginia, Oregon, Tokyo, and Frankfurt (not London). A custom Bedrock build in **eu-west-2** keeps everything in-region for UK data residency today.
- **Generalisable pattern** — the same AgentCore + Gateway + Strands approach applies to problems that have *no* managed product at all; the catalogue is a relatable vehicle to show it.

**One-line positioning:** *DataZone / SageMaker Catalog is the answer for a production catalogue; this demo shows how to build a transparent, multi-service AI agent for the cases it doesn't cover — and the pattern reuses far beyond cataloguing.*

## Target Users

| User | Example Question |
|------|-----------------|
| Data Analyst | "Find me datasets related to benefit payment fraud" |
| Case Worker | "What data do we have about a claimant's payment history?" |
| Data Engineer | "Show me the lineage for the compliance prediction score" |
| Policy Team | "Can I share this dataset with an external agency?" |
| New Starter | "I've just joined the fraud team — what data is available to me?" |
| Data Steward | "Which datasets contain national identification numbers?" |
## Architecture

### Overview

The Strands agent runs on **AgentCore Runtime** (containerized, native response streaming, long-running sessions up to 8 hours). It uses **AgentCore Gateway** as the central tool aggregation layer, discovering available tools dynamically via MCP `tools/list` at invocation time — so new data sources are added by adding a Gateway target, with no agent code change.

**Why Runtime instead of Lambda + API Gateway:** AgentCore Runtime streams responses natively and has no 29s timeout, so multi-step tool chains (e.g. "find all HIGH PII, show lineage, who owns them") stream each reasoning step live to the UI. This removes the need for API Gateway (REST 29s limit) or a WebSocket async-push workaround entirely.

### Layers

- **Strands SDK** — the agent brain (reasoning loop, tool calling, model provider). Your code.
- **AgentCore Runtime** — the managed host that runs the containerized Strands app. Streaming + long sessions.
- **AgentCore Gateway** — aggregates the 5 targets into one MCP tool list. Agent calls `tools/list` / `tools/call`.
- **Bedrock Claude Sonnet** — the LLM the Strands agent uses to reason and select tools.

### Flow

1. User sends a question via the Streamlit UI
2. Streamlit calls **AgentCore Runtime** (`InvokeAgentRuntime`, streaming) with a Cognito user token
3. The Strands agent connects to **AgentCore Gateway** (MCP) with a Cognito M2M token, calls `tools/list`
4. Agent sends the tool list + question to **Bedrock (Claude)**
5. Claude selects tool(s); agent executes via **Gateway → tools/call**
6. Gateway routes to the appropriate **target Lambda** (Glue, Athena, SageMaker, PII, KB)
7. Result returns to agent → back to Claude → next step or final answer
8. Each reasoning/tool step is `yield`ed via Strands `stream_async` → streamed by Runtime → rendered live in the Streamlit reasoning panel

### Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Streamlit Chat UI + live Reasoning Panel)        │
└──────────────────────────────┬──────────────────────────────┘
                    InvokeAgentRuntime (streaming, Cognito user token)
┌──────────────────────────────▼──────────────────────────────┐
│  Bedrock AgentCore Runtime                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Strands SDK Agent (CodeZip, HTTP/SSE)                 │  │
│  │  - stream_async yields each reasoning/tool step        │  │
│  │  - discovers tools from Gateway (MCP tools/list)       │  │
│  │  - reasons with Bedrock Claude Sonnet                  │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────┘
                    MCP tools/list + tools/call (Cognito M2M token)
┌──────────────────────────────▼──────────────────────────────┐
│  Bedrock AgentCore Gateway (JWT authorizer = Cognito)        │
│  Targets:                                                    │
│  ┌────────────────────────────────────────────────────┐     │
│  │ glue-catalogue  → search_catalogue, get_dataset_    │     │
│  │                    detail, show_lineage,            │     │
│  │                    generate_metadata, suggest_joins │     │
│  │ athena-query    → query_dataset                     │     │
│  │ sagemaker-ml    → list_ml_models, describe_ml_asset │     │
│  │ pii-classifier  → classify_pii                      │     │
│  │ governance-kb   → policy_search                     │     │
│  └────────────────────────────────────────────────────┘     │
└──┬──────────────┬──────────────┬──────────────┬────────────┘
   ▼              ▼              ▼              ▼
┌────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────────┐
│ Glue   │ │ Athena   │ │ SageMaker │ │ Bedrock KB       │
│ Data   │ │ (SQL over│ │ (Registry │ │ (S3 Vectors)     │
│ Catalog│ │  S3      │ │  + offline│ │ Gov docs: Data   │
│        │ │  Parquet)│ │  Feature  │ │ Strategy, FAIR,  │
└────────┘ └──────────┘ │  Store)   │ │ sharing policy   │
                        └───────────┘ └──────────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │ Amazon S3    │
                        │ (Parquet)    │
                        └──────────────┘
```

### Authentication — Two Boundaries

There are two separate Cognito app clients; do not conflate them:

| Boundary | Direction | Cognito flow | Purpose |
|----------|-----------|--------------|---------|
| **Inbound** | Streamlit → AgentCore Runtime | **Simplified login (CONFIRMED)** — single app-client token, no hosted UI / user pool login screen | Authenticates the caller to the Runtime |
| **M2M** | Strands agent → AgentCore Gateway | **Client-credentials** via **AgentCore Identity** | Agent gets its Gateway token through AgentCore Identity (`@requires_access_token`) using a Cognito credential provider — no hand-rolled token exchange |

**Simplified login decision:** for the demo we skip the full Cognito hosted-UI user login. Streamlit uses a single pre-provisioned app-client token to call the Runtime. No per-user accounts, no sign-in screen. (If a future pilot needs real user identity, swap this boundary for a full user pool + hosted UI — no change to the M2M boundary.)

The agent reads the Gateway URL from config; AgentCore Identity supplies the Gateway access token at invocation via the registered Cognito credential provider.

### Where the LLM Reasoning Happens (important — resolves v3 ambiguity)

**Rule: the orchestrator (Strands agent on Runtime) owns all LLM reasoning. Target Lambdas are "dumb" data accessors** — they call AWS APIs and return structured data, they do NOT call Bedrock. **No exceptions (v5)** — even governance Q&A synthesis happens in the orchestrator:

| Tool | LLM work done by | Target Lambda does |
|------|------------------|--------------------|
| `search_catalogue` | Orchestrator (picks search terms) | `glue.search_tables` / `get_tables`, returns matches |
| `get_dataset_detail` | none | `glue.get_table`, returns metadata |
| `classify_pii` | **Orchestrator** reasons over columns | Target returns column names/types/samples only |
| `show_lineage` | Orchestrator (explains in prose) | Reads Glue table properties, returns raw lineage |
| `generate_metadata` | **Orchestrator** writes the description | Target returns schema (+ optional sample); optional write-back via `update_table` |
| `suggest_joins` | Orchestrator (reasons over schemas) | Returns schemas of candidate tables |
| `query_dataset` | **Orchestrator** generates SQL | Target executes SQL on Athena, returns rows |
| `policy_search` | **Orchestrator** synthesises answer + citations from chunks | Target calls KB `retrieve`, returns chunks + source metadata |
| `list_ml_models` / `describe_ml_asset` | none | SageMaker API calls, returns metadata |

This avoids "Claude calling a tool that calls Claude," keeps target Lambdas cheap and fast, and centralizes prompt logic in one place.

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **AgentCore Runtime hosts the agent** | Native streaming + long sessions; no API GW 29s limit; on-narrative "full AgentCore" story |
| **Strands SDK for agent logic** | Same agent code regardless of host; native `stream_async` powers the reasoning panel |
| **AgentCore Gateway for tools** | Dynamic tool discovery; new data source = new target, no agent change |
| **Each target is a separate Lambda** | Separation of concerns, independent testing |
| **Orchestrator owns LLM reasoning** | No nested LLM calls; targets stay cheap data accessors |
| **S3 Vectors for KB** | No OpenSearch Serverless standing cost (~£500–700/mo avoided) |
| **Glue tables created directly** | Deterministic; no crawler timing/overwrite risk |
| **Single YAML manifest drives tables + data (v5)** | One reviewable data model; Parquet generator and Glue definitions read the same source — schema and data can't drift |
| **KB `retrieve` only, orchestrator synthesises (v5)** | Zero exceptions to the reasoning rule; synthesis + citations visible in the panel |
| **Metadata write-back off by default (v5)** | No catalogue mutation mid-demo; IAM-gated, not prompt-gated |
| **Cognito (2 app clients)** | Inbound user auth + M2M agent→Gateway auth |
## Tool Definitions

### 1. `search_catalogue`
**Purpose:** Search the Glue Data Catalog for datasets matching a natural language query.
**Implementation (v5):** Demo-primary path is `glue.get_tables()` returning the **full catalogue** (10 tables fit comfortably in context) with the **orchestrator filtering/ranking semantically** — guarantees "find datasets about fraud" always lands even when descriptions use different terms. `glue.search_tables(SearchText=query)` is kept in the target as the at-scale story (keyword-based, not semantic).
**Input:** `query: str`
**Output:** Matching tables with name, database, description, classification, owner.

### 2. `get_dataset_detail`
**Purpose:** Full details of a dataset — columns, types, descriptions, properties, location, row count.
**Implementation:** Target calls `glue.get_table(DatabaseName, Name)`.
**Input:** `database: str`, `table_name: str`
**Output:** Columns with types/comments, table properties, S3 location, last updated, owner/steward.

### 3. `classify_pii`
**Purpose:** Classify columns as NONE / LOW / MEDIUM / HIGH PII.
**Implementation:** Target returns column names, types, and optional sample. **Orchestrator (Claude)** does the classification reasoning.
- `NONE` — no PII
- `LOW` — indirect identifiers (postcode, date of birth)
- `MEDIUM` — quasi-identifiers (full name, email)
- `HIGH` — direct identifiers (national ID number, bank account)
**Input:** `database: str`, `table_name: str`
**Output:** Columns with PII classification + reasoning.

### 4. `show_lineage`
**Purpose:** Upstream sources and downstream consumers.
**Implementation:** Reads Glue table properties: `lineage_upstream`, `lineage_downstream`, `lineage_transformation` (JSON).
**Input:** `database: str`, `table_name: str`
**Output:** Upstream, transformation, downstream.

### 5. `generate_metadata`
**Purpose:** Auto-generate a FAIR-compliant description for an undocumented dataset.
**Implementation:** Target returns schema (+ optional Athena sample). **Orchestrator** generates description, column descriptions, suggested classification, tags. **Write-back via `glue.update_table()` is DISABLED by default (v5)** — read-only demo mode, enforced by IAM (no `glue:UpdateTable` on the target role unless the write-back flag is enabled at deploy). Avoids mutating catalogue state mid-demo and needing a reset.
**Input:** `database: str`, `table_name: str`
**Output:** Generated metadata.

### 6. `suggest_joins`
**Purpose:** Recommend how to join datasets for an analytical goal.
**Implementation:** Target returns schemas of candidate tables; orchestrator matches keys (`national_id`, `case_id`, `claimant_id`) and suggests joins.
**Input:** `goal: str`
**Output:** Tables, join keys, caveats (granularity mismatches).

### 7. `query_dataset`
**Purpose:** NL question → SQL → Athena → results.
**Implementation:** Orchestrator generates SQL from question + schema. Target executes via `athena.start_query_execution()` + `get_query_results()`.
**Input:** `question: str`, `database: str`, `table_name: str` (optional)
**Output:** SQL run, result rows, plain-English summary.
**Safety (enforced by IAM, not just prompt):** athena-target role gets **read-only** Glue + **read-only** S3, a dedicated Athena workgroup with a fixed output location. Orchestrator also applies `LIMIT 100` and never emits `DELETE`/`DROP`/`INSERT` — but IAM is the real guardrail.
**Demo pacing note (v5):** first Athena query of a session can take a few seconds (per-query engine startup — a `setup.sh` warm-up hours earlier doesn't help). Mitigation: the reasoning panel shows "⏳ query_dataset running…" so the wait reads as the agent working; optionally fire a throwaway query manually right before presenting.

### 8. `policy_search`
**Purpose:** Answer governance/compliance questions from agency policy docs.
**Implementation (v5):** Target calls Bedrock KB **`retrieve` only** (KB backed by S3 Vectors), returning ranked chunks + source metadata. The **orchestrator synthesises the answer and formats citations** — no KB-side generation. Keeps the "orchestrator owns reasoning" rule exception-free, makes synthesis visible in the reasoning panel, and gives full citation control.
**Input:** `question: str`
**Output:** Answer grounded in policy docs with citations (synthesised by orchestrator from retrieved chunks).

### 9. `list_ml_models`
**Purpose:** Discover SageMaker models and Feature Store groups.
**Implementation:** `sagemaker.list_model_packages()` / `list_models()` + `list_feature_groups()`.
**Input:** `query: str` (optional)
**Output:** Models/feature groups with name, date, status, description.

### 10. `describe_ml_asset`
**Purpose:** Detailed info on a model or feature group + lineage back to source datasets.
**Implementation:** `describe_model_package()` / `describe_feature_group()`. Metrics injected at registration via `ModelMetrics` / `CustomerMetadataProperties`.
**Input:** `asset_type: str` ("model" | "feature_group"), `asset_name: str`
**Output:** Features/columns, data sources, date, description, lineage to S3.

## Metadata Model (Glue Table Properties)

Every synthetic table carries these custom properties (set directly at table creation):
- `description` — human-readable summary
- `classification` — NONE | LOW | MEDIUM | HIGH
- `owner` — responsible team (e.g. "Child Maintenance Data Team")
- `steward` — named data steward (fictional, e.g. "A. Patel")  ← **new in v4, closes scenario #9 gap**
- `pdu` — Programme Delivery Unit
- `lineage_upstream` / `lineage_downstream` / `lineage_transformation` — JSON

## Synthetic SageMaker Assets (metadata only — no training)

| Asset | Type | Description | Related Datasets |
|-------|------|-------------|-----------------|
| `cms-compliance-predictor-v3` | Model (Registry) | XGBoost predicting payment non-compliance risk. High/Medium/Low. | `cms_payment_history`, `cms_compliance_predictions` |
| `cms-payment-features` | Feature Group (**offline only**) | payment_gap_days, avg_payment_amount, change_of_circs_count, days_since_last_payment | `cms_payment_history` |
| `fraud-detection-v1` | Model (Registry) | Binary fraud referral classifier. | `uc_claimant_journal`, `fraud_referral_outcomes` |
| `claimant-embedding-model` | Model (Registry) | Text embeddings for claimant journal (JCS chatbot). | `uc_claimant_journal`, `jcs_chatbot_interactions` |

**Setup:** Model Package Group + one version (dummy artifact + inference spec), Feature Group with 5–6 definitions (**offline S3 store only — no online store, to avoid standing cost**), descriptions/tags for discoverability, metrics via injected metadata.

## Synthetic Data (5–10 Parquet datasets in S3)

| Dataset | PDU / Domain | Description | ~Rows | PII |
|---------|-------------|-------------|------|-----|
| `cms_payment_history` | Child Maintenance | Monthly Collect & Pay records | 200 | HIGH |
| `cms_compliance_predictions` | Child Maintenance | XGBoost risk scores | 200 | MEDIUM |
| `uc_claimant_journal` | Benefits | Work search journal entries | 150 | HIGH |
| `uc_payment_calculations` | Benefits | Monthly payment calcs/deductions | 150 | HIGH |
| `pension_credit_eligibility` | Later Life | Eligibility assessments | 100 | HIGH |
| `fraud_referral_outcomes` | Fraud & Error | Investigation outcomes/flags | 100 | HIGH |
| `agency_staff_training_records` | People & Capability | Training completions | 100 | MEDIUM |
| `jcs_chatbot_interactions` | Working Age Services | Chatbot conversation logs | 100 | LOW |
| `service_performance_kpis` | Cross-Agency | Operational KPI aggregates | 50 | NONE |
| `config_resource_inventory` | Platform/Cloud | AWS Config resource inventory | 50 | NONE |

### Requirements
- All data fully fictional — no real names, national identification numbers, or case references
- Realistic agency column names
- Obvious PII (national_id, full_name, date_of_birth, address, bank_sort_code) for classification testing
- Non-obvious PII (postcode, phone_number) for reasoning
- Lineage + owner/steward in Glue properties

### Lineage Relationships
```
cms_payment_history:
  upstream: ["CMS2012 Operational System (external)"]
  downstream: ["cms_compliance_predictions", "service_performance_kpis"]
  transformation: "Daily ETL extract from CMS2012, loaded via Children Data Platform"
  owner: "Child Maintenance Data Team"  steward: "A. Patel"

cms_compliance_predictions:
  upstream: ["cms_payment_history", "CMS2012 change of circumstances (external)"]
  downstream: ["CMS2012 case worker screens (external)", "service_performance_kpis"]
  transformation: "Monthly SageMaker batch pipeline — XGBoost + SHAP"
  owner: "Child Maintenance Data Team"  steward: "A. Patel"

uc_claimant_journal:
  upstream: ["Benefits Full Service (external)"]
  downstream: ["fraud_referral_outcomes", "jcs_chatbot_interactions"]
  transformation: "Real-time event stream, daily Parquet partitioned by date"
  owner: "Benefits Data Team"  steward: "R. Okafor"

fraud_referral_outcomes:
  upstream: ["uc_claimant_journal", "cms_payment_history", "Revenue Authority RTI feed (external)"]
  downstream: ["service_performance_kpis"]
  transformation: "Rules engine + ML model referrals, outcomes logged by investigators"
  owner: "Counter Fraud Data Team"  steward: "S. Lewis"
```

## Bedrock Knowledge Base (S3 Vectors)

**Vector store: S3 Vectors** (not OpenSearch Serverless). **Bundle static copies of the docs in the repo** — do not fetch live external URLs at deploy time (fragile). Source documents:

1. **Agency Data Strategy 2023-2030** (synthetic)
2. **FAIR Data Principles** — summary of Findable, Accessible, Interoperable, Reusable
3. **Agency Data Sharing Policy** (synthetic) — sharing with other government departments, consent, legal gateways
4. **Agency AI Security Policy** (synthetic)
5. **Agency Information Management Policy** (synthetic)
## Tech Stack Summary

| Component | AWS Service | Purpose |
|-----------|------------|---------|
| Agent Framework | Strands SDK | Agent orchestration, tool execution, streaming |
| Agent Runtime | **Bedrock AgentCore Runtime** | Hosts Strands agent (CodeZip, HTTP/SSE); native streaming; long sessions |
| Deploy tooling | AWS CDK (data infra) + `@aws/agentcore` CLI (Runtime + Gateway) | Split deploy; `setup.sh` orchestrates both |
| Agent Identity | Bedrock AgentCore Identity | Supplies agent→Gateway access token (Cognito credential provider) |
| Tool Aggregation | Bedrock AgentCore Gateway | Aggregates 5 targets; dynamic `tools/list` |
| Auth | Amazon Cognito | Inbound (Streamlit→Runtime) + M2M (agent→Gateway) |
| LLM | Amazon Bedrock (Claude Sonnet) | Reasoning, NL understanding, metadata/SQL generation |
| Target Compute | AWS Lambda (×5) | Data-accessor targets behind the Gateway |
| ML Platform | SageMaker (Model Registry + **offline** Feature Store) | ML model/feature discovery |
| Data Catalogue | AWS Glue Data Catalog | Metadata store (tables created directly) |
| Query Engine | Amazon Athena | Serverless SQL over S3 (read-only IAM + dedicated workgroup) |
| Data Storage | Amazon S3 | Parquet synthetic datasets |
| Governance KB | Bedrock Knowledge Bases + **S3 Vectors** | RAG over governance docs |
| Frontend | Streamlit | Chat UI + live reasoning panel (consumes Runtime stream) |

## UI Design

### Layout: Chat + Agent Reasoning Panel
```
┌─────────────────────────────────────────────────────────────────────┐
│  Data Intelligence Agent                                        │
├───────────────────────────────────┬─────────────────────────────────┤
│  💬 Chat                          │  🧠 Agent Reasoning (live)      │
│  User: Find datasets about fraud  │  🔍 search_catalogue q:"fraud"  │
│  Agent: I found 3 datasets...     │  ✅ 3 results                   │
│  User: Which contain ID numbers?  │  🔍 classify_pii fraud_ref...   │
│  Agent: 2 of the 3 datasets...    │  ✅ HIGH: national_id            │
│                                   │  🔍 classify_pii cms_payment... │
│  │ Ask a question...        ⏎  │  │  ✅ HIGH: national_id, name     │
│  └─────────────────────────────┘  │                                 │
└───────────────────────────────────┴─────────────────────────────────┘
```

### Reasoning Panel Requirements
- Streams in real-time from the Runtime response stream (Strands `stream_async` events) — not shown after the fact
- Each tool call: name, parameters, status (⏳ / ✅ / ❌)
- Shows the LLM's decision/reasoning before each tool call
- Collapses completed steps
- Makes it obvious the agent is orchestrating multiple services (Glue, Athena, SageMaker, KB)

### Why it matters
- **Transparency / trust:** audience sees real tool calls and results, not hallucination
- **Education:** shows reason → act → observe → repeat
- **Wow factor:** autonomous multi-tool chaining across AWS services, streamed live

## Gateway Target Configuration

| Target | Lambda | Tools | AWS Wrapped |
|--------|--------|-------|-------------|
| `glue-catalogue` | `demo-glue-target` | search_catalogue, get_dataset_detail, show_lineage, generate_metadata, suggest_joins | Glue (get_table, get_tables, search_tables; update_table **IAM-gated behind write-back flag, off by default**) |
| `athena-query` | `demo-athena-target` | query_dataset | Athena (start_query_execution, get_query_results) — read-only IAM |
| `sagemaker-ml` | `demo-sagemaker-target` | list_ml_models, describe_ml_asset | SageMaker (list/describe model packages + feature groups) |
| `pii-classifier` | `demo-pii-target` | classify_pii | Glue (schema/sample only — no Bedrock; orchestrator reasons) |
| `governance-kb` | `demo-kb-target` | policy_search | Bedrock KB (**retrieve only** — returns chunks; orchestrator synthesises) |

## Demo Scenarios (also the integration smoke test)

1. **Discovery**: "I'm new to the fraud team — what datasets are available?"
2. **Understanding**: "What columns are in the CMS payment history table?"
3. **PII Audit**: "Which datasets contain national identification numbers?"
4. **Lineage**: "Where does the compliance prediction score come from?"
5. **Metadata Generation**: "Generate a description for the jcs_chatbot_interactions table"
6. **Join Recommendation**: "I want to link fraud referrals to payment history — how?"
7. **Live Query**: "Show me the top 10 cases with the highest non-compliance risk score"
8. **Governance**: "Can I share benefit claimant data with an external agency?"
9. **Multi-step**: "Find all HIGH PII datasets, show me their lineage, and tell me who owns them"
10. **ML Discovery**: "What ML models do we have for fraud detection?"
11. **ML + Data Lineage**: "What data was the compliance predictor trained on, and where does that come from?"

## Build Plan (single pass — all 5 targets, all 10 tools)

**Confirmed: build everything in one pass** (not phased). Ordered so each step builds on the last and can be smoke-tested as we go.

### Step 0 — Verify (one-time, per account)
- [ ] Enable Bedrock Claude Sonnet + embedding model access in eu-west-2

### Step 0.5 — Integration spike (v5 — de-risk the two biggest unknowns FIRST)
- [ ] Trivial Strands agent that `stream_async`-yields ~5 fake reasoning events with delays
- [ ] Deploy it via `agentcore` CLI as **CodeZip** (HTTP/SSE) — validates the CLI deploy path
- [ ] Consume `InvokeAgentRuntime` stream from a script — confirm events arrive **incrementally**, not buffered
- [ ] **Gate:** only proceed to the full build once live streaming is proven end-to-end (the reasoning panel depends on it)

### Step 1 — Repo + CDK data infra
- [ ] Project structure + CDK app (region eu-west-2)
- [ ] CDK stack: S3 buckets, Glue DB, Athena workgroup, IAM roles, Cognito (2 app clients)

### Step 2 — Synthetic data + Glue tables (manifest-driven, v5)
- [ ] **Single YAML manifest** defining all 10 tables: schema, description, classification, lineage, owner/steward, PDU
- [ ] Parquet data generator reads the manifest (fictional, realistic columns — schema and data can't disagree by construction)
- [ ] Direct Glue table creation loops over the same manifest (one code path, 10 tables)

### Step 3 — ML + KB infra
- [ ] SageMaker Model Registry (model package groups + versions) + offline Feature Store
- [ ] Bundle governance docs; Bedrock KB on S3 Vectors + data source

### Step 4 — All 5 target Lambdas (10 tools)
- [ ] `glue-catalogue` (search_catalogue, get_dataset_detail, show_lineage, generate_metadata, suggest_joins)
- [ ] `athena-query` (query_dataset) — read-only IAM
- [ ] `sagemaker-ml` (list_ml_models, describe_ml_asset)
- [ ] `pii-classifier` (classify_pii — returns schema/sample only)
- [ ] `governance-kb` (policy_search)

### Step 5 — AgentCore layer
- [ ] `agentcore.json`: Gateway (CUSTOM_JWT → Cognito) + 5 lambda targets with inline tool schemas + Identity credential provider
- [ ] Strands agent (CodeZip, HTTP/SSE) with all 10 tools discovered via Gateway `tools/list`

### Step 6 — Frontend + orchestration
- [ ] Streamlit UI + live reasoning panel (consumes Runtime SSE stream), run locally
- [ ] `setup.sh` (CDK deploy → data/tables/ML/KB load → agentcore deploy) + `teardown.sh`
- [ ] Integration smoke script running all 11 scenarios (**one retry with backoff** per scenario for transient Bedrock throttling / Athena timeouts — avoids false negatives in rehearsal)

### What the Human Does
- [ ] Review Kiro's output
- [ ] Enable Bedrock model access; configure AWS credentials / assume role
- [ ] Run `./setup.sh`
- [ ] Verify scenarios; prepare Tool Zone narrative
- [ ] (Optional) Fire one throwaway Athena query right before presenting — first-query latency lands off-stage

## Testing Approach (demo-level)

This is a demo/pilot/MVP — **no mocked unit tests**. Instead:
- One **integration smoke script** that fires the 11 demo scenarios against the deployed stack and checks for non-empty, sensible responses (doubles as rehearsal). **One retry with backoff per scenario** so transient Bedrock throttling / Athena timeouts don't produce false negatives
- Manual verification of the reasoning panel streaming
- Not in scope: exhaustive coverage, mocking, load/perf testing

## Cost Notes
- **S3 Vectors** replaces OpenSearch Serverless — avoids ~£500–700/mo standing cost
- **Feature Store offline-only** — avoids online-store standing cost
- **AgentCore Runtime / Gateway** — pay-per-use; ensure `teardown.sh` removes them
- Bedrock Claude — per-token; multi-step scenarios cost more, negligible at demo scale
- Run `teardown.sh` after the demo to stop all charges

## Success Criteria
- A non-technical user can find and understand datasets through conversation
- PII is correctly identified and flagged
- Lineage is traceable and explained in plain English
- Governance questions answered with policy citations
- Live data queries return correct results
- Reasoning panel streams tool calls live
- The whole interaction takes seconds, not months

## Context: Why This Matters
- The agency Data Strategy explicitly calls for this capability
- 27 PB across 20+ PDUs is largely undiscoverable without tribal knowledge
- FAIR adoption is a stated goal, not yet achieved
- 750 analysts spend significant time finding/understanding data before using it
- Demonstrates AI accelerating their strategy delivery

## Decisions (all confirmed — design is locked)
1. ~~**Region**~~ — **CONFIRMED: eu-west-2 (London)**; UK residency claim stands.
2. ~~**Inbound auth depth**~~ — **CONFIRMED: simplified login** (single app-client token, no hosted UI).
3. ~~**Streamlit hosting**~~ — **CONFIRMED: run locally** (`streamlit run app.py`) against the deployed AgentCore Runtime. Driven from the presenter's laptop for the Tool Zone session; no frontend hosting infra. (Can add S3/CloudFront SPA later without backend changes if a shareable link is ever needed.)
4. ~~**Number of datasets**~~ — **CONFIRMED: all 10 datasets.**
