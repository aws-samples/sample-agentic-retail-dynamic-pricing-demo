# Bedrock Guardrails Integration - Rollback Instructions

## What Was Added
- **Guardrail ID**: `<GUARDRAIL_ID>`
- **Version**: `1`
- **Region**: `us-east-1`
- **Account**: `<ACCOUNT_ID>`

## Policies Configured
1. **PredatoryPricing** (DENY) - Blocks strategies to sell below cost to eliminate competitors
2. **PriceFixingAndCollusion** (DENY) - Blocks coordination with competitors on pricing
3. **DiscriminatoryPricing** (DENY) - Blocks pricing based on protected characteristics
4. **PriceGouging** (DENY) - Blocks exploiting emergencies for excessive pricing
5. **Content Filters** - HATE, INSULTS, SEXUAL, VIOLENCE (HIGH), MISCONDUCT (MEDIUM)
6. **PII Protection** - EMAIL/PHONE/NAME anonymized, SSN/Credit Card blocked

## Files Modified
- `backend/agents/agentcore/guardrail_config.py` (NEW)
- `backend/agents/agentcore/competitive_intelligence_runtime.py`
- `backend/agents/agentcore/demand_forecasting_runtime.py`
- `backend/agents/agentcore/market_intelligence_runtime.py`
- `backend/agents/agentcore/strategy_synthesis_runtime.py`
- `backend/agents/agentcore/implementation_monitoring_runtime.py`

## How to Rollback (No Code Change Required)

### Option 1: Environment Variable (Fastest - No Redeploy)
Set this environment variable on all agent containers:
```
DISABLE_BEDROCK_GUARDRAILS=true
```
This causes `get_guardrail_config()` to return an empty dict, bypassing the guardrail.

### Option 2: Delete the Guardrail
```bash
aws bedrock delete-guardrail --guardrail-identifier <GUARDRAIL_ID> --region us-east-1
```
The agents will get an error on the guardrail call and fall back to unguarded behavior (Strands handles missing guardrails gracefully).

### Option 3: Revert Code Changes
Remove the `guardrail_config` import and `**guardrail_kwargs` from each agent runtime file. Revert to the previous `Agent(...)` instantiation without the guardrail kwargs.

## Performance Impact
- Added latency: ~1-3 seconds per model invocation
- Added cost: ~5-10% increase in Bedrock token costs per cycle
- Risk: False positives on legitimate aggressive pricing language (tune denied topics if needed)

## Date Added
2026-05-26
