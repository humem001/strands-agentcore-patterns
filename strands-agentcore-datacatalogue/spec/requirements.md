# Requirements — Data Catalogue & Governance Agent

> Source brief: `data_catalogue_governance_agent.md` (v5)
> Status: **DRAFT — awaiting review**
> Date: 2026-07-15

---

## 1. Purpose

A conversational AI agent that gives data analysts, case workers, and policy teams natural-language access to the department's data catalogue, governance policies, and ML assets — reducing dataset discovery time from months to seconds.

The agent is hosted on **Bedrock AgentCore Runtime** (Strands SDK, CodeZip), streams reasoning steps live to a Streamlit UI, and orchestrates five backend tool targets via **AgentCore Gateway**.

---

## 2. Regional Availability — Pre-Build Verification

All services confirmed available in **eu-west-2 (London)**:

| Service | Status |
|---------|--------|
| Amazon Bedrock (Claude Sonnet) | Available — requires per-account model access toggle |
| Amazon Bedrock (Titan Text Embeddings V2) | Available — requires per-account model access toggle |
| Bedrock AgentCore (Runtime + Gateway) | Available |
| Bedrock Knowledge Bases (RAG) + S3 Vectors | Available |
| AWS Glue | Available |
| Amazon Athena | Available |
| Amazon Cognito | Available |
| Amazon SageMaker AI | Available |

**Manual prerequisite (cannot be scripted):** Enable Bedrock model access for Claude Sonnet and Titan Text Embeddings V2 in the eu-west-2 console before running `setup.sh`.

---

## 3. Functional Requirements

### FR-1: Dataset Discovery (`search_catalogue`)

| ID | Requirement |
|----|-------------|
| FR-1.1 | The agent SHALL accept a natural-language query and return matching datasets from the Glue Data Catalog. |
| FR-1.2 | The demo-primary path SHALL use `glue.get_tables()` (full catalogue, 10 tables) with orchestrator-side semantic filtering. |
| FR-1.3 | The target Lambda SHALL also expose `glue.search_tables(SearchText=...)` as the at-scale keyword path. |
| FR-1.4 | Results SHALL include: table name, database, description, classification, and owner. |

### FR-2: Dataset Understanding (`get_dataset_detail`)

| ID | Requirement |
|----|-------------|
| FR-2.1 | Given a database and table name, the agent SHALL return full dataset details. |
| FR-2.2 | Details SHALL include: columns (name, type, description), table properties, S3 location, last updated, owner, and steward. |

### FR-3: PII Classification (`classify_pii`)

| ID | Requirement |
|----|-------------|
| FR-3.1 | The agent SHALL classify each column in a table as NONE / LOW / MEDIUM / HIGH PII. |
| FR-3.2 | Classification reasoning SHALL be performed by the orchestrator (Claude), NOT the target Lambda. |
| FR-3.3 | The target Lambda SHALL return column names, types, and optional sample data only. |
| FR-3.4 | The agent SHALL provide reasoning for each classification. |

### FR-4: Data Lineage (`show_lineage`)

| ID | Requirement |
|----|-------------|
| FR-4.1 | The agent SHALL display upstream sources, downstream consumers, and transformation descriptions for a dataset. |
| FR-4.2 | Lineage data SHALL be stored in Glue table custom properties (JSON). |
| FR-4.3 | The orchestrator SHALL explain lineage in plain English. |

### FR-5: Metadata Generation (`generate_metadata`)

| ID | Requirement |
|----|-------------|
| FR-5.1 | The agent SHALL generate FAIR-compliant descriptions for undocumented datasets. |
| FR-5.2 | The orchestrator SHALL generate: table description, column descriptions, suggested classification, and tags. |
| FR-5.3 | Write-back to Glue (`update_table`) SHALL be DISABLED by default. |
| FR-5.4 | Write-back SHALL be enforced by IAM (no `glue:UpdateTable` permission on the target role) unless a deploy flag explicitly enables it. |

### FR-6: Join Recommendations (`suggest_joins`)

| ID | Requirement |
|----|-------------|
| FR-6.1 | Given an analytical goal, the agent SHALL recommend how to join relevant datasets. |
| FR-6.2 | Recommendations SHALL include: tables, join keys, and caveats (e.g., granularity mismatches). |
| FR-6.3 | The orchestrator SHALL reason over schemas returned by the target Lambda. |

### FR-7: Live Data Querying (`query_dataset`)

| ID | Requirement |
|----|-------------|
| FR-7.1 | The agent SHALL translate a natural-language question into SQL, execute it on Athena, and return results with a plain-English summary. |
| FR-7.2 | The orchestrator SHALL apply `LIMIT 100` and SHALL NOT emit DML/DDL statements. |
| FR-7.3 | The Athena target role SHALL have read-only Glue + read-only S3 permissions only. |
| FR-7.4 | A dedicated Athena workgroup with a fixed output location SHALL be used. |
| FR-7.5 | The agent SHALL display the generated SQL to the user. |

