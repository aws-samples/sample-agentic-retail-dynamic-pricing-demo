#!/bin/bash
# =============================================================================
# Retail Dynamic Pricing — One-Click Deployment Script
# =============================================================================
# This script automates the full deployment of the Retail Dynamic Pricing
# solution. It handles all 10 steps from the README deployment guide.
# It installs the pinned/validated dependency set (requirements.txt, then
# `pip install -e . --no-deps`), builds the frontends for S3 + CloudFront
# hosting, and runs verify_deployment.py as a gate before declaring success.
#
# AgentCore order (the agents are wired to the gateway and memory when they are
# deployed, so those must already exist):
#   Step 2  CDK first pass (infrastructure + MCP server Lambdas)
#   Step 3  IAM role, AgentCore Gateway and Memory
#   Step 4  Agents (AGENTCORE_GATEWAY_ENDPOINT / AGENTCORE_MEMORY_ID set on all 6)
#   Step 5  CDK re-deploy (links the orchestrator ARN into the Lambda)
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Python 3.12+
#   - Node.js 20+
#   - Docker running (for AgentCore agent containers)
#   - AWS CDK CLI (npm install -g aws-cdk)
#     (cdk-nag is a Python dependency installed via requirements.txt)
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh --alert-email you@example.com [--region us-east-1] [--skip-agents] [--skip-frontend]
#
#   --alert-email (or ALERT_EMAIL) is required: it receives the Bedrock spend
#   budget alert (80 % of $50/month).
#
#   --specialist-timeout / --synthesis-timeout SECONDS (or SPECIALIST_TIMEOUT_SECONDS /
#   SYNTHESIS_TIMEOUT_SECONDS; defaults 300 / 180) set how long the orchestrator waits
#   for each agent. The Lambda timeouts are derived from them (shared/cycle_timeouts.py);
#   their sum can be at most 714 s. Raise them if a slower model times out.
#
#   --skip-agents skips only the agent deploy (Step 4); the IAM role, gateway and
#   memory (Step 3) are still created because they do not depend on the agents.
#
# Rollback:
#   To tear down everything (CDK stack, AgentCore resources, ECR, IAM role):
#   ./teardown.sh --region us-east-1
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
ALERT_EMAIL="${ALERT_EMAIL:-}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --region) REGION="$2"; shift 2 ;;
        --alert-email) ALERT_EMAIL="$2"; shift 2 ;;
        --specialist-timeout) SPECIALIST_TIMEOUT_SECONDS="$2"; shift 2 ;;
        --synthesis-timeout) SYNTHESIS_TIMEOUT_SECONDS="$2"; shift 2 ;;
        --skip-agents) SKIP_AGENTS=true; shift ;;
        --skip-frontend) SKIP_FRONTEND=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# The Bedrock spend budget alerts this address. Without it the budget would alert
# nobody, so refuse to deploy rather than create a cost control that does nothing.
if [[ ! "$ALERT_EMAIL" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]]; then
    echo "Error: an alert email is required for the Bedrock spend budget." >&2
    echo "  ./deploy.sh --alert-email you@example.com   (or export ALERT_EMAIL=you@example.com)" >&2
    exit 1
fi

# Pricing-cycle timeouts: check them before anything is deployed, then export them
# so the agent deploy (orchestrator) and both CDK deploys (Lambda) use the same values.
export SPECIALIST_TIMEOUT_SECONDS="${SPECIALIST_TIMEOUT_SECONDS:-}"
export SYNTHESIS_TIMEOUT_SECONDS="${SYNTHESIS_TIMEOUT_SECONDS:-}"
if ! CYCLE_TIMEOUTS=$(python3 -m shared.cycle_timeouts); then
    exit 1
fi

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

