#!/bin/bash
###############################################################################
# Switch AI Model — Update model configuration for deployed agents
#
# Use this script AFTER initial deployment to change the AI models.
# It runs the model selection tool (orchestrator model + specialist model)
# and updates model-config.json. model-config.json is not part of the agent
# images: the models reach the agents only as environment variables set by
# scripts/deploy_agentcore.py, so the change takes effect when you redeploy
# the agents (Step 3 below).
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

read_config() {
    python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2], ''))" "$CONFIG_FILE" "$1"
}
MODEL_ID=$(read_config modelId)
MODEL_NAME=$(read_config modelName)
SPECIALIST_ID=$(read_config specialistModelId)
SPECIALIST_NAME=$(read_config specialistModelName)

echo ""
echo "Step 2: Model config updated."
echo ""
echo "  model-config.json has been written. The deployed agents keep"
echo "  their current models until they are redeployed (Step 3)."
echo ""

# Step 3: Offer to redeploy agents
echo "Step 3: Redeploy agents to apply immediately? (optional)"
echo ""

if [ -n "$NON_INTERACTIVE" ]; then
    echo "  Skipping agent redeploy (--non-interactive)."
    echo "  Run 'python3 scripts/deploy_agentcore.py' to apply the new models."
else
    read -p "  Redeploy AgentCore agents now? [y/N]: " REDEPLOY
    if [[ "$REDEPLOY" =~ ^[Yy]$ ]]; then
        echo ""
        echo "  Redeploying agents..."
        ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        # No pipe here: with `| tail` the if/set -e would test tail's exit
        # status, and a failed redeploy would be reported as success.
        python3 scripts/deploy_agentcore.py \
            --region "$REGION" \
            --role-arn "arn:aws:iam::${ACCOUNT_ID}:role/RetailPricingAgentCoreRole"
        echo ""
        echo "  ✓ Agents redeployed with the new models."
    else
        echo "  Skipped. The agents keep their current models until you run"
        echo "  'python3 scripts/deploy_agentcore.py' (or re-run this script)."
    fi
fi

echo ""
echo "=============================================="
echo "  ✓ Model switch complete!"
echo ""
echo "  Orchestrator: $MODEL_NAME ($MODEL_ID)"
echo "  Specialists:  $SPECIALIST_NAME ($SPECIALIST_ID)"
echo "  Region:       $REGION"
echo "  Config:       $CONFIG_FILE"
echo "=============================================="
echo ""
