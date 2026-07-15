# FAIR Data Principles — DWP Implementation Guide

## Purpose

This guide provides practical implementation guidance for applying the FAIR data principles (Findable, Accessible, Interoperable, Reusable) to datasets managed within the Department for Work and Pensions. All analytical datasets registered in the DWP data catalogue must progressively conform to these principles as part of the DWP Data Strategy 2023-2030.

The FAIR principles were originally developed for scientific data management but have been adopted across UK Government as best practice for maximising the value of data assets while maintaining appropriate governance controls.

## Findable

Data must be easy to find for both humans and machines. A dataset that cannot be discovered cannot be reused, leading to duplication of effort, inconsistent analysis, and wasted resource.

### DWP Requirements

- **F1: Persistent internal identifier.** Every dataset must be assigned a unique, persistent catalogue identifier (format: `DWP-DS-{PDU}-{NNNNNN}`) at the point of registration. This identifier must not change even if the dataset is migrated between storage platforms.
- **F2: Rich metadata.** All datasets must have complete metadata conforming to the DWP Metadata Standard v3.2, which includes 14 mandatory fields: title, description, owner, steward, classification, domain, creation date, last updated, update frequency, schema version, row count estimate, geographic coverage, temporal coverage, and access procedure.
- **F3: Registered in the catalogue.** Metadata must be registered in the central DWP data catalogue within 30 days of dataset creation. Datasets not in the catalogue are considered ungoverned and may be subject to remediation action.
- **F4: Indexed and searchable.** The catalogue must index all metadata fields and support both structured queries and natural language semantic search to enable discovery by analysts unfamiliar with the specific dataset.

### Practical Guidance

When registering a new dataset, use the catalogue self-service portal or the automated registration API. The description field should be written for a reader who has no prior knowledge of the project — explain what the data represents, how it was collected, and what questions it can answer. Avoid jargon without definition.

## Accessible

Once a dataset is discovered, the user must be able to understand how to gain access to it, even if access is restricted.

### DWP Requirements

- **A1: Standardised access protocol.** Access to all datasets must be via documented, standardised protocols (catalogue API, Analytical Platform workspace request, or formal Data Access Request for restricted datasets).
- **A1.1: Authentication and authorisation.** Access must be controlled through DWP identity management systems. Role-based access control (RBAC) aligned to data classification levels must be enforced programmatically.
- **A1.2: Access procedure documented.** Even where data is restricted, the catalogue entry must clearly describe the access request procedure, expected approval timeline, and any prerequisites (e.g., training completion, DPIA approval).
- **A2: Metadata always accessible.** Metadata must remain accessible even if the underlying data is archived, deleted, or access-restricted. This enables discovery without exposing sensitive content.

### Practical Guidance

When setting up access controls, apply the principle of least privilege. OFFICIAL datasets should default to discoverable-by-all with access granted to authenticated analysts within the relevant domain. SECRET and above require named-individual access lists reviewed quarterly. Document the access procedure in plain English — an analyst should be able to understand what they need to do without contacting the data owner directly.

## Interoperable

Data must be able to be integrated with other datasets and work with applications and workflows for analysis and processing.

### DWP Requirements

- **I1: Standard formats.** Analytical datasets must be stored in open, non-proprietary formats. Approved formats include Apache Parquet (preferred for columnar analytical data), CSV with published schema, and JSON with JSON Schema definition. Proprietary formats (Excel, SAS, SPSS) are acceptable only as secondary copies alongside a primary open-format version.
- **I2: Controlled vocabularies.** Where datasets use categorical fields, values should reference DWP standard controlled vocabularies (benefit types, geographic codes, organisation codes) maintained in the Reference Data Service.
- **I3: Schema documentation.** All datasets must have machine-readable schema documentation (Glue Data Catalog schema, JSON Schema, or equivalent) that defines field names, types, descriptions, valid ranges, and relationships to other datasets.

### Practical Guidance

When creating new datasets, prefer Parquet format for analytical workloads — it provides efficient compression, columnar access patterns, and embedded schema. Use ONS geography codes rather than free-text location fields. Reference the DWP Controlled Vocabulary Registry when defining categorical columns to ensure consistency with existing datasets.

## Reusable

Data should be well-described so that it can be replicated and reused in different settings, with clear usage licences and provenance.

### DWP Requirements

- **R1: Usage licence specified.** Every dataset must have an explicit internal usage licence defining permitted uses, restrictions, and obligations. The DWP Internal Data Licence Framework defines four tiers: Open Internal (any analytical use), Restricted Purpose (named projects only), Consent-Bound (limited by data subject consent scope), and Legal Gateway (restricted to specific statutory purposes).
- **R1.1: Provenance documented.** Data lineage must be recorded — what source systems feed the dataset, what transformations were applied, and what quality checks were performed. This enables consumers to assess fitness for their specific purpose.
- **R1.2: Community standards.** Metadata should conform to relevant community standards including the UK Government Metadata Standard, Dublin Core where applicable, and domain-specific standards (e.g., DWP Benefits Data Standard for Universal Credit datasets).
- **R1.3: Quality assessment.** Datasets must carry a Data Quality Score (DQS) based on the six dimensions: completeness, uniqueness, timeliness, validity, accuracy, and consistency. Scores are computed automatically where possible and manually assessed annually at minimum.

### Practical Guidance

When publishing a dataset for reuse, think about what a consumer twelve months from now would need to know. Document any known limitations, biases in collection methodology, and caveats about interpretation. Record the data pipeline version that produced the dataset so that results can be reproduced. Apply the most permissive licence tier that the data classification allows — over-restriction reduces value without improving security.

## Compliance and Monitoring

FAIR maturity is assessed using the DWP FAIR Scoring Framework, which evaluates each dataset on a 1-5 scale across the four principles. Scores are published in the catalogue and aggregated quarterly for the Data Board. PDUs are expected to show progressive improvement towards the targets set in the Data Strategy.

## Document Control

| Field | Value |
|-------|-------|
| Classification | OFFICIAL |
| Owner | Data Governance Team, CDO Directorate |
| Version | 3.2 |
| Last reviewed | January 2024 |
| Next review | January 2025 |
| Status | APPROVED |

*This is a synthetic document created for demonstration purposes. It does not represent actual DWP policy.*
