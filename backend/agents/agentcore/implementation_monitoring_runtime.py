"""AgentCore Runtime entrypoint for the Implementation Monitoring Agent.

Wraps the Implementation Monitoring Agent with BedrockAgentCoreApp to expose
POST /invocations and GET /ping endpoints for AgentCore Runtime deployment.

The Implementation Monitoring Agent expects scenario data and projected
metrics in the payload context for tracking post-implementation KPIs.

Integrates with:
- AgentCore Memory: Persistent memory for tracking implementation outcomes

Usage:
    python -m backend.agents.agentcore.implementation_monitoring_runtime
"""

from __future__ import annotations

import json
import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from backend.agents.agentcore.memory_config import create_session_manager

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Handle an invocation request from AgentCore Runtime.

    Expected payload:
        {
            "prompt": "Implement and monitor approved scenario",
            "session_id": "optional-session-id",
            "actor_id": "optional-actor-id",
            "context": {
                "scenario_id": "...",
                "cycle_id": "...",
                "price_changes": [
                    {"product_id": "...", "current_price": 29.99, "new_price": 34.99}
                ],
                "projected_metrics": {
                    "projected_revenue": 150000.0,
                    "projected_margin": 0.22,
                    "projected_market_share": 0.15
                },
                "monitoring_config": {
                    "revenue_variance_threshold": 0.10,
                    "margin_variance_threshold": 0.03,
                    "polling_interval_minutes": 60
                }
            }
        }

    Returns:
        {
            "result": "<agent response text>",
            "agent": "implementation_monitoring",
            "status": "success" | "error"
        }
    """
    try:
        prompt = payload.get("prompt", "Monitor implementation performance")
        context = payload.get("context", {})
        session_id = payload.get("session_id")
        actor_id = payload.get("actor_id", "pricing-system")

        # Build the full prompt with scenario and metrics context
        full_prompt = prompt
        if context:
            context_parts = []

            if "scenario_id" in context:
                context_parts.append(f"Scenario ID: {context['scenario_id']}")
            if "cycle_id" in context:
                context_parts.append(f"Cycle ID: {context['cycle_id']}")
            if "price_changes" in context:
                context_parts.append(
                    f"Price Changes:\n{json.dumps(context['price_changes'], indent=2)}"
                )
            if "projected_metrics" in context:
                context_parts.append(
                    f"Projected Metrics:\n{json.dumps(context['projected_metrics'], indent=2)}"
                )
            if "monitoring_config" in context:
                context_parts.append(
                    f"Monitoring Config:\n{json.dumps(context['monitoring_config'], indent=2)}"
                )

            if context_parts:
                full_prompt = f"{prompt}\n\n" + "\n\n".join(context_parts)
            else:
                full_prompt = f"{prompt}\n\nContext:\n{json.dumps(context, indent=2)}"

        # Configure AgentCore Memory session manager
        session_manager = create_session_manager(
            session_id=session_id, actor_id=actor_id
        )

        # Create the agent with memory support
        # We import tools from the module and construct the agent with session_manager
        from backend.agents.implementation_monitoring import (
            IMPLEMENTATION_MONITORING_SYSTEM_PROMPT,
            execute_price_update,
            track_kpis,
            detect_performance_variance,
            generate_adjustment,
        )
        from strands import Agent
        from backend.agents.agentcore.guardrail_config import get_guardrail_config

        guardrail_kwargs = get_guardrail_config()
        agent = Agent(
            model="us.anthropic.claude-sonnet-4-6",
            system_prompt=IMPLEMENTATION_MONITORING_SYSTEM_PROMPT,
            tools=[
                execute_price_update,
                track_kpis,
                detect_performance_variance,
                generate_adjustment,
            ],
            session_manager=session_manager,
            **guardrail_kwargs,
        )

        result = agent(full_prompt)

        return {
            "result": str(result),
            "agent": "implementation_monitoring",
            "status": "success",
        }
    except Exception as e:
        logger.exception("Error invoking Implementation Monitoring Agent")
        return {
            "result": str(e),
            "agent": "implementation_monitoring",
            "status": "error",
        }


if __name__ == "__main__":
    app.run()
