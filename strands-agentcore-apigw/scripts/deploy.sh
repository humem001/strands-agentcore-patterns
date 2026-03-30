#!/usr/bin/env bash
# =============================================================================
# AgentCore API Gateway Weather Agent — Deployment Script
#
# Deploys the full stack in the correct order, handling resources that cannot
# be created via CloudFormation (credential provider).
#
# Usage:
#   ./scripts/deploy.sh \
#     --environment-name dev \
#     --weather-api-key YOUR_WEATHERAPI_KEY \
#     --region us-east-1 \
#     --s3-bucket my-deploy-bucket
# =============================================================================
set -e

# -------------------------------------------------------
# Defaults
# -------------------------------------------------------
REGION="us-east-1"
S3_BUCKET=""
ENVIRONMENT_NAME=""
WEATHER_API_KEY=""
TEMPLATE_FILE="infrastructure/cloudformation-template.yaml"

# -------------------------------------------------------
# Parse arguments
# -------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --environment-name)
      ENVIRONMENT_NAME="$2"
      shift 2
      ;;
    --weather-api-key)
      WEATHER_API_KEY="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --s3-bucket)
      S3_BUCKET="$2"
      shift 2
      ;;
    *)
      echo "Unknown parameter: $1"
      echo "Usage: $0 --environment-name NAME --weather-api-key KEY [--region REGION] [--s3-bucket BUCKET]"
      exit 1
      ;;
  esac
done

# -------------------------------------------------------
# Validate required parameters
# -------------------------------------------------------
if [[ -z "$ENVIRONMENT_NAME" ]]; then
  echo "ERROR: --environment-name is required"
  exit 1
fi

if [[ -z "$WEATHER_API_KEY" ]]; then
  echo "ERROR: --weather-api-key is required"
  exit 1
fi

STACK_NAME="${ENVIRONMENT_NAME}-weather-agent"
WEATHER_SECRET_NAME="${ENVIRONMENT_NAME}/weather-api-key"
APIGW_SECRET_NAME="${ENVIRONMENT_NAME}/apigw-api-key"

echo "============================================="
echo " AgentCore Weather Agent Deployment"
echo "============================================="
echo " Environment : ${ENVIRONMENT_NAME}"
echo " Region      : ${REGION}"
echo " Stack       : ${STACK_NAME}"
echo " S3 Bucket   : ${S3_BUCKET:-<none — direct upload>}"
echo "============================================="

# =============================================================================
# Step 1: Validate CloudFormation template
# =============================================================================
echo ""
echo ">>> Step 1: Validating CloudFormation template..."
aws cloudformation validate-template \
  --template-body "file://${TEMPLATE_FILE}" \
  --region "${REGION}" > /dev/null
echo "    Template validation passed."

# =============================================================================
# Step 2: Create/update Secrets Manager secrets
# =============================================================================
echo ""
echo ">>> Step 2: Creating/updating Secrets Manager secrets..."

# --- WeatherAPI key secret ---
if aws secretsmanager describe-secret --secret-id "${WEATHER_SECRET_NAME}" --region "${REGION}" > /dev/null 2>&1; then
  echo "    Updating existing WeatherAPI key secret..."
  aws secretsmanager put-secret-value \
    --secret-id "${WEATHER_SECRET_NAME}" \
    --secret-string "${WEATHER_API_KEY}" \
    --region "${REGION}" > /dev/null
else
  echo "    Creating WeatherAPI key secret..."
  aws secretsmanager create-secret \
    --name "${WEATHER_SECRET_NAME}" \
    --description "WeatherAPI.com API key for ${ENVIRONMENT_NAME}" \
    --secret-string "${WEATHER_API_KEY}" \
    --region "${REGION}" > /dev/null
fi

WEATHER_SECRET_ARN=$(aws secretsmanager describe-secret \
  --secret-id "${WEATHER_SECRET_NAME}" \
  --region "${REGION}" \
  --query 'ARN' --output text)
echo "    WeatherAPI secret ARN: ${WEATHER_SECRET_ARN}"

# --- Placeholder APIGW key secret ---
if aws secretsmanager describe-secret --secret-id "${APIGW_SECRET_NAME}" --region "${REGION}" > /dev/null 2>&1; then
  echo "    APIGW key secret already exists (will update after stack deploy)."
else
  echo "    Creating placeholder APIGW key secret..."
  aws secretsmanager create-secret \
    --name "${APIGW_SECRET_NAME}" \
    --description "API Gateway API key for AgentCore credential provider (${ENVIRONMENT_NAME})" \
    --secret-string "PLACEHOLDER_WILL_BE_UPDATED" \
    --region "${REGION}" > /dev/null
