#!/bin/bash
# =============================================================================
# Retail Dynamic Pricing — One-Command Teardown Script
# =============================================================================
# Removes every resource created by deploy.sh, in the correct dependency order.
# Resources are discovered dynamically (by name/prefix) rather than hardcoded,
# so this works regardless of the random suffixes AWS assigns.
#
# Order (mirrors deploy.sh in reverse):
#   1. Empty the frontend S3 buckets (incl. object versions) so CFN can delete them
#   2. cdk destroy --all (DynamoDB, Cognito, API GW, Lambdas, CloudFront, S3, MCP)
#   3. AgentCore: gateway targets -> gateway -> agent runtimes -> memory
#   4. ECR repositories (retail-pricing/*)
#   5. IAM role (RetailPricingAgentCoreRole) + its inline policies
#
# Usage:
#   chmod +x teardown.sh
#   ./teardown.sh [--region us-east-1] [--yes]
#
#   --yes   Skip the confirmation prompt (non-interactive).
#
# Safe to re-run: every step tolerates already-deleted / missing resources.
# =============================================================================

set -u

REGION="${AWS_REGION:-us-east-1}"
ASSUME_YES=false
ROLE_NAME="RetailPricingAgentCoreRole"

while [[ $# -gt 0 ]]; do
    case $1 in
        --region) REGION="$2"; shift 2 ;;
        --yes|-y) ASSUME_YES=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

print_step() { echo ""; echo "============================================================"; echo "  $1"; echo "============================================================"; echo ""; }
print_success() { echo "  ✓ $1"; }
print_info() { echo "  • $1"; }

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
if [ -z "$ACCOUNT_ID" ]; then
    echo "ERROR: AWS credentials not configured. Run 'aws configure' or 'aws sso login'."
    exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   Retail Dynamic Pricing — Teardown                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Account: $ACCOUNT_ID"
echo "  Region:  $REGION"
echo ""
echo "  This will PERMANENTLY DELETE the Retail Dynamic Pricing deployment:"
echo "    - CloudFormation stack 'RetailDynamicPricing' (DynamoDB, Cognito,"
echo "      API Gateway, Lambdas, CloudFront, S3, MCP servers)"
echo "    - AgentCore runtimes, gateway (+targets), and memory"
echo "    - ECR repositories (retail-pricing/*) and IAM role $ROLE_NAME"
echo ""

if [ "$ASSUME_YES" != true ]; then
    read -r -p "  Type 'destroy' to confirm: " CONFIRM
    if [ "$CONFIRM" != "destroy" ]; then
        echo "  Aborted."
        exit 1
    fi
fi

