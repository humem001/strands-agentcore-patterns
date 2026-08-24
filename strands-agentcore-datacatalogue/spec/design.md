# Design — Data Catalogue & Governance Agent

> Source brief: `data_catalogue_governance_agent.md` (v5)
> Requirements: `spec/requirements.md`
> Status: **DRAFT — awaiting review**
> Date: 2026-07-15

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Streamlit (local)  —  Chat UI + Live Reasoning Panel               │
└──────────────────────────────┬──────────────────────────────────────┘
              InvokeAgentRuntime (SSE stream, Cognito app-client token)
┌──────────────────────────────▼──────────────────────────────────────┐
│  Bedrock AgentCore Runtime  (eu-west-2)                             │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Strands Agent  (CodeZip, HTTP/SSE, Python)                    │ │
│  │   • stream_async yields reasoning + tool events                │ │
│  │   • tools discovered via Gateway MCP tools/list                │ │
│  │   • LLM: Bedrock Claude Sonnet (in-region)                     │ │
│  │   • @requires_access_token → AgentCore Identity (Cognito M2M)  │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
              MCP tools/list + tools/call  (Cognito M2M JWT)
┌──────────────────────────────▼──────────────────────────────────────┐
│  Bedrock AgentCore Gateway  (CUSTOM_JWT → Cognito)                  │
│                                                                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────┐  │
│  │glue-catalogue│ │athena-query │ │sagemaker-ml │ │pii-classifier│  │
│  │  5 tools     │ │  1 tool     │ │  2 tools    │ │  1 tool      │  │
│  └──────┬───────┘ └──────┬──────┘ └──────┬──────┘ └──────┬───────┘  │
│  ┌──────┴────────────────────────────────────────────────────────┐  │
│  │governance-kb  (1 tool)                                         │  │
│  └──────┬─────────────────────────────────────────────────────────┘  │
│         │         Outbound: GATEWAY_IAM_ROLE (SigV4)                 │
└─────────┼─────────────┼──────────────┼──────────────┼───────────────┘
          ▼             ▼              ▼              ▼
   ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐
   │  Lambda  │  │  Lambda  │  │  Lambda   │  │   Lambda     │
   │  glue-   │  │  athena- │  │  sage-    │  │   pii-       │
   │  target  │  │  target  │  │  maker-   │  │   target     │
   └────┬─────┘  └────┬─────┘  │  target   │  └────┬─────────┘
        │              │        └─────┬─────┘       │
        ▼              ▼              ▼             ▼
   ┌─────────┐  ┌──────────┐  ┌───────────┐  ┌─────────┐
   │AWS Glue │  │ Athena   │  │ SageMaker │  │AWS Glue │
   │Data Cat.│  │ + S3     │  │ Registry  │  │(schema) │
   └─────────┘  └──────────┘  │+ Feature  │  └─────────┘
                               │  Store    │
                               └───────────┘
   ┌──────────────────────────────────────────────┐
   │  Lambda: governance-kb-target                 │
   │  → Bedrock KB (retrieve) → S3 Vectors        │
   └──────────────────────────────────────────────┘
