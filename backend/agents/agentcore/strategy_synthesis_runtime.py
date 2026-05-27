"""AgentCore Runtime entrypoint for the Strategy Synthesis Agent.

Wraps the Strategy Synthesis Agent with BedrockAgentCoreApp to expose
POST /invocations and GET /ping endpoints for AgentCore Runtime deployment.

The Strategy Synthesis Agent expects intelligence outputs from the three
intelligence agents (Competitive, Demand, Market) in the payload context.

Integrates with:
- AgentCore Memory: Persistent memory across invocations
- AgentCore Gateway: Tool access via MCP gateway endpoint

Usage:
    python -m backend.agents.agentcore.strategy_synthesis_runtime
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

SYSTEM_PROMPT = """You are a Strategy Synthesis Agent for a retail dynamic pricing system.

Your role is to synthesize intelligence from competitive analysis, demand forecasting,
and market signals into actionable pricing strategies. You generate ranked pricing
scenarios with projected outcomes.

You have access to tools for:
- Querying cost structures and financial constraints
- Calculating margins and profitability projections
- Validating pricing against business rules
- Generating scenario comparisons

Always return structured JSON with ranked pricing scenarios, projected metrics,
and risk assessments."""


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Handle an invocation request from AgentCore Runtime.

    Expected payload:
        {
            "prompt": "Generate pricing scenarios based on intelligence",
            "session_id": "optional-session-id",
            "actor_id": "optional-actor-id",
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
        session_id = payload.get("session_id")
        actor_id = payload.get("actor_id", "pricing-system")

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
            from backend.agents.strategy_synthesis import (
                create_strategy_synthesis_agent,
            )

            fallback_agent = create_strategy_synthesis_agent(
                cost_finance_mcp_endpoint=os.environ.get("COST_FINANCE_MCP_ENDPOINT"),
            )
            result = fallback_agent(full_prompt)
            return {
                "result": str(result),
                "agent": "strategy_synthesis",
                "status": "success",
            }

        # Create agent with memory, gateway tools, and Bedrock Guardrails
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