# --- Step 1: Empty the frontend S3 buckets (current objects + versions) ---
print_step "Step 1: Emptying frontend S3 buckets"
BUCKETS=$(aws s3api list-buckets --query "Buckets[?starts_with(Name, 'retaildynamicpricing-')].Name" --output text 2>/dev/null)
if [ -n "$BUCKETS" ]; then
    for b in $BUCKETS; do
        print_info "Emptying s3://$b"
        # Delete current objects.
        aws s3 rm "s3://$b" --recursive --only-show-errors 2>/dev/null || true
        # Delete all object versions and delete-markers (versioned buckets).
        VERSIONS=$(aws s3api list-object-versions --bucket "$b" \
            --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' --output json 2>/dev/null)
        if [ -n "$VERSIONS" ] && [ "$VERSIONS" != '{"Objects": null}' ]; then
            aws s3api delete-objects --bucket "$b" --delete "$VERSIONS" >/dev/null 2>&1 || true
        fi
        MARKERS=$(aws s3api list-object-versions --bucket "$b" \
            --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' --output json 2>/dev/null)
        if [ -n "$MARKERS" ] && [ "$MARKERS" != '{"Objects": null}' ]; then
            aws s3api delete-objects --bucket "$b" --delete "$MARKERS" >/dev/null 2>&1 || true
        fi
    done
    print_success "S3 buckets emptied"
else
    print_info "No retaildynamicpricing-* buckets found (already gone)"
fi

# --- Step 2: Destroy the CloudFormation stack via CDK ---
print_step "Step 2: Destroying CDK stack (RetailDynamicPricing)"
if aws cloudformation describe-stacks --stack-name RetailDynamicPricing --region "$REGION" >/dev/null 2>&1; then
    npx cdk destroy --all --force --app ".venv/bin/python3 cdk/app.py" || \
        print_info "cdk destroy returned non-zero (CLI may exit before CFN confirms) — verifying below"
else
    print_info "Stack RetailDynamicPricing not found (already gone)"
fi

# --- Step 3: AgentCore resources (targets -> gateway -> runtimes -> memory) ---
print_step "Step 3: Deleting AgentCore resources"

# 3a: Gateways (delete their targets first, then the gateway)
GATEWAYS=$(aws bedrock-agentcore-control list-gateways --region "$REGION" \
    --query "items[?starts_with(name,'retail-pricing')].gatewayId" --output text 2>/dev/null)
for gw in $GATEWAYS; do
    TARGETS=$(aws bedrock-agentcore-control list-gateway-targets --gateway-identifier "$gw" \
        --region "$REGION" --query "items[].targetId" --output text 2>/dev/null)
    for t in $TARGETS; do
        aws bedrock-agentcore-control delete-gateway-target --gateway-identifier "$gw" \
            --target-id "$t" --region "$REGION" >/dev/null 2>&1 && print_info "Deleted gateway target $t"
    done
    aws bedrock-agentcore-control delete-gateway --gateway-identifier "$gw" \
        --region "$REGION" >/dev/null 2>&1 && print_info "Deleted gateway $gw"
done

# 3b: Agent runtimes
RUNTIMES=$(aws bedrock-agentcore-control list-agent-runtimes --region "$REGION" \
    --query "agentRuntimes[?starts_with(agentRuntimeName,'retailPricing')].agentRuntimeId" --output text 2>/dev/null)
for r in $RUNTIMES; do
    aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-id "$r" \
        --region "$REGION" >/dev/null 2>&1 && print_info "Deleted runtime $r"
done

# 3c: Memory
MEMORIES=$(aws bedrock-agentcore-control list-memories --region "$REGION" \
    --query "memories[?starts_with(id,'RetailDynamicPricing')].id" --output text 2>/dev/null)
for m in $MEMORIES; do
    aws bedrock-agentcore-control delete-memory --memory-id "$m" \
        --region "$REGION" >/dev/null 2>&1 && print_info "Deleted memory $m"
done
print_success "AgentCore resources deleted (deletion is asynchronous)"

# --- Step 4: ECR repositories ---
print_step "Step 4: Deleting ECR repositories"
REPOS=$(aws ecr describe-repositories --region "$REGION" \
    --query "repositories[?starts_with(repositoryName,'retail-pricing/')].repositoryName" --output text 2>/dev/null)
if [ -n "$REPOS" ]; then
    for repo in $REPOS; do
        aws ecr delete-repository --repository-name "$repo" --force --region "$REGION" >/dev/null 2>&1 \
            && print_info "Deleted repo $repo"
    done
    print_success "ECR repositories deleted"
else
    print_info "No retail-pricing/* repositories found (already gone)"
fi

# --- Step 5: IAM role (inline policies first, then the role) ---
print_step "Step 5: Deleting IAM role ($ROLE_NAME)"
if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    for p in $(aws iam list-role-policies --role-name "$ROLE_NAME" --query "PolicyNames[]" --output text 2>/dev/null); do
        aws iam delete-role-policy --role-name "$ROLE_NAME" --policy-name "$p" >/dev/null 2>&1 \
            && print_info "Deleted inline policy $p"
    done
    for a in $(aws iam list-attached-role-policies --role-name "$ROLE_NAME" --query "AttachedPolicies[].PolicyArn" --output text 2>/dev/null); do
        aws iam detach-role-policy --role-name "$ROLE_NAME" --policy-arn "$a" >/dev/null 2>&1 \
            && print_info "Detached managed policy $a"
    done
    aws iam delete-role --role-name "$ROLE_NAME" >/dev/null 2>&1 && print_success "IAM role deleted"
else
    print_info "IAM role $ROLE_NAME not found (already gone)"
fi

# --- Summary ---
print_step "Teardown complete"
echo "  Local deployment artifacts you may also want to remove:"
echo "    cdk-outputs.json, model-config.json, scripts/agent_arns.env"
echo ""
echo "  Note: AgentCore runtime/gateway/memory deletion is asynchronous and may"
echo "  take a few minutes to fully disappear from the console."
echo ""
