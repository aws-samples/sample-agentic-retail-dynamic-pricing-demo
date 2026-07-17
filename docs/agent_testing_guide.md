# Agent Testing Guide

This guide documents how to invoke and test each agent individually using the
testing harness before connecting them to the Orchestrator Agent.

## Overview

The testing harness (`backend/agents/testing_harness.py`) provides:
- Sample request payloads for each of the 5 agents
- Expected response schemas per agent
- SigV4-signed invocation via InvokeAgentRuntime
- Response validation against defined output schemas
- 30-second timeout enforcement
- Pass/fail reporting with detailed error information

## Prerequisites

1. AWS credentials configured (via environment, IAM role, or `~/.aws/config`)
2. Agents deployed to Amazon Bedrock AgentCore
3. Python virtual environment activated with project dependencies installed

## Quick Start

### Run all agent tests

```bash
PYTHONPATH=. .venv/bin/python -m backend.agents.testing_harness
```

### Test a single agent

```bash
PYTHONPATH=. .venv/bin/python -m backend.agents.testing_harness "Competitive Intelligence"
```

### Use from Python

```python
from backend.agents.testing_harness import (
    AGENT_TEST_CONFIGS,
    run_all_agent_tests,
    run_single_agent_test,
    print_test_report,
)
from shared.sigv4_client import AgentCoreConfig

# Configure for your region
config = AgentCoreConfig(region="us-east-1")

# Run all tests
report = run_all_agent_tests(agentcore_config=config)
print_test_report(report)

# Run a single agent test
result = run_single_agent_test(
    agent_name="Demand Forecasting",
    agentcore_config=config,
)
print(f"Passed: {result.passed}, Time: {result.response_time_seconds:.2f}s")
```

### Override agent IDs

If your deployed agent IDs differ from the defaults, pass a mapping:

```python
report = run_all_agent_tests(
    agent_ids={
        "Competitive Intelligence": "my-ci-agent-id",
        "Demand Forecasting": "my-df-agent-id",
        "Market Intelligence": "my-mi-agent-id",
        "Strategy Synthesis": "my-ss-agent-id",
        "Implementation Monitoring": "my-im-agent-id",
    }
)
```

## Agents and Sample Payloads

### 1. Competitive Intelligence Agent

**Agent ID**: `competitive-intelligence-agent`
**Model**: `us.anthropic.claude-sonnet-4-6`

**Sample Request Payload**:
```json
{
  "inputText": "Analyze the competitive pricing landscape for product 'PROD-001' in the 'Electronics' category. Gather competitor prices, price history, and market position data. Return structured competitive factors in JSON format.",
  "enableTrace": false
}
```

**Expected Response Schema**:
```json
{
  "avgCompetitorPrice": 94.50,
  "priceIndex": 105.3,
  "positioning": "premium",
  "channelAnalysis": [
    {
      "channel": "online",
      "avgPrice": 92.99,
      "priceRange": {"min": 85.00, "max": 102.00},
      "competitorCount": 5,
      "trend": "stable"
    }
  ],
  "sentimentIndicators": [
    {
      "indicator": "price_war_risk",
      "value": 0.3,
      "direction": "neutral",
      "confidence": 0.75
    }
  ],
  "competitorCount": 5,
  "dataSource": "mcp_tools",
  "marketGrowthRate": 0.04,
  "priceVolatility": 0.25
}
```

### 2. Demand Forecasting Agent

**Agent ID**: `demand-forecasting-agent`
**Model**: `us.anthropic.claude-sonnet-4-6`

**Sample Request Payload**:
```json
{
  "inputText": "Forecast demand for product 'PROD-001' in the 'Electronics' category. Analyze sales history, POS real-time data, inventory levels, and price elasticity. Return structured demand factors in JSON format including forecastedDemand, elasticity, seasonalityFactor, inventoryStatus, and trendDirection.",
  "enableTrace": false
}
```

