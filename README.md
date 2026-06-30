# Retail Dynamic Pricing — Agentic AI Solution

An agentic AI system that transforms retail pricing from a manual 6-10 week process into an autonomous workflow that completes in under 2 minutes. Built on **Amazon Bedrock AgentCore** with 6 specialized AI agents that gather market intelligence, analyze demand, and generate optimized pricing recommendations with human-in-the-loop approval.

## What It Does

- **Orchestrates 6 AI agents** to analyze competitive landscape, forecast demand, assess market conditions, synthesize pricing strategies, and monitor implementation
- **Generates ranked pricing scenarios** with confidence scores, risk classification, and projected financial impact
- **Enforces compliance** via Amazon Bedrock Guardrails (blocks predatory pricing, price fixing, discrimination, gouging)
- **Routes approvals by risk level** — LOW risk auto-approved (Straight-Through Processing), MEDIUM/HIGH routed to humans
- **Provides full audit trail** for regulatory compliance (FTC, Robinson-Patman Act, EU Omnibus Directive)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  User Layer                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
│  │  Dashboard   │  │  Storefront  │  │ CloudFront│  │  Cognito  │  │
│  │  (React/TS)  │  │  (React/TS)  │  │  (CDN)   │  │  (Auth)   │  │
│  └──────────────┘  └──────────────┘  └──────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────────┐
│  API Layer                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  API Gateway     │  │  Lambda Handlers  │  │  DynamoDB        │  │
│  │  (REST)          │  │  (Python 3.12)    │  │  (4 tables)      │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────────┐
│  AgentCore Layer                                                    │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────┐  │
│  │Orchestrator│ │Competitive │ │  Demand    │ │    Market      │  │
│  │(Opus 4)    │ │Intel (S4)  │ │Forecast(S4)│ │  Intel (S4)    │  │
│  └────────────┘ └────────────┘ └────────────┘ └────────────────┘  │
│  ┌────────────────────┐ ┌────────────────────────────────────────┐ │
│  │Strategy Synth (S4) │ │ Implementation Monitoring (S4)         │ │
│  └────────────────────┘ └────────────────────────────────────────┘ │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Bedrock Guardrails│  │AgentCore Mem │  │ AgentCore Gateway    │ │
│  └──────────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────────┐
│  Data Layer (MCP Servers on Lambda)                                 │
│  ┌──────────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │Competitor API│ │ ERP/POS  │ │Market Signals│ │Cost & Finance│  │
│  └──────────────┘ └──────────┘ └──────────────┘ └──────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent Framework | Strands Agents SDK on AgentCore | Native AWS, MCP support, managed infra |
| Data Integration | MCP Servers on Lambda | Standardized tool protocol, serverless |
| Frontend | React/TS + Vite + Tailwind | Fast iteration, type safety |
| Data Store | DynamoDB (on-demand) | Serverless, pay-per-request |
| Auth | Amazon Cognito | Managed auth, JWT, API Gateway integration |
| IaC | AWS CDK (Python) | Reproducible, automatic rollback |
| Models | Claude Opus 4 / Sonnet 4 | Best reasoning + cost-effective analysis |

---

## Project Structure

```
├── backend/
│   ├── agents/                 # Agent definitions
│   │   ├── agentcore/          # AgentCore Runtime containers (Dockerized)
│   │   ├── orchestrator.py     # Orchestrator agent logic
│   │   ├── competitive_intelligence.py
│   │   ├── demand_forecasting.py
│   │   ├── market_intelligence.py
│   │   ├── strategy_synthesis.py
│   │   ├── implementation_monitoring.py
│   │   └── testing_harness.py  # Individual agent test harness
│   ├── api_handlers/           # Lambda handlers for API Gateway
│   │   ├── pricing_cycles.py   # Initiate/get pricing cycles
│   │   ├── scenarios.py        # List/get scenarios
│   │   ├── approvals.py        # Approve/reject/revert scenarios
│   │   ├── products.py         # Product catalog (public)
│   │   ├── monitoring.py       # Implementation monitoring
│   │   └── agents_status.py    # Agent execution status
│   ├── mcp_servers/            # MCP Server Lambda functions
│   │   ├── competitor_api/     # Competitor pricing data
│   │   ├── erp_pos/            # Sales history, inventory, elasticity
│   │   ├── market_signals/     # Market trends, sentiment
│   │   └── cost_finance/       # COGS, margins, financial rules
│   └── orchestration/          # Cross-cutting orchestration concerns
│       ├── memory.py           # AgentCore Memory integration
│       ├── observability.py    # OpenTelemetry instrumentation
│       ├── persistence.py      # DynamoDB persistence
│       ├── resilience.py       # Retry/circuit breaker patterns
│       └── session_manager.py  # Agent session management
├── cdk/                        # AWS CDK infrastructure (Python)
│   ├── app.py                  # CDK app entry point
│   └── stacks/                 # CDK stack constructs
├── frontend/
│   ├── dashboard/              # Product Manager dashboard (React/TS, Cognito auth)
│   └── storefront/             # Consumer storefront (React/TS, public)
├── shared/                     # Shared business logic and data models
│   ├── models/                 # Pydantic data models
│   ├── guardrails.py           # Pricing guardrails engine
│   ├── risk_classification.py  # Risk level classification
│   ├── approval_routing.py     # HITL routing logic
│   ├── scenario_ranking.py     # Composite scoring and ranking
│   ├── variance_detection.py   # Post-implementation variance detection
│   └── sigv4_client.py         # SigV4 HTTP client for AgentCore
├── scripts/                    # Deployment and setup scripts
│   ├── deploy_agentcore.py     # Deploy agents to AgentCore Runtime
│   ├── deploy_agentcore.sh     # Shell wrapper for full agent deployment
│   ├── create_agentcore_role.py # Create IAM role for agents
│   ├── setup_gateway.py        # Register MCP Server targets on Gateway
│   ├── setup_memory.py         # Provision AgentCore Memory
│   ├── seed_products.py        # Seed DynamoDB product catalog
│   └── seed_demo_cycles.py     # Seed sample pricing cycles
├── tests/                      # Unit and property-based tests
├── docs/                       # Documentation
├── cdk.json                    # CDK configuration
└── pyproject.toml              # Python project dependencies
```

