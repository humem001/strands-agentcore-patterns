#!/usr/bin/env python3
"""
Generate synthetic Parquet files from the data manifest.

Reads data/manifest.yaml and produces one Parquet file per table into data/parquet/.
All data is entirely fictional — no real names, national identification numbers, or case references.
"""

import os
import random
import string
from pathlib import Path

import pandas as pd
import yaml
from faker import Faker

# ---------- Setup ----------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
MANIFEST_PATH = SCRIPT_DIR / "manifest.yaml"
OUTPUT_DIR = SCRIPT_DIR / "parquet"

# Seed everything for reproducibility
random.seed(42)
Faker.seed(42)
fake = Faker("en_GB")

# ---------- Domain-specific value lists ----------

SHAP_FEATURES = [
    "payment_gap_days",
    "income_volatility",
    "change_of_circs_count",
    "arrears_balance",
    "employment_status_change",
    "prior_missed_payments",
    "housing_instability",
    "debt_to_income_ratio",
    "age_of_case",
    "enforcement_history",
]

ACTIVITY_TYPES = ["job application", "interview", "training", "CV update", "work trial"]

REFERRAL_SOURCES = ["ML model", "rules engine", "manual"]

FRAUD_TYPES = ["identity", "undeclared income", "living together", "undeclared savings"]

OUTCOMES = ["confirmed", "not_proven", "no_case_to_answer"]

BENEFIT_TYPES = ["UC", "CMS", "Pension Credit"]

COURSE_NAMES = [
    "Safeguarding Fundamentals",
    "Data Protection & GDPR",
    "Fraud Awareness",
    "Unconscious Bias",
    "Customer Service Excellence",
    "Mental Health First Aid",
    "Leadership Essentials",
    "Information Security",
    "Equality & Diversity",
    "Health & Safety at Work",
]

COURSE_CATEGORIES = ["mandatory", "elective", "specialist"]

DIRECTORATES = [
    "Child Maintenance Group",
    "Benefits Programme",
    "Work & Health Services",
    "Counter Fraud & Compliance",
    "Digital Group",
    "People & Capability",
]

CHATBOT_INTENTS = [
    "job_search_help",
    "cv_advice",
    "interview_prep",
    "benefits_query",
    "appointment_booking",
    "training_courses",
    "childcare_support",
    "transport_help",
]

CHATBOT_USER_MESSAGES = [
    "How do I update my CV?",
    "I need help finding jobs near me",
    "What training courses are available?",
    "Can I book an appointment with my work coach?",
    "How do I report a change in circumstances?",
    "I have an interview next week, any tips?",
    "What childcare support is available?",
    "I'm struggling with transport to interviews",
    "How many job applications do I need to make?",
    "Can you help me with my job search plan?",
]

CHATBOT_BOT_RESPONSES = [
    "I can help you with that. Here are some resources for updating your CV...",
    "Let me search for job opportunities in your area...",
    "Here are the training courses currently available through the National Careers Service...",
    "I can help you schedule an appointment. What dates work for you?",
    "To report a change in circumstances, you'll need to update your journal...",
    "Great news about your interview! Here are some preparation tips...",
    "There are several childcare support options available. Let me outline them...",
    "I understand transport can be a barrier. Here are some options...",
    "Your commitment requirements are set by your work coach. Typically...",
    "I'd be happy to help with your job search plan. Let's start with...",
]

JC_REGIONS = [
    "North East",
    "North West",
    "Yorkshire and Humber",
    "East Midlands",
    "West Midlands",
    "East of England",
    "London",
    "South East",
    "South West",
    "Scotland",
    "Wales",
]

SERVICE_LINES = ["CMS", "UC", "Pension Credit", "Fraud"]

METRIC_NAMES = [
    "payment_compliance_rate",
    "average_processing_days",
    "claimant_satisfaction_score",
    "fraud_detection_rate",
    "staff_training_completion",
    "digital_channel_uptake",
    "first_contact_resolution",
    "arrears_collection_rate",
]

