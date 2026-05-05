#!/usr/bin/env bash
# =============================================================================
# deploy.sh — One-command deploy for strands-agentcore-mcp
#
# Usage:
#   ./scripts/deploy.sh
#
# What it does (in order):
#   1. Validate the CloudFormation template
#   2. Package Agent Lambda (two-step pip3 install)
#   3. Package MCP Server Lambda (two-step pip3 install)
#   4. Create or update the CloudFormation stack
#   5. Update Lambda function code (direct upload or S3 fallback)
#   6. Seed DynamoDB with sample products
#   7. Create Cognito test user
#   8. Generate scripts/test.sh with baked-in deployment values
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REGION="us-east-1"
STACK_NAME="agentcore-mcp"
TEMPLATE_FILE="infrastructure/cloudformation-template.yaml"

# Bedrock model ID — change this to swap models without any code changes.
# Must be a valid Bedrock cross-region inference profile or foundation model ARN.
BEDROCK_MODEL_ID="us.anthropic.claude-sonnet-4-5-20250929-v1:0"

# Test user credentials (baked into generated test.sh)
TEST_USERNAME="testuser"
TEST_PASSWORD="TestPass123!"
TEST_EMAIL="testuser@example.com"

# PID-based temp files — macOS-compatible (no mktemp suffix templates)
BUILD_DIR="/tmp/agentcore-mcp.$$.build"
TMP_AGENT_ZIP="/tmp/agentcore-mcp.$$.agent.zip"
TMP_MCP_ZIP="/tmp/agentcore-mcp.$$.mcp.zip"
TMP_STACK_OUTPUT="/tmp/agentcore-mcp.$$.stack-output.json"
TMP_DESCRIBE_ERR="/tmp/agentcore-mcp.$$.describe-err.txt"
TMP_UPDATE_ERR="/tmp/agentcore-mcp.$$.update-err.txt"

