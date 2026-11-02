"""Bedrock guardrail configuration for the Retail Dynamic Pricing agents.

The CDK stack creates the guardrail (cdk/stacks/guardrail.py; policy in
shared/pricing_guardrail.py). It blocks price fixing and collusion,
discriminatory pricing, emergency price gouging, predatory pricing and prompt
attacks. scripts/deploy_agentcore.py sets on every runtime either:

    BEDROCK_GUARDRAIL_ID / BEDROCK_GUARDRAIL_VERSION
        the stack's guardrail (BedrockGuardrailId / BedrockGuardrailVersion
        outputs), or one you set yourself before deploying
    DISABLE_BEDROCK_GUARDRAILS=true
        explicit opt-out (rollback or local testing): no guardrail is attached

Neither set is a configuration error, not a reason to run unguarded:
get_guardrail_model_kwargs() raises, so the agent fails instead of quietly
calling the model without the guardrail.

The guardrail is attached to the Bedrock *model* (BedrockModel guardrail_*
settings); strands.Agent has no guardrail parameter. Only the prompt each agent
receives is sent to the guardrail as input (guardrail_latest_message): the
system prompt and earlier turns are not re-screened on every model call, and
tool results are never screened by Converse. Every model response is screened.
Strategy Synthesis is the exception for input: see synthesis_prompt_content().
"""

import json
import os

DISABLE_ENV = "DISABLE_BEDROCK_GUARDRAILS"
GUARDRAIL_ID_ENV = "BEDROCK_GUARDRAIL_ID"
GUARDRAIL_VERSION_ENV = "BEDROCK_GUARDRAIL_VERSION"


class GuardrailNotConfigured(RuntimeError):
    """Neither a guardrail nor the explicit opt-out is configured."""


def guardrails_disabled() -> bool:
    return os.environ.get(DISABLE_ENV, "").strip().lower() == "true"


def get_guardrail_model_kwargs(latest_message: bool = True) -> dict:
    """BedrockModel keyword arguments that attach the guardrail.

    Empty if DISABLE_BEDROCK_GUARDRAILS=true. Raises GuardrailNotConfigured if no
    guardrail ID is set either. latest_message=False is for prompts that mark
    the content to screen themselves (guardContent blocks).

    Usage with Strands:
        model = BedrockModel(model_id=SPECIALIST_MODEL, **get_guardrail_model_kwargs())
        agent = Agent(model=model, system_prompt=SYSTEM_PROMPT, tools=tools)
    """
    if guardrails_disabled():
        return {}
    guardrail_id = get_guardrail_id()
    if not guardrail_id:
        raise GuardrailNotConfigured(
            f"No Bedrock guardrail configured: set {GUARDRAIL_ID_ENV} / {GUARDRAIL_VERSION_ENV} "
            f"(scripts/deploy_agentcore.py does this), or {DISABLE_ENV}=true to run without one."
        )
    return {
        "guardrail_id": guardrail_id,
        "guardrail_version": get_guardrail_version(),
        "guardrail_trace": "enabled",
        "guardrail_latest_message": latest_message,
    }


# Keys of the JSON object the orchestrator sends to Strategy Synthesis.
_ANALYST_REPORTS = ("competitive_intelligence", "demand_forecasting", "market_intelligence")
_REQUEST_FIELDS = ("objectives", "constraints")


def synthesis_prompt_content(prompt: str) -> list[dict] | None:
    """Content blocks for the synthesis prompt that screen only the request as guardrail input.

    The orchestrator sends Strategy Synthesis a JSON object with the three analyst
    reports, the product costs and the cycle's objectives and constraints. The
    reports are model responses, already screened as guardrail output by the
    agents that wrote them. Screening them again as input adds nothing for the
    denied topics, and the prompt-attack filter flags them: pricing advice reads
    like instructions ("raise online prices to $113.99"), and a legitimate
    synthesis prompt from an evaluation run was blocked on all four checks (LOW
    or MEDIUM confidence; the filter blocks from LOW). So the prompt is sent unchanged
    as text, plus a guardContent block with the objectives and constraints, the
    part a dashboard user controls. Once a message has a guardContent block,
    Bedrock screens only that block as input; every model response is still
    screened. Use with get_guardrail_model_kwargs(latest_message=False).

    Returns None (screen the whole prompt as usual) if the prompt is not that
    JSON object or the guardrail is disabled.
    """
    if guardrails_disabled():
        return None
    try:
        data = json.loads(prompt)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not any(key in data for key in _ANALYST_REPORTS):
        return None
    request = {key: data[key] for key in _REQUEST_FIELDS if data.get(key)}
    if not request:
        return None
    return [
        {"guardContent": {"text": {"text": "Pricing request: " + json.dumps(request)}}},
        {"text": prompt},
    ]


def get_guardrail_id() -> str:
    """Guardrail ID from BEDROCK_GUARDRAIL_ID ('' if unset)."""
    return os.environ.get(GUARDRAIL_ID_ENV, "").strip()


def get_guardrail_version() -> str:
    """Guardrail version from BEDROCK_GUARDRAIL_VERSION (default DRAFT)."""
    return os.environ.get(GUARDRAIL_VERSION_ENV, "").strip() or "DRAFT"
