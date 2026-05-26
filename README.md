# Retail Dynamic Pricing

Agentic AI-based dynamic pricing system for retail. Replaces a manual 6-10 week pricing process with a multi-agent orchestrator that delivers 50+ ranked pricing scenarios in 2-4 days.

Built with AWS CDK (Python), Strands Agents SDK on Amazon Bedrock AgentCore, and React/TypeScript frontends.

## Architecture

- **Orchestrator Agent** (Claude Opus) — coordinates the pipeline
- **3 Intelligence Agents** (Claude Sonnet) — competitive, demand, and market analysis in parallel
- **Strategy Synthesis Agent** (Claude Opus) — generates 50-200 ranked scenarios with guardrails
- **Implementation Monitoring Agent** (Claude Sonnet) — tracks post-approval KPIs
- **4 MCP Servers** (Lambda) — simulated data sources with randomized responses
- **Dashboard** (React/TS, Cognito auth) — for Product Managers to trigger requests and approve scenarios
- **Storefront** (React/TS, public) — consumer-facing product catalog with live price updates

## Project Structure

```
├── cdk/                    # AWS CDK infrastructure (Python)
│   ├── app.py              # CDK app entry point
│   └── stacks/             # CDK stack constructs
├── backend/
│   ├── api_handlers/       # Lambda handlers for API Gateway endpoints
│   └── mcp_servers/        # MCP Server Lambda functions (simulated data)
├── frontend/
│   ├── dashboard/          # Product Manager dashboard (React/TS, Cognito auth)
│   └── storefront/         # Consumer storefront (React/TS, public)
├── shared/                 # Shared business logic and data models
│   ├── models/             # Pydantic data models (PricingScenario, etc.)
│   ├── guardrails.py       # Pricing guardrails engine
│   ├── risk_classification.py
│   ├── approval_routing.py
│   ├── scenario_ranking.py
│   └── variance_detection.py
├── tests/                  # Unit and property-based tests
├── cdk.json                # CDK configuration
└── pyproject.toml          # Python project dependencies
```

## Prerequisites

- Python 3.12+
- Node.js 20+ (for frontends)
- AWS CDK CLI (`npm install -g aws-cdk`)
- AWS credentials configured

## Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run tests
PYTHONPATH=. pytest tests/ -v

# Synthesize CDK
cdk synth

# Deploy
cdk deploy
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent Framework | Strands Agents SDK on AgentCore | Native AWS, MCP support, managed infra |
| Data Integration | MCP Servers on Lambda | Standardized tool protocol, serverless |
| Frontend | React/TS + Vite + Tailwind | Fast iteration, type safety |
| Data Store | DynamoDB (on-demand) | Serverless, pay-per-request |
| Auth | Amazon Cognito | Managed auth, JWT, API Gateway integration |
| IaC | AWS CDK (Python) | Reproducible, automatic rollback |
| AgentCore API | SigV4 HTTP calls | Required (Lambda boto3 lacks bedrock-agentcore) |

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /pricing-cycles | Cognito | Initiate a pricing cycle |
| GET | /pricing-cycles/{id} | Cognito | Get cycle status |
| GET | /pricing-cycles/{id}/scenarios | Cognito | List scenarios (paginated) |
| POST | /approvals | Cognito | Approve/reject a scenario |
| GET | /agents/status | Cognito | Agent execution status |
| GET | /monitoring/{scenarioId} | Cognito | Monitoring metrics |
| GET | /products | Public | Product catalog |
| GET | /products/{id} | Public | Single product detail |