---

## Prerequisites

- **Python 3.12+**
- **Node.js 20+** (for frontends and CDK CLI)
- **Docker** (for building AgentCore agent containers)
- **AWS CDK CLI** (`npm install -g aws-cdk`)
- **AWS CLI** configured with credentials
- **AWS Account** with access to:
  - Amazon Bedrock (Claude Sonnet 4, Claude Opus 4)
  - Amazon Bedrock AgentCore (Runtime, Gateway, Memory)

---

## Cost Disclaimer

> You are responsible for the cost of the AWS services used while running this sample deployment. There is no additional cost for using this sample. For full details, see the pricing pages for each AWS service you will be using in this sample. Prices are subject to change.

---

## Setup & Deployment

### 1. Clone and Install

```bash
git clone <REPOSITORY_URL>
cd "Retail Dynamic Pricing"

# Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Deploy Infrastructure (CDK)

```bash
# Bootstrap CDK (first time only)
npx cdk bootstrap

# Deploy all stacks (DynamoDB, Cognito, API Gateway, Lambda, CloudFront, S3)
npx cdk deploy --all --require-approval never
```

Note the outputs: API Gateway URL, Cognito User Pool ID, Client ID, CloudFront domains, S3 bucket names.

### 3. Deploy AgentCore Agents

```bash
# Create IAM role for AgentCore
python scripts/create_agentcore_role.py --region us-east-1

# Deploy all 6 agents to AgentCore Runtime
python scripts/deploy_agentcore.py \
  --region us-east-1 \
  --role-arn arn:aws:iam::<ACCOUNT_ID>:role/RetailPricingAgentCoreRole
```

### 4. Re-deploy CDK (links agents to Lambda)

The agent deploy script saves agent ARNs to `scripts/agent_arns.env`. Re-deploy CDK
so the pricing cycles Lambda picks up the orchestrator ARN:

```bash
npx cdk deploy --all --require-approval never
```

### 5. Setup AgentCore Gateway & Memory

```bash
# Export MCP Server Lambda ARNs (get from: aws lambda list-functions --query "Functions[?starts_with(FunctionName,'rdp-mcp-')].[FunctionName,FunctionArn]" --output table)
export COMPETITOR_API_LAMBDA_ARN=<ARN for rdp-mcp-competitor-api>
export ERP_POS_LAMBDA_ARN=<ARN for rdp-mcp-erp-pos>
export MARKET_SIGNALS_LAMBDA_ARN=<ARN for rdp-mcp-market-signals>
export COST_FINANCE_LAMBDA_ARN=<ARN for rdp-mcp-cost-finance>

python scripts/setup_gateway.py --region us-east-1
python scripts/setup_memory.py --region us-east-1
```

### 6. Seed Data

```bash
python scripts/seed_products.py
```

### 7. Create Cognito Demo User

```bash
aws cognito-idp admin-create-user \
  --user-pool-id <COGNITO_USER_POOL_ID> \
  --username demo@example.com \
  --temporary-password TempPass123! \
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password \
  --user-pool-id <COGNITO_USER_POOL_ID> \
  --username demo@example.com \
  --password <COGNITO_DEMO_PASSWORD> \
  --permanent
```

### 8. Build and Deploy Frontends

```bash
# Dashboard
cd frontend/dashboard
cat > .env << EOF
VITE_API_URL=<API_GATEWAY_URL>
VITE_COGNITO_USER_POOL_ID=<COGNITO_USER_POOL_ID>
VITE_COGNITO_CLIENT_ID=<COGNITO_CLIENT_ID>
VITE_COGNITO_DOMAIN=<COGNITO_DOMAIN>
EOF
npm install && npm run build
aws s3 sync dist/ s3://<DASHBOARD_S3_BUCKET>/ --delete
cd ../..

