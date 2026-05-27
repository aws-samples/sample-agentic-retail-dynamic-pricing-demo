# Rollback Guide

## All Rollback Options in One Place

This document consolidates all rollback mechanisms for features added during development.

---

## 1. Bedrock Guardrails

**What it does:** Blocks anti-competitive, discriminatory, predatory pricing, and price gouging strategies at the model invocation level.

**Rollback (instant, no redeploy):**
```bash
# Set env var on all agent containers
DISABLE_BEDROCK_GUARDRAILS=true
```

**Rollback (permanent):**
```bash
aws bedrock delete-guardrail --guardrail-identifier <GUARDRAIL_ID> --region us-east-1
```

**Details:** See `docs/GUARDRAILS_ROLLBACK.md`

---

## 2. MCP Data Integration

**What it does:** Parses orchestrator agent response for structured MCP server data and uses it in scenario generation (instead of random values).

**Rollback (instant, no redeploy):**
```bash
aws lambda update-function-configuration \
  --function-name rdp-api-pricing-cycles \
  --environment "Variables={...,USE_MCP_DATA=false}" \
  --region us-east-1
```

**Details:** See `docs/MCP_DATA_INTEGRATION_ROLLBACK.md`

---

## 3. Straight-Through Processing (Auto-Approval)

**What it does:** LOW risk scenarios with "Recommended" status are auto-approved without human intervention.

**Rollback:** Remove or comment out the auto-approval block in `_parse_and_store_scenarios()` in `backend/api_handlers/pricing_cycles.py`. Search for `"STP: Auto-approving"`.

---

## 4. Price Revert

**What it does:** Allows reverting approved price changes back to previous values.

**Rollback:** Remove the `_revert_product_prices()` function from `backend/api_handlers/approvals.py` and the revert button from `frontend/dashboard/src/components/ScenarioDetail.tsx`.

---

## 5. Cost Explorer Integration

**What it does:** Fetches real AWS billing data via Cost Explorer API.

**Rollback:** Remove the `/billing` route from the Lambda handler. The TCO tab will still show estimates without live billing data.

---

## 6. Full Solution Teardown

```bash
# Destroy CDK stacks (removes all AWS resources)
npx cdk destroy --all

# Delete AgentCore agents
python scripts/deploy_agentcore.py --delete --region us-east-1

# Delete Guardrail
aws bedrock delete-guardrail --guardrail-identifier <GUARDRAIL_ID> --region us-east-1

# Delete AgentCore Memory
aws bedrock-agentcore-control delete-memory-store \
  --memory-id <AGENTCORE_MEMORY_ID> --region us-east-1

# Delete AgentCore Gateway
aws bedrock-agentcore-control delete-gateway \
  --gateway-id <AGENTCORE_GATEWAY_ID> --region us-east-1
```