```

---

## 2. Project Structure

```
claude-demo/
├── spec/
│   ├── requirements.md
│   └── design.md
├── data_catalogue_governance_agent.md        # source brief
├── CLAUDE.md
│
├── infra/                                    # CDK app (Python)
│   ├── app.py
│   ├── cdk.json
│   ├── requirements.txt
│   └── stacks/
│       ├── data_platform_stack.py            # S3, Glue DB, Athena workgroup
│       ├── lambda_targets_stack.py           # 5 Lambda functions + IAM roles
│       ├── cognito_stack.py                  # User pool + 2 app clients
│       ├── knowledge_base_stack.py           # Bedrock KB + S3 Vectors
│       └── ml_assets_stack.py               # SageMaker registry + Feature Store
│
├── agent/                                    # Strands agent (CodeZip payload)
│   ├── agent.py                              # Entry point (HTTP handler + Strands agent)
│   ├── requirements.txt
│   └── system_prompt.txt
│
├── targets/                                  # Lambda target code
│   ├── glue_catalogue/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── athena_query/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── sagemaker_ml/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── pii_classifier/
│   │   ├── handler.py
│   │   └── requirements.txt
│   └── governance_kb/
│       ├── handler.py
│       └── requirements.txt
│
├── frontend/
│   ├── app.py                                # Streamlit UI
│   └── requirements.txt
│
├── data/
│   ├── manifest.yaml                         # Single source of truth: 10 tables
│   ├── generate_parquet.py                   # Reads manifest → Parquet files
│   ├── parquet/                              # Generated .parquet files (gitignored)
│   └── governance_docs/                      # Bundled policy documents for KB
│       ├── agency_data_strategy_2023_2030.md
│       ├── fair_data_principles.md
│       ├── agency_data_sharing_policy.md
│       ├── agency_ai_security_policy.md
│       └── agency_information_management_policy.md
│
├── agentcore.json                            # AgentCore CLI config (Gateway + Runtime)
├── setup.sh                                  # One-command deploy
├── teardown.sh                               # Full cleanup
├── smoke_test.py                             # 11-scenario integration test
│
├── spike/                                    # Step 0.5 streaming spike
│   ├── agent.py                              # Trivial Strands agent
│   ├── agentcore.json
│   ├── test_stream.py                        # Verify incremental SSE
│   └── README.md
│
└── .gitignore
```

---

## 3. Component Design

### 3.1 Strands Agent (CodeZip)

**File:** `agent/agent.py`

The agent is a Strands SDK application deployed as a CodeZip package to AgentCore Runtime. It exposes an HTTP endpoint at `/invocations` and streams SSE events.

**Responsibilities:**
- Accept user messages via HTTP POST
- Connect to AgentCore Gateway (MCP) to discover tools via `tools/list`
- Reason with Bedrock Claude Sonnet to select and invoke tools
- Stream each reasoning step and tool result back via SSE (`stream_async`)

**Key design points:**
- Tools are NOT hardcoded — discovered dynamically from Gateway (prefixed as `${target}___${tool}`)
- System prompt instructs Claude on available capabilities, PII classification logic, SQL safety rules, and citation formatting
- `@requires_access_token` decorator obtains the Gateway JWT via AgentCore Identity
- No state between invocations (stateless per-request)

**CodeZip structure:**
```
agent.zip
├── agent.py
├── system_prompt.txt
├── requirements.txt  (strands-agents, boto3)
└── (pip-installed deps)
```

### 3.2 Target Lambdas

Each target Lambda is a thin data-accessor. It receives a tool invocation from Gateway (JSON with `tool_name` and `parameters`), calls the relevant AWS API, and returns structured data. **No Lambda calls Bedrock.**

#### 3.2.1 glue-catalogue (`targets/glue_catalogue/handler.py`)

Handles 5 tools via a dispatcher on `tool_name`:

| Tool | Implementation |
|------|---------------|
| `search_catalogue` | `glue.get_tables()` (all tables) + `glue.search_tables(SearchText=...)` |
| `get_dataset_detail` | `glue.get_table(DatabaseName, Name)` → full metadata |
| `show_lineage` | `glue.get_table()` → extract `lineage_*` from TableParameters |
| `generate_metadata` | `glue.get_table()` → return schema + sample; write-back path calls `glue.update_table()` if IAM allows |
| `suggest_joins` | `glue.get_tables()` → return schemas of all tables for orchestrator matching |

**IAM role:** `glue:GetTable`, `glue:GetTables`, `glue:SearchTables`. `glue:UpdateTable` ONLY if deploy flag `ENABLE_WRITE_BACK=true` (default: absent).

#### 3.2.2 athena-query (`targets/athena_query/handler.py`)

| Tool | Implementation |
|------|---------------|
| `query_dataset` | `athena.start_query_execution(QueryString, WorkGroup, ResultConfiguration)` → poll `get_query_execution` → `get_query_results` |

**IAM role:** `athena:StartQueryExecution`, `athena:GetQueryExecution`, `athena:GetQueryResults`, `glue:GetTable` (read), `glue:GetDatabase` (read), `s3:GetObject` on data bucket (read), `s3:PutObject`/`GetObject` on Athena results bucket only. **No** `glue:UpdateTable`, **no** S3 write to data bucket.

**Workgroup:** Dedicated `demo-athena-wg` with fixed `OutputLocation` → `s3://demo-athena-results-{account}/`.

#### 3.2.3 sagemaker-ml (`targets/sagemaker_ml/handler.py`)

