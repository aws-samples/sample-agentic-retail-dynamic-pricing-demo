"""AgentCore Runtime entrypoint for the Orchestrator Agent.

Wraps the Orchestrator Agent with BedrockAgentCoreApp to expose
POST /invocations and GET /ping endpoints for AgentCore Runtime deployment.

The orchestrator accepts a pricing cycle request, invokes the 3 intelligence
agents in parallel via invoke_agent_runtime, passes results to Strategy
Synthesis, and returns ranked scenarios.

Integrates with:
- AgentCore Memory: Persistent memory for tracking pricing cycle state

Usage:
    python -m backend.agents.agentcore.orchestrator_runtime
"""

from __future__ import annotations

import functools
import json
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from bedrock_agentcore.runtime import BedrockAgentCoreApp

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from backend.agents.agentcore.memory_config import create_session_manager
from shared.model_config import ORCHESTRATOR_MODEL

logger = logging.getLogger(__name__)

# [SECURITY FIX] Inline agent output sanitization for prompt injection defense
import re as _re
_INJECTION_PATTERNS = [
    _re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|context)", _re.IGNORECASE),
    _re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", _re.IGNORECASE),
    _re.compile(r"<\s*system\s*>|<<\s*SYS\s*>>|\[INST\]", _re.IGNORECASE),
    _re.compile(r"(forget|disregard|override)\s+(everything|all|your)\s+(above|previous|instructions|rules)", _re.IGNORECASE),
    _re.compile(r"(DAN|do\s+anything\s+now|jailbreak|bypass\s+(safety|guardrail|filter))", _re.IGNORECASE),
]

def _sanitize_agent_output(data: dict, agent_name: str) -> dict:
    """Scan agent output for prompt injection. Returns data if clean, empty dict if detected."""
    def _scan(value):
        if isinstance(value, str):
            for pattern in _INJECTION_PATTERNS:
                if pattern.search(value):
                    logger.warning("Prompt injection detected in %s output", agent_name)
                    return True
        elif isinstance(value, dict):
            for v in value.values():
                if _scan(v):
                    return True
        elif isinstance(value, (list, tuple)):
            for item in value:
                if _scan(item):
                    return True
        return False
    if _scan(data):
        return {}
    return data



app = BedrockAgentCoreApp()

# The orchestrator model comes from shared.model_config (set by
# scripts/select_model.py -> model-config.json, or the ORCHESTRATOR_MODEL_ID
# env var). Imported above as ORCHESTRATOR_MODEL.

# Agent ARNs (set as environment variables on the container)
CI_ARN = os.environ["COMPETITIVE_INTELLIGENCE_AGENT_ARN"]
DF_ARN = os.environ["DEMAND_FORECASTING_AGENT_ARN"]
MI_ARN = os.environ["MARKET_INTELLIGENCE_AGENT_ARN"]
SS_ARN = os.environ["STRATEGY_SYNTHESIS_AGENT_ARN"]
IM_ARN = os.environ["IMPLEMENTATION_MONITORING_AGENT_ARN"]

# Timeout and retry configuration.
#
# Sized from sandbox runs: Market Intelligence ~38 s, Competitive Intelligence
# ~58 s, Demand Forecasting 58-240 s, Strategy Synthesis 71-83 s. Each value is
# the botocore read timeout for that call. The runtimes reply with one JSON body
# when the agent finishes, so the read timeout bounds the whole call.
SPECIALIST_TIMEOUT_SECONDS = 300
SYNTHESIS_TIMEOUT_SECONDS = 180
CONNECT_TIMEOUT_SECONDS = 10

# The orchestrator is the only layer that retries specialist calls: the SDK
# retries are off. It retries only failures that are retryable AND fast (the
# request was rejected or never reached the agent). A read timeout or a slow
# failure means the agent probably ran, so retrying would re-run it and pay for
# it twice.
MAX_RETRIES = 2
FAST_FAILURE_SECONDS = 15
RETRY_BACKOFF_SECONDS = 1.0
_RETRYABLE_ERROR_CODES = frozenset({
    "ThrottlingException",
    "ServiceUnavailableException",
    "InternalServerException",
})

