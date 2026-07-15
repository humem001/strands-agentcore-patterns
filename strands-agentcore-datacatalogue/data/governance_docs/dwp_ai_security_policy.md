# DWP AI Security Policy

## Purpose and Scope

This policy establishes the security requirements for the development, deployment, and operation of Artificial Intelligence (AI) and Machine Learning (ML) systems within the Department for Work and Pensions. It applies to all AI/ML models, whether developed in-house, procured from vendors, or accessed as cloud services, that process DWP data or influence decisions relating to DWP operations or claimants.

AI systems present unique security challenges beyond traditional software: adversarial inputs can manipulate model behaviour, training data poisoning can embed persistent vulnerabilities, and the opacity of complex models can obscure security-relevant failures. This policy addresses these challenges within the context of DWP's specific threat landscape and operational requirements.

## Model Risk Assessment

All AI/ML models must undergo a Model Risk Assessment (MRA) before deployment to production. The MRA evaluates:

- **Impact classification:** Models are classified as LOW, MEDIUM, or HIGH impact based on the consequences of incorrect outputs. Any model whose output directly influences a decision affecting a claimant's benefit entitlement, sanction, or referral is automatically classified as HIGH impact.
- **Threat surface:** Assessment of attack vectors including adversarial inputs, data poisoning, model extraction, membership inference, and prompt injection (for generative AI systems).
- **Data sensitivity:** Classification of training data, inference inputs, and model outputs using the DWP Data Classification Framework.
- **Failure modes:** Identification of how the model can fail, the detectability of each failure mode, and the consequence severity.

MRAs must be reviewed by the AI Security Panel (a sub-committee of the DWP Cyber Security Board) and updated annually or upon material change to the model, its training data, or its operating environment.

## Data Classification for Training Data

Training data inherits the classification of the most sensitive data element it contains. Additional requirements apply:

- **Training data provenance:** Complete lineage records must be maintained documenting the source, transformations, and quality checks applied to all training data. This enables rapid assessment if a source is later found to be compromised.
- **Data segregation:** Training data classified as OFFICIAL-SENSITIVE or above must be stored in dedicated, access-controlled environments separate from general analytical workspaces. Access is restricted to named individuals with valid justification.
- **Synthetic data preference:** Where model performance objectives can be met with synthetic or anonymised data, this must be preferred over real personal data. A documented assessment justifying the use of real personal data is required where synthetic alternatives are rejected.
- **Retention and disposal:** Training datasets must follow the same retention schedules as operational data of equivalent classification. Models trained on data that has been subject to deletion requests must be assessed for memorisation risk.

## Adversarial Attack Mitigation

DWP AI systems must implement defences appropriate to their impact classification:

- **Input validation:** All inference inputs must be validated against expected distributions. Anomalous inputs must be flagged for review rather than processed silently.
- **Robustness testing:** HIGH impact models must undergo adversarial robustness testing before deployment, using techniques appropriate to the model type (e.g., projected gradient descent for classifiers, red-teaming for generative models).
- **Output monitoring:** Production models must have continuous monitoring for output drift, confidence score distribution changes, and anomalous prediction patterns that may indicate adversarial activity.
- **Rate limiting:** External-facing AI services must implement rate limiting to prevent model extraction attacks through systematic querying.
- **Prompt injection defences:** Generative AI systems must implement input sanitisation, system prompt protection, and output filtering to mitigate prompt injection and jailbreak attempts.

## Explainability Requirements

AI systems that influence decisions affecting DWP claimants must provide explanations that are:

- **Meaningful to the decision-maker:** The human reviewing the AI output must receive sufficient explanation to understand why the model reached its conclusion and to identify obvious errors.
- **Appropriate to the impact level:** HIGH impact decisions require feature-level explanations (which input factors most influenced the output). MEDIUM impact decisions require at minimum a confidence score and flagging of unusual inputs.
- **Auditable:** Explanations must be logged alongside decisions to support retrospective review, complaint investigation, and legal challenge.
- **Compliant with UK GDPR Article 22:** Where decisions are solely automated and produce legal or similarly significant effects, data subjects have the right to meaningful information about the logic involved. Explanations must be expressible in terms a claimant can understand.

## Human-in-the-Loop Requirements

The following mandates apply based on impact classification:

- **HIGH impact models:** A trained human decision-maker must review and approve every individual output before it is actioned. The model output is advisory only. The human must have the authority, training, and time to override the model recommendation. Rubber-stamping without genuine review is a policy violation.
- **MEDIUM impact models:** Human review is required for cases where the model confidence score falls below the defined threshold, and for a random sample of at minimum 5% of all outputs (reviewed retrospectively within 48 hours).
- **LOW impact models:** Automated operation is permitted with retrospective quality assurance review at defined intervals (minimum monthly).

## Approved Deployment Platforms

AI/ML models processing DWP data may only be deployed on approved platforms:

- **DWP Analytical Platform** (AWS-based, managed by DWP Digital)
- **Amazon Bedrock** (for foundation model access, approved under DWP Cloud Security Framework)
- **Amazon SageMaker** (for custom model training and hosting, within DWP-managed AWS accounts)

Deployment on personal devices, unapproved cloud services, or third-party platforms without security accreditation is prohibited. Shadow AI (use of unapproved AI services for DWP work) is a security violation reportable through the DWP Incident Management Process.

## Incident Response for AI Failures

AI-specific incidents must be reported and managed through an extension to the standard DWP Cyber Security Incident Response Process:

- **Detection:** Automated monitoring alerts, user reports of anomalous model behaviour, or identification during quality assurance review.
- **Classification:** AI incidents are classified using the standard severity framework with additional consideration of the number of potentially affected claimants and whether incorrect decisions may have been actioned.
- **Containment:** For HIGH impact models, the default containment action is immediate model suspension (fallback to manual processing) pending investigation. For MEDIUM/LOW, containment may involve output quarantine pending review.
- **Investigation:** Root cause analysis must determine whether the failure was adversarial (external attack), systemic (model degradation, data drift), or operational (infrastructure failure). Different remediations apply to each.
- **Remediation and recovery:** Model retraining, patching, or replacement as appropriate. Affected decisions must be identified and reviewed for potential correction.
- **Reporting:** AI incidents affecting claimant decisions must be reported to the Information Commissioner's Office where they constitute a personal data breach, and to the relevant Parliamentary Select Committee where they affect a significant number of claimants.

## Compliance

Compliance with this policy is mandatory for all DWP staff, contractors, and third-party suppliers involved in AI/ML development or operation. Non-compliance is managed through the DWP Security Governance Framework and may result in access revocation, disciplinary action, or contract termination.

## Document Control

| Field | Value |
|-------|-------|
| Classification | OFFICIAL |
| Owner | Chief Information Security Officer, DWP Digital |
| Version | 2.0 |
| Last reviewed | November 2023 |
| Next review | November 2024 |
| Status | APPROVED |

*This is a synthetic document created for demonstration purposes. It does not represent actual DWP policy.*
