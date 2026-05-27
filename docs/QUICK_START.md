# Quick Start Guide

## Dynamic Pricing for Retail — Agentic AI Solution

### Prerequisites

- AWS Account with Bedrock model access (Claude Sonnet 4, Claude Opus 4)
- AWS CLI configured with credentials
- Node.js 18+ and Python 3.12+
- Docker (for AgentCore agent deployment)

---

### 1. Clone and Setup

```bash
git clone <repository-url>
cd "Retail Dynamic Pricing"
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
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
- DynamoDB tables (Products, PricingCycles, PricingScenarios, Approvals)
- Cognito User Pool + Hosted UI
- CloudFront distributions (Dashboard + Storefront)
- S3 buckets for static hosting

### 3. Deploy AgentCore Agents

```bash
# Create the IAM role for AgentCore
python scripts/create_agentcore_role.py --region us-east-1

# Deploy all 6 agents to AgentCore Runtime
python scripts/deploy_agentcore.py \
  --region us-east-1 \
  --role-arn arn:aws:iam::<ACCOUNT_ID>:role/RetailPricingAgentCoreRole
```

### 4. Setup AgentCore Gateway & Memory

```bash
python scripts/setup_gateway.py --region us-east-1
python scripts/setup_memory.py --region us-east-1
```

### 5. Seed Product Data

```bash
python scripts/seed_products.py
```

### 6. Create Cognito User

```bash
aws cognito-idp admin-create-user \
  --user-pool-id <USER_POOL_ID> \
  --username demo@example.com \
  --temporary-password TempPass123! \
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password \
  --user-pool-id <USER_POOL_ID> \
  --username demo@example.com \
  --password DemoPass123! \
  --permanent
```

### 7. Build and Deploy Frontends

```bash
# Dashboard
cd frontend/dashboard
echo "VITE_API_URL=<API_GATEWAY_URL>" > .env
echo "VITE_COGNITO_USER_POOL_ID=<POOL_ID>" >> .env
echo "VITE_COGNITO_CLIENT_ID=<CLIENT_ID>" >> .env
echo "VITE_COGNITO_DOMAIN=<COGNITO_DOMAIN>" >> .env
npm install && npm run build
cd ../..

# Storefront
cd frontend/storefront
echo "VITE_API_URL=<API_GATEWAY_URL>" > .env
npm install && npm run build
cd ../..

# Upload to S3
aws s3 sync frontend/dashboard/dist/ s3://<DASHBOARD_BUCKET>/ --delete
aws s3 sync frontend/storefront/dist/ s3://<STOREFRONT_BUCKET>/ --delete
```

### 8. Update Lambda with Orchestrator ARN

```bash
aws lambda update-function-configuration \
  --function-name rdp-api-pricing-cycles \
  --environment "Variables={...,ORCHESTRATOR_AGENT_ARN=<ARN>}"
```

### 9. Access the Demo

- **Dashboard:** `https://<DASHBOARD_CLOUDFRONT>.cloudfront.net`
- **Storefront:** `https://<STOREFRONT_CLOUDFRONT>.cloudfront.net`
- **Login:** `demo@example.com` / `DemoPass123!`

---

### Useful Commands

```bash
# Redeploy Lambda code
zip -j /tmp/handlers.zip backend/api_handlers/*.py
aws lambda update-function-code --function-name rdp-api-pricing-cycles --zip-file fileb:///tmp/handlers.zip

# Redeploy Dashboard
cd frontend/dashboard && npm run build && cd ../..
aws s3 sync frontend/dashboard/dist/ s3://<BUCKET>/ --delete
aws cloudfront create-invalidation --distribution-id <DIST_ID> --paths "/*"

# Re-seed products
python scripts/seed_products.py

# Redeploy agents
python scripts/deploy_agentcore.py --region us-east-1 --role-arn <ROLE_ARN>
```

---

### Troubleshooting

| Issue | Solution |
|-------|----------|
| 504 Gateway Timeout | Lambda timeout too low — should be 300s |
| CORS error | Check API Gateway CORS origins match CloudFront domains |
| No module 'backend' | Lambda handlers must be self-contained (no cross-package imports) |
| AccessDeniedException on AgentCore | Add `bedrock-agentcore:*` to Lambda role |
| Scenarios not auto-approving | Check `dynamodb:UpdateItem` permission on PricingScenarios table |
| Cost Explorer shows $0 | Normal — 24-48 hour delay on billing data |