# Upper bound for one cycle, used by rdp-api-pricing-cycles to size its own read
# timeout (tests/test_pricing_cycle_timeouts.py checks the chain). Per call: two
# fast failures plus backoff, then one full-length attempt.
_RETRY_OVERHEAD_SECONDS = MAX_RETRIES * FAST_FAILURE_SECONDS + sum(
    RETRY_BACKOFF_SECONDS * 2**attempt for attempt in range(MAX_RETRIES)
)
ORCHESTRATOR_WORST_CASE_SECONDS = int(
    SPECIALIST_TIMEOUT_SECONDS + SYNTHESIS_TIMEOUT_SECONDS + 2 * _RETRY_OVERHEAD_SECONDS
)

# Minimum session ID length required by AgentCore Runtime
_MIN_SESSION_ID_LENGTH = 33

# Fields of a pricing cycle request. rdp-api-pricing-cycles sends them at the top
# level of the payload; older versions sent them as a JSON string in "prompt".
_CYCLE_REQUEST_KEYS = ("pricing_group", "objectives", "constraints", "product_costs", "session_id")


@functools.lru_cache(maxsize=None)
def _get_agentcore_client(read_timeout: int):
    """Return a bedrock-agentcore client with the given read timeout and no SDK retries."""
    region = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))
    return boto3.client(
        "bedrock-agentcore",
        region_name=region,
        config=Config(
            connect_timeout=CONNECT_TIMEOUT_SECONDS,
            read_timeout=read_timeout,
            retries={"total_max_attempts": 1, "mode": "standard"},
        ),
    )


def _is_retryable(exc: Exception) -> bool:
    """True if the failed call most likely never ran the agent."""
    if isinstance(exc, ReadTimeoutError):
        return False
    if isinstance(exc, (ConnectTimeoutError, EndpointConnectionError)):
        return True
    if isinstance(exc, ClientError):
        return exc.response.get("Error", {}).get("Code", "") in _RETRYABLE_ERROR_CODES
    return False


def _parse_cycle_request(payload: dict) -> dict:
    """Read the cycle request from the payload, accepting both payload shapes.

    Raises ValueError if a field is present with the wrong type.
    """
    request = dict(payload)
    if "pricing_group" not in request and isinstance(request.get("prompt"), str):
        try:
            nested = json.loads(request["prompt"])
        except ValueError:
            nested = None
        if isinstance(nested, dict):
            for key in _CYCLE_REQUEST_KEYS:
                if key in nested and key not in request:
                    request[key] = nested[key]

    if "pricing_group" not in request:
        logger.warning("Payload has no pricing_group; using 'default_category'")

    parsed = {
        "pricing_group": request.get("pricing_group", "default_category"),
        "objectives": request.get("objectives", ["balanced"]),
        "constraints": request.get("constraints", {}),
        "product_costs": request.get("product_costs", []),
        "session_id": request.get("session_id"),
    }
    if not isinstance(parsed["pricing_group"], str) or not parsed["pricing_group"]:
        raise ValueError("pricing_group must be a non-empty string")
    if not isinstance(parsed["objectives"], list) or not all(isinstance(o, str) for o in parsed["objectives"]):
        raise ValueError("objectives must be a list of strings")
    if not isinstance(parsed["constraints"], dict):
        raise ValueError("constraints must be an object")
    if not isinstance(parsed["product_costs"], list):
        raise ValueError("product_costs must be a list")
    if parsed["session_id"] is not None and not isinstance(parsed["session_id"], str):
        raise ValueError("session_id must be a string")
    return parsed


def _ensure_session_id(session_id: str | None) -> str:
    """Ensure the session ID meets AgentCore's minimum length requirement (33+ chars)."""
    if not session_id:
        session_id = f"pricing-cycle-{uuid.uuid4().hex}"
    if len(session_id) < _MIN_SESSION_ID_LENGTH:
        padding = uuid.uuid4().hex
        session_id = f"{session_id}-{padding}"
    return session_id[:128]


def _invoke_agent_runtime(
    agent_arn: str,
    prompt: str,
    session_id: str,
    timeout_seconds: int = SPECIALIST_TIMEOUT_SECONDS,
) -> dict:
    """Invoke an agent via AgentCore Runtime API.

    timeout_seconds is the read timeout. A slow but successful response is
    returned, not discarded.
    """
    client = _get_agentcore_client(timeout_seconds)
    payload = json.dumps({"prompt": prompt}).encode()

    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        runtimeSessionId=session_id,
        payload=payload,
        qualifier="DEFAULT",
    )

    response_body = response["response"].read()

    try:
        result = json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        result = {"raw_output": response_body.decode("utf-8", errors="replace")}

    return result


