# Quick Start Guide

## CCOE Dynamic Pricing Solution for Retail Transformation

### Prerequisites

- AWS Account with Bedrock model access (Claude Sonnet 4, Claude Opus 4)
- AWS CLI configured with credentials
- Node.js 20+ and Python 3.12+
- Docker (for AgentCore agent deployment)
- AWS CDK CLI (`npm install -g aws-cdk`)

---

### 1. Clone and Setup

```bash
git clone <repository-url>
cd "Retail Dynamic Pricing"
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Deploy Infrastructure (CDK)

```bash
# Bootstrap CDK (first time only)
npx cdk bootstrap

# Deploy all stacks
npx cdk deploy --all --require-approval never
```

This creates:
- API Gateway + Lambda handlers
- DynamoDB tables (Products, PricingCycles, PricingScenarios, Approvals, AuditTrail)
- Cognito User Pool + Hosted UI domain
- CloudFront distributions (Dashboard + Storefront)
- S3 buckets for static hosting

Note the CDK outputs — you'll need: API Gateway URL, User Pool ID, Client ID, Cognito Domain, CloudFront URLs, S3 bucket names.

### 3. Deploy AgentCore Agents

```bash
# Create the IAM role for AgentCore
python3 scripts/create_agentcore_role.py --region us-east-1

# Deploy all 6 agents to AgentCore Runtime (requires Docker running)
python3 scripts/deploy_agentcore.py \
  --region us-east-1 \
  --role-arn arn:aws:iam::<ACCOUNT_ID>:role/RetailPricingAgentCoreRole
```

### 4. Re-deploy CDK (links agents to Lambda)

The agent deploy script saves ARNs to `scripts/agent_arns.env`. Re-deploy so the Lambda picks up the orchestrator ARN:

```bash
npx cdk deploy --all --require-approval never
```

### 5. Setup AgentCore Gateway & Memory

```bash
# Get MCP Server Lambda ARNs
aws lambda list-functions \
  --query "Functions[?starts_with(FunctionName,'rdp-mcp-')].[FunctionName,FunctionArn]" \
  --output table --region us-east-1

# Export them
export COMPETITOR_API_LAMBDA_ARN=<ARN for rdp-mcp-competitor-api>
export ERP_POS_LAMBDA_ARN=<ARN for rdp-mcp-erp-pos>
export MARKET_SIGNALS_LAMBDA_ARN=<ARN for rdp-mcp-market-signals>
export COST_FINANCE_LAMBDA_ARN=<ARN for rdp-mcp-cost-finance>

# Setup gateway and memory
python3 scripts/setup_gateway.py --region us-east-1
python3 scripts/setup_memory.py --region us-east-1
```

### 6. Seed Product Data

```bash
python3 scripts/seed_products.py
```

### 7. Create Cognito Demo Users

```bash
# Create demo user (PricingAnalysts group)
aws cognito-idp admin-create-user \
  --user-pool-id <USER_POOL_ID> \
  --username demo@example.com \
  --temporary-password TempPass123! \
  --user-attributes Name=email,Value=demo@example.com Name=email_verified,Value=true \
  --message-action SUPPRESS \
  --region us-east-1

aws cognito-idp admin-add-user-to-group \
  --user-pool-id <USER_POOL_ID> \
  --username demo@example.com \
  --group-name PricingAnalysts \
  --region us-east-1

# Create ops user (Operations group)
aws cognito-idp admin-create-user \
  --user-pool-id <USER_POOL_ID> \
  --username ops@example.com \
  --temporary-password TempPass123! \
  --user-attributes Name=email,Value=ops@example.com Name=email_verified,Value=true \
  --message-action SUPPRESS \
  --region us-east-1

aws cognito-idp admin-add-user-to-group \
  --user-pool-id <USER_POOL_ID> \
  --username ops@example.com \
  --group-name Operations \
  --region us-east-1
