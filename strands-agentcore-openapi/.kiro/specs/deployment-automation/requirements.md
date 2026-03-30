# Requirements Document

## Introduction

The OpenAPI Agent Gateway project currently requires 5-6 manual steps to deploy: CloudFormation stack deployment, saving stack outputs, packaging Lambda code, deploying Lambda code to S3, creating a Cognito test user, and running an end-to-end test. This feature introduces a unified `deploy.sh` shell script that orchestrates all deployment steps in sequence, with proper error handling, prerequisite validation, and idempotent behavior so developers can deploy with a single command.

## Glossary

- **Deploy_Script**: The `deploy.sh` Bash shell script that orchestrates the full deployment pipeline
- **Stack**: The `openapi-agent-gateway` AWS CloudFormation stack containing all infrastructure resources
- **Stack_Outputs**: The JSON file at `deployment/stack_outputs.json` containing CloudFormation output values (CognitoUserPoolId, GatewayId, AgentLambdaArn)
- **Lambda_Package**: The ZIP archive at `deployment/agent-lambda.zip` (~62MB) containing the Agent Lambda function code and dependencies
- **Test_User**: The Cognito user (`testuser@example.com`) created for end-to-end testing with JWT tokens saved to `deployment/test_credentials.json`
- **Prerequisite_Check**: Validation that required external tools and resources exist before deployment begins
- **Deployment_Step**: One discrete operation in the deployment pipeline (e.g., deploy stack, package Lambda)

## Requirements

### Requirement 1: Prerequisite Validation

**User Story:** As a developer, I want the deploy script to verify all prerequisites before starting deployment, so that I get clear early feedback instead of failures mid-deploy.

#### Acceptance Criteria

1. WHEN the Deploy_Script starts, THE Deploy_Script SHALL verify that the AWS CLI is installed and configured for the `us-east-1` region
2. WHEN the Deploy_Script starts, THE Deploy_Script SHALL verify that Python 3 is available on the PATH
3. WHEN the Deploy_Script starts, THE Deploy_Script SHALL verify that the `infrastructure/cloudformation-template.yaml` file exists
4. WHEN the Deploy_Script starts, THE Deploy_Script SHALL verify that the `deployment/package_lambdas.py`, `update_lambda_code.py`, and `deployment/setup_test_user.py` scripts exist
5. IF any Prerequisite_Check fails, THEN THE Deploy_Script SHALL print a descriptive error message identifying the missing prerequisite and exit with a non-zero exit code
6. WHEN all Prerequisite_Checks pass, THE Deploy_Script SHALL print a summary of validated prerequisites before proceeding

### Requirement 2: CloudFormation Stack Deployment

**User Story:** As a developer, I want the deploy script to deploy the CloudFormation stack automatically, so that I do not need to remember the exact `aws cloudformation deploy` command and flags.

#### Acceptance Criteria

1. WHEN Prerequisite_Checks pass, THE Deploy_Script SHALL deploy the Stack using `aws cloudformation deploy` with the template at `infrastructure/cloudformation-template.yaml`, stack name `openapi-agent-gateway`, region `us-east-1`, and `CAPABILITY_NAMED_IAM`
2. WHEN the Stack deployment succeeds, THE Deploy_Script SHALL proceed to the next Deployment_Step
3. IF the Stack deployment fails, THEN THE Deploy_Script SHALL print the CloudFormation error output and exit with a non-zero exit code
4. WHEN the Stack deployment completes with no changes, THE Deploy_Script SHALL treat the result as success and proceed to the next Deployment_Step

### Requirement 3: Stack Outputs Capture

**User Story:** As a developer, I want the deploy script to automatically save CloudFormation stack outputs, so that downstream scripts can reference resource identifiers without manual copy-paste.

#### Acceptance Criteria

1. WHEN the Stack deployment succeeds, THE Deploy_Script SHALL query the Stack outputs using `aws cloudformation describe-stacks`
2. WHEN the Stack outputs are retrieved, THE Deploy_Script SHALL save the outputs as JSON to `deployment/stack_outputs.json` with keys including `CognitoUserPoolId`, `GatewayId`, and `AgentLambdaArn`
3. IF the Stack outputs query fails, THEN THE Deploy_Script SHALL print a descriptive error message and exit with a non-zero exit code

### Requirement 4: Lambda Packaging

**User Story:** As a developer, I want the deploy script to package the Lambda function automatically, so that I do not need to run the packaging script manually.