### FR-8: Governance Q&A (`policy_search`)

| ID | Requirement |
|----|-------------|
| FR-8.1 | The agent SHALL answer governance/compliance questions grounded in agency policy documents. |
| FR-8.2 | The target Lambda SHALL call Bedrock KB `retrieve` only (NOT `retrieve_and_generate`). |
| FR-8.3 | The orchestrator SHALL synthesise answers and format citations from returned chunks. |
| FR-8.4 | Answers SHALL include source document references. |

### FR-9: ML Asset Discovery (`list_ml_models`, `describe_ml_asset`)

| ID | Requirement |
|----|-------------|
| FR-9.1 | The agent SHALL list SageMaker Model Registry models and Feature Store groups. |
| FR-9.2 | The agent SHALL describe individual models/feature groups including: features, data sources, metrics, and lineage to source datasets. |
| FR-9.3 | Feature Store SHALL be offline-only (no online store). |

### FR-10: Multi-Step Orchestration

| ID | Requirement |
|----|-------------|
| FR-10.1 | The agent SHALL chain multiple tools autonomously within a single user query. |
| FR-10.2 | Each reasoning and tool-call step SHALL stream incrementally to the UI (SSE). |
| FR-10.3 | The orchestrator SHALL own ALL LLM reasoning — target Lambdas SHALL NOT call Bedrock. |

---

## 4. Non-Functional Requirements

### NFR-1: Streaming & Transparency

| ID | Requirement |
|----|-------------|
| NFR-1.1 | The agent SHALL stream each reasoning/tool step incrementally via SSE (Strands `stream_async`). |
| NFR-1.2 | The UI SHALL display a live reasoning panel showing: tool name, parameters, status (pending/success/error), and LLM decision text before each tool call. |
| NFR-1.3 | Streaming fidelity SHALL be proven in Step 0.5 (integration spike) before the full build proceeds. |

### NFR-2: Security & Auth

| ID | Requirement |
|----|-------------|
| NFR-2.1 | Inbound auth (Streamlit → Runtime) SHALL use a single pre-provisioned Cognito app-client token (simplified login, no hosted UI). |
| NFR-2.2 | M2M auth (agent → Gateway) SHALL use Cognito client-credentials via AgentCore Identity (`@requires_access_token`). |
| NFR-2.3 | Gateway inbound auth SHALL use a CUSTOM_JWT authorizer validating against Cognito. |
| NFR-2.4 | Gateway outbound to Lambdas SHALL use `GATEWAY_IAM_ROLE` (SigV4). |
| NFR-2.5 | AgentCore Policy (Cedar) SHALL NOT be used. |
| NFR-2.6 | All safety guardrails (Athena read-only, metadata write-back disabled) SHALL be enforced by IAM, not prompt-level controls alone. |

### NFR-3: Data Residency

| ID | Requirement |
|----|-------------|
| NFR-3.1 | ALL resources SHALL be deployed in eu-west-2 (London) only. |
| NFR-3.2 | No cross-region inference (in-region Bedrock only). |

### NFR-4: Cost Discipline

| ID | Requirement |
|----|-------------|
| NFR-4.1 | No standing-cost services: S3 Vectors (not OpenSearch Serverless), offline-only Feature Store, pay-per-use AgentCore. |
| NFR-4.2 | `teardown.sh` SHALL return the account to zero ongoing charges (explicitly destroying S3 Vectors store, KB, Gateway, Runtime, Cognito pool). |

### NFR-5: Deployability

| ID | Requirement |
|----|-------------|
| NFR-5.1 | `./setup.sh` SHALL create the complete environment from scratch with no manual steps beyond credentials and model access enablement. |
| NFR-5.2 | Infrastructure SHALL be split: CDK (Python) for data-plane + `@aws/agentcore` CLI for Runtime/Gateway/Identity. |
| NFR-5.3 | `teardown.sh` SHALL provide full cleanup. |

### NFR-6: Data

| ID | Requirement |
|----|-------------|
| NFR-6.1 | 10 synthetic datasets — fully fictional (no real names, national ID numbers, or case references). |
| NFR-6.2 | A single YAML manifest SHALL drive both Glue table definitions and Parquet data generation. |
| NFR-6.3 | SageMaker assets SHALL be metadata-only (no training). |
| NFR-6.4 | Governance KB SHALL bundle static copies of policy documents (not fetched live). |

---

## 5. Constraints (Fixed — Do Not Re-Open)

