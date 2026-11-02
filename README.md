# Retail Dynamic Pricing Transformation - Agentic AI Solution [Demo]

[![Built with Kiro](https://img.shields.io/badge/Built_with-Kiro-6236FF?style=flat&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0id2hpdGUiPjxwYXRoIGQ9Ik0xMiAyQzcuNTggMiA0IDUuNTggNCAxMHY4LjVjMCAuODMuNjcgMS41IDEuNSAxLjVzMS4wOC0uMzkgMS4zNS0uODVjLjI3LS40Ni43Ny0uNjUgMS4xNS0uNjVzLjg4LjE5IDEuMTUuNjVjLjI3LjQ2Ljc3Ljg1IDEuMzUuODVzMS4wOC0uMzkgMS4zNS0uODVjLjI3LS40Ni43Ny0uNjUgMS4xNS0uNjVzLjg4LjE5IDEuMTUuNjVjLjI3LjQ2Ljc3Ljg1IDEuMzUuODVzMS4wOC0uMzkgMS4zNS0uODVjLjI3LS40Ni43Ny0uNjUgMS4xNS0uNjVzLjg4LjE5IDEuMTUuNjVjLjI3LjQ2Ljc3Ljg1IDEuMzUuODVzMS41LS42NyAxLjUtMS41VjEwYzAtNC40Mi0zLjU4LTgtOC04em0tMyA5YTEuNSAxLjUgMCAxMTAtMyAxLjUgMS41IDAgMDEwIDN6bTYgMGExLjUgMS41IDAgMTEwLTMgMS41IDEuNSAwIDAxMCAzeiIvPjwvc3ZnPg==)](https://kiro.dev)

> An agentic AI system that transforms retail pricing from a manual 6-10 week process into an autonomous, governed workflow completing in under 5 minutes. Six specialized AI agents on Amazon Bedrock AgentCore gather competitive intelligence, forecast demand, assess market conditions, synthesize optimized pricing strategies, and monitor post-implementation performance — with human-in-the-loop approval for high-risk decisions and fully autonomous execution for low-risk changes.

## What It Does

- **Orchestrates 6 AI agents** — Competitive Intelligence, Demand Forecasting and Market Intelligence run in parallel, then feed Strategy Synthesis for scenario generation. Each call has its own read timeout (300 s for specialists, 180 s for synthesis by default, configurable); only fast, retryable failures are retried, and a slow agent degrades the cycle instead of re-running
- **Generates 5 ranked pricing scenarios** per cycle — the selected objective sets the price direction (increase/decrease), and each strategy (Aggressive Growth, Market Share Capture, Balanced Optimization, Margin Protection, Conservative Protection) applies a different level of aggressiveness with corresponding risk classification and confidence scores
- **Enforces pricing compliance** via 4 application-layer guardrails (below-cost rejection, MAP enforcement, geographic bias detection, PII protection), plus an Amazon Bedrock guardrail, created by the stack, that blocks price fixing, discriminatory pricing, emergency price gouging, predatory pricing and prompt attacks at the model level (`scripts/check_guardrail.py` checks it against legitimate and harmful samples)
- **Routes approvals by risk** — LOW risk auto-approved (Straight-Through Processing), MEDIUM requires human review, HIGH requires 50+ character justification with escalation to Pricing Manager
- **Enforces separation of duties and roles** — only the PricingAnalysts group can approve or reject scenarios, only Operations can revert prices, and the pricing cycle initiator cannot approve their own scenarios (server-side enforcement)
- **Monitors post-implementation KPIs** — Implementation Monitoring agent tracks revenue and margin variance against projections with configurable thresholds (10% revenue, 3pp margin)
- **Provides full audit trail** with immutable records (IAM-enforced) for regulatory compliance (FTC, Robinson-Patman Act, EU Omnibus Directive)
- **Dual frontend** — Authenticated Dashboard (pricing management, simulations, analytics, scheduling) and public Storefront (consumer catalog with live price updates)
- **Tiered model strategy** — you pick one model for the orchestrator (recommended: Claude Opus, for complex reasoning) and one for the five specialists (recommended: Claude Sonnet, for data analysis), keeping most model calls fast and cost-efficient
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
│  │(Opus tier) │ │Intel (S)   │ │Forecast(S) │ │  Intel (S)     │  │
│  └────────────┘ └────────────┘ └────────────┘ └────────────────┘  │
│  ┌────────────────────┐ ┌────────────────────────────────────────┐ │
│  │Strategy Synth (S)  │ │ Implementation Monitoring (S)          │ │
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
| Models | Claude Opus (orchestrator) + Claude Sonnet (five specialists) | Best reasoning where it matters + cost-effective analysis; both models chosen at deploy via `select_model.py` |

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
│   ├── create_agentcore_role.py # Create the IAM roles for the agents and the gateway
│   ├── setup_gateway.py        # Create the gateway (AWS_IAM) and register MCP Server targets
│   ├── secure_gateway.py       # Check SigV4 on the gateway; delete the open one of earlier versions
│   ├── check_guardrail.py      # Run sample prompts against the stack's Bedrock guardrail
│   ├── setup_memory.py         # Provision AgentCore Memory
│   ├── seed_products.py        # Seed DynamoDB product catalog
│   └── seed_demo_cycles.py     # Seed sample pricing cycles
├── evals/                      # Specialist model evaluation (see evals/README.md)
├── tests/                      # Unit and property-based tests
├── docs/                       # Documentation
├── cdk.json                    # CDK configuration
└── pyproject.toml              # Python project dependencies
```

---

## Model Configuration

The AI models used by the pricing agents are configurable, in two tiers: one model for the orchestrator and one for the five specialist agents. The system scans your Bedrock model access, flags deprecated (LEGACY) models, and recommends the newest ACTIVE Opus model for the orchestrator and the newest ACTIVE Sonnet model for the specialists. Running the specialists on a smaller model keeps most model calls faster and cheaper.

### During Initial Deployment

Model selection runs automatically as Step 1.7 in `deploy.sh`. You'll see one table of available models and two prompts: first the **orchestrator** model, then the **specialist** model. Press Enter at both to accept the recommended pair. The choices are written to `model-config.json` (`modelId` for the orchestrator, `specialistModelId` for the specialists). `model-config.json` is not part of the container images, so `deploy_agentcore.py` passes them to every runtime as the `ORCHESTRATOR_MODEL_ID` / `SPECIALIST_MODEL_ID` environment variables, which the runtimes read through `shared/model_config.py`.

To skip a prompt, set `ORCHESTRATOR_MODEL_ID` and/or `SPECIALIST_MODEL_ID` (a cross-region model ID such as `us.anthropic.claude-sonnet-4-6`) before running `deploy.sh` or `scripts/select_model.py`. `--non-interactive` accepts both recommendations.

### Switching Models After Deployment

To change the models on an existing deployment:

```bash
bash scripts/switch_model.sh
```

This will:
1. Scan available Bedrock models and show recommendations for both tiers
2. Flag any LEGACY models with end-of-life dates
3. Ask for the orchestrator model and the specialist model, and update `model-config.json`
4. Optionally redeploy the AgentCore agents. **The new models take effect only after this redeploy**: the deployed agents keep their current models until `deploy_agentcore.py` runs again

Options:
- `--non-interactive` — auto-select the recommended models (and skip the redeploy)
- `--region us-west-2` — target a specific region

### Checking a Model Before You Switch

`python -m evals.run_eval` runs the dashboard presets through the real agent code on each specialist model you give it, scores the results (deterministic checks plus an LLM judge) and writes a report. Each request costs about as much as one pricing cycle, so nothing runs without `--yes`. See [evals/README.md](evals/README.md).

### Model Tiers

| Tier | Setting | Used By | Purpose |
|------|---------|---------|---------|
| Orchestrator (recommended: Opus) | `modelId` / `ORCHESTRATOR_MODEL_ID` | Orchestrator | Complex multi-step reasoning and coordination |
| Specialist (recommended: Sonnet) | `specialistModelId` / `SPECIALIST_MODEL_ID` | Competitive Intelligence, Demand Forecasting, Market Intelligence, Strategy Synthesis, Implementation Monitoring | Data analysis and scenario generation |

---

## Prerequisites

- **Python 3.12+**
- **Node.js 20+** (for frontends and CDK CLI)
- **Docker** (for building AgentCore agent containers)
- **AWS CDK CLI** (`npm install -g aws-cdk`)
- **AWS CLI** configured with credentials

> **Note:** `cdk-nag` (the CDK security linter the app runs) is a Python dependency installed automatically via `requirements.txt` — no manual install step is needed.
- **AWS Account** with access to:
  - Amazon Bedrock (a Claude Opus model and a Claude Sonnet model; `select_model.py` lists what your account can access and lets you choose)
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

The script asks for an email address for the Bedrock spend budget alert (80 % of $50/month). Pass `--alert-email you@example.com` (or set `ALERT_EMAIL`) to skip the prompt; without a terminal, as in CI, it is required. `--specialist-timeout` / `--synthesis-timeout` (seconds, defaults 300 / 180) set how long the orchestrator waits for each agent; raise them if a slower model times out. The Lambda timeouts are derived from them (`shared/cycle_timeouts.py`, sum at most 714 s), and `python3 -m shared.cycle_timeouts --specialist N` prints the resulting chain. The script automates all steps below, including prerequisites check, CDK deployment, AgentCore role/gateway/memory setup, agent deployment, data seeding, user creation, and frontend build. Supports `--skip-agents` and `--skip-frontend` flags for partial redeployments (`--skip-agents` skips only the agent deploy in Step 4; the role, gateway and memory are still created).

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

# Install the pinned/validated dependency set, then the project itself
pip install -r requirements.txt
pip install -e . --no-deps
```

> The pinned `requirements.txt` is the validated dependency set (it includes `cdk-nag`, which the CDK app requires). Installing it before `pip install -e . --no-deps` keeps the resolved versions reproducible.

### 2. Deploy Infrastructure (CDK)

```bash
# Bootstrap CDK (first time only)
npx cdk bootstrap

# Deploy all stacks (DynamoDB, Cognito, API Gateway, Lambda, CloudFront, S3)
npx cdk deploy --all --require-approval never
```

Note the outputs: API Gateway URL, Cognito User Pool ID, Client ID, CloudFront domains, S3 bucket names.

### 3. Create the IAM Role, AgentCore Gateway & Memory

The gateway and memory must exist **before** the agents are deployed (step 4), because the agents are wired to them at deploy time.

```bash
# IAM roles: RetailPricingAgentCoreRole (agents) and RetailPricingGatewayRole (gateway;
# only invokes the rdp-mcp-* Lambdas). Re-run any time to update them in place.
python scripts/create_agentcore_role.py --region us-east-1

# Export MCP Server Lambda ARNs (get from: aws lambda list-functions --query "Functions[?starts_with(FunctionName,'rdp-mcp-')].[FunctionName,FunctionArn]" --output table)
export COMPETITOR_API_LAMBDA_ARN=<ARN for rdp-mcp-competitor-api>
export ERP_POS_LAMBDA_ARN=<ARN for rdp-mcp-erp-pos>
export MARKET_SIGNALS_LAMBDA_ARN=<ARN for rdp-mcp-market-signals>
export COST_FINANCE_LAMBDA_ARN=<ARN for rdp-mcp-cost-finance>

# Gateway retail-pricing-gateway-iam (inbound auth AWS_IAM) with the four MCP server targets
python scripts/setup_gateway.py --region us-east-1
python scripts/setup_memory.py --region us-east-1
```

### 4. Deploy AgentCore Agents

```bash
# Deploy all 6 agents to AgentCore Runtime
python scripts/deploy_agentcore.py \
  --region us-east-1 \
  --role-arn arn:aws:iam::<ACCOUNT_ID>:role/RetailPricingAgentCoreRole
```

`deploy_agentcore.py` discovers the gateway and memory from step 3 and sets these environment variables on every runtime (on create and on update), so no manual `export` is needed: `AGENTCORE_GATEWAY_ENDPOINT` (the gateway's MCP URL, `<gatewayUrl>/mcp`), `AGENTCORE_GATEWAY_AUTH=AWS_IAM` (the agents sign their MCP calls with SigV4), `AGENTCORE_MEMORY_ID`, the stack's guardrail, the model IDs (`ORCHESTRATOR_MODEL_ID` / `SPECIALIST_MODEL_ID`), and, for the orchestrator, the five specialist runtime ARNs. It exits non-zero without building anything if the gateway, memory or guardrail cannot be found.

Then check SigV4 on the gateway. The script checks that an unsigned call is rejected and that a signed tool call works. On a deployment older than this version it then deletes the open `retail-pricing-gateway` (no inbound auth), but only once every agent signs its calls to `retail-pricing-gateway-iam`:

```bash
python scripts/secure_gateway.py --region us-east-1
```

### 5. Re-deploy CDK (links agents to Lambda)

The agent deploy script saves agent ARNs to `scripts/agent_arns.env`. Re-deploy CDK
so the pricing cycles Lambda picks up the orchestrator ARN:

```bash
npx cdk deploy --all --require-approval never
```

### 6. Seed Data

```bash
python scripts/seed_products.py
```

### 7. Create Cognito Demo Users

Two users, matching what `deploy.sh` creates:
- `demo@example.com`: a **Pricing Analyst** (PricingAnalysts group). Runs pricing requests and simulations, and approves or rejects scenarios from cycles someone else started.
- `ops@example.com`: an **admin** (Operations **and** PricingAnalysts groups). Sees everything, including the Operations tab, approves or rejects cycles someone else started, and reverts prices.

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

aws cognito-idp admin-add-user-to-group \
  --user-pool-id <COGNITO_USER_POOL_ID> \
  --username demo@example.com \
  --group-name PricingAnalysts

aws cognito-idp admin-create-user \
  --user-pool-id <COGNITO_USER_POOL_ID> \
  --username ops@example.com \
  --temporary-password TempPass2024!Secure \
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password \
  --user-pool-id <COGNITO_USER_POOL_ID> \
  --username ops@example.com \
  --password <COGNITO_OPS_PASSWORD> \
  --permanent

aws cognito-idp admin-add-user-to-group \
  --user-pool-id <COGNITO_USER_POOL_ID> \
  --username ops@example.com \
  --group-name Operations

aws cognito-idp admin-add-user-to-group \
  --user-pool-id <COGNITO_USER_POOL_ID> \
  --username ops@example.com \
  --group-name PricingAnalysts
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
  --allowed-o-auth-flows "code" \
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

`deploy.sh` creates two users:

| User | Groups | Role |
|------|--------|------|
| `demo@example.com` | PricingAnalysts | Pricing Analyst: runs pricing requests and simulations, approves or rejects scenarios from cycles someone else started |
| `ops@example.com` | Operations + PricingAnalysts | Admin: everything above, plus the Operations tab and reverting prices |

> **Approvals need a second person.** Whoever starts a pricing cycle cannot approve or reject its scenarios (separation of duties), and only PricingAnalysts members can approve or reject. To show an approval, start the cycle as one user and approve it as the other (for example, start as `demo@example.com` and approve as `ops@example.com`, using a second browser profile or a private window). LOW risk scenarios are auto-approved, so they need no second user.

### As Pricing Analyst (`demo@example.com` / `DemoPass2024!`)

1. **Open Dashboard** → Log in with Cognito credentials
2. **Simulations tab** → Select a scenario preset (e.g., "Competitor Price War")
3. **Watch the pipeline** → 6 agents execute in under 2 minutes
4. **Review scenarios** → 5 ranked recommendations with strategy names and risk levels
5. **Approve/Reject** → on a cycle started by another user (see the note above). HIGH risk requires a 50+ character justification; LOW risk auto-approves
6. **Check Storefront** → Prices update in real-time after approval
7. **Price Predictions tab** → Select a product, click Simulate, explore the decision tree with drill-down explainability
8. **Product Catalog tab** → View all products with unit economics (cost, margin, inventory, MAP floors). Click any product to expand cost breakdown and pricing boundaries
9. **Guardrails Demo** → Scroll to "Guardrails Enforcement" section, click any card to see compliance blocking in action

### As Admin (`ops@example.com` / `OpsPass2024!`)

The admin user is in both groups, so it can do everything the Pricing Analyst can, plus the steps below.

1. **Log in** → Notice the "Operations" tab appears (not visible to Pricing Analysts)
2. **Operations → System Health** → All 12 services with status and latency
3. **Operations → Metrics** → Operational KPIs (cycles run, error rates, invocations)
4. **Operations → Architecture** → System architecture diagram
5. **Operations → TCO & ROI** → Cost breakdown per cycle, monthly projections, AWS billing data
6. **Revert Prices** → On an approved scenario, roll prices back to their previous values (Operations group only)

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
| [docs/agent_testing_guide.md](docs/agent_testing_guide.md) | Agent testing procedures |
| [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) | Deployment issues and resolutions |

---

## Cost

- **Per pricing cycle:** ~$0.25 (dominated by Bedrock model invocations)
- **Monthly at demo scale (~50 cycles):** ~$30
- **Infrastructure (serverless):** ~$10-25/month fixed

---

## Teardown

### One-command teardown (recommended)

```bash
./teardown.sh --region us-east-1
```

`teardown.sh` removes everything `deploy.sh` created, in the correct dependency
order: empties the frontend S3 buckets (including object versions), runs
`cdk destroy --all`, deletes the AgentCore gateway targets → gateway → agent
runtimes → memory, then the ECR repositories and the IAM role. Resources are
discovered dynamically by name, and every step is safe to re-run. It prompts for
confirmation; pass `--yes` to skip the prompt.

### Manual teardown (fallback)

```bash
# 1. Empty the frontend S3 buckets first (CloudFormation cannot delete non-empty buckets)
for b in $(aws s3api list-buckets --query "Buckets[?starts_with(Name,'retaildynamicpricing-')].Name" --output text); do
  aws s3 rm "s3://$b" --recursive
done

# 2. Destroy the CDK stack
npx cdk destroy --all --app ".venv/bin/python3 cdk/app.py"

# 3. Delete AgentCore resources (gateway targets -> gateway -> runtimes -> memory).
#    Discover IDs with: aws bedrock-agentcore-control list-gateways / list-agent-runtimes / list-memories
#    then delete-gateway-target, delete-gateway, delete-agent-runtime, delete-memory.

# 4. Delete ECR repositories and the IAM roles
for r in $(aws ecr describe-repositories --query "repositories[?starts_with(repositoryName,'retail-pricing/')].repositoryName" --output text); do
  aws ecr delete-repository --repository-name "$r" --force
done
aws iam delete-role-policy --role-name RetailPricingAgentCoreRole --policy-name RetailPricingAgentCorePolicy
aws iam delete-role --role-name RetailPricingAgentCoreRole
aws iam delete-role-policy --role-name RetailPricingGatewayRole --policy-name RetailPricingGatewayPolicy
aws iam delete-role --role-name RetailPricingGatewayRole
```

> **Note:** the Bedrock guardrail and its versions are part of the CDK stack, so
> deleting the stack (step 1) deletes them.

---

## Security

> **Disclaimer:** This is sample code, for non-production usage. You should work with your security and legal teams to meet your organizational security, regulatory and compliance requirements before deployment.

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
- Role-based approval: approve/reject requires the PricingAnalysts group, price revert requires Operations (exact group match, checked before any write)
- Dependency vulnerability scanning (pip-audit) in deployment pipeline
- Audit trail immutability (IAM deny on mutations)
- DynamoDB Streams for price change detection
- Prompt injection sanitizer for AI agent inputs/outputs (input_sanitizer.py)
- Optional KMS CMK encryption for sensitive tables
- Memory integrity hashing (SHA-256) for AgentCore Memory with fail-closed verification

**Intentionally unauthenticated:** `GET /products` and `GET /products/{id}` are public (the Storefront calls them without a token); all other API routes require Cognito. The AgentCore Gateway requires SigV4 (`AWS_IAM` inbound auth): the agents sign their MCP calls with their execution role, and `verify_deployment.py` checks that an unsigned call is rejected. Earlier versions created the gateway `retail-pricing-gateway` with no inbound auth. A gateway's authorizer cannot be changed after creation, so on those deployments `deploy.sh` creates `retail-pricing-gateway-iam`, moves the agents to it, and then deletes the open gateway (Step 4.5). See [Demo Limitations](#demo-limitations--production-considerations).

---

## Demo Limitations & Production Considerations

This solution is a functional demonstration. Several features illustrate production patterns without full backend implementation:

| Feature | Demo Behavior | Production Implementation |
|---------|---------------|---------------------------|
| **Scheduling Tab** | Displays configuration UI for autonomous pricing schedules (frequency, triggers, approval windows). Settings are persisted locally in the browser but do not trigger actual scheduled executions. | Integrate with Amazon EventBridge Scheduler to create cron/rate rules that invoke `POST /pricing-cycles`. Add a DynamoDB `Schedules` table to persist configuration server-side, with Lambda-backed CRUD endpoints. |
| **MCP Server Data** | Returns simulated market, competitor, ERP, and cost data generated at request time. | Connect to real data sources — competitor price feeds, POS/ERP APIs, market data providers — and implement caching/staleness checks. |
| **Server-side RBAC** | Frontend routing restricts tabs by role; all authenticated users can invoke any API endpoint. | Add `cognito:groups` claim validation in Lambda authorizers. Enforce role-based access at the API layer, not just the UI. |
| **Public Product Endpoints & Gateway Auth** | `GET /products` and `GET /products/{id}` need no authentication because the public Storefront calls them anonymously (`verify_deployment.py` also uses `/products` as an anonymous health check). The AgentCore Gateway uses `AWS_IAM` inbound auth, so any principal in the account with `bedrock-agentcore:InvokeGateway` can call every tool. | Put the catalog behind WAF/CloudFront rules or API keys if it should not be scrapeable. Attach an AgentCore Policy engine to the gateway to allow specific tools per caller. |
| **Hardcoded Demo Credentials** | `deploy.sh` creates demo users with preset passwords. MFA is still required. | Use SSM Parameter Store or Secrets Manager for initial credentials. Rotate on first use. |
| **Guardrails Enforcement** | The stack's Bedrock guardrail screens the prompt each agent receives and every model response. Strategy Synthesis screens only the cycle's objectives and constraints as input; the analyst reports in its prompt were already screened as model output. Tool results are not screened (the Converse API does not evaluate them), so instructions hidden in tool data are caught only by the orchestrator's injection filter and by output screening. Application-layer guardrails use hardcoded pass/fail for demo scenarios. | Call Bedrock Guardrails API at price-modification points (before writing to Products table) for runtime validation. |
| **Kill Switches** | `SKIP_INPUT_SANITIZATION` and `DISABLE_BEDROCK_GUARDRAILS` env vars allow bypassing controls for local testing. `deploy_agentcore.py` attaches the stack's guardrail (or `BEDROCK_GUARDRAIL_ID` / `_VERSION` if set) and exits non-zero if it cannot find one; `DISABLE_BEDROCK_GUARDRAILS=true` is the only way to deploy agents without a guardrail, and `verify_deployment.py` then fails. | Remove or protect via AWS Service Control Policies (SCPs) and AWS Config rules. Never deploy to production. |
| **Pricing Model** | Flat catalog pricing only — one price per product, all customers, all channels. Products with `mapPrice: null` behave as private-label (no MAP floor, cost floor only). | Add `pricingModel` field ("catalog", "private-label", "surge", "tiered") per product. Strategy Synthesis applies model-specific strategies. See "Extensible Pricing Models" below. |
| **Architecture Pattern** | Synchronous Lambda → AgentCore invocation (optimized for real-time demo UX). | Migrate to EventBridge + Step Functions for async fan-out, independent agent scaling, automatic retries with DLQ, native event audit trail, and elimination of API Gateway timeout constraints. |

### Production Evolution Path

This demo proves the agentic orchestration pattern works. Production deployments would layer in ML models, learning loops, and memory systems:

| Capability | Demo Approach | Production Extension |
|-----------|---------------|----------------------|
| **ML-Powered Forecasting (SageMaker)** | LLM reasons over simulated MCP data to infer demand and elasticity. | Deploy SageMaker endpoints for price elasticity models (trained on transaction history), DeepAR demand forecasting, and competitive response prediction. Intelligence agents call ML endpoints instead of simulated data. |
| **Self-Healing & Continuous Learning** | Each pricing cycle is independent. Bad prices require manual revert. | Track post-implementation performance (revenue, margin, units) over 24-72h. Auto-rollback if actuals deviate >X% from predictions. Trigger SageMaker Pipeline retraining when model accuracy drifts. A/B test price points across segments. |
| **Semantic Memory** | AgentCore Memory stores short-term session state only. | Vector-index historical cycle outcomes (product, strategy, market conditions → result). Strategy Synthesis retrieves "what worked before in similar conditions" via similarity search before generating new scenarios. |
| **Episodic Memory** | No cross-session continuity. | Store complete decision episodes (trigger → data inputs → reasoning chain → decision → 30-day outcome). Enables decision replay for audit, pattern learning across seasons, and explainability for regulatory review. |

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
