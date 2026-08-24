#!/bin/bash
set -euo pipefail

REGION="eu-west-2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  Data Intelligence Agent — Teardown"
echo "  Region: $REGION"
echo "============================================"
echo ""

# --- Step 1: AgentCore teardown ---
echo "[1/4] Destroying AgentCore (Runtime + Gateway + Identity)..."
agentcore destroy --force 2>/dev/null || echo "  (agentcore destroy skipped or already removed)"
echo ""

# --- Step 2: Empty S3 buckets ---
echo "[2/4] Emptying S3 buckets..."
if [ -f cdk-outputs.json ]; then
    DATA_BUCKET=$(python -c "
import json
with open('cdk-outputs.json') as f:
    outputs = json.load(f)
for stack in outputs.values():
    for k, v in stack.items():
        if 'DataBucket' in k or 'databucket' in k.lower():
            print(v); break
    else: continue
    break
" 2>/dev/null || echo "")

    KB_BUCKET=$(python -c "
import json
with open('cdk-outputs.json') as f:
    outputs = json.load(f)
for stack in outputs.values():
    for k, v in stack.items():
        if 'KbSource' in k or 'kbsource' in k.lower():
            print(v); break
    else: continue
    break
" 2>/dev/null || echo "")

    ATHENA_BUCKET=$(python -c "
import json
with open('cdk-outputs.json') as f:
    outputs = json.load(f)
for stack in outputs.values():
    for k, v in stack.items():
        if 'AthenaResults' in k or 'athenaresults' in k.lower():
            print(v); break
    else: continue
    break
" 2>/dev/null || echo "")

    for bucket in $DATA_BUCKET $KB_BUCKET $ATHENA_BUCKET; do
        if [ -n "$bucket" ]; then
            echo "  Emptying s3://$bucket..."
            aws s3 rm "s3://$bucket" --recursive --region $REGION 2>/dev/null || true
        fi
    done
else
    echo "  (No cdk-outputs.json found — skipping bucket cleanup)"
fi
echo ""

# --- Step 3: Delete SageMaker assets ---
echo "[3/4] Cleaning up SageMaker assets..."
for group in cms-compliance-predictor-v3 fraud-detection-v1 claimant-embedding-model; do
    # Delete all model packages in the group first
    PACKAGES=$(aws sagemaker list-model-packages --model-package-group-name "$group" --region $REGION --query "ModelPackageSummaryList[].ModelPackageArn" --output text 2>/dev/null || echo "")
    for pkg in $PACKAGES; do
        aws sagemaker delete-model-package --model-package-name "$pkg" --region $REGION 2>/dev/null || true
    done
    aws sagemaker delete-model-package-group --model-package-group-name "$group" --region $REGION 2>/dev/null || true
done
aws sagemaker delete-feature-group --feature-group-name "cms-payment-features" --region $REGION 2>/dev/null || true
echo "  ✓ SageMaker assets removed"
echo ""

# --- Step 4: CDK destroy ---
echo "[4/4] Destroying CDK stacks..."
cd infra
cdk destroy --all --force
cd ..
echo ""

# Cleanup
rm -f cdk-outputs.json

echo "============================================"
echo "  ✅ All resources destroyed."
echo "  Account should have zero ongoing charges."
echo "============================================"