| # | Constraint |
|---|-----------|
| C-1 | Region: eu-west-2 (London) only |
| C-2 | Agent host: Bedrock AgentCore Runtime — CodeZip (HTTP/SSE), NOT Lambda |
| C-3 | Agent framework: Strands SDK (`stream_async`) |
| C-4 | LLM: Bedrock Claude Sonnet; Embeddings: Titan Text Embeddings V2 |
| C-5 | Tools: AgentCore Gateway with 5 lambda targets exposing 10 tools |
| C-6 | KB vector store: S3 Vectors (NOT OpenSearch Serverless) |
| C-7 | KB access: `retrieve` only — orchestrator synthesises (no `retrieve_and_generate`) |
| C-8 | Auth: Cognito simplified inbound + AgentCore Identity for M2M |
| C-9 | Glue tables created directly (no Crawler); single YAML manifest drives schema + data |
| C-10 | `generate_metadata` write-back disabled by default (IAM-gated) |
| C-11 | Step 0.5 streaming spike is a hard gate before the full build |
| C-12 | Frontend: Streamlit, run locally |
| C-13 | Data: 10 synthetic fictional datasets |
| C-14 | Deploy: CDK + `@aws/agentcore` CLI, orchestrated by `setup.sh`; `teardown.sh` for cleanup |
| C-15 | Testing: demo-level only (11-scenario smoke script, one retry + backoff, no unit tests) |

---

## 6. Acceptance Criteria (11 Demo Scenarios)

The system passes acceptance when ALL of the following scenarios produce correct, non-empty, streaming responses:

| # | Scenario | Expected Behaviour |
|---|----------|-------------------|
| AC-1 | "I'm new to the fraud team — what datasets are available?" | Returns relevant datasets (fraud_referral_outcomes, etc.) with descriptions |
| AC-2 | "What columns are in the CMS payment history table?" | Returns full column list with types and descriptions |
| AC-3 | "Which datasets contain national identification numbers?" | Identifies datasets with HIGH PII (nino column) with reasoning |
| AC-4 | "Where does the compliance prediction score come from?" | Shows lineage: cms_payment_history → SageMaker pipeline → cms_compliance_predictions |
| AC-5 | "Generate a description for the jcs_chatbot_interactions table" | Produces FAIR-compliant metadata (write-back disabled) |
| AC-6 | "I want to link fraud referrals to payment history — how?" | Suggests join on nino/case_id with caveats |
| AC-7 | "Show me the top 10 cases with the highest non-compliance risk score" | Generates SQL, executes on Athena, returns rows + summary |
| AC-8 | "Can I share benefit claimant data with an external agency?" | Answers from policy docs with citations |
| AC-9 | "Find all HIGH PII datasets, show me their lineage, and tell me who owns them" | Multi-step: classify → lineage → owner for multiple datasets |
| AC-10 | "What ML models do we have for fraud detection?" | Lists fraud-detection-v1 model with description |
| AC-11 | "What data was the compliance predictor trained on, and where does that come from?" | Shows model → training data → source lineage chain |

**For each scenario:** the live reasoning panel SHALL stream tool calls and intermediate reasoning in real-time.

---

## 7. Out of Scope

- Per-user authentication / authorization (single shared token for demo)
- AgentCore Policy (Cedar)
- DataZone / SageMaker Catalog integration
- Load testing, performance testing, mocked unit tests
- Frontend hosting infrastructure (Streamlit runs locally)
- Production hardening (rate limiting, WAF, monitoring dashboards)
- Real personal information
- Online Feature Store
- Cross-region failover

---

## 8. Assumptions

1. The deploying account has Bedrock model access enabled for Claude Sonnet and Titan Text Embeddings V2 in eu-west-2.
2. The deploying IAM principal has sufficient permissions to create all required resources (CDK bootstrap, Lambda, Cognito, Glue, Athena, SageMaker, Bedrock KB, AgentCore).
3. The `@aws/agentcore` CLI is installed and authenticated.
4. Python 3.11+ and Node.js (for CDK) are available on the deployment machine.
5. The presenter's machine has network access to the AgentCore Runtime endpoint.

---

## 9. Dependencies

| Dependency | Type | Risk |
|------------|------|------|
| Bedrock model access (manual toggle) | External / manual | Low — one-time setup |
| AgentCore Runtime CodeZip streaming fidelity | Technical | **High** — gated by Step 0.5 spike |
| `@aws/agentcore` CLI deploy path | Technical | Medium — validated in Step 0.5 |
| S3 Vectors + KB integration | Technical | Low — GA since Dec 2025 |
| Athena first-query cold-start latency | Operational | Low — mitigated by reasoning panel UX |

---

*End of requirements. Awaiting review before proceeding to design.*
