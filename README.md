# Retail Dynamic Pricing — Agentic AI Solution

> An agentic AI system that transforms retail pricing from a manual 6-10 week process into an autonomous, governed workflow completing in under 2 minutes. Six specialized AI agents on Amazon Bedrock AgentCore gather competitive intelligence, forecast demand, assess market conditions, synthesize optimized pricing strategies, and monitor post-implementation performance — with human-in-the-loop approval for high-risk decisions and fully autonomous execution for low-risk changes.

## What It Does

- **Orchestrates 6 AI agents in parallel** — Competitive Intelligence, Demand Forecasting, and Market Intelligence agents run simultaneously (120s timeout, 2 retries, graceful degradation), feeding into Strategy Synthesis for scenario generation
- **Generates 5 ranked pricing scenarios** per cycle — the selected objective sets the price direction (increase/decrease), and each strategy (Aggressive Growth, Market Share Capture, Balanced Optimization, Margin Protection, Conservative Protection) applies a different level of aggressiveness with corresponding risk classification and confidence scores
- **Enforces pricing compliance** via 4 application-layer guardrails (below-cost rejection, MAP enforcement, geographic bias detection, PII protection) plus Amazon Bedrock Guardrails blocking anti-competitive strategies
- **Routes approvals by risk** — LOW risk auto-approved (Straight-Through Processing), MEDIUM requires human review, HIGH requires 50+ character justification with escalation to Pricing Manager
- **Enforces separation of duties** — the pricing cycle initiator cannot approve their own scenarios (server-side enforcement)
- **Monitors post-implementation KPIs** — Implementation Monitoring agent tracks revenue and margin variance against projections with configurable thresholds (10% revenue, 3pp margin)
- **Provides full audit trail** with immutable records (IAM-enforced) for regulatory compliance (FTC, Robinson-Patman Act, EU Omnibus Directive)
- **Dual frontend** — Authenticated Dashboard (pricing management, simulations, analytics, scheduling) and public Storefront (consumer catalog with live price updates)
- **Tiered model strategy** — Claude Opus for complex reasoning (orchestrator, synthesis), Claude Sonnet for data analysis (specialists) — optimizing cost without sacrificing quality
- **Price Prediction Simulator** — Interactive what-if analysis with transparent factor scoring (Competitive Pressure, Demand Signal, Margin Constraint, Market Intelligence), adjustable market condition sliders, and live price impact calculations from current catalog prices
- **Product Catalog & Unit Economics** — Full visibility into cost structure (materials, labor, overhead, shipping), gross margins, MAP floors, inventory levels, days of supply, and stock health for every product — showing exactly what data drives AI pricing decisions
- **One-click deployment** — Automated `deploy.sh` handles CDK infrastructure, agent deployment, MCP server setup, and frontend builds

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
│  │  (REST)          │  │  (Python 3.12)    │  │  (5 tables)      │  │
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

## Model Configuration

The AI models used by the pricing agents are configurable. The system scans your Bedrock model access, flags deprecated (LEGACY) models, and recommends the best available option.

### During Initial Deployment

Model selection runs automatically as Step 1.7 in `deploy.sh`. You'll see a table of available models with status indicators and choose one interactively. The selected model ID is written to `model-config.json` and used by all agents.

### Switching Models After Deployment

To change the model on an existing deployment:

```bash
bash scripts/switch_model.sh
```

This will:
1. Scan available Bedrock models and show recommendations
2. Flag any LEGACY models with end-of-life dates
3. Update `model-config.json`
4. Optionally redeploy AgentCore agents to apply immediately

Options:
- `--non-interactive` — auto-select the recommended model
- `--region us-west-2` — target a specific region

### Model Tiers

| Tier | Used By | Purpose |
|------|---------|---------|
| Opus | Orchestrator, Strategy Synthesis | Complex multi-step reasoning |
| Sonnet | Competitive, Demand, Market, Implementation agents | Data analysis |

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

### Quick Deploy (Recommended)

```bash
git clone <REPOSITORY_URL>
cd "Retail Dynamic Pricing"
chmod +x deploy.sh
./deploy.sh
```

The script automates all steps below, including prerequisites check, CDK deployment, agent deployment, data seeding, user creation, and frontend build. Supports `--skip-agents` and `--skip-frontend` flags for partial redeployments.

After deployment completes, run the validation script:

```bash
python3 scripts/verify_deployment.py
```

### Manual Deployment

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
  --temporary-password TempPass2024!Secure \
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password \
  --user-pool-id <COGNITO_USER_POOL_ID> \
  --username demo@example.com \
  --password <COGNITO_DEMO_PASSWORD> \
  --permanent