fi

APIGW_SECRET_ARN=$(aws secretsmanager describe-secret \
  --secret-id "${APIGW_SECRET_NAME}" \
  --region "${REGION}" \
  --query 'ARN' --output text)
echo "    APIGW secret ARN: ${APIGW_SECRET_ARN}"

# =============================================================================
# Step 3: Deploy CloudFormation stack
# =============================================================================
echo ""
echo ">>> Step 3: Deploying CloudFormation stack '${STACK_NAME}'..."

STACK_EXISTS=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${REGION}" \
  --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [[ "${STACK_EXISTS}" == "DOES_NOT_EXIST" ]]; then
  echo "    Creating new stack..."
  aws cloudformation create-stack \
    --stack-name "${STACK_NAME}" \
    --template-body "file://${TEMPLATE_FILE}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "${REGION}" \
    --parameters \
      ParameterKey=EnvironmentName,ParameterValue="${ENVIRONMENT_NAME}" \
      ParameterKey=WeatherApiKeySecretArn,ParameterValue="${WEATHER_SECRET_ARN}" > /dev/null

  echo "    Waiting for stack creation to complete..."
  aws cloudformation wait stack-create-complete \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}"
else
  echo "    Updating existing stack..."
  aws cloudformation update-stack \
    --stack-name "${STACK_NAME}" \
    --template-body "file://${TEMPLATE_FILE}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "${REGION}" \
    --parameters \
      ParameterKey=EnvironmentName,ParameterValue="${ENVIRONMENT_NAME}" \
      ParameterKey=WeatherApiKeySecretArn,ParameterValue="${WEATHER_SECRET_ARN}" \
      ParameterKey=CredentialProviderArn,UsePreviousValue=true > /dev/null 2>&1 || {
        echo "    No updates to perform (stack is already up to date)."
      }

  echo "    Waiting for stack update to complete..."
  aws cloudformation wait stack-update-complete \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" 2>/dev/null || true
fi

echo "    Stack deployment complete."

# Retrieve stack outputs
get_output() {
  aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" \
    --output text
}

GATEWAY_ID=$(get_output "GatewayId")
REST_API_ID=$(get_output "RestApiId")
API_KEY_ID=$(get_output "ApiKeyId")
USER_POOL_ID=$(get_output "UserPoolId")
USER_POOL_CLIENT_ID=$(get_output "UserPoolClientId")
COGNITO_JWKS_URL=$(get_output "CognitoJwksUrl")
LAMBDA_ARN=$(get_output "AgentLambdaArn")
API_ENDPOINT_URL=$(get_output "ApiEndpointUrl")

echo ""
echo "    Stack Outputs:"
echo "      Gateway ID        : ${GATEWAY_ID}"
echo "      REST API ID       : ${REST_API_ID}"
echo "      API Key ID        : ${API_KEY_ID}"
echo "      User Pool ID      : ${USER_POOL_ID}"
echo "      Client ID         : ${USER_POOL_CLIENT_ID}"
echo "      JWKS URL          : ${COGNITO_JWKS_URL}"
echo "      Lambda ARN        : ${LAMBDA_ARN}"
echo "      API Endpoint      : ${API_ENDPOINT_URL}"

# =============================================================================
# Step 4: Retrieve API Gateway key value and update Secrets Manager
# =============================================================================
echo ""
echo ">>> Step 4: Retrieving API Gateway key value..."

API_KEY_VALUE=$(aws apigateway get-api-key \
  --api-key "${API_KEY_ID}" \
  --include-value \
  --region "${REGION}" \
  --query 'value' --output text)

if [[ -z "${API_KEY_VALUE}" || "${API_KEY_VALUE}" == "None" ]]; then
  echo "ERROR: Failed to retrieve API Gateway key value."
  exit 1
fi

echo "    API key retrieved successfully."

echo ""
echo ">>> Step 5: Updating Secrets Manager with real API Gateway key..."
aws secretsmanager put-secret-value \
  --secret-id "${APIGW_SECRET_NAME}" \
  --secret-string "${API_KEY_VALUE}" \
  --region "${REGION}" > /dev/null
echo "    APIGW key secret updated."

# =============================================================================
# Step 6: Create/update credential provider (CLI or manual)
# =============================================================================
echo ""
echo ">>> Step 6: Creating/updating credential provider..."