**Expected Response Schema**:
```json
{
  "forecastedDemand": 1250,
  "elasticity": -1.4,
  "seasonalityFactor": 1.15,
  "inventoryStatus": "healthy",
  "trendDirection": "increasing"
}
```

### 3. Market Intelligence Agent

**Agent ID**: `market-intelligence-agent`
**Model**: `us.anthropic.claude-sonnet-4-6`

**Sample Request Payload**:
```json
{
  "inputText": "Analyze market conditions for the 'Electronics' category. Examine market trends, consumer sentiment, and macroeconomic indicators. Return structured market factors in JSON format including trendScore, sentimentScore, macroOutlook, opportunityIndicators, and marketMomentum.",
  "enableTrace": false
}
```

**Expected Response Schema**:
```json
{
  "trendScore": 0.65,
  "sentimentScore": 0.72,
  "macroOutlook": "bullish",
  "opportunityIndicators": [
    {
      "type": "seasonal_peak",
      "description": "Holiday season approaching with strong consumer confidence",
      "confidence": 0.85
    },
    {
      "type": "market_expansion",
      "description": "Category growing at 8% YoY with new entrants",
      "confidence": 0.70
    }
  ],
  "marketMomentum": "accelerating"
}
```

### 4. Strategy Synthesis Agent

**Agent ID**: `strategy-synthesis-agent`
**Model**: `us.anthropic.claude-opus-4-7`

**Sample Request Payload**:
```json
{
  "inputText": "Synthesize pricing strategies for pricing cycle 'CYCLE-001'. Combine the following intelligence inputs:\nCompetitive: avg competitor price $99.99, price index 102, positioning competitive, 5 competitors analyzed.\nDemand: forecasted demand 1200 units, elasticity -1.5, seasonality factor 1.1, inventory healthy, trend increasing.\nMarket: trend score 0.6, sentiment 0.72, macro outlook bullish, momentum accelerating.\nGenerate 50-200 pricing scenarios, apply guardrails, rank by composite business impact, and classify risk levels.",
  "enableTrace": false
}
```

**Expected Response Schema** (abbreviated):
```json
{
  "ranked_scenarios": [
    {
      "scenarioId": "SCN-CYCLE001-0001",
      "cycleId": "CYCLE-001",
      "rank": 1,
      "confidenceScore": 85,
      "statusLabel": "Recommended",
      "riskLevel": "LOW",
      "priceChanges": [
        {
          "productId": "PROD-001",
          "currentPrice": 99.99,
          "newPrice": 103.99,
          "changePercent": 4.0
        }
      ],
      "projectedRevenue": 124800.0,
      "projectedMargin": 0.2250,
      "projectedMarketShare": 0.32,
      "compositeScore": 87.5,
      "competitiveFactors": {"avg_competitor_price": 99.99},
      "demandFactors": {"elasticity": -1.5},
      "marketFactors": {"market_growth_rate": 0.08}
    }
  ],
  "synthesis_metadata": {
    "cycle_id": "CYCLE-001",
    "total_generated": 120,
    "total_valid": 95,
    "total_rejected": 25
  }
}
```

### 5. Implementation Monitoring Agent

**Agent ID**: `implementation-monitoring-agent`
**Model**: `us.anthropic.claude-sonnet-4-6`

**Sample Request Payload**:
```json
{
  "inputText": "Execute price update for approved scenario 'SCN-001'. Update product 'PROD-001' from $99.99 to $104.99 (5% increase). Track KPIs: projected revenue $125,000, projected margin 22%, projected conversion rate 3.5%. Monitor for variance against thresholds (10% revenue, 3pp margin).",
  "enableTrace": false
}
```

**Expected Response Schema**:
```json
{
  "scenario_id": "SCN-001",
  "timestamp": "2024-01-15T10:30:00Z",
  "total_updates": 1,
  "successful": 1,
  "failed": 0,
  "details": [
    {
      "productId": "PROD-001",
      "status": "success",
      "previousPrice": 99.99,
      "newPrice": 104.99
    }
  ]
}
```

