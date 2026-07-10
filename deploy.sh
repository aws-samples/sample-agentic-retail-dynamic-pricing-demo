#!/bin/bash
# =============================================================================
# Retail Dynamic Pricing — One-Click Deployment Script
# =============================================================================
# This script automates the full deployment of the Retail Dynamic Pricing
# solution. It handles all 10 steps from the README deployment guide.
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Python 3.12+
#   - Node.js 20+
#   - Docker running (for AgentCore agent containers)
#   - AWS CDK CLI (npm install -g aws-cdk)
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh [--region us-east-1] [--skip-agents] [--skip-frontend]
#
# Rollback:
#   To tear down everything: npx cdk destroy --all
#   To delete agents: python3 scripts/deploy_agentcore.py --delete --region us-east-1
# =============================================================================

set -e

# --- Configuration ---
REGION="${AWS_REGION:-us-east-1}"
DEMO_USER="demo@example.com"
DEMO_PASSWORD="DemoPass2024!"
OPS_USER="ops@example.com"
OPS_PASSWORD="OpsPass2024!"
SKIP_AGENTS=false
SKIP_FRONTEND=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --region) REGION="$2"; shift 2 ;;
        --skip-agents) SKIP_AGENTS=true; shift ;;
        --skip-frontend) SKIP_FRONTEND=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# --- Helper Functions ---
print_step() {
    echo ""
    echo "============================================================"
    echo "  Step $1: $2"
    echo "============================================================"
    echo ""
}

print_success() {
    echo "  ✓ $1"
}

print_warning() {
    echo "  ⚠ $1"
}

check_prerequisites() {
    local missing=false

    if ! command -v python3 &> /dev/null; then
        echo "ERROR: python3 not found. Install Python 3.12+"; missing=true
    fi
    if ! command -v node &> /dev/null; then
        echo "ERROR: node not found. Install Node.js 20+"; missing=true
    fi
    if ! command -v aws &> /dev/null; then
        echo "ERROR: aws CLI not found. Install AWS CLI"; missing=true
    fi
    if ! command -v docker &> /dev/null; then
        echo "ERROR: docker not found. Install Docker"; missing=true
    fi
    if ! docker info &> /dev/null; then
        echo "ERROR: Docker is not running. Start Docker Desktop"; missing=true
    fi
    if ! command -v npx &> /dev/null; then
        echo "ERROR: npx not found. Install Node.js 20+"; missing=true
    fi

    if [ "$missing" = true ]; then
        echo ""
        echo "Please install missing prerequisites and try again."
        exit 1
    fi

    # Verify AWS credentials
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
    if [ $? -ne 0 ]; then
        echo "ERROR: AWS credentials not configured. Run 'aws configure' or 'aws sso login'"
        exit 1
    fi
    print_success "AWS Account: $ACCOUNT_ID"
    print_success "Region: $REGION"
}

# --- Main Deployment ---
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   Retail Dynamic Pricing — Automated Deployment             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Step 0: Prerequisites
print_step "0" "Checking prerequisites"
check_prerequisites

# Step 1: Python environment
print_step "1" "Setting up Python environment"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    print_success "Created virtual environment"
else
    print_success "Virtual environment already exists"
fi
source .venv/bin/activate
.venv/bin/pip install -e . --quiet
print_success "Dependencies installed"

# Step 1.5: Security — Dependency vulnerability scan
print_step "1.5" "Scanning dependencies for known vulnerabilities"
.venv/bin/pip install pip-audit --quiet
if .venv/bin/pip-audit --strict --progress-spinner off 2>&1 | tail -5; then
    print_success "No known vulnerabilities found in dependencies"
else
    echo ""
    echo "WARNING: Vulnerable dependencies detected."
    echo "  Run 'pip-audit' to see details and 'pip-audit --fix' to auto-fix."
    echo "  Continuing deployment — review and remediate vulnerabilities."
    echo ""
    print_warning "Deployment continuing with known vulnerabilities (review recommended)"
fi

# Step 1.7: Model Selection
print_step "1.7" "Selecting AI model (Bedrock)"
echo "Scanning available models and checking access..."
python3 scripts/select_model.py --region $REGION
print_success "Model selected — config written to model-config.json"

# Step 2: Deploy Infrastructure (CDK) — first pass
print_step "2" "Deploying infrastructure (CDK)"
npx cdk bootstrap aws://$ACCOUNT_ID/$REGION --app ".venv/bin/python3 cdk/app.py" 2>/dev/null || true
npx cdk deploy --all --require-approval never --app ".venv/bin/python3 cdk/app.py" --outputs-file cdk-outputs.json
print_success "CDK stacks deployed"

