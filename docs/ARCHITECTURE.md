# Architecture Document

## CCOE Dynamic Pricing Solution for Retail Transformation

---

## Solution Overview

An agentic AI system that transforms retail pricing from a manual 6-10 week process into an autonomous workflow that completes in under 2 minutes. Built on Amazon Bedrock AgentCore with 6 specialized AI agents that gather market intelligence, analyze demand, and generate optimized pricing recommendations.

---

## Architecture Layers

### 1. User Layer
| Component | Service | Purpose |
|-----------|---------|---------|
| Dashboard | React/TypeScript + Vite | Pricing management UI with tabs (Overview, Price Predictions, Simulations, Analytics, Product Catalog, Audit Trail, Scheduling, Operations) |
| Storefront | React/TypeScript + Vite | Consumer-facing product catalog showing live prices |
| CDN | Amazon CloudFront (2 distributions) | Global content delivery, HTTPS termination |
| Static Hosting | Amazon S3 (2 buckets) | SPA hosting for Dashboard and Storefront |
| Authentication | Amazon Cognito | User pool with hosted UI, JWT token validation |

### 2. API Layer
| Component | Service | Purpose |
|-----------|---------|---------|
| REST API | Amazon API Gateway | Request routing, Cognito authorization, CORS |
| API Handlers | AWS Lambda (Python 3.12) | Thin wrappers: validate → persist → invoke AgentCore |
| State Store | Amazon DynamoDB (5 tables) | Products, PricingCycles, PricingScenarios, Approvals, AuditTrail |

### 3. AgentCore Layer
| Component | Service | Purpose |
|-----------|---------|---------|
| Agent Runtime | Amazon Bedrock AgentCore Runtime | Serverless execution of 6 AI agents |
| Agent Gateway | Amazon Bedrock AgentCore Gateway | MCP protocol endpoint for 4 data server targets |
| Agent Memory | Amazon Bedrock AgentCore Memory | Persistent state across pricing cycles |
| Guardrails | Amazon Bedrock Guardrails | Policy enforcement (4 denied topics + PII) |
| Foundation Models | Amazon Bedrock (Claude Opus 4.7, Sonnet 4.6) | LLM reasoning for pricing analysis |
| Container Registry | Amazon ECR (6 repositories) | Docker images for agent runtimes |

### 4. Data Layer (MCP Servers)
| Server | Lambda Function | Data Provided |
|--------|----------------|---------------|
| Competitor API | rdp-mcp-competitor-api | Real-time competitor prices, market positioning |
| ERP/POS | rdp-mcp-erp-pos | Sales history, inventory levels, price elasticity |
| Market Signals | rdp-mcp-market-signals | Market trends, consumer sentiment, inflation |
| Cost & Finance | rdp-mcp-cost-finance | COGS, margin constraints, financial rules |

---

## Agent Architecture

### Multi-Agent Orchestrator Pattern

```
                    ┌─────────────────────┐
                    │  Orchestrator Agent  │
                    │  (Claude Opus 4.7)   │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──────┐ ┌──────▼───────┐ ┌──────▼──────────┐
    │  Competitive   │ │   Demand     │ │    Market       │
    │  Intelligence  │ │  Forecasting │ │  Intelligence   │
    │ (Sonnet 4.6)   │ │ (Sonnet 4.6) │ │ (Sonnet 4.6)   │
    └────────────────┘ └──────────────┘ └─────────────────┘
              │                │                │
              └────────────────┼────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Strategy Synthesis  │
                    │  (Sonnet 4.6)       │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Implementation    │
                    │    Monitoring       │
                    │  (Sonnet 4.6)       │
                    └─────────────────────┘
```

### Agent Responsibilities

| Agent | Model | Role | MCP Tools |
|-------|-------|------|-----------|
| Orchestrator | Claude Opus 4.7 | Coordinates pipeline, parallel dispatch, result aggregation | — |
| Competitive Intelligence | Claude Sonnet 4.6 | Competitor price monitoring, market positioning analysis | Competitor API |
| Demand Forecasting | Claude Sonnet 4.6 | Price elasticity, demand curves, seasonal patterns | ERP/POS |
| Market Intelligence | Claude Sonnet 4.6 | Market trends, consumer sentiment, cross-product opportunities | Market Signals |
| Strategy Synthesis | Claude Opus 4.7 | Combines intelligence, generates ranked scenarios | Cost & Finance |
| Implementation Monitoring | Claude Sonnet 4.6 | Executes price changes, monitors actual vs projected | ERP/POS |

---

## Data Flow

### Pricing Cycle Lifecycle

