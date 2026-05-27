# MCP Data Integration - Documentation & Rollback

## What Was Added

The scenario generation now attempts to use real data from the orchestrator agent's
MCP server calls (Competitor API, ERP/POS, Market Signals, Cost & Finance) to populate
the contributing factors in pricing scenarios.

### Flow:
```
Orchestrator Agent (AgentCore)
    → Calls MCP Servers via Gateway
    → Returns response with structured data
        ↓
Lambda (_parse_and_store_scenarios)
    → _extract_mcp_data(orchestrator_result)
    → If MCP data found: use it for competitiveFactors, demandFactors, marketFactors
    → If not found: fall back to representative random data (previous behavior)
```

### What Changed:
- `backend/api_handlers/pricing_cycles.py`:
  - Added `_extract_mcp_data()` function — parses orchestrator response for structured MCP data
  - Added `_build_competitive_factors()` — uses MCP data or falls back to random
  - Added `_build_demand_factors()` — uses MCP data or falls back to random
  - Added `_build_market_factors()` — uses MCP data or falls back to random
  - Updated `_generate_scenarios_from_products()` to accept `mcp_data` parameter
  - Each scenario now includes `"dataSource": "mcp_servers" | "simulated"` field

### Data Sources:
| Factor | MCP Server | Data Provided |
|--------|-----------|---------------|
| competitiveFactors | competitor-api | Price index, market position, price gap, competitor count |
| demandFactors | erp-pos | Elasticity, seasonal index, trend, weekly demand, inventory health, days of supply |
| marketFactors | market-signals | Inflation rate, consumer sentiment, supply chain risk, growth rate, category trend |

## How to Verify Data Source

Each scenario's contributing factors now include a `"dataSource"` field:
- `"mcp_servers"` — data came from actual MCP server responses via the orchestrator
- `"simulated"` — fallback random data (same as previous behavior)

The scenario-level `"dataSource"` field also indicates which path was used.

## Rollback Options

### Option 1: Environment Variable (Instant, No Redeploy)
```bash
aws lambda update-function-configuration \
  --function-name rdp-api-pricing-cycles \
  --environment "Variables={...,USE_MCP_DATA=false}" \
  --region us-east-1
```
This disables MCP data extraction and always uses the random fallback.

### Option 2: Remove the Code
Revert `_extract_mcp_data()` to always return `None`:
```python
def _extract_mcp_data(orchestrator_result):
    return None  # Disabled — using fallback
```

### Option 3: Full Revert
Remove the `mcp_data` parameter from `_generate_scenarios_from_products()` and
revert the `_build_*_factors()` functions to inline random generation.

## Performance Impact
- Zero additional latency (parsing in-memory data, no new API calls)
- Zero additional cost (no new model invocations)
- Slightly richer scenario data when MCP data is available

## Date Added
2026-05-27
