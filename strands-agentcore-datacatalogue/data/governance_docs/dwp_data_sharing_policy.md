# DWP Data Sharing Policy

## Purpose and Scope

This policy establishes the framework under which the Department for Work and Pensions (DWP) shares personal and non-personal data with Other Government Departments (OGDs), local authorities, and approved third-party organisations. It applies to all data sharing arrangements where DWP is the disclosing party, regardless of the method of transfer or the classification level of the data.

Data sharing is essential to DWP's mission. Effective collaboration with partner organisations enables fraud detection, service improvement, policy development, and better outcomes for citizens. However, all sharing must be lawful, proportionate, and conducted with appropriate safeguards to protect the rights of data subjects.

## Legal Gateways

All DWP data sharing must operate under a valid legal gateway. The following primary gateways are available:

### Data Protection Act 2018 (DPA 2018) and UK GDPR

Processing of personal data for sharing must have a lawful basis under Article 6 UK GDPR. For DWP operational data sharing, the most common bases are:

- **Article 6(1)(e):** Processing necessary for the performance of a task carried out in the public interest or in the exercise of official authority (primary basis for most DWP-to-OGD sharing)
- **Article 6(1)(c):** Processing necessary for compliance with a legal obligation

Where special category data is involved (health data, ethnicity, trade union membership), an additional condition under Article 9 must be satisfied, typically Article 9(2)(g) (substantial public interest) with reliance on Schedule 1, Part 2 of the DPA 2018.

### Digital Economy Act 2017 (DEA)

The DEA provides specific legal gateways for data sharing between public authorities for defined objectives:

- **Chapter 1:** Improving public service delivery to individuals and households
- **Chapter 2:** Tackling fraud against the public sector (including benefit fraud)
- **Chapter 3:** Debt owed to the public sector
- **Chapter 4:** Research purposes (via the UK Statistics Authority accredited researcher scheme)

DWP is a specified person under Schedules 4, 6, 8, and 12 of the DEA. Each share under the DEA must reference the specific chapter and objective.

### Social Security Administration Act 1992

Section 122 provides specific powers for DWP to share information for the purposes of social security functions, including with HMRC for earnings verification and with local authorities for Housing Benefit administration.

## Approved Partner Organisations

DWP maintains standing Data Sharing Agreements (DSAs) with the following OGD partners:

| Partner | Primary Purpose | Legal Gateway | Review Cycle |
|---------|----------------|---------------|--------------|
| HMRC | Earnings verification, fraud detection, tax credits | SSAA 1992 s.122, DEA Ch.2 | Annual |
| Home Office | Immigration status verification, identity fraud | DEA Ch.1, DPA 2018 Art.6(1)(e) | Annual |
| NHS Digital | Health-related benefit eligibility, disability assessments | DPA 2018 Art.6(1)(e), Art.9(2)(g) | Biennial |
| Local Authorities (via DWP Hub) | Housing Benefit, Council Tax Reduction, homelessness prevention | SSAA 1992 s.122, DEA Ch.1 | Annual |
| Ministry of Justice | Prison data for benefit suspension, probation service support | DEA Ch.1, DPA 2018 Art.6(1)(e) | Annual |
| Cabinet Office | National Fraud Initiative, Government as a Platform | DEA Ch.2 | Annual |

New partner organisations must be onboarded through the Data Sharing Governance Board (see Approval Process below).

## Data Minimisation Requirements

All data shares must comply with the principle of data minimisation:

- **Minimum necessary fields:** Only the specific data fields required to achieve the stated purpose may be shared. Full dataset extracts are never permitted where a subset would suffice.
- **Minimum necessary records:** Sharing must be limited to the population of data subjects relevant to the stated purpose. Bulk transfers of entire databases require explicit justification and enhanced controls.
- **Minimum necessary retention:** The receiving organisation must delete shared data when the purpose is fulfilled, subject to their own legal retention requirements. Maximum retention periods must be specified in the DSA.
- **Pseudonymisation where possible:** Where the purpose can be achieved with pseudonymised data (e.g., statistical analysis), personal identifiers must be removed or replaced before transfer.

## Data Protection Impact Assessments