# ---------------------------------------------------------------------------
# Cleanup trap — runs on exit (success or failure)
# ---------------------------------------------------------------------------
cleanup() {
  rm -rf \
    "$BUILD_DIR" \
    "$TMP_AGENT_ZIP" \
    "$TMP_MCP_ZIP" \
    "$TMP_STACK_OUTPUT" \
    "$TMP_DESCRIBE_ERR" \
    "$TMP_UPDATE_ERR" \
    2>/dev/null || true
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() { echo "[deploy] $*"; }
die() { echo "[deploy] ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# STEP 1: Validate CloudFormation template
# This MUST run before any other AWS CLI call (Requirement 13.1, 13.5)
# ---------------------------------------------------------------------------
log "Step 1: Validating CloudFormation template..."
aws cloudformation validate-template \
  --template-body "file://${TEMPLATE_FILE}" \
  --region "$REGION" \
  > /dev/null
log "Template validation passed."

# ---------------------------------------------------------------------------
# STEP 2 & 3: Package Lambda functions
#
# Two-step pip3 install (Requirement 11.1, 11.2, 11.3):
#   Step A: binary packages via --only-binary=:all: against requirements.txt
#   Step B: pure-Python packages via --only-binary=:all: --no-deps
#
# Rules:
#   - Use pip3, never pip (Requirement 13.4)
#   - Preserve src/ prefix inside zip (Requirement 11.4)
#   - Never delete .dist-info directories (Requirement 11.3)
#   - If zip > 50 MB, upload to S3 (Requirement 11.5)
# ---------------------------------------------------------------------------

package_lambda() {
  # Usage: package_lambda <build_dir> <output_zip>
  local DIR="$1"
  local OUT_ZIP="$2"

  log "  Packaging into $OUT_ZIP ..."

  # Step A: binary packages from requirements.txt
  pip3 install \
    --target "$DIR" \
    --platform manylinux2014_x86_64 \
    --python-version 3.12 \
    --only-binary=:all: \
    -r requirements.txt \
    --quiet

  # Step B: pure-Python packages skipped by --only-binary in step A
  # --no-deps prevents pulling in transitive binary deps again
  pip3 install \
    --target "$DIR" \
    --platform manylinux2014_x86_64 \
    --python-version 3.12 \
    --only-binary=:all: \
    --no-deps \
    requests urllib3 charset-normalizer idna certifi PyJWT cryptography cffi mcp \
    --quiet

  # Copy src/ tree preserving the src/ prefix so handler paths resolve
  cp -r src/ "$DIR/src/"

  # Zip everything — do NOT remove .dist-info directories
  (cd "$DIR" && zip -qr "$OUT_ZIP" .)

  log "  Packaged: $OUT_ZIP ($(du -sh "$OUT_ZIP" | cut -f1))"
}

log "Step 2: Packaging Agent Lambda..."
mkdir -p "$BUILD_DIR"
package_lambda "$BUILD_DIR" "$TMP_AGENT_ZIP"

# MCP Server Lambda shares the same dependency set and src/ tree.
# Both Lambdas need the full src/ tree (agent imports shared, mcp_server imports shared).
# We reuse the same build dir content and produce a separate zip.
log "Step 3: Packaging MCP Server Lambda..."
package_lambda "$BUILD_DIR" "$TMP_MCP_ZIP"

# ---------------------------------------------------------------------------
# STEP 4: Create or update the CloudFormation stack
#
# Decision logic (Requirement 13.2, 13.3):
#   - Case-insensitive match against DOES_NOT_EXIST → create
#   - ROLLBACK_COMPLETE → delete + wait, then create
#   - Otherwise → update (tolerate "No updates are to be performed")
# ---------------------------------------------------------------------------
log "Step 4: Deploying CloudFormation stack '$STACK_NAME'..."

STACK_ACTION="update"

# Capture both stdout and stderr from describe-stacks
if ! aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    > "$TMP_STACK_OUTPUT" \
    2> "$TMP_DESCRIBE_ERR"; then

  # Case-insensitive match for DOES_NOT_EXIST (Requirement 13.2)
  if grep -qi "DOES_NOT_EXIST" "$TMP_DESCRIBE_ERR" || grep -qi "does not exist" "$TMP_DESCRIBE_ERR"; then
    STACK_ACTION="create"
  else
    # Unexpected error — surface it
    cat "$TMP_DESCRIBE_ERR" >&2
    die "Unexpected error describing stack '$STACK_NAME'"
  fi
else
  # Stack exists — check for ROLLBACK_COMPLETE (Requirement 13.3)
  STACK_STATUS=$(python3 -c "
import json, sys
data = json.load(open('$TMP_STACK_OUTPUT'))
print(data['Stacks'][0]['StackStatus'])
")
  if [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ]; then
    log "  Stack is in ROLLBACK_COMPLETE — deleting before recreating..."
    aws cloudformation delete-stack \
      --stack-name "$STACK_NAME" \
      --region "$REGION"
    aws cloudformation wait stack-delete-complete \
      --stack-name "$STACK_NAME" \
      --region "$REGION"
    log "  Stack deleted. Will create fresh."
    STACK_ACTION="create"
  fi
fi

if [ "$STACK_ACTION" = "create" ]; then
  log "  Creating stack '$STACK_NAME'..."
  aws cloudformation create-stack \
    --stack-name "$STACK_NAME" \
    --template-body "file://${TEMPLATE_FILE}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameters "ParameterKey=BedrockModelId,ParameterValue=${BEDROCK_MODEL_ID}" \
    --region "$REGION"
  log "  Waiting for stack creation to complete..."
  aws cloudformation wait stack-create-complete \
    --stack-name "$STACK_NAME" \
    --region "$REGION"
  log "  Stack created successfully."
else
  log "  Updating stack '$STACK_NAME'..."
  if ! aws cloudformation update-stack \
      --stack-name "$STACK_NAME" \
      --template-body "file://${TEMPLATE_FILE}" \
      --capabilities CAPABILITY_NAMED_IAM \
      --parameters "ParameterKey=BedrockModelId,ParameterValue=${BEDROCK_MODEL_ID}" \
      --region "$REGION" \
      2> "$TMP_UPDATE_ERR"; then

    # Tolerate "No updates are to be performed" (Requirement 13.2)
    if grep -q "No updates are to be performed" "$TMP_UPDATE_ERR"; then
      log "  No stack changes detected — skipping update."
    else
      cat "$TMP_UPDATE_ERR" >&2
      die "Stack update failed for '$STACK_NAME'"
    fi
  else
    log "  Waiting for stack update to complete..."
    aws cloudformation wait stack-update-complete \
      --stack-name "$STACK_NAME" \
      --region "$REGION"
    log "  Stack updated successfully."
  fi
fi

# ---------------------------------------------------------------------------
# Read stack outputs
# ---------------------------------------------------------------------------
log "Reading stack outputs..."
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  > "$TMP_STACK_OUTPUT"

# Parse outputs into shell variables.
# Write the Python script to a temp file to avoid shell brace-expansion issues
# with dict comprehensions inside eval "$(...)".
TMP_PARSE_PY="/tmp/agentcore-mcp.$$.parse.py"
cat > "$TMP_PARSE_PY" << 'PYEOF'
import json, sys

data = json.load(open(sys.argv[1]))
outputs = {}
for o in data['Stacks'][0].get('Outputs', []):
    outputs[o['OutputKey']] = o['OutputValue']

keys = [
    'AgentLambdaName',
    'McpServerLambdaName',
    'CognitoUserPoolId',
    'CognitoClientId',
    'McpApiInvokeUrl',
    'GatewayUrl',
    'ProductTableName',
]
for k in keys:
    v = outputs.get(k, '')
    v_escaped = v.replace("'", "'\\''")
    print(f"{k}='{v_escaped}'")
PYEOF

eval "$(python3 "$TMP_PARSE_PY" "$TMP_STACK_OUTPUT")"
rm -f "$TMP_PARSE_PY"

log "  AgentLambdaName:     $AgentLambdaName"
log "  McpServerLambdaName: $McpServerLambdaName"
log "  CognitoUserPoolId:   $CognitoUserPoolId"
log "  CognitoClientId:     $CognitoClientId"
log "  McpApiInvokeUrl:     $McpApiInvokeUrl"
log "  GatewayUrl:          $GatewayUrl"
log "  ProductTableName:    $ProductTableName"

# ---------------------------------------------------------------------------
# STEP 5: Update Lambda function code (Requirement 11.5)
#
# If zip ≤ 50 MB: direct upload via --zip-file fileb://
# If zip > 50 MB: upload to S3 first, then deploy via --s3-bucket / --s3-key
# ---------------------------------------------------------------------------

update_lambda_code() {
  # Usage: update_lambda_code <function_name> <zip_path>
  local FUNC_NAME="$1"
  local ZIP_PATH="$2"

  # Get zip size in bytes (macOS-compatible stat)
  local ZIP_SIZE
  ZIP_SIZE=$(stat -f%z "$ZIP_PATH" 2>/dev/null || stat -c%s "$ZIP_PATH")
  local MAX_DIRECT_BYTES=$((50 * 1024 * 1024))  # 50 MB

  if [ "$ZIP_SIZE" -le "$MAX_DIRECT_BYTES" ]; then
    log "  Uploading $ZIP_PATH directly ($(( ZIP_SIZE / 1024 / 1024 )) MB)..."
    aws lambda update-function-code \
      --function-name "$FUNC_NAME" \
      --zip-file "fileb://${ZIP_PATH}" \
      --region "$REGION" \
      > /dev/null
  else
    # S3 fallback — derive bucket name from account id + stack name
    local ACCOUNT_ID
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$REGION")
    local S3_BUCKET="${ACCOUNT_ID}-${STACK_NAME}-deploy"
    local S3_KEY="lambda/$(basename "$ZIP_PATH")"

    log "  Zip exceeds 50 MB — uploading to s3://${S3_BUCKET}/${S3_KEY}..."

    # Create bucket if it doesn't exist
    if ! aws s3api head-bucket --bucket "$S3_BUCKET" --region "$REGION" 2>/dev/null; then
      log "  Creating S3 bucket $S3_BUCKET..."
      if [ "$REGION" = "us-east-1" ]; then
        aws s3api create-bucket \
          --bucket "$S3_BUCKET" \
          --region "$REGION" \
          > /dev/null
      else
        aws s3api create-bucket \
          --bucket "$S3_BUCKET" \
          --region "$REGION" \
          --create-bucket-configuration "LocationConstraint=${REGION}" \
          > /dev/null
      fi
    fi

    aws s3 cp "$ZIP_PATH" "s3://${S3_BUCKET}/${S3_KEY}" --region "$REGION"

    aws lambda update-function-code \
      --function-name "$FUNC_NAME" \
      --s3-bucket "$S3_BUCKET" \
      --s3-key "$S3_KEY" \
      --region "$REGION" \
      > /dev/null
  fi

  log "  Waiting for function update to complete..."
  aws lambda wait function-updated \
    --function-name "$FUNC_NAME" \
    --region "$REGION"
  log "  $FUNC_NAME updated."
}

log "Step 5: Updating Lambda function code..."
update_lambda_code "$AgentLambdaName" "$TMP_AGENT_ZIP"
update_lambda_code "$McpServerLambdaName" "$TMP_MCP_ZIP"

# ---------------------------------------------------------------------------
# STEP 5b: Create or update the AgentCore MCP Target
#
# McpTarget is NOT in the CloudFormation template because AgentCore probes
# tools/list during target creation — the placeholder Lambda would return a
# non-MCP response causing a Forbidden error. We create it here after the
# real Lambda code is deployed.
#
# We use the AWS CLI (bedrock-agentcore-control) to create/update the target.
# ---------------------------------------------------------------------------
log "Step 5b: Creating/updating AgentCore MCP Target..."

GATEWAY_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='GatewayId'].OutputValue" \
  --output text 2>/dev/null || echo "")

# If GatewayId output not present, derive from GatewayUrl
if [ -z "$GATEWAY_ID" ] || [ "$GATEWAY_ID" = "None" ]; then
  # GatewayUrl format: https://<gateway-id>.gateway.bedrock-agentcore.<region>.amazonaws.com
  GATEWAY_ID=$(echo "$GatewayUrl" | python3 -c "
import sys
url = sys.stdin.read().strip()
# Extract the subdomain part before .gateway.
part = url.replace('https://', '').split('.')[0]
print(part)
")
fi

log "  Gateway ID: $GATEWAY_ID"
log "  MCP Endpoint: $McpApiInvokeUrl"

MCP_ENDPOINT="$McpApiInvokeUrl"
TMP_TARGET_OUTPUT="/tmp/agentcore-mcp.$$.target-output.json"

# Check if target already exists
EXISTING_TARGET_ID=$(aws bedrock-agentcore-control list-gateway-targets \
  --gateway-identifier "$GATEWAY_ID" \
  --region "$REGION" \
  --query "items[?name=='mcp-server-target'].targetId" \
  --output text 2>/dev/null || echo "")

if [ -z "$EXISTING_TARGET_ID" ] || [ "$EXISTING_TARGET_ID" = "None" ]; then
  log "  Creating new MCP target..."
  # Use boto3 directly — the AWS CLI's local schema validation rejects
  # iamCredentialProvider even though the service requires it for mcpServer targets.
  TMP_TARGET_PY="/tmp/agentcore-mcp.$$.target.py"
  cat > "$TMP_TARGET_PY" << PYEOF
import boto3, sys, json

client = boto3.client('bedrock-agentcore-control', region_name=sys.argv[1])
resp = client.create_gateway_target(
    gatewayIdentifier=sys.argv[2],
    name='mcp-server-target',
    description='MCP target pointing at the API Gateway HTTPS endpoint',
    credentialProviderConfigurations=[{
        'credentialProviderType': 'GATEWAY_IAM_ROLE',
        'credentialProvider': {
            'iamCredentialProvider': {
                'service': 'execute-api'
            }
        }
    }],
    targetConfiguration={
        'mcp': {
            'mcpServer': {
                'endpoint': sys.argv[3]
            }
        }
    }
)
print(json.dumps({'targetId': resp.get('targetId', '')}))
PYEOF
  python3 "$TMP_TARGET_PY" "$REGION" "$GATEWAY_ID" "$MCP_ENDPOINT" > "$TMP_TARGET_OUTPUT"
  rm -f "$TMP_TARGET_PY"
  TARGET_ID=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('targetId',''))" "$TMP_TARGET_OUTPUT")
  log "  MCP target created (targetId: $TARGET_ID)."
else
  log "  Updating existing MCP target ($EXISTING_TARGET_ID)..."
  TMP_TARGET_PY="/tmp/agentcore-mcp.$$.target.py"
  cat > "$TMP_TARGET_PY" << PYEOF
import boto3, sys, json

client = boto3.client('bedrock-agentcore-control', region_name=sys.argv[1])
resp = client.update_gateway_target(
    gatewayIdentifier=sys.argv[2],
    targetId=sys.argv[3],
    name='mcp-server-target',
    description='MCP target pointing at the API Gateway HTTPS endpoint',
    credentialProviderConfigurations=[{
        'credentialProviderType': 'GATEWAY_IAM_ROLE',
        'credentialProvider': {
            'iamCredentialProvider': {
                'service': 'execute-api'
            }
        }
    }],
    targetConfiguration={
        'mcp': {
            'mcpServer': {
                'endpoint': sys.argv[4]
            }
        }
    }
)
print(json.dumps({'targetId': resp.get('targetId', '')}))
PYEOF
  python3 "$TMP_TARGET_PY" "$REGION" "$GATEWAY_ID" "$EXISTING_TARGET_ID" "$MCP_ENDPOINT" > "$TMP_TARGET_OUTPUT"
  rm -f "$TMP_TARGET_PY"
  TARGET_ID="$EXISTING_TARGET_ID"
  log "  MCP target updated."
fi

# Synchronize the target so the gateway indexes the tools from the MCP server.
# Without this, tools/list returns 0 tools and the agent has nothing to call.
log "  Synchronizing MCP target to index tools..."
TMP_SYNC_PY="/tmp/agentcore-mcp.$$.sync.py"
cat > "$TMP_SYNC_PY" << PYEOF
import boto3, sys, json, time

client = boto3.client('bedrock-agentcore-control', region_name=sys.argv[1])
gateway_id = sys.argv[2]
target_id = sys.argv[3]

# Wait for target to reach a stable state before synchronizing
print("  Waiting for target to reach stable state...", flush=True)
for _ in range(36):  # up to 3 minutes
    resp = client.get_gateway_target(
        gatewayIdentifier=gateway_id,
        targetId=target_id
    )
    status = resp.get('status', '')
    print(f"  Target status: {status}", flush=True)
    if status not in ('CREATING', 'UPDATING', 'SYNCHRONIZING'):
        break
    time.sleep(5)

# Trigger synchronization
print("  Triggering synchronization...", flush=True)
client.synchronize_gateway_targets(
    gatewayIdentifier=gateway_id,
    targetIdList=[target_id]
)

# Poll until sync completes
for _ in range(36):  # up to 3 minutes
    resp = client.get_gateway_target(
        gatewayIdentifier=gateway_id,
        targetId=target_id
    )
    status = resp.get('status', '')
    reasons = resp.get('statusReasons', [])
    print(f"  Target status: {status}", flush=True)
    if status not in ('SYNCHRONIZING', 'CREATING', 'UPDATING'):
        if reasons:
            print(f"  Status reasons: {reasons}", flush=True)
        break
    time.sleep(5)

print(f"Final status: {status}")
PYEOF
python3 "$TMP_SYNC_PY" "$REGION" "$GATEWAY_ID" "$TARGET_ID"
rm -f "$TMP_SYNC_PY"
log "  MCP target synchronized."

rm -f "$TMP_TARGET_OUTPUT"

# ---------------------------------------------------------------------------
# STEP 6: Seed DynamoDB with sample products (Requirement 10.3)
#
# At least three items across at least two categories.
# DynamoDB attribute-value JSON format.
# ---------------------------------------------------------------------------
log "Step 6: Seeding DynamoDB table '$ProductTableName'..."

aws dynamodb put-item \
  --table-name "$ProductTableName" \
  --item '{
    "category":  {"S": "Electronics"},
    "productId": {"S": "ELEC-001"},
    "name":      {"S": "Noise-cancelling Headphones"},
    "price":     {"N": "199.99"}
  }' \
  --region "$REGION"

aws dynamodb put-item \
  --table-name "$ProductTableName" \
  --item '{
    "category":  {"S": "Electronics"},
    "productId": {"S": "ELEC-002"},
    "name":      {"S": "Wireless Keyboard"},
    "price":     {"N": "79.99"}
  }' \
  --region "$REGION"