RAG_STATUSES = ["Red", "Amber", "Green"]

TRENDS = ["improving", "stable", "declining"]

AWS_RESOURCE_TYPES = [
    "AWS::EC2::Instance",
    "AWS::S3::Bucket",
    "AWS::RDS::DBInstance",
    "AWS::Lambda::Function",
    "AWS::DynamoDB::Table",
    "AWS::ECS::Service",
    "AWS::SQS::Queue",
    "AWS::SNS::Topic",
]

AWS_REGIONS = ["eu-west-2", "eu-west-1", "us-east-1"]

ENVIRONMENTS = ["prod", "staging", "dev"]

OWNING_TEAMS = [
    "Platform Engineering",
    "Data Engineering",
    "Application Support",
    "Security Operations",
    "Networking",
    "Identity & Access",
]

PAYMENT_METHODS = ["Collect & Pay", "Direct Pay"]

COMPLIANCE_STATUSES_CMS = ["on_time", "late", "missed"]

COMPLIANCE_STATUSES_CONFIG = ["COMPLIANT", "NON_COMPLIANT"]


# ---------- Generator helpers ----------


def generate_national_id():
    """Generate a fictional national identification number (e.g. AB123456C)."""
    prefix_letters = "ABCEGHJKLMNPRSTWXYZ"
    suffix_letters = "ABCD"
    first = random.choice(prefix_letters)
    second = random.choice(prefix_letters)
    digits = "".join([str(random.randint(0, 9)) for _ in range(6)])
    suffix = random.choice(suffix_letters)
    return f"{first}{second}{digits}{suffix}"


def generate_sort_code():
    """Generate a bank sort code formatted as XX-XX-XX."""
    digits = "".join([str(random.randint(0, 9)) for _ in range(6)])
    return f"{digits[0:2]}-{digits[2:4]}-{digits[4:6]}"


def generate_account_number():
    """Generate an 8-digit bank account number."""
    return "".join([str(random.randint(0, 9)) for _ in range(8)])


def generate_aws_account_id():
    """Generate a 12-digit AWS account ID."""
    return "".join([str(random.randint(0, 9)) for _ in range(12)])


def generate_resource_name():
    """Generate a plausible AWS resource name."""
    prefixes = ["agency", "cms", "benefits", "platform", "data"]
    suffixes = ["api", "worker", "store", "queue", "cache", "db", "func", "bucket"]
    envs = ["prod", "staging", "dev"]
    return f"{random.choice(prefixes)}-{random.choice(suffixes)}-{random.choice(envs)}"


def generate_journal_entry():
    """Generate a plausible work search journal entry."""
    entries = [
        "Applied for warehouse operative role at local distribution centre",
        "Attended telephone interview for customer service position",
        "Completed online training module on interview techniques",
        "Updated CV with new references from voluntary work",
        "Searched Indeed and Reed for administrative roles within 10 miles",
        "Attended job fair at local community centre",
        "Completed application for retail assistant at supermarket",
        "Had informal chat with manager at local cafe about vacancies",
        "Enrolled in basic IT skills course at library",
        "Applied for three cleaning positions through agency",
        "Practiced interview questions with family member",
        "Registered with two new recruitment agencies",
        "Attended group session on confidence building",
        "Submitted application for driving assessment grant",
        "Completed mandatory online course on workplace rights",
    ]
    return random.choice(entries)


