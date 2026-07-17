#!/bin/bash
###############################################################################
# Switch AI Model — Update model configuration for deployed agents
#
# Use this script AFTER initial deployment to change the AI model.
# It runs the model selection tool and updates model-config.json.
# AgentCore agents read model config at startup, so they will pick up
# the new model on their next cold start (or you can redeploy agents).
#
# Usage:
#   bash scripts/switch_model.sh [--non-interactive] [--region us-east-1]
###############################################################################

set -e

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NON_INTERACTIVE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --non-interactive) NON_INTERACTIVE="--non-interactive"; shift ;;
        --region) REGION="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo ""
echo "=============================================="
echo "  Switch AI Model (Existing Deployment)"
echo "  Region: $REGION"
echo "=============================================="
echo ""

# Step 1: Run model selection
echo "Step 1: Select new model..."
echo ""
cd "$PROJECT_ROOT"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

python3 scripts/select_model.py --region "$REGION" $NON_INTERACTIVE

# Read selected model from config
CONFIG_FILE="$PROJECT_ROOT/model-config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: model-config.json not found. Model selection may have failed."
    exit 1
fi

MODEL_ID=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['modelId'])")
MODEL_NAME=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['modelName'])")

echo ""
echo "Step 2: Model config updated."
echo ""
echo "  The model-config.json has been written. Agents using"
echo "  shared/model_config.py will pick up the new model on"
echo "  their next cold start."
echo ""

# Step 3: Offer to redeploy agents
echo "Step 3: Redeploy agents to apply immediately? (optional)"
echo ""

if [ -n "$NON_INTERACTIVE" ]; then
    echo "  Skipping agent redeploy (--non-interactive)."
    echo "  Run 'python3 scripts/deploy_agentcore.py' to redeploy agents."
else
    read -p "  Redeploy AgentCore agents now? [y/N]: " REDEPLOY
    if [[ "$REDEPLOY" =~ ^[Yy]$ ]]; then
        echo ""
        echo "  Redeploying agents..."
        ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        python3 scripts/deploy_agentcore.py \
            --region "$REGION" \
            --role-arn "arn:aws:iam::${ACCOUNT_ID}:role/RetailPricingAgentCoreRole" 2>&1 | tail -5
        echo ""
        echo "  ✓ Agents redeployed with new model."
    else
        echo "  Skipped. Agents will use the new model on next cold start."
    fi
fi

echo ""
echo "=============================================="
echo "  ✓ Model switch complete!"
echo ""
echo "  Model:  $MODEL_NAME"
echo "  ID:     $MODEL_ID"
echo "  Region: $REGION"
echo "  Config: $CONFIG_FILE"
echo "=============================================="
echo ""