aws dynamodb put-item \
  --table-name "$ProductTableName" \
  --item '{
    "category":  {"S": "Books"},
    "productId": {"S": "BOOK-001"},
    "name":      {"S": "Clean Code"},
    "price":     {"N": "34.99"}
  }' \
  --region "$REGION"

log "  Seeded 3 products (Electronics x2, Books x1)."

# ---------------------------------------------------------------------------
# STEP 7: Create Cognito test user (Requirement 1.2)
# ---------------------------------------------------------------------------
log "Step 7: Creating Cognito test user '$TEST_USERNAME'..."

# Create user (suppress welcome email)
aws cognito-idp admin-create-user \
  --user-pool-id "$CognitoUserPoolId" \
  --username "$TEST_USERNAME" \
  --user-attributes "Name=email,Value=${TEST_EMAIL}" \
  --message-action SUPPRESS \
  --region "$REGION" \
  > /dev/null 2>&1 || log "  User '$TEST_USERNAME' already exists — skipping create."

# Set permanent password (confirms the user)
aws cognito-idp admin-set-user-password \
  --user-pool-id "$CognitoUserPoolId" \
  --username "$TEST_USERNAME" \
  --password "$TEST_PASSWORD" \
  --permanent \
  --region "$REGION"

log "  Test user '$TEST_USERNAME' is CONFIRMED."