| Tool | Implementation |
|------|---------------|
| `list_ml_models` | `sagemaker.list_model_package_groups()` + `list_feature_groups()` |
| `describe_ml_asset` | `describe_model_package()` or `describe_feature_group()` depending on `asset_type` |

**IAM role:** `sagemaker:List*`, `sagemaker:Describe*` (read-only).

#### 3.2.4 pii-classifier (`targets/pii_classifier/handler.py`)

| Tool | Implementation |
|------|---------------|
| `classify_pii` | `glue.get_table()` → return column names, types, descriptions, and sample values from table parameters |

**IAM role:** `glue:GetTable` (read-only). No Bedrock permissions.

#### 3.2.5 governance-kb (`targets/governance_kb/handler.py`)

| Tool | Implementation |
|------|---------------|
| `policy_search` | `bedrock_agent_runtime.retrieve(knowledgeBaseId, retrievalQuery)` → return chunks + source metadata |

**IAM role:** `bedrock:Retrieve` on the specific KB ARN. No `bedrock:RetrieveAndGenerate`.

---

### 3.3 AgentCore Gateway Configuration

**File:** `agentcore.json` (Gateway section)

```json
{
  "gateway": {
    "name": "demo-gateway",
    "authorizerConfig": {
      "type": "CUSTOM_JWT",
      "jwtConfiguration": {
        "issuer": "https://cognito-idp.eu-west-2.amazonaws.com/{user_pool_id}",
        "audience": ["{m2m_client_id}"]
      }
    },
    "targets": [
      {
        "name": "glue-catalogue",
        "type": "lambda",
        "lambdaArn": "{from CDK output}",
        "authType": "GATEWAY_IAM_ROLE",
        "toolDefinitions": [
          {"name": "search_catalogue", "description": "...", "inputSchema": {...}},
          {"name": "get_dataset_detail", "description": "...", "inputSchema": {...}},
          {"name": "show_lineage", "description": "...", "inputSchema": {...}},
          {"name": "generate_metadata", "description": "...", "inputSchema": {...}},
          {"name": "suggest_joins", "description": "...", "inputSchema": {...}}
        ]
      },
      {
        "name": "athena-query",
        "type": "lambda",
        "lambdaArn": "{from CDK output}",
        "authType": "GATEWAY_IAM_ROLE",
        "toolDefinitions": [
          {"name": "query_dataset", "description": "...", "inputSchema": {...}}
        ]
      },
      {
        "name": "sagemaker-ml",
        "type": "lambda",
        "lambdaArn": "{from CDK output}",
        "authType": "GATEWAY_IAM_ROLE",
        "toolDefinitions": [
          {"name": "list_ml_models", "description": "...", "inputSchema": {...}},
          {"name": "describe_ml_asset", "description": "...", "inputSchema": {...}}
        ]
      },
      {
        "name": "pii-classifier",
        "type": "lambda",
        "lambdaArn": "{from CDK output}",
        "authType": "GATEWAY_IAM_ROLE",
        "toolDefinitions": [
          {"name": "classify_pii", "description": "...", "inputSchema": {...}}
        ]
      },
      {
        "name": "governance-kb",
        "type": "lambda",
        "lambdaArn": "{from CDK output}",
        "authType": "GATEWAY_IAM_ROLE",
        "toolDefinitions": [
          {"name": "policy_search", "description": "...", "inputSchema": {...}}
        ]
      }
    ]
  }
}
```

**Tool naming:** Gateway auto-prefixes tools as `glue-catalogue___search_catalogue`, etc. The Strands agent discovers these via `tools/list` and Claude sees them in its tool list.

---

### 3.4 Authentication Flows

#### Flow A: Inbound (Streamlit → Runtime)

```
Streamlit                    Cognito                   AgentCore Runtime
    │                            │                            │
    │  (pre-provisioned          │                            │
    │   client_id + secret)      │                            │
    │──── POST /oauth2/token ───▶│                            │
    │◀─── access_token ──────────│                            │
    │                            │                            │
    │──── InvokeAgentRuntime ────────────────────────────────▶│
    │     (Authorization: Bearer {token})                     │
    │◀─── SSE stream ────────────────────────────────────────│
```

- Single Cognito app client (client-credentials grant)
- No user pool login, no hosted UI
- Token cached in Streamlit session; refreshed on expiry

#### Flow B: M2M (Agent → Gateway)

