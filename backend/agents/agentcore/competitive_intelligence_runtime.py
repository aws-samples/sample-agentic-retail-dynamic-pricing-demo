"""AgentCore Runtime entrypoint for the Competitive Intelligence Agent.

Wraps the Competitive Intelligence Agent with BedrockAgentCoreApp to expose
POST /invocations and GET /ping endpoints for AgentCore Runtime deployment.

Usage:
    python -m backend.agents.agentcore.competitive_intelligence_runtime
"""

from __future__ import annotations

import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from backend.agents.competitive_intelligence import create_competitive_intelligence_agent

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

# Create the agent instance at module level for reuse across invocations
agent = create_competitive_intelligence_agent(
    competitor_api_mcp_endpoint=os.environ.get("COMPETITOR_API_MCP_ENDPOINT"),
    use_browser=os.environ.get("USE_BROWSER", "false").lower() == "true",
)


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Handle an invocation request from AgentCore Runtime.

    Expected payload:
        {
            "prompt": "Analyze competitor pricing for product X",
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

        # Build the full prompt with context if provided
        full_prompt = prompt
        if context:
            full_prompt = f"{prompt}\n\nContext:\n{json.dumps(context, indent=2)}"

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