def _invoke_with_retry(
    agent_arn: str,
    prompt: str,
    agent_name: str,
    session_id: str,
    max_retries: int = MAX_RETRIES,
    timeout_seconds: int = SPECIALIST_TIMEOUT_SECONDS,
) -> dict:
    """Invoke an agent, retrying only fast, retryable failures. Returns result dict with status."""
    runtime_session_id = _ensure_session_id(session_id)

    for attempt in range(1 + max_retries):
        start_time = time.time()
        try:
            logger.info(
                "Invoking %s via AgentCore Runtime (attempt %d/%d)",
                agent_name, attempt + 1, 1 + max_retries,
            )
            output_data = _invoke_agent_runtime(
                agent_arn=agent_arn,
                prompt=prompt,
                session_id=runtime_session_id,
                timeout_seconds=timeout_seconds,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("%s completed in %dms", agent_name, duration_ms)

            return {
                "agent_name": agent_name,
                "success": True,
                "data": output_data,
                "duration_ms": duration_ms,
                "retries_used": attempt,
            }
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            retry = (
                attempt < max_retries
                and _is_retryable(e)
                and duration_ms < FAST_FAILURE_SECONDS * 1000
            )
            if retry:
                logger.warning(
                    "%s failed on attempt %d/%d (%dms): %s. Retrying...",
                    agent_name, attempt + 1, 1 + max_retries, duration_ms, str(e),
                )
                time.sleep(RETRY_BACKOFF_SECONDS * 2**attempt)
            else:
                logger.error(
                    "%s failed on attempt %d (%dms), not retrying: %s. Degrading.",
                    agent_name, attempt + 1, duration_ms, str(e),
                )
                return {
                    "agent_name": agent_name,
                    "success": False,
                    "error": str(e),
                    "duration_ms": duration_ms,
                    "retries_used": attempt,
                }

    return {
        "agent_name": agent_name,
        "success": False,
        "error": "Unexpected: exhausted all retry attempts",
        "retries_used": max_retries,
    }


def _run_parallel_intelligence(prompt: str, session_id: str) -> list[dict]:
    """Run the 3 intelligence agents in parallel."""
    agent_configs = [
        {"arn": CI_ARN, "name": "Competitive Intelligence"},
        {"arn": DF_ARN, "name": "Demand Forecasting"},
        {"arn": MI_ARN, "name": "Market Intelligence"},
    ]

    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                _invoke_with_retry,
                agent_arn=cfg["arn"],
                prompt=prompt,
                agent_name=cfg["name"],
                session_id=session_id,
            ): cfg["name"]
            for cfg in agent_configs
        }

        for future in as_completed(futures):
            agent_name = futures[future]
            try:
                # as_completed only yields finished futures; each call is
                # bounded by its read timeout.
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error("%s raised unexpected exception: %s", agent_name, e)
                results.append({
                    "agent_name": agent_name,
                    "success": False,
                    "error": f"Unexpected error: {e}",
                    "retries_used": MAX_RETRIES,
                })

    return results


