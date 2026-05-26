# Retail Dynamic Pricing - Deployment Guide

Complete deployment sequence for the Retail Dynamic Pricing multi-agent system using AWS Bedrock AgentCore.

## Prerequisites

- AWS CLI configured with appropriate credentials
- Python 3.12+
- Docker (for building agent containers)
- AWS CDK CLI (`npm install -g aws-cdk`)
- Node.js 18+ (for CDK and frontends)

## Deployment Sequence

### 1. Create IAM Role

Create the IAM execution role for AgentCore Runtime agents:

```bash
python scripts/create_agentcore_role.py
```

This creates a role with permissions for:
- Bedrock model invocation
- AgentCore Memory read/write
- AgentCore Gateway access
- DynamoDB access for pricing data
- CloudWatch Logs for observability

### 2. Setup AgentCore Memory

Provision the shared memory resource that agents use to persist pricing outcomes and learning:

```bash
python scripts/setup_memory.py --region us-east-1
```

This outputs a `AGENTCORE_MEMORY_ID` — export it for subsequent steps:

```bash
export AGENTCORE_MEMORY_ID=<memory-id-from-output>
```

### 3. Deploy CDK Infrastructure

Deploy the core infrastructure (DynamoDB tables, Lambda MCP Servers, Cognito, API Gateway):

```bash
cd cdk
cdk deploy --all
```

After deployment, note the Lambda ARNs from the CDK outputs for the gateway setup.

### 4. Setup AgentCore Gateway

Register the MCP Server Lambda functions as gateway targets:

```bash
export COMPETITOR_API_LAMBDA_ARN=<from-cdk-output>
export ERP_POS_LAMBDA_ARN=<from-cdk-output>
export MARKET_SIGNALS_LAMBDA_ARN=<from-cdk-output>
export COST_FINANCE_LAMBDA_ARN=<from-cdk-output>

python scripts/setup_gateway.py --region us-east-1
```

Note the gateway endpoint URL from the output:

```bash
export AGENTCORE_GATEWAY_ENDPOINT=<gateway-endpoint-url>
```

### 5. Deploy Agents to AgentCore Runtime

Build and deploy agent containers:

```bash
./scripts/deploy_agentcore.sh
```

This script:
- Builds Docker images for each agent (with OpenTelemetry instrumentation)
- Pushes to ECR
- Registers/updates AgentCore Runtime agents
- Configures environment variables including `AGENTCORE_MEMORY_ID` and `AGENTCORE_GATEWAY_ENDPOINT`

### 6. Seed Products

Populate the DynamoDB product catalog with initial data:

```bash
python scripts/seed_products.py
```

### 7. Create Cognito User

Create an initial user in the Cognito User Pool for dashboard access:

```bash
aws cognito-idp admin-create-user \
  --user-pool-id <user-pool-id> \
  --username <email> \
  --user-attributes Name=email,Value=<email> \
  --temporary-password <temp-password>
```

### 8. Configure and Deploy Frontends

Deploy the pricing dashboard and approval UI:

```bash
cd frontend
npm install
npm run build
# Deploy to S3/CloudFront or your hosting solution
```

## Environment Variables Reference

| Variable | Description | Set By |
|----------|-------------|--------|
| `AGENTCORE_MEMORY_ID` | Memory resource ID | `setup_memory.py` |
| `AGENTCORE_GATEWAY_ENDPOINT` | Gateway endpoint URL | `setup_gateway.py` |
| `AWS_REGION` | AWS region | Manual |
| `COMPETITOR_API_LAMBDA_ARN` | Competitor API Lambda ARN | CDK output |
| `ERP_POS_LAMBDA_ARN` | ERP/POS Lambda ARN | CDK output |
| `MARKET_SIGNALS_LAMBDA_ARN` | Market Signals Lambda ARN | CDK output |
| `COST_FINANCE_LAMBDA_ARN` | Cost/Finance Lambda ARN | CDK output |
| `COMPETITIVE_INTELLIGENCE_AGENT_ARN` | CI agent runtime ARN | AgentCore deploy |
| `DEMAND_FORECASTING_AGENT_ARN` | DF agent runtime ARN | AgentCore deploy |
| `MARKET_INTELLIGENCE_AGENT_ARN` | MI agent runtime ARN | AgentCore deploy |
| `STRATEGY_SYNTHESIS_AGENT_ARN` | SS agent runtime ARN | AgentCore deploy |
| `IMPLEMENTATION_MONITORING_AGENT_ARN` | IM agent runtime ARN | AgentCore deploy |

## Observability

All agents are instrumented with OpenTelemetry via `aws-opentelemetry-distro`. Traces and metrics are automatically exported to AWS X-Ray and CloudWatch when running in AgentCore Runtime.

The Dockerfile CMD uses `opentelemetry-instrument` to auto-instrument the application:

```dockerfile
CMD opentelemetry-instrument python -m uvicorn backend.agents.agentcore.${AGENT_ENTRYPOINT}:app --host 0.0.0.0 --port 8080
```

## Troubleshooting

### Memory not working
- Verify `AGENTCORE_MEMORY_ID` is set in the agent container environment
- Check that the IAM role has `bedrock-agentcore:*Memory*` permissions
- Memory is optional — agents function without it but lose cross-session learning

### Gateway connection failures
- Verify `AGENTCORE_GATEWAY_ENDPOINT` is set
- Ensure Lambda functions are deployed and accessible
- Check gateway target synchronization status in the AgentCore console

### Agent invocation timeouts
- Default timeout is 120s per agent invocation
- The orchestrator retries up to 2 times per intelligence agent
- Check CloudWatch Logs for individual agent errors
