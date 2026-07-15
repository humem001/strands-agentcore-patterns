# DWP Data Strategy 2023-2030

## Executive Summary

The Department for Work and Pensions (DWP) manages one of the largest and most complex data estates in UK Government. With over 27 petabytes of data distributed across more than 20 Policy Delivery Units (PDUs), approximately 750 analysts, and responsibility for services touching nearly every citizen at some point in their lives, the strategic management of data is not merely an operational concern but a fundamental enabler of the Department's mission.

This strategy sets out how DWP will transform its relationship with data over the period 2023 to 2030, moving from fragmented, siloed data holdings towards a unified, discoverable, and governed data estate that enables rapid insight generation while maintaining the highest standards of privacy and security.

## Strategic Pillars

### 1. Data as a Strategic Asset

DWP recognises data as a strategic asset of equivalent importance to its workforce and financial resources. Every dataset created, collected, or derived within the Department has potential value beyond its original purpose. The strategy mandates that all datasets must be registered in the central data catalogue within 30 days of creation, with complete metadata that enables discovery by analysts who were not involved in the original data collection.

The current state is characterised by significant discovery friction. Analysts report that locating relevant datasets for a new project can take weeks or even months, as institutional knowledge is distributed across teams and informal networks. The target state is to reduce this discovery time from months to hours through comprehensive cataloguing, rich metadata, and intelligent search capabilities.

### 2. Adoption of FAIR Principles

All DWP data assets will progressively conform to the FAIR data principles — Findable, Accessible, Interoperable, and Reusable. This is not an aspirational statement but a measurable programme of work with defined milestones:

- By end 2024: All OFFICIAL-tier analytical datasets catalogued with minimum mandatory metadata fields
- By end 2025: All datasets assigned persistent internal identifiers and linked to data lineage records
- By end 2026: Cross-PDU data sharing agreements standardised and machine-readable
- By end 2028: Full FAIR maturity assessment scoring applied to all Tier 1 and Tier 2 datasets

The FAIR programme is governed by the Chief Data Officer's team and reports quarterly to the DWP Data Board.

### 3. Data Catalogue for Discovery

The central data catalogue is the cornerstone of the discovery transformation. It provides a single, searchable registry of all analytical datasets, their schemas, ownership, classification, quality scores, and access procedures. The catalogue supports both structured search (by domain, classification, owner, date range) and semantic search (natural language queries about data content and meaning).

The catalogue is not merely a static registry. It integrates with data pipelines to maintain currency, records lineage from source to derived products, and provides automated quality scoring based on completeness, timeliness, consistency, and validity metrics.

### 4. AI and Machine Learning for Fraud Detection and Service Improvement

DWP is investing significantly in AI/ML capabilities, with a particular focus on fraud and error detection within Universal Credit, Housing Benefit, and legacy benefits. The Department's Counter Fraud, Compliance and Debt (CFCD) directorate uses machine learning models to identify patterns indicative of fraudulent claims, enabling targeted interventions that protect the public purse while minimising disruption to legitimate claimants.

All AI/ML models that influence decisions affecting claimants must comply with the DWP AI Ethics Framework, which mandates explainability, fairness testing across protected characteristics, and human-in-the-loop oversight for high-impact determinations. Model risk is managed through the Three Lines of Defence framework, with independent validation required before any model enters production.

### 5. Data Sharing with Other Government Departments

DWP shares data with approved Other Government Departments (OGDs) including HMRC, the Home Office, NHS Digital, and local authorities under specific legal gateways. The strategy commits to making these data shares more efficient through standardised APIs, pre-approved sharing patterns, and automated Data Protection Impact Assessments for routine recurring shares.

All new data sharing arrangements must be approved through the DWP Data Sharing Governance Board, which assesses legal basis, proportionality, data minimisation, and recipient security posture.

### 6. Data Literacy Programme

The strategy recognises that tools and infrastructure alone are insufficient without workforce capability. The DWP Data Literacy Programme targets three tiers:

- **Foundation tier** (all staff): Understanding data classifications, handling requirements, and the value of good data practice
- **Practitioner tier** (analysts, policy professionals): Proficiency with analytical tools, statistical methods, and data governance procedures
- **Expert tier** (data scientists, engineers): Advanced capabilities in ML, cloud-native analytics, and data architecture

The programme aims to certify 5,000 staff at Foundation level and 1,500 at Practitioner level by 2026.

### 7. Cloud-First Analytics

DWP has committed to a cloud-first approach for analytical workloads, migrating from legacy on-premises infrastructure to AWS cloud services. This enables elastic scaling, access to managed AI/ML services, and significantly reduced time-to-insight for analytical projects.

The Analytical Platform provides a governed, secure environment where analysts can access catalogued datasets, run queries against data lakes, train models, and publish results — all within a framework of appropriate access controls, audit logging, and data classification enforcement.

## Governance and Accountability

The strategy is governed by the DWP Data Board, chaired by the Chief Data Officer and comprising Senior Responsible Owners from each PDU. Progress is reported quarterly against a balanced scorecard covering catalogue coverage, FAIR maturity, data literacy certification rates, incident volumes, and analyst satisfaction scores.

## Success Measures

| Metric | Baseline (2023) | Target (2030) |
|--------|-----------------|---------------|
| Catalogue coverage (Tier 1 datasets) | 35% | 100% |
| Mean discovery time for new projects | 6-8 weeks | < 4 hours |
| FAIR maturity score (average) | 1.8 / 5.0 | 4.2 / 5.0 |
| Data literacy Foundation certification | 800 staff | 5,000 staff |
| Cross-PDU data reuse incidents | 12 per year | 200+ per year |
| Time to provision new data share | 16 weeks | 2 weeks |

## Document Control

| Field | Value |
|-------|-------|
| Classification | OFFICIAL |
| Owner | Chief Data Officer, DWP |
| Version | 2.1 |
| Last reviewed | March 2024 |
| Next review | March 2025 |
| Status | APPROVED |

*This is a synthetic document created for demonstration purposes. It does not represent actual DWP policy.*
