"""AgentCore Runtime entrypoint for the Market Intelligence Agent.

Wraps the Market Intelligence Agent with BedrockAgentCoreApp to expose
POST /invocations and GET /ping endpoints for AgentCore Runtime deployment.

Usage:
    python -m backend.agents.agentcore.market_intelligence_runtime
"""

from __future__ import annotations

import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from backend.agents.market_intelligence import create_market_intelligence_agent

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

# Create the agent instance at module level for reuse across invocations
agent = create_market_intelligence_agent(
    mcp_server_url=os.environ.get("MARKET_SIGNALS_MCP_ENDPOINT"),
    region=os.environ.get("AWS_REGION", "us-east-1"),
)


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Handle an invocation request from AgentCore Runtime.

    Expected payload:
        {
            "prompt": "Analyze market conditions for category X",
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

        # Build the full prompt with context if provided
        full_prompt = prompt
        if context:
            full_prompt = f"{prompt}\n\nContext:\n{json.dumps(context, indent=2)}"

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
