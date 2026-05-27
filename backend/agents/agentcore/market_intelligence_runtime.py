"""AgentCore Runtime entrypoint for the Market Intelligence Agent.

Wraps the Market Intelligence Agent with BedrockAgentCoreApp to expose
POST /invocations and GET /ping endpoints for AgentCore Runtime deployment.

Integrates with:
- AgentCore Memory: Persistent memory across invocations
- AgentCore Gateway: Tool access via MCP gateway endpoint

Usage:
    python -m backend.agents.agentcore.market_intelligence_runtime
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

SYSTEM_PROMPT = """You are a Market Intelligence Agent for a retail dynamic pricing system.

Your role is to analyze market trends, consumer sentiment, economic indicators, and
external signals that affect pricing decisions.

You have access to tools for:
- Monitoring market trends and news
- Analyzing consumer sentiment and reviews
- Tracking economic indicators (CPI, consumer confidence)
- Identifying seasonal events and promotional calendars

Always return structured JSON analysis with market signals and their pricing implications."""


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Handle an invocation request from AgentCore Runtime.

    Expected payload:
        {
            "prompt": "Analyze market conditions for category X",
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
            "agent": "market_intelligence",
            "status": "success" | "error"
        }
    """
    try:
        prompt = payload.get("prompt", "Analyze market conditions and trends")
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
            from backend.agents.market_intelligence import (
                create_market_intelligence_agent,
            )

            fallback_agent = create_market_intelligence_agent(
                mcp_server_url=os.environ.get("MARKET_SIGNALS_MCP_ENDPOINT"),
                region=os.environ.get("AWS_REGION", "us-east-1"),
            )
            result = fallback_agent(full_prompt)
            return {
                "result": str(result),
                "agent": "market_intelligence",
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
            "agent": "market_intelligence",
            "status": "success",
        }
    except Exception as e:
        logger.exception("Error invoking Market Intelligence Agent")
        return {
            "result": str(e),
            "agent": "market_intelligence",
            "status": "error",
        }


if __name__ == "__main__":
    app.run()