```

> **Note:** Passwords must be at least 12 characters with uppercase, lowercase, digits, and symbols. MFA (TOTP) enrollment is required on first login — users will need an authenticator app (e.g., Google Authenticator, Authy).

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

### As Pricing Analyst (`demo@example.com` / `DemoPass2024!`)

1. **Open Dashboard** → Log in with Cognito credentials
2. **Simulations tab** → Select a scenario preset (e.g., "Competitor Price War")
3. **Watch the pipeline** → 6 agents execute in under 2 minutes
4. **Review scenarios** → 5 ranked recommendations with strategy names and risk levels
5. **Approve/Reject** → HIGH risk requires justification, LOW risk auto-approves
6. **Check Storefront** → Prices update in real-time after approval
7. **Price Predictions tab** → Select a product, click Simulate, explore the decision tree with drill-down explainability
8. **Product Catalog tab** → View all products with unit economics (cost, margin, inventory, MAP floors). Click any product to expand cost breakdown and pricing boundaries
9. **Guardrails Demo** → Scroll to "Guardrails Enforcement" section, click any card to see compliance blocking in action

### As Operations (`ops@example.com` / `OpsPass2024!`)

1. **Log in** → Notice the "Operations" tab appears (not visible to Pricing Analysts)
2. **Operations → System Health** → All 12 services with status and latency
3. **Operations → Metrics** → Operational KPIs (cycles run, error rates, invocations)
4. **Operations → Architecture** → System architecture diagram
5. **Operations → TCO & ROI** → Cost breakdown per cycle, monthly projections, AWS billing data

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

A comprehensive STRIDE threat model has been completed for this solution. See [`docs/.threatmodel/`](docs/.threatmodel/) for the full analysis (Threat Composer JSON + Markdown report).

**Security controls implemented:**
- CloudFront Response Headers Policy — CSP, HSTS (2yr preload), X-Frame-Options DENY, X-Content-Type-Options, Referrer-Policy
- API input validation — prompt injection scanning and field length limits at the API boundary before data reaches AI agents
- API Gateway usage plan with rate limiting (100 burst / 50 sustained requests per second)
- OAuth 2.0 authorization code flow only (implicit grant disabled)
- CORS restricted to known CloudFront origins
- Cognito MFA (TOTP) required for all dashboard users
- Separation of duties enforcement (cycle initiator cannot approve)
- Dependency vulnerability scanning (pip-audit) in deployment pipeline
- Audit trail immutability (IAM deny on mutations)
- DynamoDB Streams for price change detection
- Prompt injection sanitizer for AI agent inputs/outputs (input_sanitizer.py)
- Optional KMS CMK encryption for sensitive tables
- Memory integrity hashing (SHA-256) for AgentCore Memory with fail-closed verification

---

## Demo Limitations & Production Considerations

This solution is a functional demonstration. Several features illustrate production patterns without full backend implementation:

| Feature | Demo Behavior | Production Implementation |
|---------|---------------|---------------------------|
| **Scheduling Tab** | Displays configuration UI for autonomous pricing schedules (frequency, triggers, approval windows). Settings are persisted locally in the browser but do not trigger actual scheduled executions. | Integrate with Amazon EventBridge Scheduler to create cron/rate rules that invoke `POST /pricing-cycles`. Add a DynamoDB `Schedules` table to persist configuration server-side, with Lambda-backed CRUD endpoints. |
| **MCP Server Data** | Returns simulated market, competitor, ERP, and cost data generated at request time. | Connect to real data sources — competitor price feeds, POS/ERP APIs, market data providers — and implement caching/staleness checks. |
| **Server-side RBAC** | Frontend routing restricts tabs by role; all authenticated users can invoke any API endpoint. | Add `cognito:groups` claim validation in Lambda authorizers. Enforce role-based access at the API layer, not just the UI. |
| **Hardcoded Demo Credentials** | `deploy.sh` creates demo users with preset passwords. MFA is still required. | Use SSM Parameter Store or Secrets Manager for initial credentials. Rotate on first use. |
| **Guardrails Enforcement** | Bedrock Guardrails validate at the model level. Application-layer guardrails use hardcoded pass/fail for demo scenarios. | Call Bedrock Guardrails API at price-modification points (before writing to Products table) for runtime validation. |
| **Kill Switches** | `SKIP_INPUT_SANITIZATION` and `DISABLE_BEDROCK_GUARDRAILS` env vars allow bypassing controls for local testing. | Remove or protect via AWS Service Control Policies (SCPs) and AWS Config rules. Never deploy to production. |
| **Pricing Model** | Flat catalog pricing only — one price per product, all customers, all channels. Products with `mapPrice: null` behave as private-label (no MAP floor, cost floor only). | Add `pricingModel` field ("catalog", "private-label", "surge", "tiered") per product. Strategy Synthesis applies model-specific strategies. See "Extensible Pricing Models" below. |

### Extensible Pricing Models

The current demo implements catalog pricing. The architecture supports extension to multiple pricing models by adding a `pricingModel` field to the Products table and routing the Strategy Synthesis agent's behavior based on it:

| Model | How It Works | Strategy Synthesis Behavior |
|-------|-------------|----------------------------|
| **Catalog (current)** | One fixed price per SKU. MAP enforced where applicable. | Standard scenario generation with guardrail validation. |
| **Private-Label** | Retailer is manufacturer. No MAP. Full pricing discretion. | Price relative to category leader (e.g., "25% below branded competitor"). Higher margin targets (45-60%). Can use loss-leader pricing for basket building. Aggressive clearance without MAP constraint. |
| **Surge/Dynamic** | Real-time price multiplier based on demand intensity. | Replace cycle-based flow with event-driven (EventBridge every 60s). Auto-approve LOW-risk multipliers. Cap at configurable ceiling (e.g., 2.0x). Decay multiplier as demand normalizes. |
| **Tiered/Volume** | Different prices based on purchase quantity or customer segment. | Generate price tiers (1-9 units, 10-49, 50+) per product. Apply segment-specific elasticity from Demand Forecasting agent. |
| **Channel-Specific** | Different prices per sales channel (online, in-store, marketplace). | Add `channel` sort key to Products table. Generate per-channel recommendations. Geographic bias guardrail checks cross-channel variance. |

To implement private-label strategies, the Strategy Synthesis prompt would route on `pricingModel`:
- **Category Leader Undercut** — price at 25-35% below the nearest branded competitor
- **Margin Target** — work backward from target margin (45%) to set price
- **Anchor Pricing** — widen or narrow gap to branded alternatives based on category strategy
- **Promotional Elasticity** — use demand elasticity to find optimal promotional price (no MAP prevents aggressive discounting)
- **Inventory Clearance** — mark down aggressively for perishables with excess stock (only cost floor applies)

---

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file.
