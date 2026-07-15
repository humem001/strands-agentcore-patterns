# DWP Information Management Policy

## Purpose and Scope

This policy establishes the requirements for the management of information assets across the Department for Work and Pensions throughout their lifecycle — from creation through active use, retention, and eventual disposal. It applies to all information held by DWP regardless of format (digital or physical), classification level, or storage location.

Effective information management is a legal obligation, an operational necessity, and a prerequisite for the Department's data strategy ambitions. Without reliable retention, quality, and metadata practices, the data catalogue cannot function, analytical outputs cannot be trusted, and the Department cannot meet its statutory obligations for transparency and accountability.

## Data Retention Periods

DWP applies retention periods based on data classification and business purpose. The following schedule defines minimum and maximum retention periods:

### Operational Claimant Data

| Data Category | Retention Period | Trigger | Authority |
|---------------|-----------------|---------|-----------|
| Active claim records | Duration of claim + 6 years | Claim closure date | Limitation Act 1980 |
| Closed claim records (standard) | 6 years from closure | Claim closure date | Limitation Act 1980 |
| Closed claim records (fraud-related) | 12 years from closure | Case closure date | Proceeds of Crime Act 2002 |
| Medical evidence and assessments | 7 years from decision | Decision date | NHS Records Management Code |
| Overpayment and debt records | Duration of recovery + 6 years | Final payment/write-off | Treasury guidelines |
| Sanctions and compliance records | 6 years from sanction end | Sanction expiry date | DWP operational requirement |

### Analytical and Derived Data

| Data Category | Retention Period | Trigger | Authority |
|---------------|-----------------|---------|-----------|
| Analytical datasets (OFFICIAL) | 7 years from last use | Last access date | DWP Data Strategy |
| Model training data | Life of model + 3 years | Model decommission | AI Security Policy |
| Statistical publications (source data) | Permanent | N/A | Statistics and Registration Service Act 2007 |
| Research datasets (DEA gateway) | Duration of project + 2 years | Project closure | Digital Economy Act 2017 |
| Temporary analytical extracts | 90 days | Creation date | DWP operational requirement |

### Corporate and Administrative Data

| Data Category | Retention Period | Trigger | Authority |
|---------------|-----------------|---------|-----------|
| Board papers and minutes | 20 years | Meeting date | Public Records Act 1958 |
| Policy submissions | 10 years | Submission date | DWP corporate requirement |
| Contracts and commercial records | Duration + 6 years | Contract end | Limitation Act 1980 |
| HR records | Employment + 6 years | Leaving date | Employment legislation |
| Financial records | Current year + 6 years | Financial year end | Finance Act requirements |

## Destruction Schedules

Data must be destroyed in accordance with the retention schedule. The destruction process requires:

- **Automated flagging:** The DWP Records Management System flags records approaching their destruction date 90 days in advance.
- **Review and authorisation:** The Information Asset Owner (IAO) or delegated Records Manager must authorise destruction. Destruction of records classified OFFICIAL-SENSITIVE or above requires two-person authorisation.
- **Destruction method:** Digital records must be destroyed using methods appropriate to classification — logical deletion with verification for OFFICIAL, cryptographic erasure for OFFICIAL-SENSITIVE, and certified destruction for SECRET and above.
- **Destruction certificate:** A destruction certificate must be generated and retained permanently, recording what was destroyed, when, by whom, under what authority, and the method used.
- **Exceptions:** Records subject to legal hold, FOI request, Subject Access Request, or active litigation must NOT be destroyed regardless of retention expiry until the hold is lifted.

## Legal Holds

A legal hold suspends normal retention and destruction schedules for specified records. Legal holds are issued by DWP Legal Services and must be applied within 24 hours of notification. Common triggers include:

- Active or anticipated litigation involving DWP
- Parliamentary inquiry or select committee investigation
- Information Commissioner investigation
- Criminal investigation (internal or external)
- Judicial review proceedings

Legal holds apply to all copies of the specified records across all storage locations. Staff who become aware of potential litigation must notify DWP Legal Services immediately to enable early preservation.

## Records Management

All DWP information must be managed within approved records management systems:

- **Electronic records:** Managed within DWP-approved platforms with appropriate access controls, version management, and audit trails.
- **Physical records:** Managed through the DWP Records Centre or approved off-site storage with tracked retrieval and destruction services.
- **Hybrid records:** Where a physical original has been digitised, the digital copy becomes the official record if digitisation meets the BS 10008 standard. The physical original may then be destroyed in accordance with the digitisation disposal schedule.

