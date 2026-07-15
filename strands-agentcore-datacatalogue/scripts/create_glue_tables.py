#!/usr/bin/env python3
"""Create Glue tables directly from the manifest (no Crawler)."""

import argparse
import json
import yaml
import boto3

REGION = "eu-west-2"

TYPE_MAP = {
    "string": "string",
    "int": "int",
    "double": "double",
    "boolean": "boolean",
    "date": "date",
    "timestamp": "timestamp",
}


def load_manifest(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_data_bucket(outputs: dict) -> str:
    for stack_key, stack_outputs in outputs.items():
        for key, val in stack_outputs.items():
            if "DataBucket" in key or "databucket" in key.lower():
                if val.startswith("s3://"):
                    return val.replace("s3://", "").rstrip("/")
                return val
    raise ValueError("Could not find data bucket in CDK outputs")


def create_table(glue, database: str, table: dict, bucket_name: str):
    columns = [
        {"Name": col["name"], "Type": TYPE_MAP.get(col["type"], "string"), "Comment": col.get("description", "")}
        for col in table["columns"]
    ]

    parameters = {
        "description": table["description"],
        "classification": table["classification"],
        "owner": table["owner"],
        "steward": table["steward"],
        "pdu": table["pdu"],
        "lineage_upstream": json.dumps(table["lineage"]["upstream"]),
        "lineage_downstream": json.dumps(table["lineage"]["downstream"]),
        "lineage_transformation": table["lineage"]["transformation"],
    }

    s3_location = f"s3://{bucket_name}/{table['location_suffix']}"

    table_input = {
        "Name": table["name"],
        "Description": table["description"],
        "Parameters": parameters,
        "StorageDescriptor": {
            "Columns": columns,
            "Location": s3_location,
            "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
            "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
            "SerdeInfo": {
                "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe",
            },
        },
        "TableType": "EXTERNAL_TABLE",
    }

    try:
        glue.create_table(DatabaseName=database, TableInput=table_input)
        print(f"  ✓ Created: {table['name']}")
    except glue.exceptions.AlreadyExistsException:
        glue.update_table(DatabaseName=database, TableInput=table_input)
        print(f"  ↻ Updated: {table['name']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="data/manifest.yaml")
    parser.add_argument("--outputs", default="cdk-outputs.json")
    parser.add_argument("--bucket", default=None, help="Override data bucket name")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    database = manifest["database"]

    if args.bucket:
        bucket_name = args.bucket
    else:
        with open(args.outputs) as f:
            outputs = json.load(f)
        bucket_name = get_data_bucket(outputs)

    glue = boto3.client("glue", region_name=REGION)

    print(f"Creating {len(manifest['tables'])} tables in database '{database}'...")
    for table in manifest["tables"]:
        create_table(glue, database, table, bucket_name)

    print(f"\nDone. {len(manifest['tables'])} tables created/updated.")


if __name__ == "__main__":
    main()
