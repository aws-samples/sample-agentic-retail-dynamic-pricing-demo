"""AgentCore Runtime entrypoint for the Demand Forecasting Agent.

Wraps the Demand Forecasting Agent with BedrockAgentCoreApp to expose
POST /invocations and GET /ping endpoints for AgentCore Runtime deployment.

Usage:
    python -m backend.agents.agentcore.demand_forecasting_runtime
"""

from __future__ import annotations

import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from backend.agents.demand_forecasting import create_demand_forecasting_agent

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

# Create the agent instance at module level for reuse across invocations
agent = create_demand_forecasting_agent(
    erp_pos_mcp_endpoint=os.environ.get("ERP_POS_MCP_ENDPOINT"),
)


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Handle an invocation request from AgentCore Runtime.

    Expected payload:
        {
            "prompt": "Forecast demand for product X",
            "context": {
                "product_id": "...",
                "category": "...",
                "time_horizon": "7d" | "30d" | "90d"
            }
        }

    Returns:
        {
            "result": "<agent response text>",
            "agent": "demand_forecasting",
            "status": "success" | "error"
        }
    """
    try:
        prompt = payload.get("prompt", "Analyze demand patterns and forecast")
        context = payload.get("context", {})

        # Build the full prompt with context if provided
        full_prompt = prompt
        if context:
            full_prompt = f"{prompt}\n\nContext:\n{json.dumps(context, indent=2)}"

        result = agent(full_prompt)

        return {
            "result": str(result),
            "agent": "demand_forecasting",
            "status": "success",
        }
    except Exception as e:
        logger.exception("Error invoking Demand Forecasting Agent")
        return {
            "result": str(e),
            "agent": "demand_forecasting",
            "status": "error",
        }


if __name__ == "__main__":
    app.run()