Records must be filed in accordance with the DWP File Plan, which provides a hierarchical classification scheme aligned to departmental functions. Misfiled or unfiled records (including email attachments, local desktop files, and personal drives) are considered ungoverned and represent a compliance risk.

## Freedom of Information Obligations

DWP is a public authority under the Freedom of Information Act 2000. Effective information management directly supports FOI compliance:

- **Retrieval capability:** Records must be organised and indexed such that relevant information can be located and retrieved within the 20 working day statutory deadline.
- **Publication scheme:** Information routinely published under the DWP Publication Scheme must be proactively maintained and updated. Dataset metadata in the catalogue supports this obligation.
- **Exemptions assessment:** Where exemptions are claimed, the original records must be available for internal review and potential ICO investigation.

## Subject Access Requests

Under UK GDPR Article 15, data subjects have the right to access their personal data held by DWP. The information management framework must support:

- **Comprehensive search:** The ability to locate all personal data relating to an identified individual across all DWP systems within the one calendar month statutory deadline.
- **Format requirements:** Data must be provided in a commonly used electronic format. Structured datasets must be extractable in machine-readable form.
- **Third-party redaction:** Where records contain third-party personal data, the information management system must support efficient redaction workflows.

DWP receives approximately 15,000 Subject Access Requests per year. Effective metadata and cataloguing directly reduces the cost and effort of SAR compliance.

## Data Quality Standards

All DWP datasets must meet minimum data quality standards assessed across six dimensions:

- **Completeness:** The proportion of required fields that contain values. Target: >95% for mandatory fields.
- **Uniqueness:** The absence of unintentional duplicate records. Target: <0.1% duplication rate for entity records.
- **Timeliness:** Data reflects the real-world state within the expected latency. Target: defined per dataset based on update frequency.
- **Validity:** Values conform to defined formats, ranges, and business rules. Target: >99% validity rate for constrained fields.
- **Accuracy:** Values correctly represent the real-world entity they describe. Target: assessed through sampling and reconciliation.
- **Consistency:** The same fact is represented identically across all datasets where it appears. Target: zero unreconciled contradictions in master data entities.

Data quality is measured automatically where possible (completeness, uniqueness, validity) and by periodic manual assessment where automation is not feasible (accuracy). Quality scores are published in the data catalogue as part of dataset metadata.

## Mandatory Metadata for All Datasets

Every dataset registered in the DWP data catalogue must carry the following mandatory metadata fields:

1. **Dataset title** — Human-readable name following DWP naming conventions
2. **Description** — Plain-English description of content and purpose (minimum 50 words)
3. **Owner** — The SCS-level Information Asset Owner responsible for the dataset
4. **Steward** — The operational data steward responsible for day-to-day management
5. **Classification** — Security classification (OFFICIAL, OFFICIAL-SENSITIVE, SECRET)
6. **PII level** — Personal data sensitivity (NONE, LOW, MEDIUM, HIGH)
7. **Domain** — Business domain from the DWP Domain Taxonomy
8. **Creation date** — Date the dataset was first created
9. **Last updated** — Date of most recent data refresh
10. **Update frequency** — How often the data is refreshed (real-time, daily, weekly, monthly, quarterly, annual, ad-hoc)
11. **Retention period** — Applicable retention schedule reference
12. **Geographic coverage** — Geographic scope (GB, England, Wales, Scotland, regional, local)
13. **Temporal coverage** — Date range of data content
14. **Access procedure** — How to request access (link to request form or API documentation)

Datasets missing mandatory metadata fields are flagged as non-compliant in the catalogue and escalated to the IAO for remediation within 30 days.

## Annual Data Audit

Each PDU must conduct an annual data audit covering:

- Inventory reconciliation (all datasets accounted for in the catalogue)
- Retention compliance (no data held beyond retention period without justification)
- Access review (all access grants still appropriate and justified)
- Quality assessment (quality scores current and accurate)
- Classification review (classifications still appropriate given any changes in data content)

Audit results are reported to the DWP Data Board and inform the annual Governance Statement to Parliament.

## Document Control

| Field | Value |
|-------|-------|
| Classification | OFFICIAL |
| Owner | Head of Information Management, DWP Digital |
| Version | 4.1 |
| Last reviewed | June 2023 |
| Next review | June 2024 |
| Status | APPROVED |

*This is a synthetic document created for demonstration purposes. It does not represent actual DWP policy.*