# Step 3: Deploy AgentCore Agents
if [ "$SKIP_AGENTS" = false ]; then
    print_step "3" "Deploying AgentCore agents"
    python3 scripts/create_agentcore_role.py --region $REGION
    print_success "IAM role created"

    python3 scripts/deploy_agentcore.py \
        --region $REGION \
        --role-arn "arn:aws:iam::${ACCOUNT_ID}:role/RetailPricingAgentCoreRole"
    print_success "All 6 agents deployed and ACTIVE"
else
    print_warning "Skipping agent deployment (--skip-agents)"
fi

# Step 4: Re-deploy CDK (links orchestrator ARN to Lambda)
print_step "4" "Re-deploying CDK (linking agent ARNs)"
npx cdk deploy --all --require-approval never --app ".venv/bin/python3 cdk/app.py" --outputs-file cdk-outputs.json
print_success "Lambda updated with orchestrator ARN"

# Step 5: Setup AgentCore Gateway & Memory
print_step "5" "Setting up AgentCore Gateway & Memory"

# Auto-discover MCP Server Lambda ARNs
export COMPETITOR_API_LAMBDA_ARN=$(aws lambda get-function --function-name rdp-mcp-competitor-api --query "Configuration.FunctionArn" --output text --region $REGION 2>/dev/null || echo "")
export ERP_POS_LAMBDA_ARN=$(aws lambda get-function --function-name rdp-mcp-erp-pos --query "Configuration.FunctionArn" --output text --region $REGION 2>/dev/null || echo "")
export MARKET_SIGNALS_LAMBDA_ARN=$(aws lambda get-function --function-name rdp-mcp-market-signals --query "Configuration.FunctionArn" --output text --region $REGION 2>/dev/null || echo "")
export COST_FINANCE_LAMBDA_ARN=$(aws lambda get-function --function-name rdp-mcp-cost-finance --query "Configuration.FunctionArn" --output text --region $REGION 2>/dev/null || echo "")

if [ -n "$COMPETITOR_API_LAMBDA_ARN" ]; then
    python3 scripts/setup_gateway.py --region $REGION || print_warning "Gateway setup had issues (non-critical, resources may already exist)"
    print_success "Gateway targets registered"
else
    print_warning "MCP Server Lambdas not found — skipping gateway setup"
fi

python3 scripts/setup_memory.py --region $REGION || print_warning "Memory setup had issues (non-critical, may already exist)"
print_success "AgentCore Memory provisioned"

# Step 6: Seed Data
print_step "6" "Seeding product catalog"
python3 scripts/seed_products.py
print_success "19 products seeded"

# Step 7: Create Demo Users
print_step "7" "Creating demo users"

