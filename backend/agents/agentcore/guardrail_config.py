"""Bedrock Guardrails configuration for Retail Dynamic Pricing agents.

All agents in the pricing system use this guardrail to prevent:
- Predatory pricing strategies
- Price fixing and collusion
- Discriminatory pricing based on protected characteristics
- Price gouging during emergencies

Guardrail ID: mgu29odtpk6m
Version: 1

ROLLBACK: To disable guardrails, set environment variable
DISABLE_BEDROCK_GUARDRAILS=true on the agent containers.
This will cause get_guardrail_config() to return an empty dict,
effectively bypassing the guardrail without code changes.
"""

import os

# Guardrail identifiers (created via Bedrock API)
GUARDRAIL_ID = "mgu29odtpk6m"
GUARDRAIL_VERSION = "4"


def get_guardrail_config() -> dict:
    """Return the guardrail configuration for Strands Agent model kwargs.

    Returns an empty dict if DISABLE_BEDROCK_GUARDRAILS=true is set,
    allowing quick rollback without redeployment.

    Usage with Strands Agent:
        from backend.agents.agentcore.guardrail_config import get_guardrail_config

        agent = Agent(
            model="us.anthropic.claude-sonnet-4-6",
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
            **get_guardrail_config(),
        )
    """
    if os.environ.get("DISABLE_BEDROCK_GUARDRAILS", "").lower() == "true":
        return {}

    return {
        "guardrail_config": {
            "guardrailIdentifier": GUARDRAIL_ID,
            "guardrailVersion": GUARDRAIL_VERSION,
            "trace": "enabled",
        }
    }


def get_guardrail_id() -> str:
    """Return the guardrail ID for direct API usage."""
    return GUARDRAIL_ID


def get_guardrail_version() -> str:
    """Return the guardrail version for direct API usage."""
    return GUARDRAIL_VERSION
