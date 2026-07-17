"""AgentCore Runtime entrypoint for the Competitive Intelligence Agent.

Wraps the Competitive Intelligence Agent with BedrockAgentCoreApp to expose
POST /invocations and GET /ping endpoints for AgentCore Runtime deployment.

Integrates with:
- AgentCore Memory: Persistent memory across invocations
- AgentCore Gateway: Tool access via MCP gateway endpoint

Usage:
    python -m backend.agents.agentcore.competitive_intelligence_runtime
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

SYSTEM_PROMPT = """You are a Competitive Intelligence Agent for a retail dynamic pricing system.

Your role is to analyze competitor pricing data, identify pricing patterns, and provide
actionable intelligence about the competitive landscape.

You have access to tools for:
- Fetching competitor prices for products and categories
- Analyzing price history and trends
- Monitoring competitor promotions and discounts
- Comparing price positioning across channels

Always return structured JSON analysis with clear recommendations."""


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Handle an invocation request from AgentCore Runtime.

    Expected payload:
        {
            "prompt": "Analyze competitor pricing for product X",
            "session_id": "optional-session-id",
            "actor_id": "optional-actor-id",
            "context": {
                "product_id": "...",
                "category": "...",
                "pricing_group": "..."
            }
        }

    Returns:
        {
            "result": "<agent response text>",
            "agent": "competitive_intelligence",
            "status": "success" | "error"
        }
    """
    try:
        prompt = payload.get("prompt", "Analyze competitor pricing data")
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
            from backend.agents.competitive_intelligence import (
                create_competitive_intelligence_agent,
            )

            fallback_agent = create_competitive_intelligence_agent(
                competitor_api_mcp_endpoint=os.environ.get(
                    "COMPETITOR_API_MCP_ENDPOINT"
                ),
                use_browser=os.environ.get("USE_BROWSER", "false").lower() == "true",
            )
            result = fallback_agent(full_prompt)
            return {
                "result": str(result),
                "agent": "competitive_intelligence",
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
            "agent": "competitive_intelligence",
            "status": "success",
        }
    except Exception as e:
        logger.exception("Error invoking Competitive Intelligence Agent")
        return {
            "result": str(e),
            "agent": "competitive_intelligence",
            "status": "error",
        }


if __name__ == "__main__":
    app.run()