# ---------------------------------------------------------------------------
# STEP 8: Generate scripts/test.sh with baked-in literal values
#
# Rules (Requirement 13.6, 13.7):
#   - Use a heredoc + sed substitution (NOT nested echo emitting JSON)
#   - Bake in USER_POOL_ID, CLIENT_ID, AGENT_LAMBDA_NAME, USERNAME, PASSWORD
#   - Accept $1 as optional prompt, fall back to DEFAULT_PROMPT
#   - Obtain ID token via initiate-auth USER_PASSWORD_AUTH
#   - Invoke Agent Lambda with {"jwt": "<id_token>", "prompt": "<prompt>"}
#   - Print the model's final answer
# ---------------------------------------------------------------------------
log "Step 8: Generating scripts/test.sh..."

# Write the template with placeholder tokens
cat > scripts/test.sh <<'EOF'
#!/usr/bin/env bash
# =============================================================================
# test.sh — End-to-end smoke test for strands-agentcore-mcp
#
# Generated by deploy.sh — do not edit manually.
#
# Usage:
#   ./scripts/test.sh                                      # default prompt
#   ./scripts/test.sh 'List all products in Electronics'
#   ./scripts/test.sh 'Get product ELEC-001 details'
#   ./scripts/test.sh 'Add a new product called Widget'
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Baked-in deployment values (substituted by deploy.sh)
# ---------------------------------------------------------------------------
USER_POOL_ID="__USER_POOL_ID__"
CLIENT_ID="__CLIENT_ID__"
AGENT_LAMBDA_NAME="__AGENT_LAMBDA_NAME__"
USERNAME="__USERNAME__"
PASSWORD="__PASSWORD__"
DEFAULT_PROMPT="List all products."
REGION="us-east-1"