```

Note: MFA (TOTP) is REQUIRED. On first login, each user will be prompted to set a new password and configure their authenticator app.

### 8. Build and Deploy Frontends

```bash
# Dashboard
cd frontend/dashboard
cat > .env << EOF
VITE_API_URL=<API_GATEWAY_URL>
VITE_COGNITO_USER_POOL_ID=<USER_POOL_ID>
VITE_COGNITO_CLIENT_ID=<CLIENT_ID>
VITE_COGNITO_DOMAIN=<COGNITO_DOMAIN from CDK outputs>
EOF
npm install && npm run build
aws s3 sync dist/ s3://<DASHBOARD_BUCKET>/ --delete
cd ../..

# Storefront
cd frontend/storefront
echo "VITE_API_URL=<API_GATEWAY_URL>" > .env
npm install && npm run build
aws s3 sync dist/ s3://<STOREFRONT_BUCKET>/ --delete
cd ../..
```

### 9. Update Cognito Callback URLs

```bash
aws cognito-idp update-user-pool-client \
  --user-pool-id <USER_POOL_ID> \
  --client-id <CLIENT_ID> \
  --callback-urls '["https://<DASHBOARD_CLOUDFRONT_DOMAIN>/callback"]' \
  --logout-urls '["https://<DASHBOARD_CLOUDFRONT_DOMAIN>"]' \
  --allowed-o-auth-flows "code" "implicit" \
  --allowed-o-auth-scopes "openid" "email" "profile" \
  --supported-identity-providers "COGNITO" \
  --allowed-o-auth-flows-user-pool-client \
  --region us-east-1
```

### 10. Access the Demo

- **Dashboard:** `https://<DASHBOARD_CLOUDFRONT_DOMAIN>`
- **Storefront:** `https://<STOREFRONT_CLOUDFRONT_DOMAIN>`
- **Login:** `demo@example.com` / `TempPass123!` (first login will prompt for password change + MFA setup)

On first login:
1. Enter the temporary password
2. Set a new permanent password (12+ chars, uppercase, lowercase, digit, symbol)
3. Scan the QR code with an authenticator app (Google Authenticator, Authy, 1Password)
4. Enter the 6-digit TOTP code to complete setup
5. Subsequent logins require password + TOTP code

---

### Useful Commands

```bash
# List CDK outputs
aws cloudformation describe-stacks --stack-name RetailDynamicPricing \
  --query "Stacks[0].Outputs[*].[OutputKey,OutputValue]" --output table --region us-east-1

# Find S3 bucket names
aws s3 ls | grep retail

# Rebuild and redeploy Dashboard
cd frontend/dashboard && npm run build && cd ../..
aws s3 sync frontend/dashboard/dist/ s3://<DASHBOARD_BUCKET>/ --delete

# Clear CloudFront cache
aws cloudfront create-invalidation --distribution-id <DIST_ID> --paths "/*"

# Re-seed products
python3 scripts/seed_products.py

# Redeploy agents
python3 scripts/deploy_agentcore.py --region us-east-1 \
  --role-arn arn:aws:iam::<ACCOUNT_ID>:role/RetailPricingAgentCoreRole
```

---

### Troubleshooting

See [docs/KNOWN_ISSUES.md](KNOWN_ISSUES.md) for detailed deployment issues and resolutions.

| Issue | Solution |
|-------|----------|
| CDK can't find aws_cdk module | Ensure venv is active; use `--app ".venv/bin/python3 cdk/app.py"` if path has spaces |
| ECR permission error on agent deploy | Fixed in `create_agentcore_role.py` — uses `retail-pricing/*` resource path |
| Gateway target registration fails | Wait 30s after gateway creation, then re-run `setup_gateway.py` |
| CORS error on /billing or /reset | Route must exist in API Gateway CDK — verify with `npx cdk deploy` |
| Login redirect_mismatch | Update callback URLs (Step 9) with actual CloudFront domain |
| Pricing cycle AccessDenied | Lambda needs DynamoDB Scan/BatchWriteItem + AgentCore InvokeAgentRuntime |
| Cost Explorer shows $0 | Normal — 24-48 hour delay on billing data |