```
Strands Agent               AgentCore Identity          Gateway
    │                            │                        │
    │  @requires_access_token    │                        │
    │  (registered Cognito       │                        │
    │   credential provider)     │                        │
    │──── get token ────────────▶│                        │
    │◀─── JWT ───────────────────│                        │
    │                            │                        │
    │──── tools/list (JWT) ──────────────────────────────▶│
    │◀─── tool definitions ──────────────────────────────│
    │──── tools/call (JWT) ──────────────────────────────▶│
    │◀─── result ────────────────────────────────────────│
```

- AgentCore Identity manages the Cognito client-credentials exchange
- Agent code uses `@requires_access_token` — no manual token logic
- Gateway validates JWT via CUSTOM_JWT authorizer (issuer + audience match)

---

### 3.5 Cognito Setup

| Resource | Purpose |
|----------|---------|
| User Pool (`demo-pool`) | Token issuer for both boundaries |
| App Client 1 (`demo-inbound`) | Streamlit → Runtime (client-credentials, `runtime/invoke` scope) |
| App Client 2 (`demo-m2m`) | Agent → Gateway (client-credentials, `gateway/tools` scope) |
| Resource Server (`demo-api`) | Defines custom scopes |

Both clients use `ALLOW_CLIENT_CREDENTIALS` auth flow. No user sign-up/sign-in configuration needed.

---

## 4. Data Model

### 4.1 Manifest Schema (`data/manifest.yaml`)

The single YAML manifest defines all 10 tables. Both the Parquet generator and Glue table creation read from this file.

```yaml
database: agency_data_catalogue

tables:
  - name: cms_payment_history
    description: "Monthly Collect & Pay payment records for Child Maintenance Service"
    classification: HIGH
    owner: "Child Maintenance Data Team"
    steward: "A. Patel"
    pdu: "Child Maintenance"
    location_suffix: "cms_payment_history/"
    lineage:
      upstream: ["CMS2012 Operational System (external)"]
      downstream: ["cms_compliance_predictions", "service_performance_kpis"]
      transformation: "Daily ETL extract from CMS2012, loaded via Children Data Platform"
    columns:
      - name: record_id
        type: string
        description: "Unique payment record identifier"
        pii: NONE
      - name: nino
        type: string
        description: "national identification number"
        pii: HIGH
      - name: paying_parent_name
        type: string
        description: "Full name of paying parent"
        pii: MEDIUM
      # ... (all columns defined here)
    row_count: 200
    generator:
      seed: 42
      # Column-specific generation rules (faker providers, ranges, etc.)
```

**Guarantees:**
- Column names in Parquet match column names in Glue table definition (same source)
- PII classifications are pre-annotated per-column (used by `classify_pii` for verification)
- Lineage stored in table properties matches what `show_lineage` returns

### 4.2 Glue Table Properties (custom metadata)

Each table gets these `Parameters` at creation:

```json
{
  "description": "...",
  "classification": "HIGH",
  "owner": "Child Maintenance Data Team",
  "steward": "A. Patel",
  "pdu": "Child Maintenance",
  "lineage_upstream": "[\"CMS2012 Operational System (external)\"]",
  "lineage_downstream": "[\"cms_compliance_predictions\", \"service_performance_kpis\"]",
  "lineage_transformation": "Daily ETL extract from CMS2012, loaded via Children Data Platform"
}
```

### 4.3 Governance Documents (KB source)

Five markdown files bundled in `data/governance_docs/`, uploaded to the KB S3 data source bucket, then synced to S3 Vectors via Bedrock KB:

1. `agency_data_strategy_2023_2030.md` — real published content (gov.uk)
2. `fair_data_principles.md` — FAIR summary
3. `agency_data_sharing_policy.md` — synthetic (sharing with external agencies, Home Office, NHS; consent and legal gateways)
4. `agency_ai_security_policy.md` — real published content (gov.uk)
5. `agency_information_management_policy.md` — real published content (gov.uk)

### 4.4 SageMaker Assets

| Asset | Type | Setup |
|-------|------|-------|
| `cms-compliance-predictor-v3` | Model Package Group + 1 version | Dummy S3 artifact + inference spec; metrics in CustomerMetadataProperties |
| `fraud-detection-v1` | Model Package Group + 1 version | Same pattern |
| `claimant-embedding-model` | Model Package Group + 1 version | Same pattern |
| `cms-payment-features` | Feature Group (offline only) | 5–6 feature definitions; offline S3 store; no online store |