CRED_PROVIDER_NAME="${ENVIRONMENT_NAME}-weather-apigw-key"
CRED_PROVIDER_ARN=""

# Detect CLI support by listing providers (help command is buggy in some CLI versions)
if aws bedrock-agentcore-control list-api-key-credential-providers --region "${REGION}" > /dev/null 2>&1; then
  # Check if provider already exists
  EXISTING_ARN=$(aws bedrock-agentcore-control list-api-key-credential-providers \
    --region "${REGION}" \
    --query "credentialProviders[?name=='${CRED_PROVIDER_NAME}'].credentialProviderArn" \
    --output text 2>/dev/null)

  if [[ -n "${EXISTING_ARN}" && "${EXISTING_ARN}" != "None" ]]; then
    echo "    Updating existing credential provider with new API key..."
    UPDATE_OUTPUT=$(aws bedrock-agentcore-control update-api-key-credential-provider \
      --name "${CRED_PROVIDER_NAME}" \
      --api-key "${API_KEY_VALUE}" \
      --region "${REGION}" 2>&1) || {
        echo "    WARNING: update-api-key-credential-provider failed. Deleting and recreating..."
        aws bedrock-agentcore-control delete-api-key-credential-provider \
          --name "${CRED_PROVIDER_NAME}" \
          --region "${REGION}" > /dev/null 2>&1 || true
        # Small delay for eventual consistency
        sleep 3
        EXISTING_ARN=""
      }
    if [[ -n "${EXISTING_ARN}" ]]; then
      CRED_PROVIDER_ARN="${EXISTING_ARN}"
      echo "    Credential provider updated: ${CRED_PROVIDER_ARN}"
    fi
  fi

  if [[ -z "${CRED_PROVIDER_ARN}" || "${CRED_PROVIDER_ARN}" == "None" ]]; then
    echo "    Creating credential provider via CLI..."
    CRED_PROVIDER_ARN=$(aws bedrock-agentcore-control create-api-key-credential-provider \
      --name "${CRED_PROVIDER_NAME}" \
      --api-key "${API_KEY_VALUE}" \
      --region "${REGION}" \
      --query 'credentialProviderArn' --output text 2>&1) || {
        echo "    ERROR: Failed to create credential provider: ${CRED_PROVIDER_ARN}"
        CRED_PROVIDER_ARN=""
      }
    if [[ -n "${CRED_PROVIDER_ARN}" && "${CRED_PROVIDER_ARN}" != "None" ]]; then
      echo "    Credential provider created: ${CRED_PROVIDER_ARN}"
    fi
  fi
fi

if [[ -n "${CRED_PROVIDER_ARN}" && "${CRED_PROVIDER_ARN}" != "None" ]]; then
  # Verify the credential provider was updated correctly
  VERIFY_TIME=$(aws bedrock-agentcore-control list-api-key-credential-providers \
    --region "${REGION}" \
    --query "credentialProviders[?name=='${CRED_PROVIDER_NAME}'].lastUpdatedTime" \
    --output text 2>/dev/null)
  echo "    Credential provider verified (last updated: ${VERIFY_TIME})"
  echo ""
  echo ">>> Step 6b: Updating stack with credential provider ARN..."
  aws cloudformation update-stack \
    --stack-name "${STACK_NAME}" \
    --template-body "file://${TEMPLATE_FILE}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "${REGION}" \
    --parameters \
      ParameterKey=EnvironmentName,ParameterValue="${ENVIRONMENT_NAME}" \
      ParameterKey=WeatherApiKeySecretArn,ParameterValue="${WEATHER_SECRET_ARN}" \
      ParameterKey=CredentialProviderArn,ParameterValue="${CRED_PROVIDER_ARN}" > /dev/null 2>&1 || {
        echo "    No stack updates needed."
      }
  aws cloudformation wait stack-update-complete \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" 2>/dev/null || true
  echo "    Stack updated with credential provider."