def _get_agent_data(results: list[dict], agent_name: str) -> dict:
    """Extract data from a specific agent's result."""
    for result in results:
        if result["agent_name"] == agent_name:
            if result["success"]:
                return result.get("data", {})
            else:
                return {"_degraded": True, "_error": result.get("error")}
    return {"_degraded": True, "_error": "Agent not found in results"}


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Handle an invocation request from AgentCore Runtime.

    Expected payload (the same fields as a JSON string in "prompt" are also
    accepted, for callers deployed before the top-level shape):
        {
            "pricing_group": "Electronics",
            "objectives": ["revenue_maximization"],
            "constraints": {"min_margin": 0.15},
            "product_costs": [...],
            "session_id": "optional-session-id"
        }

    Returns:
        {
            "cycle_id": "...",
            "status": "COMPLETE" | "DEGRADED" | "FAILED",
            "ranked_scenarios": [...],
            "degraded_agents": [...],
            "metadata": {...}
        }
    """
    try:
        request = _parse_cycle_request(payload)
        pricing_group = request["pricing_group"]
        objectives = request["objectives"]
        constraints = request["constraints"]
        product_costs = request["product_costs"]
        session_id = request["session_id"]

        cycle_id = str(uuid.uuid4())
        cycle_start = time.time()

        # Configure AgentCore Memory for cycle state tracking
        session_manager = create_session_manager(
            session_id=session_id, actor_id="orchestrator"
        )

        logger.info(
            "Starting pricing cycle %s for group '%s' with objectives %s (memory=%s)",
            cycle_id, pricing_group, objectives,
            "enabled" if session_manager else "disabled",
        )

        # Build the analysis prompt for intelligence agents
        analysis_prompt = (
            f"Analyze pricing for the '{pricing_group}' product group. "
            f"Strategic objectives: {', '.join(objectives)}. "
        )
        if constraints:
            analysis_prompt += f"Constraints: {constraints}. "
        analysis_prompt += (
            "Use your available MCP tools to gather data and return your "
            "structured analysis as JSON."
        )

        # Phase 1: Parallel intelligence gathering
        agent_results = _run_parallel_intelligence(analysis_prompt, session_id)

        successful_results = [r for r in agent_results if r["success"]]
        degraded_agents = [r["agent_name"] for r in agent_results if not r["success"]]

        # Check if we can proceed
        if len(successful_results) == 0:
            logger.error("All intelligence agents failed for cycle %s.", cycle_id)
            return {
                "cycle_id": cycle_id,
                "status": "FAILED",
                "ranked_scenarios": [],
                "degraded_agents": degraded_agents,
                "metadata": {
                    "duration_ms": int((time.time() - cycle_start) * 1000),
                    "reason": "All intelligence agents failed after retries",
                },
            }

        # Phase 2: Strategy Synthesis via AgentCore Runtime
        competitive_data = _get_agent_data(agent_results, "Competitive Intelligence")
        demand_data = _get_agent_data(agent_results, "Demand Forecasting")
        market_data = _get_agent_data(agent_results, "Market Intelligence")

        # [SECURITY FIX] Sanitize agent outputs before passing to synthesis
        competitive_data = _sanitize_agent_output(competitive_data, "Competitive Intelligence")
        demand_data = _sanitize_agent_output(demand_data, "Demand Forecasting")
        market_data = _sanitize_agent_output(market_data, "Market Intelligence")

        synthesis_prompt = json.dumps({
            "competitive_intelligence": competitive_data,
            "demand_forecasting": demand_data,
            "market_intelligence": market_data,
            "product_costs": product_costs,
            "cycle_id": cycle_id,
            "objectives": objectives,
            "constraints": constraints,
        })

        logger.info(
            "Invoking Strategy Synthesis Agent with %d/%d intelligence inputs",
            len(successful_results), len(agent_results),
        )

        synthesis = _invoke_with_retry(
            agent_arn=SS_ARN,
            prompt=synthesis_prompt,
            agent_name="Strategy Synthesis",
            session_id=session_id,
            timeout_seconds=SYNTHESIS_TIMEOUT_SECONDS,
        )
        if not synthesis["success"]:
            return {
                "cycle_id": cycle_id,
                "status": "FAILED",
                "ranked_scenarios": [],
                "degraded_agents": degraded_agents + ["Strategy Synthesis"],
                "error": synthesis.get("error"),
                "metadata": {
                    "duration_ms": int((time.time() - cycle_start) * 1000),
                    "reason": "Strategy Synthesis failed",
                },
            }
        synthesis_result = synthesis["data"]

        ranked_scenarios = synthesis_result.get("ranked_scenarios", [])
        status = "DEGRADED" if degraded_agents else "COMPLETE"
        cycle_duration_ms = int((time.time() - cycle_start) * 1000)

        logger.info(
            "Pricing cycle %s completed with status %s: %d scenarios in %dms",
            cycle_id, status, len(ranked_scenarios), cycle_duration_ms,
        )

        return {
            "cycle_id": cycle_id,
            "status": status,
            "ranked_scenarios": ranked_scenarios,
            "degraded_agents": degraded_agents,
            "metadata": {
                "duration_ms": cycle_duration_ms,
                "pricing_group": pricing_group,
                "objectives": objectives,
                "constraints": constraints,
                "synthesis_metadata": synthesis_result.get("synthesis_metadata", {}),
            },
        }

    except Exception as e:
        logger.exception("Orchestrator runtime error")
        return {
            "cycle_id": payload.get("cycle_id", "unknown"),
            "status": "FAILED",
            "ranked_scenarios": [],
            "degraded_agents": [],
            "error": str(e),
        }


if __name__ == "__main__":
    app.run()