---

## 5. Strands Agent Design

### 5.1 System Prompt (summary)

The system prompt instructs Claude to:
- Act as a Data Intelligence Agent
- Use available tools (discovered from Gateway) to answer questions
- For PII classification: reason over column names/types/descriptions and classify as NONE/LOW/MEDIUM/HIGH
- For SQL generation: always use `LIMIT 100`, never use DML/DDL, always show the SQL to the user
- For governance Q&A: synthesise answers from retrieved chunks and cite sources
- For metadata generation: produce FAIR-compliant descriptions (note write-back is disabled)
- For multi-step queries: chain tools as needed, explaining reasoning at each step
- Always explain reasoning before acting

### 5.2 Streaming Events

The Strands `stream_async` generator yields events of these types (consumed by the Streamlit reasoning panel):

| Event Type | Content | UI Rendering |
|------------|---------|-------------|
| `reasoning` | LLM's decision text before a tool call | Displayed as thought/decision text |
| `tool_start` | Tool name + parameters | Shows "⏳ {tool_name}({params})" |
| `tool_result` | Tool return value | Shows "✅ {summary}" or "❌ {error}" |
| `text` | Final/intermediate response text | Appended to chat panel |

### 5.3 Tool Schema (inline in agentcore.json)

Each tool definition follows MCP tool schema format:

```json
{
  "name": "search_catalogue",
  "description": "Search the agency data catalogue for datasets matching a query. Returns table names, descriptions, classifications, and owners.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Natural language search query"
      }
    },
    "required": ["query"]
  }
}
```

Full schemas for all 10 tools defined in Section 10 (Appendix).

---

## 6. Frontend Design (Streamlit)

### 6.1 Layout

Two-column layout:
- **Left (60%):** Chat panel (user messages + agent responses)
- **Right (40%):** Live reasoning panel (streamed tool calls + decisions)

### 6.2 SSE Consumption

```python
# Pseudocode — Streamlit app consuming AgentCore Runtime stream
response = invoke_agent_runtime(prompt, token, stream=True)
for event in response.event_stream:
    if event.type == "reasoning":
        reasoning_panel.write(event.text)
    elif event.type == "tool_start":
        reasoning_panel.status(f"⏳ {event.tool_name}")
    elif event.type == "tool_result":
        reasoning_panel.success(f"✅ {event.tool_name}")
    elif event.type == "text":
        chat_panel.write(event.text)
```

### 6.3 Auth in Streamlit

On app start:
1. Load `client_id` and `client_secret` from environment / `.env`
2. Call Cognito token endpoint → get access token
3. Cache token in `st.session_state`; refresh when expired
4. Pass token as `Authorization: Bearer` header on each `InvokeAgentRuntime` call

---

## 7. CDK Infrastructure Design

### 7.1 Stack Decomposition

| Stack | Resources | Outputs |
|-------|-----------|---------|
| `DataPlatformStack` | S3 buckets (data, Athena results, KB source, KB vectors), Glue Database, Athena Workgroup | Bucket ARNs, DB name, workgroup name |
| `CognitoStack` | User Pool, Resource Server, 2 App Clients | Pool ID, Pool ARN, client IDs, client secrets, issuer URL |
| `LambdaTargetsStack` | 5 Lambda functions, 5 IAM roles (least-privilege) | 5 Lambda ARNs |
| `KnowledgeBaseStack` | Bedrock KB, S3 Vectors bucket/index, KB data source | KB ID, KB ARN |
| `MlAssetsStack` | SageMaker Model Package Groups + versions, Feature Group | — |

**Cross-stack references:** `LambdaTargetsStack` imports bucket ARNs and DB name from `DataPlatformStack`. `KnowledgeBaseStack` imports the KB source bucket. All Lambda ARNs exported for `agentcore.json` consumption.

### 7.2 IAM Design (least privilege)