# Audit a fully pinned requirements file with pip-audit and report exactly ONE of
# three truthful outcomes. It never fails the deploy (warn and continue), and it
# never prints a ✓ unless pip-audit itself reported a clean result.
#   $1  what is being scanned (used in the messages)
#   $2  fully pinned requirements file
#   $3  how to fix findings (printed when vulnerabilities are found)
scan_requirements() {
    local label="$1" req_file="$2" fix_hint="$3"
    local audit_log audit_status
    audit_log="$(mktemp "${TMPDIR:-/tmp}/rdp-pip-audit.XXXXXX")"

    # --no-deps/--disable-pip audit the pinned versions exactly as listed. The
    # default mode builds a temporary venv for every run (ensurepip), which
    # aborted with SIGABRT on some hosts. --strict makes a package that could not
    # be audited a failure instead of a silent skip.
    # The scanner's OWN exit status is tested: piping it into `tail` would test
    # tail's status instead and report success even when the scan crashed.
    if .venv/bin/pip-audit -r "$req_file" --no-deps --disable-pip --strict \
            --progress-spinner off > "$audit_log" 2>&1; then
        audit_status=0
    else
        audit_status=$?
    fi

    if [ "$audit_status" -eq 0 ] \
            && grep -q "No known vulnerabilities found" "$audit_log" \
            && ! grep -q "Skip Reason" "$audit_log"; then
        print_success "No known vulnerabilities found in $label"
    elif [ "$audit_status" -ne 0 ] && grep -Eq "Found [0-9]+ known vulnerabilit" "$audit_log"; then
        echo ""
        print_warning "KNOWN VULNERABILITIES found in $label:"
        sed -n '/Found [0-9]* known vulnerabilit/,$p' "$audit_log" | sed 's/^/      /'
        echo ""
        echo "      $fix_hint"
        print_warning "Deployment continuing with known vulnerabilities (review recommended)"
    else
        echo ""
        tail -n 20 "$audit_log" | sed 's/^/      /'
        echo ""
        print_warning "Dependency scan COULD NOT RUN for $label — pip-audit exit $audit_status; vulnerability status UNKNOWN"
        print_warning "Deployment continuing; run 'pip-audit' manually to check this dependency set"
    fi
    rm -f "$audit_log"
}

