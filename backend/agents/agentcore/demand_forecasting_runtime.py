"""AgentCore Runtime entrypoint for the Demand Forecasting Agent.

Wraps the Demand Forecasting Agent with BedrockAgentCoreApp to expose
POST /invocations and GET /ping endpoints for AgentCore Runtime deployment.

Integrates with:
- AgentCore Memory: Persistent memory across invocations
- AgentCore Gateway: Tool access via MCP gateway endpoint

Usage:
    python -m backend.agents.agentcore.demand_forecasting_runtime
"""

from __future__ import annotations

import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.tools.mcp import MCPClient

from backend.agents.agentcore.memory_config import create_session_manager
from backend.agents.agentcore.guardrail_config import get_guardrail_config

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

GATEWAY_ENDPOINT = os.environ.get("AGENTCORE_GATEWAY_ENDPOINT", "")

SYSTEM_PROMPT = """You are a Demand Forecasting Agent for a retail dynamic pricing system.

Your role is to analyze historical sales data, seasonal patterns, and external factors
to forecast demand for products and categories.

You have access to tools for:
- Querying ERP/POS sales history
- Analyzing inventory levels and turnover rates
- Identifying seasonal and cyclical demand patterns
- Correlating demand with pricing changes

Always return structured JSON analysis with demand forecasts and confidence intervals."""


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Handle an invocation request from AgentCore Runtime.

    Expected payload:
        {
            "prompt": "Forecast demand for product X",
            "session_id": "optional-session-id",
            "actor_id": "optional-actor-id",
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
        session_id = payload.get("session_id")
        actor_id = payload.get("actor_id", "pricing-system")

        # Build the full prompt with context if provided
        full_prompt = prompt
        if context:
            full_prompt = f"{prompt}\n\nContext:\n{json.dumps(context, indent=2)}"

        # Configure AgentCore Memory session manager
        session_manager = create_session_manager(
            session_id=session_id, actor_id=actor_id
        )

        # Configure tools via AgentCore Gateway or fallback to direct import
        tools = []
        if GATEWAY_ENDPOINT:
            mcp_client = MCPClient(
                lambda: MCPClient.streamable_http(GATEWAY_ENDPOINT)
            )
            tools = [mcp_client]
        else:
            # Fallback: import tools directly from the agent module
            from backend.agents.demand_forecasting import (
                create_demand_forecasting_agent,
            )

            fallback_agent = create_demand_forecasting_agent(
                erp_pos_mcp_endpoint=os.environ.get("ERP_POS_MCP_ENDPOINT"),
            )
            result = fallback_agent(full_prompt)
            return {
                "result": str(result),
                "agent": "demand_forecasting",
                "status": "success",
            }

        # Create agent with memory and gateway tools
        guardrail_kwargs = get_guardrail_config()
        agent = Agent(
            model="us.anthropic.claude-sonnet-4-6",
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
            session_manager=session_manager,
            **guardrail_kwargs,
        )

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