#### Acceptance Criteria

1. WHEN Stack_Outputs are saved, THE Deploy_Script SHALL execute `python deployment/package_lambdas.py` to create the Lambda_Package
2. WHEN the packaging script completes successfully, THE Deploy_Script SHALL verify that `deployment/agent-lambda.zip` exists
3. IF the packaging script exits with a non-zero code, THEN THE Deploy_Script SHALL print a descriptive error message and exit with a non-zero exit code

### Requirement 5: Lambda Code Deployment

**User Story:** As a developer, I want the deploy script to upload and deploy the Lambda code automatically, so that the Lambda function is updated with the latest code after each deploy.

#### Acceptance Criteria

1. WHEN the Lambda_Package exists, THE Deploy_Script SHALL execute `python update_lambda_code.py` to upload the package to S3 and update the Lambda function code
2. IF the Lambda code deployment script exits with a non-zero code, THEN THE Deploy_Script SHALL print a descriptive error message and exit with a non-zero exit code

### Requirement 6: Test User Creation

**User Story:** As a developer, I want the deploy script to create a Cognito test user and save JWT tokens automatically, so that I can immediately run end-to-end tests after deployment.

#### Acceptance Criteria

1. WHEN Lambda code deployment succeeds, THE Deploy_Script SHALL execute `python deployment/setup_test_user.py` to create the Test_User and save JWT tokens
2. WHEN the test user setup completes successfully, THE Deploy_Script SHALL verify that `deployment/test_credentials.json` exists
3. IF the test user setup script exits with a non-zero code, THEN THE Deploy_Script SHALL print a descriptive error message and exit with a non-zero exit code

### Requirement 7: End-to-End Smoke Test

**User Story:** As a developer, I want the deploy script to run a quick smoke test after deployment, so that I have immediate confidence the deployed system works.

#### Acceptance Criteria

1. WHEN the Test_User is created, THE Deploy_Script SHALL invoke the `dev-agent-lambda` Lambda function with a test prompt and the saved JWT access token
2. WHEN the Lambda invocation returns a successful response (HTTP 200 status in the response body), THE Deploy_Script SHALL print the response and report the smoke test as passed
3. IF the Lambda invocation fails or returns an error response, THEN THE Deploy_Script SHALL print the error details and report the smoke test as failed with a non-zero exit code

### Requirement 8: Step Execution Control

**User Story:** As a developer, I want to skip certain deployment steps or start from a specific step, so that I can re-run only the parts that failed without repeating the entire pipeline.

#### Acceptance Criteria

1. WHERE a `--skip-packaging` flag is provided, THE Deploy_Script SHALL skip the Lambda packaging step and proceed directly to Lambda code deployment
2. WHERE a `--skip-test-user` flag is provided, THE Deploy_Script SHALL skip the test user creation step
3. WHERE a `--skip-smoke-test` flag is provided, THE Deploy_Script SHALL skip the end-to-end smoke test step
4. WHERE a `--step` flag is provided with a step name, THE Deploy_Script SHALL begin execution from the specified step, skipping all prior steps

### Requirement 9: Deployment Progress Reporting

**User Story:** As a developer, I want clear progress output during deployment, so that I know which step is running and how long the deployment takes.

#### Acceptance Criteria

1. WHEN each Deployment_Step begins, THE Deploy_Script SHALL print a clearly labeled header indicating the step name and step number (e.g., "[Step 2/6] Saving stack outputs...")
2. WHEN each Deployment_Step completes successfully, THE Deploy_Script SHALL print a success indicator for that step
3. WHEN the full deployment completes, THE Deploy_Script SHALL print a summary showing total elapsed time and the status of each step
4. IF any Deployment_Step fails, THEN THE Deploy_Script SHALL print which step failed and list the remaining steps that were skipped

### Requirement 10: Fail-Fast Error Handling

**User Story:** As a developer, I want the deploy script to stop immediately on any failure, so that I do not waste time on steps that depend on a failed step.

#### Acceptance Criteria

1. THE Deploy_Script SHALL enable Bash strict mode (`set -euo pipefail`) to exit on any command failure, unset variable, or pipeline error
2. WHEN a Deployment_Step fails, THE Deploy_Script SHALL exit immediately with a non-zero exit code without executing subsequent steps
3. IF a Deployment_Step fails, THEN THE Deploy_Script SHALL print the name of the failed step and a suggestion for how to retry (e.g., "Re-run with --step <step-name> to resume from this step")