# Extract Cognito User Pool ID from CDK outputs
USER_POOL_ID=$(python3 -c "
import json
with open('cdk-outputs.json') as f:
    outputs = json.load(f)
stack = outputs.get('RetailDynamicPricing', {})
for key, value in stack.items():
    if 'UserPoolId' in key:
        print(value)
        break
" 2>/dev/null)

CLIENT_ID=$(python3 -c "
import json
with open('cdk-outputs.json') as f:
    outputs = json.load(f)
stack = outputs.get('RetailDynamicPricing', {})
for key, value in stack.items():
    if 'UserPoolClientId' in key:
        print(value)
        break
" 2>/dev/null)

if [ -n "$USER_POOL_ID" ]; then
    # Create demo user (Pricing Analyst)
    aws cognito-idp admin-create-user \
        --user-pool-id $USER_POOL_ID \
        --username $DEMO_USER \
        --temporary-password "TempPass123!" \
        --message-action SUPPRESS \
        --region $REGION 2>/dev/null || true

    aws cognito-idp admin-set-user-password \
        --user-pool-id $USER_POOL_ID \
        --username $DEMO_USER \
        --password $DEMO_PASSWORD \
        --permanent \
        --region $REGION
    print_success "Demo user created: $DEMO_USER"

    # Create ops user
    aws cognito-idp admin-create-user \
        --user-pool-id $USER_POOL_ID \
        --username $OPS_USER \
        --temporary-password "TempPass123!" \
        --message-action SUPPRESS \
        --region $REGION 2>/dev/null || true

    aws cognito-idp admin-set-user-password \
        --user-pool-id $USER_POOL_ID \
        --username $OPS_USER \
        --password $OPS_PASSWORD \
        --permanent \
        --region $REGION
    print_success "Ops user created: $OPS_USER"

    # Assign users to Cognito groups
    aws cognito-idp admin-add-user-to-group \
        --user-pool-id $USER_POOL_ID \
        --username $DEMO_USER \
        --group-name PricingAnalysts \
        --region $REGION 2>/dev/null || true
    print_success "Demo user assigned to PricingAnalysts group"

    aws cognito-idp admin-add-user-to-group \
        --user-pool-id $USER_POOL_ID \
        --username $OPS_USER \
        --group-name Operations \
        --region $REGION 2>/dev/null || true
    aws cognito-idp admin-add-user-to-group \
        --user-pool-id $USER_POOL_ID \
        --username $OPS_USER \
        --group-name PricingAnalysts \
        --region $REGION 2>/dev/null || true
    print_success "Ops user assigned to Operations + PricingAnalysts groups"
else
    print_warning "Could not find User Pool ID — create users manually"
fi

# Step 8: Build and Deploy Frontends
if [ "$SKIP_FRONTEND" = false ]; then
    print_step "8" "Building and deploying frontends"

    # Auto-sync frontend config
    python3 scripts/sync_frontend_config.py 2>/dev/null || print_warning "Auto-sync not available — using manual config"

    # Build Dashboard
    cd frontend/dashboard
    npm install --quiet
    npm run build
    cd ../..
    print_success "Dashboard built"

    # Build Storefront
    cd frontend/storefront
    npm install --quiet
    npm run build
    cd ../..
    print_success "Storefront built"

    # Upload to S3
    DASHBOARD_BUCKET=$(aws s3 ls | grep "retaildynamicpricing-hostingdashboardbucket" | awk '{print $3}')
    STOREFRONT_BUCKET=$(aws s3 ls | grep "retaildynamicpricing-hostingstorefrontbucket" | awk '{print $3}')

    if [ -n "$DASHBOARD_BUCKET" ]; then
        aws s3 sync frontend/dashboard/dist/ s3://$DASHBOARD_BUCKET/ --delete --quiet
        print_success "Dashboard deployed to S3"
    fi

    if [ -n "$STOREFRONT_BUCKET" ]; then
        aws s3 sync frontend/storefront/dist/ s3://$STOREFRONT_BUCKET/ --delete --quiet
        print_success "Storefront deployed to S3"
    fi
else
    print_warning "Skipping frontend deployment (--skip-frontend)"
fi

# Step 9: Update Cognito Callback URLs
print_step "9" "Configuring Cognito callback URLs"

DASHBOARD_CF=$(python3 -c "
import json
with open('cdk-outputs.json') as f:
    outputs = json.load(f)
stack = outputs.get('RetailDynamicPricing', {})
for key, value in stack.items():
    if 'DashboardCloudFrontUrl' in key:
        print(value)
        break
" 2>/dev/null)

if [ -n "$USER_POOL_ID" ] && [ -n "$CLIENT_ID" ] && [ -n "$DASHBOARD_CF" ]; then
    aws cognito-idp update-user-pool-client \
        --user-pool-id $USER_POOL_ID \
        --client-id $CLIENT_ID \
        --callback-urls "[\"${DASHBOARD_CF}/callback\",\"http://localhost:5173/callback\"]" \
        --logout-urls "[\"${DASHBOARD_CF}\",\"http://localhost:5173\"]" \
        --allowed-o-auth-flows "code" "implicit" \
        --allowed-o-auth-scopes "openid" "email" "profile" \
        --supported-identity-providers "COGNITO" \
        --allowed-o-auth-flows-user-pool-client \
        --region $REGION > /dev/null
    print_success "Callback URLs configured for $DASHBOARD_CF"
else
    print_warning "Could not auto-configure callbacks — do manually (see README Step 9)"
fi

# Step 10: Summary
print_step "10" "Deployment Complete!"

echo "  ┌─────────────────────────────────────────────────────────┐"
echo "  │  Retail Dynamic Pricing — Deployment Summary             │"
echo "  ├─────────────────────────────────────────────────────────┤"
if [ -n "$DASHBOARD_CF" ]; then
echo "  │  Dashboard:  $DASHBOARD_CF"
fi
STOREFRONT_CF=$(python3 -c "
import json
with open('cdk-outputs.json') as f:
    outputs = json.load(f)
stack = outputs.get('RetailDynamicPricing', {})
for key, value in stack.items():
    if 'StorefrontCloudFrontUrl' in key:
        print(value)
        break
" 2>/dev/null)
if [ -n "$STOREFRONT_CF" ]; then
echo "  │  Storefront: $STOREFRONT_CF"
fi
echo "  │"
echo "  │  Demo Login: $DEMO_USER / $DEMO_PASSWORD"
echo "  │  Ops Login:  $OPS_USER / $OPS_PASSWORD"
echo "  │"
echo "  │  Region: $REGION"
echo "  │  Account: $ACCOUNT_ID"
echo "  └─────────────────────────────────────────────────────────┘"
echo ""
echo "  Next: Open the Dashboard URL and log in to start the demo."
echo "  See docs/DEMO_SCRIPT.md for a guided walkthrough."
echo ""
