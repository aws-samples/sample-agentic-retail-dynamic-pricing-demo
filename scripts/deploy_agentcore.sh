#!/usr/bin/env bash
# Deploy Retail Dynamic Pricing agents to Amazon Bedrock AgentCore Runtime.
#
# This shell wrapper:
# 1. Detects the AWS account ID via `aws sts get-caller-identity`
# 2. Logs into ECR
# 3. Calls the Python deployment script
#
# Usage:
#   ./scripts/deploy_agentcore.sh --role-arn <arn> [--region us-east-1]
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Docker installed and running (with buildx support)
#   - Python 3.10+ with boto3 installed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Default values
REGION="us-east-1"
ROLE_ARN=""
EXTRA_ARGS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --region)
            REGION="$2"
            shift 2
            ;;
        --role-arn)
            ROLE_ARN="$2"
            shift 2
            ;;
        *)
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

if [[ -z "${ROLE_ARN}" ]]; then
    echo "ERROR: --role-arn is required"
    echo "Usage: $0 --role-arn <arn> [--region us-east-1]"
    exit 1
fi

echo "============================================================"
echo "Retail Dynamic Pricing - AgentCore Deployment"
echo "============================================================"

# Step 1: Detect AWS account ID
echo ""
echo "[1/3] Detecting AWS account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
if [[ -z "${ACCOUNT_ID}" ]]; then
    echo "ERROR: Could not detect AWS account ID. Check your AWS credentials."
    exit 1
fi
echo "  Account ID: ${ACCOUNT_ID}"
echo "  Region:     ${REGION}"
echo "  Role ARN:   ${ROLE_ARN}"

# Step 2: Log into ECR
echo ""
echo "[2/3] Authenticating Docker to ECR..."
REGISTRY_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
aws ecr get-login-password --region "${REGION}" | \
    docker login --username AWS --password-stdin "${REGISTRY_URI}"
echo "  Logged into: ${REGISTRY_URI}"

# Step 3: Run the Python deployment script
echo ""
echo "[3/3] Running deployment script..."
echo "------------------------------------------------------------"

python "${SCRIPT_DIR}/deploy_agentcore.py" \
    --region "${REGION}" \
    --account-id "${ACCOUNT_ID}" \
    --role-arn "${ROLE_ARN}" \
    "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"

echo ""
echo "============================================================"
echo "Deployment complete!"
echo ""
echo "Agent ARNs saved to:"
echo "  - ${SCRIPT_DIR}/agent_arns.env"
echo "  - ${PROJECT_ROOT}/backend/agents/agentcore/agent_config.json"
echo ""
echo "To load ARNs into your shell:"
echo "  source ${SCRIPT_DIR}/agent_arns.env"
echo "============================================================"