| Role | Permissions | Denies |
|------|-------------|--------|
| `glue-target-role` | `glue:GetTable`, `glue:GetTables`, `glue:SearchTables`, `glue:GetDatabase` | `glue:UpdateTable` (unless `ENABLE_WRITE_BACK=true`) |
| `athena-target-role` | `athena:*QueryExecution`, `athena:GetQueryResults`, `glue:GetTable/Database` (read), `s3:GetObject` (data), `s3:PutObject/GetObject` (results bucket) | No `glue:Update*`, no S3 write to data bucket |
| `sagemaker-target-role` | `sagemaker:List*`, `sagemaker:Describe*` | No `sagemaker:Create*`, `Update*`, `Delete*` |
| `pii-target-role` | `glue:GetTable` | No Bedrock, no writes |
| `kb-target-role` | `bedrock:Retrieve` (specific KB) | No `bedrock:RetrieveAndGenerate`, no `bedrock:Invoke*` |
| `gateway-invocation-role` | `lambda:InvokeFunction` (5 specific ARNs) | — |

---

## 8. Deployment Design

### 8.1 `setup.sh` Sequence

```bash
#!/bin/bash
set -euo pipefail

# 1. Pre-build checks
echo "Checking Bedrock model access..."
aws bedrock get-foundation-model --model-identifier anthropic.claude-sonnet-v2 --region eu-west-2
aws bedrock get-foundation-model --model-identifier amazon.titan-embed-text-v2:0 --region eu-west-2

# 2. CDK deploy
cd infra && cdk deploy --all --require-approval never --outputs-file ../cdk-outputs.json
cd ..

# 3. Generate + upload Parquet data
python data/generate_parquet.py                          # reads manifest.yaml → data/parquet/
aws s3 sync data/parquet/ s3://{data-bucket}/            # upload to S3

# 4. Create Glue tables (reads manifest.yaml + uses CDK-output DB name)
python scripts/create_glue_tables.py --manifest data/manifest.yaml --outputs cdk-outputs.json

# 5. Register SageMaker assets
python scripts/register_ml_assets.py --outputs cdk-outputs.json

# 6. Upload governance docs to KB source bucket + sync KB
aws s3 sync data/governance_docs/ s3://{kb-source-bucket}/
python scripts/sync_knowledge_base.py --outputs cdk-outputs.json   # triggers sync, waits for completion

# 7. Populate agentcore.json with CDK outputs (Lambda ARNs, Cognito details)
python scripts/populate_agentcore_json.py --outputs cdk-outputs.json

# 8. AgentCore deploy (Gateway + Identity + Runtime)
agentcore deploy

# 9. Output instructions
echo "✅ Deployment complete."
echo "Runtime endpoint: $(jq -r '.runtime.endpoint' agentcore-outputs.json)"
echo "Run: cd frontend && streamlit run app.py"
```

### 8.2 `teardown.sh` Sequence

```bash
#!/bin/bash
set -euo pipefail

# 1. AgentCore teardown (Runtime + Gateway + Identity)
agentcore destroy

# 2. Empty S3 buckets (required before CDK destroy)
aws s3 rm s3://{data-bucket} --recursive
aws s3 rm s3://{kb-source-bucket} --recursive
aws s3 rm s3://{athena-results-bucket} --recursive
# S3 Vectors bucket emptied by CDK RemovalPolicy.DESTROY or explicit delete

# 3. CDK destroy
cd infra && cdk destroy --all --force
cd ..

echo "✅ All resources destroyed. Account at zero ongoing charges."
```

### 8.3 `agentcore.json` Template

The file is a template with placeholders (`{LAMBDA_ARN_GLUE}`, `{COGNITO_ISSUER}`, etc.) that `populate_agentcore_json.py` fills from `cdk-outputs.json` before `agentcore deploy` runs.

---

## 9. Step 0.5 — Streaming Spike Design

**Purpose:** Validate that AgentCore Runtime CodeZip streaming delivers events incrementally (not buffered) and that the `@aws/agentcore` CLI deploy path works.

### Spike Agent (`spike/agent.py`)

```python
from strands import Agent
from strands.models import BedrockModel
import asyncio

model = BedrockModel(model_id="anthropic.claude-sonnet-v2", region_name="eu-west-2")
agent = Agent(model=model, system_prompt="You are a test agent. Count from 1 to 5 slowly.")

# HTTP handler for /invocations — streams SSE
async def handler(request):
    async for event in agent.stream_async(request.body["prompt"]):
        yield event  # Each event must arrive incrementally
```

### Spike Verification (`spike/test_stream.py`)

```python
# Calls InvokeAgentRuntime, measures time-to-first-event vs time-to-last-event
# PASS criteria: first event arrives within 3s; events are spaced (not all-at-once)
```

### Gate Criteria