## Validation Rules

Each agent response is validated against these criteria:

| Check | Requirement | Failure Condition |
|-------|-------------|-------------------|
| Timeout | ≤ 30 seconds | Response time exceeds 30s |
| HTTP Status | 2xx | Non-success HTTP status code |
| JSON Parse | Valid JSON | Response cannot be parsed as JSON |
| Required Fields | All present | Any required field missing |
| Type Check | Correct types | Field type doesn't match schema |
| Enum Values | Valid values | Value not in allowed enum set |
| Numeric Bounds | Within range | Value outside min/max bounds |

## Test Report Format

The harness produces a structured report:

```
======================================================================
AGENT TESTING HARNESS - INDIVIDUAL INVOCATION RESULTS
======================================================================

  ✓ PASS  Competitive Intelligence
         Agent ID: competitive-intelligence-agent
         Response Time: 4.523s

  ✓ PASS  Demand Forecasting
         Agent ID: demand-forecasting-agent
         Response Time: 3.891s

  ✗ FAIL  Market Intelligence
         Agent ID: market-intelligence-agent
         Response Time: 31.205s
         ⚠ TIMEOUT EXCEEDED (30s limit)
         Error: Agent 'Market Intelligence' exceeded 30s timeout

----------------------------------------------------------------------
  SUMMARY: 2/3 passed, 1 failed
  STATUS: SOME TESTS FAILED
======================================================================
```

## Troubleshooting

### Agent not responding

1. Verify the agent is deployed: check AgentCore console
2. Confirm agent ID matches the deployed agent
3. Check AWS credentials have `bedrock:InvokeAgent` permission
4. Verify the region matches where agents are deployed

### Schema validation failures

1. Check the agent's system prompt produces structured JSON output
2. Verify MCP tools are accessible from the agent
3. Review the raw response in the test result for debugging
4. Compare against the expected schema in `testing_harness.py`

### Timeout exceeded

1. Check if MCP Server Lambda functions are cold-starting
2. Verify MCP Server timeout is ≤ 30 seconds
3. Consider warming up Lambda functions before testing
4. Check network connectivity to AgentCore endpoint

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Testing Harness                         │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐                  │
│  │ Sample       │    │ Expected     │                  │
│  │ Payloads     │    │ Schemas      │                  │
│  └──────┬───────┘    └──────┬───────┘                  │
│         │                   │                          │
│         ▼                   ▼                          │
│  ┌──────────────────────────────────┐                  │
│  │  invoke_agent_and_validate()     │                  │
│  │  - SigV4 sign request            │                  │
│  │  - Send to AgentCore Runtime     │                  │
│  │  - Measure response time         │                  │
│  │  - Parse JSON response           │                  │
│  │  - Validate against schema       │                  │
│  └──────────────┬───────────────────┘                  │
│                 │                                       │
│                 ▼                                       │
│  ┌──────────────────────────────────┐                  │
│  │  AgentTestResult                 │                  │
│  │  - passed / failed               │                  │
│  │  - response_time_seconds         │                  │
│  │  - schema_errors                 │                  │
│  │  - error_message                 │                  │
│  └──────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
         │
         │ SigV4 HTTP (InvokeAgentRuntime)
         ▼
┌─────────────────────────────────────────────────────────┐
│  Amazon Bedrock AgentCore Runtime                       │
│                                                         │
│  ┌────────────┐ ┌────────────┐ ┌────────────────────┐  │
│  │ Competitive│ │  Demand    │ │    Market          │  │
│  │ Intel      │ │ Forecasting│ │  Intelligence      │  │
│  └────────────┘ └────────────┘ └────────────────────┘  │
│  ┌────────────┐ ┌────────────────────────────────────┐  │
│  │ Strategy   │ │  Implementation Monitoring         │  │
│  │ Synthesis  │ │                                    │  │
│  └────────────┘ └────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```