A Data Protection Impact Assessment (DPIA) is mandatory for:

- All new data sharing arrangements
- Material changes to existing arrangements (new fields, new populations, new purposes)
- Any sharing involving special category data
- Any sharing involving data relating to children
- Bulk transfers exceeding 10,000 data subject records

DPIAs must be completed using the DWP DPIA Template v4.1 and approved by the relevant Information Asset Owner (IAO) and the DWP Data Protection Officer (DPO). High-risk DPIAs (those involving HIGH PII data or vulnerable populations) require additional review by the Caldicott Guardian where health data is involved.

## Approval Process for New Data Shares

1. **Initiation:** The requesting team completes the Data Sharing Request Form, identifying the purpose, legal gateway, data fields, population, frequency, and transfer method.
2. **IAO Assessment:** The Information Asset Owner for the relevant dataset assesses proportionality and confirms the legal gateway.
3. **DPIA Completion:** A DPIA is completed and reviewed by the DPO team.
4. **Security Assessment:** Information Security assesses the recipient's security posture and the proposed transfer mechanism.
5. **Governance Board Review:** The Data Sharing Governance Board reviews the complete package and either approves, requests amendments, or rejects.
6. **DSA Execution:** Upon approval, a formal Data Sharing Agreement is drafted by DWP Legal and executed by both parties.
7. **Implementation:** Technical implementation proceeds with appropriate testing and audit logging.

Standard timeline: 8-12 weeks from initiation to implementation for routine shares. Complex or high-risk shares may require 16+ weeks.

## Special Categories and Restrictions

### Universal Credit Claimant Data

Universal Credit data is classified as HIGH PII due to the breadth of personal circumstances it captures (income, housing, health conditions, caring responsibilities, sanctions history). Sharing UC claimant data is subject to enhanced controls:

- Field-level justification required for every UC data element shared
- Recipient must demonstrate equivalent or higher security posture to DWP
- Quarterly audit of recipient's data handling compliance
- Automated anomaly detection on access patterns

### Fraud Referral Data

Data shared for fraud investigation purposes carries additional restrictions:

- Must not be used for any purpose other than the investigation of the specific suspected fraud
- Subject access requests relating to fraud data must be routed through DWP Counter Fraud rather than standard SAR processes
- Onward sharing by the recipient is prohibited without DWP written consent
- Destruction certificate required within 30 days of case closure

### HIGH PII Datasets — Ministerial Approval

Any proposal to share a dataset classified as HIGH PII with an external organisation (including OGDs) that has not previously received HIGH PII data from DWP requires Ministerial approval via written submission. This applies regardless of the legal gateway and is an additional governance control beyond legal compliance.

The submission must include:
- Clear statement of public benefit
- Confirmation that the purpose cannot be achieved with lower-classified data
- Risk assessment including reputational risk
- DPO recommendation

## Transfer Methods

Approved transfer methods, by classification:

| Classification | Approved Methods |
|---------------|-----------------|
| OFFICIAL | Secure API (HTTPS/mTLS), SFTP, DWP Secure Transfer Service |
| OFFICIAL-SENSITIVE | Secure API (HTTPS/mTLS) with field encryption, DWP Secure Transfer Service with encryption at rest |
| SECRET | Dedicated secure channels only — contact Information Security |

Email is never an approved transfer method for personal data, regardless of classification.

## Monitoring and Compliance

All active data sharing arrangements are subject to:

- Annual review and re-certification by the IAO
- Quarterly compliance reporting to the Data Sharing Governance Board
- Random audit by DWP Internal Audit (minimum 10% of active DSAs per year)
- Breach reporting within 24 hours via the DWP Data Incident Management Process

Non-compliance may result in suspension of the data share pending investigation.

## Document Control

| Field | Value |
|-------|-------|
| Classification | OFFICIAL |
| Owner | Data Sharing Governance Board, DWP |
| Version | 5.3 |
| Last reviewed | September 2023 |
| Next review | September 2024 |
| Status | APPROVED |

*THIS IS A SYNTHETIC DOCUMENT created for demonstration purposes. It does not represent actual DWP policy or reveal any real data sharing arrangements.*
