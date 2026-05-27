# Dynamic Pricing for Retail — Documentation Index

## Agentic AI Solution powered by Amazon Bedrock AgentCore

---

### Quick Links

| Document | Description |
|----------|-------------|
| [QUICK_START.md](QUICK_START.md) | Setup and deployment instructions |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Solution architecture, data flow, agent design |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | 5-minute demo walkthrough script |
| [GUIDANCE_ALIGNMENT.md](GUIDANCE_ALIGNMENT.md) | Mapping to AWS Guidance Paper |
| [TCO_ESTIMATE.md](TCO_ESTIMATE.md) | Total Cost of Ownership analysis |
| [ROLLBACK_GUIDE.md](ROLLBACK_GUIDE.md) | How to revert any feature |
| [GUARDRAILS_ROLLBACK.md](GUARDRAILS_ROLLBACK.md) | Bedrock Guardrails details |
| [MCP_DATA_INTEGRATION_ROLLBACK.md](MCP_DATA_INTEGRATION_ROLLBACK.md) | MCP data parsing details |
| [deployment_guide.md](deployment_guide.md) | Original deployment guide |
| [agent_testing_guide.md](agent_testing_guide.md) | Agent testing procedures |

---

### Solution Summary

| Aspect | Detail |
|--------|--------|
| **Purpose** | Transform retail pricing from 6-10 week manual process to ~55 second AI-driven workflow |
| **Architecture** | 6 AI agents on Amazon Bedrock AgentCore Runtime |
| **Framework** | Strands Agents SDK |
| **Models** | Claude Opus 4 (orchestrator), Claude Sonnet 4 (specialists) |
| **Data Integration** | 4 MCP Servers via AgentCore Gateway |
| **Compliance** | Bedrock Guardrails (4 policies) + full audit trail |
| **Approval** | Risk-based HITL routing + Straight-Through Processing for LOW risk |
| **Frontend** | React/TypeScript Dashboard + Consumer Storefront |
| **Infrastructure** | Fully serverless (CDK-deployed) |
| **Cost** | ~$0.25/cycle, ~$30/month at demo scale |

---

### Key URLs (Current Deployment)

| Resource | URL |
|----------|-----|
| Dashboard | https://<DASHBOARD_CLOUDFRONT_DOMAIN> |
| Storefront | https://<STOREFRONT_CLOUDFRONT_DOMAIN> |
| API Gateway | https://<API_GATEWAY_ID>.execute-api.<REGION>.amazonaws.com/prod/ |
| Login | <COGNITO_DEMO_USER> / <COGNITO_DEMO_PASSWORD> |

---

### AWS Services Used

- Amazon Bedrock (Foundation Models)
- Amazon Bedrock AgentCore (Runtime, Gateway, Memory, Identity, Observability)
- Amazon Bedrock Guardrails
- AWS Lambda
- Amazon API Gateway
- Amazon DynamoDB
- Amazon Cognito
- Amazon CloudFront
- Amazon S3
- Amazon ECR
- AWS IAM
- AWS CloudWatch
- AWS Cost Explorer
- AWS CDK (Infrastructure as Code)
