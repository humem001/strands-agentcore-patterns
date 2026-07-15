#!/usr/bin/env python3
"""Trigger Bedrock KB sync and wait for completion."""

import argparse
import json
import time
import boto3

REGION = "eu-west-2"
MAX_WAIT_SECONDS = 300
POLL_INTERVAL = 10


def get_kb_details(outputs: dict) -> tuple:
    kb_id = None
    ds_id = None
    for stack_outputs in outputs.values():
        for key, val in stack_outputs.items():
            if "KbId" in key or "kbid" in key.lower():
                kb_id = val
            if "DataSourceId" in key or "datasourceid" in key.lower():
                ds_id = val
    if not kb_id or not ds_id:
        raise ValueError(f"Could not find KB ID ({kb_id}) or DataSource ID ({ds_id}) in CDK outputs")
    return kb_id, ds_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outputs", default="cdk-outputs.json")
    parser.add_argument("--kb-id", default=None)
    parser.add_argument("--datasource-id", default=None)
    args = parser.parse_args()

    if args.kb_id and args.datasource_id:
        kb_id, ds_id = args.kb_id, args.datasource_id
    else:
        with open(args.outputs) as f:
            outputs = json.load(f)
        kb_id, ds_id = get_kb_details(outputs)

    client = boto3.client("bedrock-agent", region_name=REGION)

    print(f"Starting ingestion job for KB={kb_id}, DataSource={ds_id}...")
    response = client.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=ds_id,
    )
    job_id = response["ingestionJob"]["ingestionJobId"]
    print(f"  Job ID: {job_id}")

    elapsed = 0
    while elapsed < MAX_WAIT_SECONDS:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

        status_response = client.get_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
            ingestionJobId=job_id,
        )
        status = status_response["ingestionJob"]["status"]
        print(f"  [{elapsed}s] Status: {status}")

        if status == "COMPLETE":
            stats = status_response["ingestionJob"].get("statistics", {})
            print(f"  ✓ Sync complete. Documents: {stats}")
            return
        elif status in ("FAILED", "STOPPED"):
            reason = status_response["ingestionJob"].get("failureReasons", ["Unknown"])
            print(f"  ✗ Sync failed: {reason}")
            raise RuntimeError(f"KB sync failed: {reason}")

    raise TimeoutError(f"KB sync did not complete within {MAX_WAIT_SECONDS}s")


if __name__ == "__main__":
    main()