# ---------------------------------------------------------------------------
# Accept optional prompt argument
# ---------------------------------------------------------------------------
PROMPT="${1:-$DEFAULT_PROMPT}"

echo "[test] Authenticating as '$USERNAME'..."

# ---------------------------------------------------------------------------
# Obtain ID token via USER_PASSWORD_AUTH
# ---------------------------------------------------------------------------
AUTH_RESULT=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id "$CLIENT_ID" \
  --auth-parameters "USERNAME=${USERNAME},PASSWORD=${PASSWORD}" \
  --region "$REGION" \
  --output json)

ID_TOKEN=$(echo "$AUTH_RESULT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data['AuthenticationResult']['IdToken'])
")

echo "[test] Authenticated. Invoking agent with prompt: $PROMPT"

# ---------------------------------------------------------------------------
# Invoke Agent Lambda
# Payload written to a temp file to avoid shell quoting / JSON injection issues
# ---------------------------------------------------------------------------
TMP_PAYLOAD="/tmp/test-payload.$$.json"
TMP_RESPONSE="/tmp/test-response.$$.json"
trap 'rm -f "$TMP_PAYLOAD" "$TMP_RESPONSE"' EXIT

python3 -c "
import json, sys
payload = {'jwt': sys.argv[1], 'prompt': sys.argv[2]}
print(json.dumps(payload))
" "$ID_TOKEN" "$PROMPT" > "$TMP_PAYLOAD"

aws lambda invoke \
  --function-name "$AGENT_LAMBDA_NAME" \
  --payload "fileb://${TMP_PAYLOAD}" \
  --region "$REGION" \
  --cli-binary-format raw-in-base64-out \
  "$TMP_RESPONSE" \
  > /dev/null

echo ""
echo "=== Agent Response ==="
python3 -c "
import json, sys
data = json.load(open(sys.argv[1]))
# AgentResponse dataclass: {success, response, error}
if isinstance(data, dict) and 'response' in data:
    print(data['response'])
else:
    print(json.dumps(data, indent=2))
" "$TMP_RESPONSE"
EOF

# Substitute placeholder tokens with actual deployment values using sed
# (literal string substitution — no nested echo emitting JSON)
sed -i.bak \
  -e "s|__USER_POOL_ID__|${CognitoUserPoolId}|g" \
  -e "s|__CLIENT_ID__|${CognitoClientId}|g" \
  -e "s|__AGENT_LAMBDA_NAME__|${AgentLambdaName}|g" \
  -e "s|__USERNAME__|${TEST_USERNAME}|g" \
  -e "s|__PASSWORD__|${TEST_PASSWORD}|g" \
  scripts/test.sh

# Remove sed backup file
rm -f scripts/test.sh.bak

chmod +x scripts/test.sh
log "  Generated scripts/test.sh"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log ""
log "============================================================"
log "Deployment complete!"
log "============================================================"
log ""
log "Run the smoke test:"
log "  ./scripts/test.sh"
log ""
log "Or with a custom prompt:"
log "  ./scripts/test.sh 'List all products in Electronics'"
log "  ./scripts/test.sh 'Get product ELEC-001 details'"
log ""