- [ ] `agentcore deploy` succeeds (CodeZip uploaded, Runtime created)
- [ ] `InvokeAgentRuntime` returns SSE stream
- [ ] First event arrives within 5 seconds of invocation
- [ ] Events arrive incrementally (inter-event gap measurable, not all buffered at end)
- [ ] At least 3 distinct events observed in the stream

**Only proceed to Step 1 once all gate criteria pass.**

---

## 10. Appendix — Tool Input/Output Schemas

### search_catalogue

```json
{
  "input": {"query": "string (required)"},
  "output": {
    "tables": [{"name": "str", "database": "str", "description": "str", "classification": "str", "owner": "str"}]
  }
}
```

### get_dataset_detail

```json
{
  "input": {"database": "string (required)", "table_name": "string (required)"},
  "output": {
    "name": "str", "database": "str", "description": "str", "classification": "str",
    "owner": "str", "steward": "str", "location": "str", "last_updated": "str",
    "columns": [{"name": "str", "type": "str", "description": "str"}],
    "properties": {"key": "value"}
  }
}
```

### classify_pii

```json
{
  "input": {"database": "string (required)", "table_name": "string (required)"},
  "output": {
    "table_name": "str",
    "columns": [{"name": "str", "type": "str", "description": "str", "sample_values": ["str"]}]
  }
}
```

### show_lineage

```json
{
  "input": {"database": "string (required)", "table_name": "string (required)"},
  "output": {
    "table_name": "str",
    "upstream": ["str"],
    "downstream": ["str"],
    "transformation": "str"
  }
}
```

### generate_metadata

```json
{
  "input": {"database": "string (required)", "table_name": "string (required)"},
  "output": {
    "table_name": "str",
    "columns": [{"name": "str", "type": "str", "description": "str"}],
    "sample_rows": [{}],
    "write_back_enabled": false
  }
}
```

### suggest_joins

```json
{
  "input": {"goal": "string (required)"},
  "output": {
    "tables": [{"name": "str", "columns": [{"name": "str", "type": "str"}]}]
  }
}
```

### query_dataset

```json
{
  "input": {
    "question": "string (required)",
    "database": "string (required)",
    "table_name": "string (optional)"
  },
  "output": {
    "sql": "str",
    "columns": ["str"],
    "rows": [{}],
    "row_count": "int"
  }
}
```

### policy_search

```json
{
  "input": {"question": "string (required)"},
  "output": {
    "chunks": [{"text": "str", "source": "str", "score": "float"}]
  }
}
```

### list_ml_models

```json
{
  "input": {"query": "string (optional)"},
  "output": {
    "models": [{"name": "str", "type": "str", "description": "str", "status": "str", "created": "str"}],
    "feature_groups": [{"name": "str", "description": "str", "status": "str", "created": "str"}]
  }
}
```

### describe_ml_asset

```json
{
  "input": {
    "asset_type": "string (required) — 'model' | 'feature_group'",
    "asset_name": "string (required)"
  },
  "output": {
    "name": "str", "type": "str", "description": "str",
    "features_or_columns": [{"name": "str", "type": "str"}],
    "data_sources": ["str"],
    "metrics": {"key": "value"},
    "lineage": {"upstream_datasets": ["str"]}
  }
}
```

---

## 11. Key Design Decisions (rationale recap)

| # | Decision | Rationale |
|---|----------|-----------|
| D-1 | Single YAML manifest drives both Glue tables and Parquet data | Schema/data can't drift; one reviewable file |
| D-2 | `get_tables()` as demo-primary path (not `search_tables`) | 10 tables fit in context; semantic filtering by orchestrator guarantees cross-term matches |
| D-3 | Tool dispatch via `tool_name` field in Lambda handler | Single Lambda per target = fewer cold starts; dispatcher is trivial |
| D-4 | Template-based `agentcore.json` populated from CDK outputs | Avoids hardcoding ARNs; single `setup.sh` creates everything |
| D-5 | Spike before full build | Streaming fidelity is the demo's core value; if it doesn't work, the architecture changes |
| D-6 | No AgentCore Policy (Cedar) | Single M2M token gives nothing to differentiate on; adds complexity for zero value |
| D-7 | Offline-only Feature Store | Avoids standing cost; metadata discovery works the same |
| D-8 | Bundled governance docs (not fetched live) | Deployment reliability; no dependency on external URLs at deploy time |

---

*End of design. Awaiting review before proceeding to task breakdown.*