def generate_column_data(col_name, col_type, row_count, table_name):
    """Generate a list of fictional values for a given column."""

    # --- ID columns ---
    if col_name in ("record_id", "journal_id", "calculation_id", "assessment_id",
                    "referral_id", "interaction_id", "session_id", "kpi_id",
                    "resource_id"):
        return [fake.uuid4()[:12] for _ in range(row_count)]

    if col_name in ("case_id", "claimant_id", "staff_id"):
        return [fake.uuid4()[:12] for _ in range(row_count)]

    if col_name.endswith("_id") and col_type == "string":
        return [fake.uuid4()[:12] for _ in range(row_count)]

    # --- National ID Numbers ---
    if col_name in ("nino", "partner_nino"):
        return [generate_national_id() for _ in range(row_count)]

    # --- Names ---
    if col_name in ("full_name", "paying_parent_name", "receiving_parent_name"):
        return [fake.name() for _ in range(row_count)]

    # --- Date of birth ---
    if col_name == "date_of_birth":
        return [fake.date_of_birth(minimum_age=18, maximum_age=80) for _ in range(row_count)]

    # --- Contact info ---
    if col_name == "email":
        return [fake.email() for _ in range(row_count)]

    if col_name == "phone_number":
        return [fake.phone_number() for _ in range(row_count)]

    if col_name == "address":
        return [fake.address().replace("\n", ", ") for _ in range(row_count)]

    if col_name == "postcode":
        return [fake.postcode() for _ in range(row_count)]

    # --- Banking ---
    if col_name == "bank_sort_code":
        return [generate_sort_code() for _ in range(row_count)]

    if col_name == "bank_account_number":
        return [generate_account_number() for _ in range(row_count)]

    # --- Date type columns ---
    if col_type == "date":
        return [fake.date_between(start_date="-2y", end_date="today") for _ in range(row_count)]

    # --- Timestamp type columns ---
    if col_type == "timestamp":
        return [fake.date_time_between(start_date="-1y") for _ in range(row_count)]

    # --- Double type columns ---
    if col_type == "double":
        if "score" in col_name and "percent" not in col_name:
            # Scores between 0 and 1 (risk_score, confidence_score)
            return [round(random.uniform(0.0, 1.0), 4) for _ in range(row_count)]
        if "amount" in col_name or "payment" in col_name or "income" in col_name:
            return [round(random.uniform(50.0, 2000.0), 2) for _ in range(row_count)]
        if "element" in col_name or "allowance" in col_name:
            return [round(random.uniform(0.0, 800.0), 2) for _ in range(row_count)]
        if "savings" in col_name:
            return [round(random.uniform(0.0, 50000.0), 2) for _ in range(row_count)]
        if "weekly" in col_name:
            return [round(random.uniform(50.0, 500.0), 2) for _ in range(row_count)]
        if "target" in col_name:
            return [round(random.uniform(50.0, 99.0), 1) for _ in range(row_count)]
        if "metric" in col_name:
            return [round(random.uniform(10.0, 99.0), 1) for _ in range(row_count)]
        # Default double
        return [round(random.uniform(0.0, 1000.0), 2) for _ in range(row_count)]

    # --- Int type columns ---
    if col_type == "int":
        if "days" in col_name or "duration" in col_name:
            return [random.randint(1, 365) for _ in range(row_count)]
        if "count" in col_name:
            return [random.randint(0, 12) for _ in range(row_count)]
        if "percent" in col_name or "score_percent" in col_name:
            return [random.randint(40, 100) for _ in range(row_count)]
        if "gap" in col_name:
            return [random.randint(0, 180) for _ in range(row_count)]
        # Default int
        return [random.randint(1, 100) for _ in range(row_count)]

    # --- Boolean type columns ---
    if col_type == "boolean":
        return [random.choice([True, False]) for _ in range(row_count)]

    # --- String type columns (domain-specific inference) ---
    if col_type == "string":
        # Payment method
        if col_name == "payment_method":
            return [random.choice(PAYMENT_METHODS) for _ in range(row_count)]

        # Compliance status (context-dependent)
        if col_name == "compliance_status":
            if table_name == "config_resource_inventory":
                return [random.choice(COMPLIANCE_STATUSES_CONFIG) for _ in range(row_count)]
            return [random.choice(COMPLIANCE_STATUSES_CMS) for _ in range(row_count)]

        # Risk category
        if col_name == "risk_category":
            return [random.choice(["HIGH", "MEDIUM", "LOW"]) for _ in range(row_count)]

        # SHAP features
        if col_name in ("top_feature_1", "top_feature_2"):
            return [random.choice(SHAP_FEATURES) for _ in range(row_count)]

        # Journal entry text
        if col_name == "entry_text":
            return [generate_journal_entry() for _ in range(row_count)]

        # Activity type
        if col_name == "activity_type":
            return [random.choice(ACTIVITY_TYPES) for _ in range(row_count)]

        # Fraud-related
        if col_name == "referral_source":
            return [random.choice(REFERRAL_SOURCES) for _ in range(row_count)]

        if col_name == "fraud_type":
            return [random.choice(FRAUD_TYPES) for _ in range(row_count)]

        if col_name == "outcome":
            return [random.choice(OUTCOMES) for _ in range(row_count)]

        if col_name == "benefit_type":
            return [random.choice(BENEFIT_TYPES) for _ in range(row_count)]

        # Training
        if col_name == "course_name":
            return [random.choice(COURSE_NAMES) for _ in range(row_count)]

        if col_name == "course_category":
            return [random.choice(COURSE_CATEGORIES) for _ in range(row_count)]

        if col_name == "directorate":
            return [random.choice(DIRECTORATES) for _ in range(row_count)]

        # Chatbot
        if col_name == "user_message":
            return [random.choice(CHATBOT_USER_MESSAGES) for _ in range(row_count)]

        if col_name == "bot_response":
            return [random.choice(CHATBOT_BOT_RESPONSES) for _ in range(row_count)]

        if col_name == "intent_detected":
            return [random.choice(CHATBOT_INTENTS) for _ in range(row_count)]

        # Region (context-dependent)
        if col_name == "region":
            if table_name == "config_resource_inventory":
                return [random.choice(AWS_REGIONS) for _ in range(row_count)]
            return [random.choice(JC_REGIONS) for _ in range(row_count)]

        # KPIs
        if col_name == "service_line":
            return [random.choice(SERVICE_LINES) for _ in range(row_count)]

        if col_name == "metric_name":
            return [random.choice(METRIC_NAMES) for _ in range(row_count)]

        if col_name == "rag_status":
            return [random.choice(RAG_STATUSES) for _ in range(row_count)]

        if col_name == "trend":
            return [random.choice(TRENDS) for _ in range(row_count)]

        # AWS Config inventory
        if col_name == "resource_type":
            return [random.choice(AWS_RESOURCE_TYPES) for _ in range(row_count)]

        if col_name == "resource_name":
            return [generate_resource_name() for _ in range(row_count)]

        if col_name == "account_id":
            return [generate_aws_account_id() for _ in range(row_count)]

        if col_name == "environment":
            return [random.choice(ENVIRONMENTS) for _ in range(row_count)]

        if col_name == "owning_team":
            return [random.choice(OWNING_TEAMS) for _ in range(row_count)]

        # Default string: generate a short sentence
        return [fake.sentence(nb_words=4) for _ in range(row_count)]

    # Fallback
    return [None] * row_count


# ---------- Main ----------


def main():
    # Load manifest
    with open(MANIFEST_PATH, "r") as f:
        manifest = yaml.safe_load(f)

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tables = manifest.get("tables", [])
    print(f"Generating Parquet files for {len(tables)} tables...")
    print(f"Output directory: {OUTPUT_DIR}\n")

    for table in tables:
        table_name = table["name"]
        row_count = table.get("row_count", 100)
        columns = table.get("columns", [])

        print(f"  Generating {table_name} ({row_count} rows, {len(columns)} columns)...", end=" ")

        # Build data dict
        data = {}
        for col in columns:
            col_name = col["name"]
            col_type = col["type"]
            data[col_name] = generate_column_data(col_name, col_type, row_count, table_name)

        # Create DataFrame and write Parquet
        df = pd.DataFrame(data)
        output_path = OUTPUT_DIR / f"{table_name}.parquet"
        df.to_parquet(output_path, engine="pyarrow", index=False)

        print(f"done -> {output_path.name}")

    print(f"\nComplete. {len(tables)} Parquet files written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

# ---------- Dependencies ----------
# pip install pyyaml pandas pyarrow faker
