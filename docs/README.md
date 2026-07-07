# CCOE Dynamic Pricing Solution for Retail Transformation — Documentation

## Agentic AI Solution powered by Amazon Bedrock AgentCore

---

### Quick Links

| Document | Description |
|----------|-------------|
| [QUICK_START.md](QUICK_START.md) | Concise setup and deployment steps |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Solution architecture, data flow, agent design |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | 7-8 minute demo walkthrough script |
| [agent_testing_guide.md](agent_testing_guide.md) | Agent testing procedures and harness usage |
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | Deployment issues and resolutions |

---

### Solution Summary

| Aspect | Detail |
|--------|--------|
| **Purpose** | Transform retail pricing from 6-10 week manual process to an AI-driven workflow completing in under 2 minutes |
| **Architecture** | 6 AI agents on Amazon Bedrock AgentCore Runtime |
| **Framework** | Strands Agents SDK |
| **Models** | Claude Opus 4.7 (orchestrator, synthesis), Claude Sonnet 4.6 (specialists) |
| **Data Integration** | 4 MCP Servers via AgentCore Gateway |
| **Compliance** | Bedrock Guardrails (4 policies) + full audit trail |
| **Approval** | Risk-based HITL routing + Straight-Through Processing for LOW risk |
| **Frontend** | React/TypeScript Dashboard + Consumer Storefront |
| **Infrastructure** | Fully serverless (CDK-deployed) |
| **Cost** | ~$0.25/cycle, ~$30/month at demo scale |

---

### Key URLs (After Deployment)

| Resource | URL |
|----------|-----|
| Dashboard | `https://<DASHBOARD_CLOUDFRONT_DOMAIN>` |
| Storefront | `https://<STOREFRONT_CLOUDFRONT_DOMAIN>` |
| API Gateway | `https://<API_GATEWAY_URL>/prod/` |
| Login | `demo@example.com` / `ops@example.com` (MFA TOTP required) |

---

### AWS Services Used

- Amazon Bedrock (Foundation Models — Claude Opus 4.7, Sonnet 4.6, configurable via `scripts/select_model.py`)
- Amazon Bedrock AgentCore (Runtime, Gateway, Memory, Identity, Observability)
- Amazon Bedrock Guardrails
- AWS Lambda (Python 3.12)
- Amazon API Gateway (REST)
- Amazon DynamoDB (5 tables, on-demand)
- Amazon Cognito (User Pool + Hosted UI)
- Amazon CloudFront (2 distributions)
- Amazon S3 (static hosting)
- Amazon ECR (6 agent container repositories)
- AWS IAM
- AWS CloudWatch
- AWS CDK (Infrastructure as Code)