else
  echo ""
  echo "============================================="
  echo " MANUAL STEP: Create Credential Provider"
  echo "============================================="
  echo ""
  echo " Your AWS CLI does not support bedrock-agentcore-control."
  echo " Upgrade to AWS CLI 2.28+ or create manually:"
  echo ""
  echo " Option A — Upgrade CLI then run:"
  echo ""
  echo "   aws bedrock-agentcore-control create-api-key-credential-provider \\"
  echo "     --name ${CRED_PROVIDER_NAME} \\"
  echo "     --api-key \$(aws apigateway get-api-key --api-key ${API_KEY_ID} --include-value --region ${REGION} --query 'value' --output text) \\"
  echo "     --region ${REGION}"
  echo ""
  echo " Option B — AWS Console:"
  echo ""
  echo "   1. Open: https://console.aws.amazon.com/bedrock-agentcore/"
  echo "   2. Go to Identity → Outbound Auth"
  echo "   3. Click 'Add OAuth client/API Key' → select 'API Key'"
  echo "   4. Name: ${CRED_PROVIDER_NAME}"
  echo "   5. API Key: (run the command below to get the value)"
  echo "      aws apigateway get-api-key --api-key ${API_KEY_ID} --include-value --region ${REGION} --query 'value' --output text"
  echo ""
  echo " After creating, update the stack with the credential provider ARN:"
  echo ""
  echo "   aws cloudformation update-stack \\"
  echo "     --stack-name ${STACK_NAME} \\"
  echo "     --template-body file://${TEMPLATE_FILE} \\"
  echo "     --capabilities CAPABILITY_NAMED_IAM \\"
  echo "     --region ${REGION} \\"
  echo "     --parameters \\"
  echo "       ParameterKey=EnvironmentName,ParameterValue=${ENVIRONMENT_NAME} \\"
  echo "       ParameterKey=WeatherApiKeySecretArn,ParameterValue=${WEATHER_SECRET_ARN} \\"
  echo "       ParameterKey=CredentialProviderArn,ParameterValue=<YOUR_CREDENTIAL_PROVIDER_ARN>"
  echo ""
  echo "============================================="
fi

# =============================================================================
# Step 7: Package Lambda code
# =============================================================================
echo ""
echo ">>> Step 7: Packaging Lambda code..."

PACKAGE_DIR=$(mktemp -d)
ZIP_FILE="lambda-package.zip"

echo "    Installing dependencies for python3.12 / x86_64..."
pip3 install \
  --target "${PACKAGE_DIR}" \
  --platform manylinux2014_x86_64 \
  --python-version 3.12 \
  --only-binary=:all: \
  -r requirements.txt \
  --quiet

echo "    Installing pure Python dependencies (requests, PyJWT)..."
pip3 install \
  --target "${PACKAGE_DIR}" \
  --platform manylinux2014_x86_64 \
  --python-version 3.12 \
  --only-binary=:all: \
  --no-deps \
  requests urllib3 charset-normalizer idna certifi PyJWT cryptography cffi \
  --quiet

# Remove .egg-info directories only — preserve .dist-info (opentelemetry needs them)
find "${PACKAGE_DIR}" -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true

echo "    Copying application code..."
cp -r src/agent "${PACKAGE_DIR}/agent"
cp -r src/shared "${PACKAGE_DIR}/shared"

# Ensure __init__.py files exist
touch "${PACKAGE_DIR}/agent/__init__.py" 2>/dev/null || true
touch "${PACKAGE_DIR}/shared/__init__.py" 2>/dev/null || true

echo "    Creating zip package..."
(cd "${PACKAGE_DIR}" && zip -r -q "${OLDPWD}/${ZIP_FILE}" .)

PACKAGE_SIZE=$(stat -f%z "${ZIP_FILE}" 2>/dev/null || stat -c%s "${ZIP_FILE}" 2>/dev/null)
PACKAGE_SIZE_MB=$((PACKAGE_SIZE / 1024 / 1024))
echo "    Package size: ${PACKAGE_SIZE_MB} MB (${PACKAGE_SIZE} bytes)"

# =============================================================================
# Step 8: Deploy Lambda code
# =============================================================================
echo ""
echo ">>> Step 8: Deploying Lambda code..."

LAMBDA_FUNCTION_NAME="${ENVIRONMENT_NAME}-weather-agent"
FIFTY_MB=$((50 * 1024 * 1024))

if [[ ${PACKAGE_SIZE} -gt ${FIFTY_MB} ]]; then
  echo "    Package exceeds 50 MB — uploading to S3..."
  if [[ -z "${S3_BUCKET}" ]]; then
    echo "ERROR: Package is >50 MB but no --s3-bucket was provided."
    echo "       Re-run with --s3-bucket <bucket-name>"
    rm -rf "${PACKAGE_DIR}" "${ZIP_FILE}"
    exit 1
  fi

  S3_KEY="${STACK_NAME}/lambda-package.zip"
  aws s3 cp "${ZIP_FILE}" "s3://${S3_BUCKET}/${S3_KEY}" \
    --region "${REGION}" --quiet
  echo "    Uploaded to s3://${S3_BUCKET}/${S3_KEY}"

  aws lambda update-function-code \
    --function-name "${LAMBDA_FUNCTION_NAME}" \
    --s3-bucket "${S3_BUCKET}" \
    --s3-key "${S3_KEY}" \
    --region "${REGION}" > /dev/null
