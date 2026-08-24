#!/bin/bash
set -euo pipefail

REGION="eu-west-2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  Data Intelligence Agent — Setup"
echo "  Region: $REGION"
echo "============================================"
echo ""

# --- Step 0: Pre-build checks ---
echo "[1/9] Pre-build checks..."
echo "  Checking Bedrock model access..."
aws bedrock get-foundation-model --model-identifier anthropic.claude-sonnet-4-6 --region $REGION > /dev/null 2>&1 \
  && echo "  ✓ Claude Sonnet accessible" \
  || { echo "  ✗ Claude Sonnet not accessible — enable in Bedrock console"; exit 1; }

aws bedrock get-foundation-model --model-identifier amazon.titan-embed-text-v2:0 --region $REGION > /dev/null 2>&1 \
  && echo "  ✓ Titan Embeddings V2 accessible" \
  || { echo "  ✗ Titan Embeddings V2 not accessible — enable in Bedrock console"; exit 1; }

echo ""

# --- Step 1: CDK deploy ---
echo "[2/9] Deploying CDK infrastructure..."
cd infra
pip install -r requirements.txt -q
cdk deploy --all --require-approval never --outputs-file ../cdk-outputs.json
cd ..
echo "  ✓ CDK stacks deployed"
echo ""

# --- Step 2: Generate and upload Parquet data ---
echo "[3/9] Generating synthetic data..."
pip install pyyaml pandas pyarrow faker -q
python data/generate_parquet.py
echo ""

echo "[4/9] Uploading data to S3..."
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
")
aws s3 sync data/parquet/ "s3://$DATA_BUCKET/" --region $REGION
echo "  ✓ Parquet data uploaded"
echo ""

# --- Step 3: Create Glue tables ---
echo "[5/9] Creating Glue tables..."
python scripts/create_glue_tables.py --manifest data/manifest.yaml --outputs cdk-outputs.json
echo ""

# --- Step 4: Register ML assets ---
echo "[6/9] Registering SageMaker assets..."
python scripts/register_ml_assets.py --outputs cdk-outputs.json
echo ""

# --- Step 5: Upload governance docs and sync KB ---
echo "[7/9] Uploading governance docs and syncing Knowledge Base..."
KB_SOURCE_BUCKET=$(python -c "
import json
with open('cdk-outputs.json') as f:
    outputs = json.load(f)
for stack in outputs.values():
    for k, v in stack.items():
        if 'KbSource' in k or 'kbsource' in k.lower():
            print(v); break
    else: continue
    break
")
aws s3 sync data/governance_docs/ "s3://$KB_SOURCE_BUCKET/" --region $REGION
python scripts/sync_knowledge_base.py --outputs cdk-outputs.json
echo ""

# --- Step 6: Populate agentcore.json ---
echo "[8/9] Configuring AgentCore..."
python scripts/populate_agentcore_json.py --outputs cdk-outputs.json
echo ""

# --- Step 7: Deploy AgentCore (Runtime + Gateway + Identity) ---
echo "[9/9] Deploying AgentCore Runtime + Gateway..."
agentcore deploy
echo ""

echo "============================================"
echo "  ✅ Deployment complete!"
echo ""
echo "  To run the frontend:"
echo "    cd frontend"
echo "    pip install -r requirements.txt"
echo "    export COGNITO_CLIENT_ID=<from cdk-outputs.json>"
echo "    export COGNITO_CLIENT_SECRET=<from cdk-outputs.json>"
echo "    export COGNITO_TOKEN_ENDPOINT=<from cdk-outputs.json>"
echo "    export AGENT_RUNTIME_ARN=<from agentcore status>"
echo "    streamlit run app.py"
echo "============================================"
