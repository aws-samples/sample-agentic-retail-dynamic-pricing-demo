"""AgentCore Runtime entrypoint for the Strategy Synthesis Agent.

Wraps the Strategy Synthesis Agent with BedrockAgentCoreApp to expose
POST /invocations and GET /ping endpoints for AgentCore Runtime deployment.

The Strategy Synthesis Agent expects intelligence outputs from the three
intelligence agents (Competitive, Demand, Market) in the payload context.

Usage:
    python -m backend.agents.agentcore.strategy_synthesis_runtime
"""

from __future__ import annotations

import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from backend.agents.strategy_synthesis import create_strategy_synthesis_agent

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

# Create the agent instance at module level for reuse across invocations
agent = create_strategy_synthesis_agent(
    cost_finance_mcp_endpoint=os.environ.get("COST_FINANCE_MCP_ENDPOINT"),
)


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Handle an invocation request from AgentCore Runtime.

    Expected payload:
        {
            "prompt": "Generate pricing scenarios based on intelligence",
            "context": {
                "cycle_id": "...",
                "pricing_group": "...",
                "competitive_intelligence": { ... },
                "demand_forecasting": { ... },
                "market_intelligence": { ... },
                "constraints": {
                    "min_margin": 0.15,
                    "max_price_change": 0.20,
                    "channel_restrictions": []
                }
            }
        }

    Returns:
        {
            "result": "<agent response text>",
            "agent": "strategy_synthesis",
            "status": "success" | "error"
        }
    """
    try:
        prompt = payload.get("prompt", "Synthesize pricing strategies")
        context = payload.get("context", {})

        # Build the full prompt including intelligence outputs
        full_prompt = prompt
        if context:
            intelligence_summary = []

            if "competitive_intelligence" in context:
                intelligence_summary.append(
                    f"Competitive Intelligence:\n{json.dumps(context['competitive_intelligence'], indent=2)}"
                )
            if "demand_forecasting" in context:
                intelligence_summary.append(
                    f"Demand Forecasting:\n{json.dumps(context['demand_forecasting'], indent=2)}"
                )
            if "market_intelligence" in context:
                intelligence_summary.append(
                    f"Market Intelligence:\n{json.dumps(context['market_intelligence'], indent=2)}"
                )
            if "constraints" in context:
                intelligence_summary.append(
                    f"Constraints:\n{json.dumps(context['constraints'], indent=2)}"
                )

            if intelligence_summary:
                full_prompt = f"{prompt}\n\n" + "\n\n".join(intelligence_summary)
            else:
                full_prompt = f"{prompt}\n\nContext:\n{json.dumps(context, indent=2)}"

        result = agent(full_prompt)

        return {
            "result": str(result),
            "agent": "strategy_synthesis",
            "status": "success",
        }
    except Exception as e:
        logger.exception("Error invoking Strategy Synthesis Agent")
        return {
            "result": str(e),
            "agent": "strategy_synthesis",
            "status": "error",
        }


if __name__ == "__main__":
    app.run()