# Storefront
cd frontend/storefront
echo "VITE_API_URL=<API_GATEWAY_URL>" > .env
npm install && npm run build
aws s3 sync dist/ s3://<STOREFRONT_S3_BUCKET>/ --delete
cd ../..
```

### 9. Update Cognito Callback URLs

After deploying frontends, update the Cognito app client with the actual CloudFront URL:

```bash
aws cognito-idp update-user-pool-client \
  --user-pool-id <COGNITO_USER_POOL_ID> \
  --client-id <COGNITO_CLIENT_ID> \
  --callback-urls '["https://<DASHBOARD_CLOUDFRONT_DOMAIN>/callback"]' \
  --logout-urls '["https://<DASHBOARD_CLOUDFRONT_DOMAIN>"]' \
  --allowed-o-auth-flows "code" "implicit" \
  --allowed-o-auth-scopes "openid" "email" "profile" \
  --supported-identity-providers "COGNITO" \
  --allowed-o-auth-flows-user-pool-client \
  --region us-east-1
```

### 10. Access the Demo

| Resource | URL |
|----------|-----|
| Dashboard | `https://<DASHBOARD_CLOUDFRONT_DOMAIN>` |
| Storefront | `https://<STOREFRONT_CLOUDFRONT_DOMAIN>` |
| Login | `<COGNITO_DEMO_USER>` / `<COGNITO_DEMO_PASSWORD>` |

---

## Running the Demo

1. **Open Dashboard** → Log in with Cognito credentials
2. **Simulations tab** → Select a scenario preset (e.g., "Competitor Price War")
3. **Watch the pipeline** → 6 agents execute in under 2 minutes
4. **Review scenarios** → 3 ranked recommendations with risk levels
5. **Approve/Reject** → HIGH risk requires justification, LOW risk auto-approves
6. **Check Storefront** → Prices update in real-time after approval
7. **Guardrails Demo** → Scroll to "🛡️ Guardrails Enforcement" section, click any card to see compliance blocking in action (below-cost, MAP, geographic bias, predatory pricing, PII, price fixing)

See [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) for a detailed 5-minute demo walkthrough.

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /pricing-cycles | Cognito | Initiate a pricing cycle |
| GET | /pricing-cycles | Cognito | List all pricing cycles |
| GET | /pricing-cycles/{id} | Cognito | Get cycle status |
| GET | /pricing-cycles/{id}/scenarios | Cognito | List scenarios (paginated) |
| POST | /approvals | Cognito | Approve/reject a scenario |
| GET | /agents/status | Cognito | Agent execution status |
| GET | /monitoring/{scenarioId} | Cognito | Monitoring metrics |
| GET | /billing | Cognito | AWS Cost Explorer data |
| POST | /reset | Cognito | Reset demo data |
| POST | /seed | Cognito | Seed historical demo data |
| GET | /products | Public | Product catalog |
| GET | /products/{id} | Public | Single product detail |
| POST | /guardrails/demo | Cognito | Guardrails enforcement demo |

---

## Testing

```bash
# Run all tests (unit + property-based)
PYTHONPATH=. pytest tests/ -v

# Run only property-based tests
PYTHONPATH=. pytest tests/test_prop_*.py -v

# Run agent integration tests (requires deployed agents)
PYTHONPATH=. python -m backend.agents.testing_harness
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Full architecture, data flow, agent design |
| [docs/QUICK_START.md](docs/QUICK_START.md) | Setup and deployment instructions |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | 5-minute demo walkthrough |
| [docs/GUIDANCE_ALIGNMENT.md](docs/GUIDANCE_ALIGNMENT.md) | Mapping to AWS Guidance Paper |
| [docs/TCO_ESTIMATE.md](docs/TCO_ESTIMATE.md) | Total Cost of Ownership analysis |
| [docs/agent_testing_guide.md](docs/agent_testing_guide.md) | Agent testing procedures |
| [docs/SYSTEM_DEEP_DIVE.md](docs/SYSTEM_DEEP_DIVE.md) | Full system analysis, demo walkthroughs, Well-Architected alignment |
| [docs/GLOSSARY.md](docs/GLOSSARY.md) | Industry terms, abbreviations, and definitions |
| [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) | Deployment issues and resolutions |

---

## Cost

- **Per pricing cycle:** ~$0.25 (dominated by Bedrock model invocations)
- **Monthly at demo scale (~50 cycles):** ~$30
- **Infrastructure (serverless):** ~$10-25/month fixed

See [docs/TCO_ESTIMATE.md](docs/TCO_ESTIMATE.md) for full breakdown and scaling projections.

---

## Teardown

```bash
# Destroy CDK stacks
npx cdk destroy --all

# Delete AgentCore resources
python scripts/deploy_agentcore.py --delete --region us-east-1
aws bedrock delete-guardrail --guardrail-identifier <GUARDRAIL_ID> --region us-east-1
```

---

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

---

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file.