# The agent containers install backend/agents/agentcore/requirements.txt, which is
# intentionally unpinned (version floors only), and pip-audit rejects unpinned
# input. Ask pip's resolver what a container build would install right now (a dry
# run: nothing is installed) and audit that pinned set.
scan_container_requirements() {
    local label="agent container dependencies (resolved from backend/agents/agentcore/requirements.txt)"
    local work
    work="$(mktemp -d "${TMPDIR:-/tmp}/rdp-container-deps.XXXXXX")"

    if .venv/bin/pip install --dry-run --ignore-installed --quiet --disable-pip-version-check \
            --report "$work/report.json" -r backend/agents/agentcore/requirements.txt \
            > "$work/resolve.log" 2>&1 \
        && .venv/bin/python -c '
import json, sys
for item in json.load(open(sys.argv[1]))["install"]:
    meta = item["metadata"]
    print(meta["name"] + "==" + meta["version"])
' "$work/report.json" > "$work/pinned.txt"; then
        scan_requirements "$label" "$work/pinned.txt" \
            "Raise the version floor in backend/agents/agentcore/requirements.txt, then re-run deploy.sh."
    else
        tail -n 10 "$work/resolve.log" | sed 's/^/      /'
        echo ""
        print_warning "Dependency scan COULD NOT RUN for $label — dependency resolution failed; vulnerability status UNKNOWN"
    fi
    rm -rf "$work"
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
# Install the PINNED, validated dependency set first for reproducible builds,
# then install the local package itself (-e .). Installing requirements.txt
# first means every deploy uses the exact versions we validated end-to-end,
# rather than whatever pip resolves from the looser pyproject.toml ranges.
.venv/bin/pip install -r requirements.txt --quiet
.venv/bin/pip install -e . --no-deps --quiet
print_success "Dependencies installed (pinned from requirements.txt)"

# Step 1.5: Security — Dependency vulnerability scan
print_step "1.5" "Scanning dependencies for known vulnerabilities"
# The scan never blocks the deploy, but it reports the truth: clean, vulnerable
# (findings listed) or could-not-run (a warning, never a ✓).
if ! .venv/bin/pip install pip-audit --quiet; then
    print_warning "Dependency scan COULD NOT RUN (pip-audit failed to install) — vulnerability status UNKNOWN"
else
    # Audit the pinned requirements set (the versions actually deployed).
    scan_requirements "deployment dependencies (requirements.txt)" requirements.txt \
        "Update the pinned version(s) in requirements.txt (see 'Fix Versions'), reinstall, and re-run deploy.sh."
    # ...and the set the agent containers will install.
    if [ "$SKIP_AGENTS" = false ]; then
        scan_container_requirements
    fi
fi

# Step 1.7: Model Selection
print_step "1.7" "Selecting AI model (Bedrock)"
echo "Scanning available models and checking access..."
python3 scripts/select_model.py --region $REGION
print_success "Model selected — config written to model-config.json"

# Step 2: Deploy Infrastructure (CDK) — first pass
print_step "2" "Deploying infrastructure (CDK)"
npx cdk bootstrap aws://$ACCOUNT_ID/$REGION --app ".venv/bin/python3 cdk/app.py" 2>/dev/null || true
npx cdk deploy --all --require-approval never --app ".venv/bin/python3 cdk/app.py" -c alertEmail="$ALERT_EMAIL" --outputs-file cdk-outputs.json
print_success "CDK stacks deployed"

# Step 3: AgentCore prerequisites — IAM role, Gateway & Memory
# These must exist BEFORE the agents are deployed (Step 4): the agents are wired
# to them through runtime environment variables set at deploy time. They only need
# the MCP server Lambdas from Step 2, and the gateway needs the IAM role.
print_step "3" "Setting up AgentCore IAM role, Gateway & Memory"

python3 scripts/create_agentcore_role.py --region $REGION
print_success "IAM role created/updated"

# Auto-discover MCP Server Lambda ARNs
export COMPETITOR_API_LAMBDA_ARN=$(aws lambda get-function --function-name rdp-mcp-competitor-api --query "Configuration.FunctionArn" --output text --region $REGION 2>/dev/null || echo "")
export ERP_POS_LAMBDA_ARN=$(aws lambda get-function --function-name rdp-mcp-erp-pos --query "Configuration.FunctionArn" --output text --region $REGION 2>/dev/null || echo "")
export MARKET_SIGNALS_LAMBDA_ARN=$(aws lambda get-function --function-name rdp-mcp-market-signals --query "Configuration.FunctionArn" --output text --region $REGION 2>/dev/null || echo "")
export COST_FINANCE_LAMBDA_ARN=$(aws lambda get-function --function-name rdp-mcp-cost-finance --query "Configuration.FunctionArn" --output text --region $REGION 2>/dev/null || echo "")

if [ -n "$COMPETITOR_API_LAMBDA_ARN" ]; then
    # setup_gateway.py is idempotent (reuses an existing gateway/targets) and
    # exits 0 on success. A non-zero exit is a real failure, so let it stop the
    # deploy (set -e) rather than masking it — a silent gateway failure leaves
    # the agents with no MCP tools.
    python3 scripts/setup_gateway.py --region $REGION
    print_success "Gateway targets registered"
else
    echo "ERROR: MCP Server Lambdas (rdp-mcp-*) not found. CDK deploy (Step 2)"
    echo "       must complete before gateway setup. Aborting."
    exit 1
fi

# setup_memory.py is idempotent (reuses the existing memory) and exits 0 on
# success; a non-zero exit is a real failure and should stop the deploy.
python3 scripts/setup_memory.py --region $REGION
print_success "AgentCore Memory provisioned"

# Step 4: Deploy AgentCore Agents (wired to the gateway and memory from Step 3)
if [ "$SKIP_AGENTS" = false ]; then
    print_step "4" "Deploying AgentCore agents"
    # deploy_agentcore.py discovers the gateway and memory created in Step 3 and
    # sets AGENTCORE_GATEWAY_ENDPOINT / AGENTCORE_MEMORY_ID (plus the model IDs,
    # guardrail settings and, for the orchestrator, the specialist ARNs) as
    # environment variables on all 6 runtimes — on create AND update. It exits
    # non-zero (stopping the deploy) rather than deploy agents that are unwired.
    python3 scripts/deploy_agentcore.py \
        --region $REGION \
        --role-arn "arn:aws:iam::${ACCOUNT_ID}:role/RetailPricingAgentCoreRole"
    print_success "All 6 agents deployed, wired to the gateway and memory, and ACTIVE"
else
    print_warning "Skipping agent deployment (--skip-agents)"
fi

# Step 5: Re-deploy CDK (links orchestrator ARN to Lambda)
# Must run after Step 4: CDK reads scripts/agent_arns.env at synth time.
print_step "5" "Re-deploying CDK (linking agent ARNs)"
npx cdk deploy --all --require-approval never --app ".venv/bin/python3 cdk/app.py" -c alertEmail="$ALERT_EMAIL" --outputs-file cdk-outputs.json
print_success "Lambda updated with orchestrator ARN"

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

# Step 9.5: Verify the deployment is actually healthy before declaring success.
# This turns "the script finished" into "the deployment works" — a full deploy
# must pass verification, otherwise we exit non-zero so the failure is visible.
if [ "$SKIP_AGENTS" = false ] && [ "$SKIP_FRONTEND" = false ]; then
    print_step "9.5" "Verifying deployment"
    if python3 scripts/verify_deployment.py --region $REGION; then
        print_success "Deployment verification passed"
    else
        echo ""
        echo "ERROR: Deployment verification FAILED. The stack deployed but one or"
        echo "       more health checks did not pass. Review the output above before"
        echo "       using the demo. See docs/KNOWN_ISSUES.md for common causes."
        exit 1
    fi
else
    print_warning "Skipping deployment verification (partial deploy: --skip-agents/--skip-frontend)"
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
echo "  │  Budget alerts: $ALERT_EMAIL"
echo "  │  Cycle timeouts: $CYCLE_TIMEOUTS"
echo "  └─────────────────────────────────────────────────────────┘"
echo ""
echo "  Next: Open the Dashboard URL and log in to start the demo."
echo "  See docs/DEMO_SCRIPT.md for a guided walkthrough."
echo ""