```
1. POST /pricing-cycles (Dashboard)
   → Lambda validates, writes to DynamoDB (status: INITIATED)
   → Returns 202 immediately
   → Triggers async Lambda self-invocation

2. Async Lambda invokes AgentCore Orchestrator
   → Orchestrator dispatches 3 intelligence agents in parallel
   → Each agent calls MCP Servers via Gateway for data
   → Results aggregated → Strategy Synthesis generates 5 ranked scenarios
   → Bedrock Guardrails validate all recommendations
   → Scenarios written to DynamoDB
   → LOW risk scenarios auto-approved (STP)
   → Status updated to COMPLETE

3. Dashboard polls GET /pricing-cycles/{id}
   → Shows real-time pipeline progress
   → Displays scenarios when complete

4. Human approves/rejects (or auto-approved for LOW risk)
   → POST /approvals
   → Product prices updated in DynamoDB
   → Storefront reflects new prices
```

### DynamoDB Table Schema

| Table | Partition Key | Sort Key | Purpose |
|-------|--------------|----------|---------|
| Products | productId | — | Product catalog with current/previous prices |
| PricingCycles | cycleId | status | Cycle lifecycle, agent statuses |
| PricingScenarios | cycleId | scenarioId | Generated scenarios with approval status |
| Approvals | scenarioId | timestamp | Approval audit records |
| AuditTrail | scenarioId | timestamp#ruleId | Guardrail evaluation records (append-only, IAM-enforced immutability) |

---

## Security & Compliance

### Authentication & Authorization
- Cognito User Pool with hosted UI (OAuth 2.0 / OIDC)
- API Gateway Cognito Authorizer validates JWT on every request
- Lambda extracts `sub` claim for audit trail attribution

### Guardrails (Amazon Bedrock Guardrails)
- **PredatoryPricing** — blocks below-cost pricing to eliminate competitors
- **PriceFixingAndCollusion** — blocks coordination with competitors
- **DiscriminatoryPricing** — blocks pricing based on protected characteristics
- **PriceGouging** — blocks exploiting emergencies for excessive prices
- **PII Protection** — anonymizes email/phone, blocks SSN/credit cards

### Audit Trail
- Every pricing decision recorded with full traceability
- Inputs, AI rationale, guardrail results, approval status, actor, timestamps
- Queryable via GET /pricing-cycles endpoint
- Supports regulatory examination (FTC, Robinson-Patman Act, EU Omnibus Directive)

---

## Deployment Architecture

### Infrastructure as Code (AWS CDK)
- Single `cdk deploy --all` deploys entire solution
- Stacks: DynamoDB, Cognito, API Gateway + Lambda, CloudFront + S3

### Agent Deployment
- Docker containers built locally, pushed to ECR
- `deploy_agentcore.py` script creates/updates AgentCore Runtimes
- Each agent is independently deployable and scalable

### CI/CD Ready
- All infrastructure in CDK (reproducible)
- Agent code in `backend/agents/agentcore/`
- Frontend builds are standard Vite → S3 sync → CloudFront invalidation

---

## Scalability

| Dimension | Approach |
|-----------|----------|
| Compute | AgentCore Runtime auto-scales (serverless) |
| API | API Gateway + Lambda scale automatically |
| Storage | DynamoDB on-demand mode (no capacity planning) |
| Agents | Each agent runs in isolated microVM, scales independently |
| Products | Scan-based for MVP; production would use GSI queries |
| Concurrency | Lambda reserved concurrency configurable per handler |

---

## Cost Model

- **80%+ of cost** is Bedrock model invocations (token-based)
- **Infrastructure** is negligible at all scales (serverless, pay-per-use)
- **Per cycle:** ~$0.25
- **Monthly (demo):** ~$30
- **Monthly (enterprise, 50K cycles):** ~$13,000
- See the **TCO** tab in the Operations dashboard for live cost breakdown and scaling projections


---

## Production Extensions

The current architecture is designed for extensibility. Key integration points for production:

| Extension | Integration Point | AWS Services |
|-----------|-------------------|--------------|
| ML demand models | Replace MCP Server simulated data with SageMaker endpoint responses | SageMaker (DeepAR, Autopilot), S3 (training data) |
| Autonomous scheduling | EventBridge Scheduler triggers pricing cycles on cron/rate | EventBridge Scheduler, Step Functions |
| Cross-cycle learning | AgentCore Memory persists strategy outcomes across cycles | AgentCore Memory (already provisioned), OpenSearch (vector index) |
| Real-time competitive monitoring | Stream competitor price changes via EventBridge Pipes | EventBridge Pipes, Kinesis Data Streams, Lambda |
| Post-implementation feedback | CloudWatch custom metrics trigger rollback workflows | CloudWatch Alarms, Step Functions, SNS |

The MCP Server interface (`backend/mcp_servers/`) is the primary integration boundary — each server can be independently replaced with real data source connectors without modifying agent logic.