else
  echo "    Deploying directly (package < 50 MB)..."
  aws lambda update-function-code \
    --function-name "${LAMBDA_FUNCTION_NAME}" \
    --zip-file "fileb://${ZIP_FILE}" \
    --region "${REGION}" > /dev/null
fi

echo "    Lambda code deployed."

# Cleanup
rm -rf "${PACKAGE_DIR}" "${ZIP_FILE}"

# =============================================================================
# Step 9: Create test user
# =============================================================================
echo ""
echo ">>> Step 9: Creating test user..."

TEST_USERNAME="testuser"
TEST_PASSWORD="TestPass123!"

# Check if user already exists
if aws cognito-idp admin-get-user \
    --user-pool-id "${USER_POOL_ID}" \
    --username "${TEST_USERNAME}" \
    --region "${REGION}" > /dev/null 2>&1; then
  echo "    Test user '${TEST_USERNAME}' already exists."
else
  echo "    Creating test user '${TEST_USERNAME}'..."
  aws cognito-idp admin-create-user \
    --user-pool-id "${USER_POOL_ID}" \
    --username "${TEST_USERNAME}" \
    --temporary-password "TempPass123!" \
    --message-action SUPPRESS \
    --region "${REGION}" > /dev/null

  echo "    Setting permanent password..."
  aws cognito-idp admin-set-user-password \
    --user-pool-id "${USER_POOL_ID}" \
    --username "${TEST_USERNAME}" \
    --password "${TEST_PASSWORD}" \
    --permanent \
    --region "${REGION}" > /dev/null

  echo "    Test user created."
fi

# =============================================================================
# Done
# =============================================================================
# Write a test script that can be run directly
TEST_SCRIPT="scripts/test.sh"
cat > "${TEST_SCRIPT}" << 'TESTEOF'
#!/usr/bin/env bash
set -e
TESTEOF

cat >> "${TEST_SCRIPT}" << EOF
CLIENT_ID="${USER_POOL_CLIENT_ID}"
FUNCTION_NAME="${LAMBDA_FUNCTION_NAME}"
REGION="${REGION}"
USERNAME="${TEST_USERNAME}"
PASSWORD="${TEST_PASSWORD}"
EOF

cat >> "${TEST_SCRIPT}" << 'TESTEOF'

echo "Getting ID token..."
ID_TOKEN=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id "${CLIENT_ID}" \
  --auth-parameters USERNAME="${USERNAME}",PASSWORD="${PASSWORD}" \
  --region "${REGION}" \
  --query 'AuthenticationResult.IdToken' --output text)

if [[ -z "${ID_TOKEN}" || "${ID_TOKEN}" == "None" ]]; then
  echo "ERROR: Failed to get ID token"
  exit 1
fi
echo "Token obtained (${#ID_TOKEN} chars)"

PROMPT="${1:-What is the weather in London, UK?}"
echo "Invoking agent with: ${PROMPT}"

PAYLOAD=$(python3 -c "
import json
inner = json.dumps({'prompt': '${PROMPT}'})
outer = json.dumps({'body': inner, 'headers': {'Authorization': 'Bearer ${ID_TOKEN}'}})
print(outer)
")

aws lambda invoke \
  --function-name "${FUNCTION_NAME}" \
  --region "${REGION}" \
  --cli-binary-format raw-in-base64-out \
  --payload "${PAYLOAD}" \
  /tmp/response.json

echo ""
echo "=== Response ==="
python3 -c "
import json
with open('/tmp/response.json') as f:
    resp = json.load(f)
if 'body' in resp:
    body = json.loads(resp['body'])
    if 'response' in body:
        print(body['response'])
    elif 'error' in body:
        print(f\"ERROR: {body['error']}\")
    else:
        print(json.dumps(body, indent=2))
else:
    print(json.dumps(resp, indent=2))
"
TESTEOF

chmod +x "${TEST_SCRIPT}"

echo ""
echo "============================================="
echo " Deployment Complete!"
echo "============================================="
echo ""
echo " Test the agent:"
echo ""
echo "   ./scripts/test.sh"
echo "   ./scripts/test.sh 'What is the weather in Liverpool, England?'"
echo ""
