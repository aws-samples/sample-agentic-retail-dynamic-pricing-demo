"""Orchestrator Agent for the Retail Dynamic Pricing system.

The central coordinating agent that receives pricing requests, delegates work
to specialized intelligence agents in parallel, feeds combined outputs to the
Strategy Synthesis Agent, and hands off approved scenarios to the Implementation
Monitoring Agent.

Uses Amazon Bedrock AgentCore Runtime API (invoke_agent_runtime) exclusively
for agent invocation. All agents run on AgentCore — there is no local
execution mode.

Architecture:
    1. Receive pricing request (product group, objectives, constraints)
    2. Invoke 3 intelligence agents in parallel (120s timeout each):
       - Competitive Intelligence Agent
       - Demand Forecasting Agent
       - Market Intelligence Agent
    3. Wait for all 3 to complete (or timeout/fail with retry up to 2x)
    4. Pass combined intelligence outputs to Strategy Synthesis Agent
    5. Return ranked pricing scenarios
    6. On approval, hand off to Implementation Monitoring Agent

Requirements: 1.1, 1.2, 1.3
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from dataclasses import dataclass, field
from typing import Any

import boto3
from strands import Agent

from backend.agents.strategy_synthesis import synthesize_pricing_strategies

logger = logging.getLogger(__name__)

# Model configuration for orchestrator (Requirement 1.6)
from shared.model_config import ORCHESTRATOR_MODEL

# Timeout and retry configuration (Requirements 1.5, 1.8)
AGENT_TIMEOUT_SECONDS = 120
MAX_RETRIES = 2


# ---------------------------------------------------------------------------
# AgentCore Runtime configuration (environment variables)
# All ARNs are REQUIRED. If missing, the system raises a clear error when
# the agent is invoked. There is no local execution fallback.
# ---------------------------------------------------------------------------


def _require_env(var_name: str) -> str:
    """Read a required environment variable or raise a clear error.

    Called at invocation time to validate that the ARN is configured.
    """
    value = os.environ.get(var_name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{var_name}' is not set. "
            f"All agent ARNs must be configured for AgentCore Runtime. "
            f"There is no local execution fallback."
        )
    return value


def _get_agent_arn(var_name: str) -> str:
    """Get an agent ARN from environment, raising if not set."""
    return _require_env(var_name)

# Minimum session ID length required by AgentCore Runtime
_MIN_SESSION_ID_LENGTH = 33

# ---------------------------------------------------------------------------
# System prompt for orchestration
# ---------------------------------------------------------------------------

ORCHESTRATOR_SYSTEM_PROMPT = """You are the Orchestrator Agent for a retail dynamic pricing system.

Your role is to coordinate the end-to-end pricing cycle by delegating tasks to specialized agents, assembling their outputs, and managing the workflow from request to implementation.

## Responsibilities

1. **Receive Pricing Requests**: Accept pricing update requests specifying a Pricing Group (product family, sub-category, or category), strategic objectives, and business constraints.

2. **Delegate to Intelligence Agents**: Invoke three specialized agents in parallel:
   - Competitive Intelligence Agent: Analyzes competitor pricing, market positioning, and channel dynamics
   - Demand Forecasting Agent: Analyzes sales history, POS data, inventory levels, and price elasticity
   - Market Intelligence Agent: Analyzes market trends, consumer sentiment, and macroeconomic indicators

3. **Coordinate Execution**: Monitor agent progress, enforce 120-second timeouts per agent, retry failed agents up to 2 times, and gracefully degrade when agents fail after all retries.

4. **Assemble Results**: Once all intelligence agents complete (or degrade), pass their combined outputs to the Strategy Synthesis Agent to generate 50+ ranked pricing scenarios.

5. **Manage Approvals**: After scenarios are generated and reviewed, hand off approved scenarios to the Implementation Monitoring Agent for price updates and KPI tracking.

## Execution Rules

- Each intelligence agent has a 120-second timeout. If an agent exceeds this, terminate and retry.
- Retry failed agents up to 2 times before marking as degraded.
- If an agent fails after all retries, proceed with available outputs and flag the incomplete analysis.
- The Strategy Synthesis Agent receives all available intelligence outputs plus cost/finance data.
- Maintain session isolation: each pricing cycle operates independently.

## Graceful Degradation

- 3 of 3 agents succeed: Full analysis, highest confidence scenarios
- 2 of 3 agents succeed: Generate scenarios with available data, flag missing analysis
- 1 of 3 agents succeed: Generate limited scenarios, prominently warn about incomplete analysis
- 0 of 3 agents succeed: Fail the pricing cycle, notify the Product Manager

## Output

Coordinate the full pipeline and return the final set of ranked pricing scenarios with confidence scores, risk classifications, and status labels.
"""


# ---------------------------------------------------------------------------
# Data classes for orchestration state
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Result from a single agent invocation.

    Attributes:
        agent_name: Name of the agent that produced this result.
        success: Whether the agent completed successfully.
        data: The agent's output data (structured dict).
        error: Error message if the agent failed.
        duration_ms: Execution duration in milliseconds.
        retries_used: Number of retries that were needed.
    """

    agent_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: int = 0
    retries_used: int = 0


@dataclass
class PricingCycleRequest:
    """Input request for a pricing cycle.

    Attributes:
        pricing_group: The product group to analyze (product family, sub-category, or category).
        pricing_group_type: Type of grouping (PRODUCT_FAMILY, SUB_CATEGORY, CATEGORY).
        objectives: Strategic objectives (e.g., revenue_maximization, margin_protection).
        constraints: Business constraints (min margin, max price change, etc.).
        product_costs: Product cost data for guardrail validation.
        session_id: Optional session ID for AgentCore session scoping.
    """

    pricing_group: str
    pricing_group_type: str = "CATEGORY"
    objectives: list[str] = field(default_factory=lambda: ["balanced"])
    constraints: dict[str, Any] = field(default_factory=dict)
    product_costs: list[dict[str, Any]] = field(default_factory=list)
    session_id: str | None = None


@dataclass
class PricingCycleResult:
    """Output from a complete pricing cycle.

    Attributes:
        cycle_id: Unique identifier for this pricing cycle.
        status: Overall cycle status (COMPLETE, DEGRADED, FAILED).
        ranked_scenarios: List of ranked pricing scenarios.
        agent_results: Results from each intelligence agent.
        degraded_agents: List of agent names that failed and were degraded.
        shortfall_notification: Notification if fewer than 50 scenarios generated.
        metadata: Additional metadata about the cycle execution.
    """

    cycle_id: str
    status: str
    ranked_scenarios: list[dict[str, Any]] = field(default_factory=list)
    agent_results: list[AgentResult] = field(default_factory=list)
    degraded_agents: list[str] = field(default_factory=list)
    shortfall_notification: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# AgentCore Runtime invocation helpers
# ---------------------------------------------------------------------------


def _get_agentcore_client():
    """Create a boto3 client for bedrock-agentcore.

    Returns:
        boto3 client for bedrock-agentcore service.
    """
    region = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))
    return boto3.client("bedrock-agentcore", region_name=region)


def _ensure_session_id(session_id: str | None) -> str:
    """Ensure the session ID meets AgentCore's minimum length requirement (33+ chars).

    If no session_id is provided, generates a new one. If the provided session_id
    is too short, pads it with a UUID suffix.

    Args:
        session_id: Optional session ID from the pricing cycle request.

    Returns:
        A session ID string of at least 33 characters.
    """
    if not session_id:
        session_id = f"pricing-cycle-{uuid.uuid4().hex}"

    if len(session_id) < _MIN_SESSION_ID_LENGTH:
        padding = uuid.uuid4().hex
        session_id = f"{session_id}-{padding}"

    return session_id[:128]  # AgentCore max is 128 chars


def _invoke_agent_runtime(
    agent_arn: str,
    prompt: str,
    session_id: str,
    timeout_seconds: int = AGENT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Invoke an agent via AgentCore Runtime API (boto3 invoke_agent_runtime).

    Sends the prompt to the specified agent runtime and reads the streaming
    response.

    Args:
        agent_arn: The ARN of the AgentCore Runtime agent.
        prompt: The prompt/payload to send to the agent.
        session_id: The runtime session ID (must be 33+ chars).
        timeout_seconds: Timeout for the invocation.

    Returns:
        Parsed response data as a dictionary.

    Raises:
        TimeoutError: If the invocation exceeds the timeout.
        Exception: On any other invocation failure.
    """
    client = _get_agentcore_client()

    payload = json.dumps({"prompt": prompt}).encode()

    start_time = time.time()

    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        runtimeSessionId=session_id,
        payload=payload,
        qualifier="DEFAULT",
    )

    # Read the streaming response
    response_body = response["response"].read()
    elapsed_ms = int((time.time() - start_time) * 1000)

    if elapsed_ms > timeout_seconds * 1000:
        raise TimeoutError(
            f"AgentCore invocation exceeded {timeout_seconds}s timeout "
            f"(took {elapsed_ms}ms)"
        )

    # Parse the response
    try:
        result = json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        # If response isn't JSON, wrap it
        result = {"raw_output": response_body.decode("utf-8", errors="replace")}

    return result


# ---------------------------------------------------------------------------
# Agent invocation helpers
# ---------------------------------------------------------------------------


def _invoke_agent_with_retry(
    agent_arn: str,
    prompt: str,
    agent_name: str,
    max_retries: int = MAX_RETRIES,
    timeout_seconds: int = AGENT_TIMEOUT_SECONDS,
    session_id: str | None = None,
) -> AgentResult:
    """Invoke an agent via AgentCore Runtime with timeout and retry logic.

    Args:
        agent_arn: The AgentCore Runtime ARN for the agent.
        prompt: The prompt to send to the agent.
        agent_name: Human-readable name for logging.
        max_retries: Maximum number of retries on failure.
        timeout_seconds: Timeout per invocation attempt in seconds.
        session_id: Optional session ID for AgentCore Runtime scoping.

    Returns:
        AgentResult with success/failure status and data.
    """
    runtime_session_id = _ensure_session_id(session_id)
    retries_used = 0

    for attempt in range(1 + max_retries):
        start_time = time.time()
        try:
            logger.info(
                "Invoking %s via AgentCore Runtime (attempt %d/%d)",
                agent_name,
                attempt + 1,
                1 + max_retries,
            )
            output_data = _invoke_agent_runtime(
                agent_arn=agent_arn,
                prompt=prompt,
                session_id=runtime_session_id,
                timeout_seconds=timeout_seconds,
            )

            # Security: Validate agent output for prompt injection patterns
            from backend.orchestration.input_sanitizer import sanitize_agent_output
            output_data = sanitize_agent_output(output_data, agent_name)

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "%s completed in %dms (attempt %d) [AgentCore]",
                agent_name,
                duration_ms,
                attempt + 1,
            )

            return AgentResult(
                agent_name=agent_name,
                success=True,
                data=output_data,
                duration_ms=duration_ms,
                retries_used=retries_used,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            retries_used = attempt

            if attempt < max_retries:
                logger.warning(
                    "%s failed on attempt %d/%d (%dms): %s. Retrying...",
                    agent_name,
                    attempt + 1,
                    1 + max_retries,
                    duration_ms,
                    str(e),
                )
            else:
                logger.error(
                    "%s failed after %d attempts (%dms): %s. Degrading.",
                    agent_name,
                    1 + max_retries,
                    duration_ms,
                    str(e),
                )
                return AgentResult(
                    agent_name=agent_name,
                    success=False,
                    error=str(e),
                    duration_ms=duration_ms,
                    retries_used=retries_used,
                )

    # Should not reach here, but safety fallback
    return AgentResult(
        agent_name=agent_name,
        success=False,
        error="Unexpected: exhausted all retry attempts",
        retries_used=max_retries,
    )


# ---------------------------------------------------------------------------
# Core orchestration functions
# ---------------------------------------------------------------------------


def run_pricing_cycle(
    request: PricingCycleRequest | None = None,
    pricing_group: str | None = None,
    objectives: list[str] | None = None,
    constraints: dict[str, Any] | None = None,
    product_costs: list[dict[str, Any]] | None = None,
) -> PricingCycleResult:
    """Execute a complete pricing cycle with parallel intelligence gathering.

    This is the main orchestration function that:
    1. Invokes 3 intelligence agents in parallel (with 120s timeout each)
    2. Waits for all 3 to complete (or timeout/fail with retry)
    3. Passes combined intelligence outputs to Strategy Synthesis Agent
    4. Returns the ranked scenarios

    Can be called with either a PricingCycleRequest object or individual
    parameters for convenience.

    Args:
        request: Full pricing cycle request object. If provided, other
            params are ignored.
        pricing_group: The product group to analyze (used if request is None).
        objectives: Strategic objectives (used if request is None).
        constraints: Business constraints (used if request is None).
        product_costs: Product cost data for guardrails (used if request is None).

    Returns:
        PricingCycleResult with ranked scenarios and execution metadata.
    """
    # Build request from individual params if not provided
    if request is None:
        request = PricingCycleRequest(
            pricing_group=pricing_group or "default_category",
            objectives=objectives or ["balanced"],
            constraints=constraints or {},
            product_costs=product_costs or [],
        )

    cycle_id = str(uuid.uuid4())
    cycle_start = time.time()

    logger.info(
        "Starting pricing cycle %s for group '%s' with objectives %s",
        cycle_id,
        request.pricing_group,
        request.objectives,
    )

    # Build the analysis prompt for intelligence agents
    analysis_prompt = (
        f"Analyze pricing for the '{request.pricing_group}' product group. "
        f"Strategic objectives: {', '.join(request.objectives)}. "
    )
    if request.constraints:
        analysis_prompt += f"Constraints: {request.constraints}. "
    analysis_prompt += (
        "Use your available MCP tools to gather data and return your "
        "structured analysis as JSON."
    )

    # -----------------------------------------------------------------------
    # Phase 1: Parallel intelligence gathering (Requirement 1.1)
    # -----------------------------------------------------------------------
    agent_results = _run_parallel_intelligence_agents(
        analysis_prompt,
        session_id=request.session_id,
    )

    # Determine which agents succeeded
    successful_results = [r for r in agent_results if r.success]
    failed_results = [r for r in agent_results if not r.success]
    degraded_agents = [r.agent_name for r in failed_results]

    # Check if we can proceed (need at least 1 successful agent)
    if len(successful_results) == 0:
        logger.error(
            "All intelligence agents failed for cycle %s. Failing cycle.",
            cycle_id,
        )
        return PricingCycleResult(
            cycle_id=cycle_id,
            status="FAILED",
            agent_results=agent_results,
            degraded_agents=degraded_agents,
            metadata={
                "duration_ms": int((time.time() - cycle_start) * 1000),
                "reason": "All intelligence agents failed after retries",
            },
        )

    # -----------------------------------------------------------------------
    # Phase 2: Strategy Synthesis (Requirement 1.3)
    # -----------------------------------------------------------------------
    competitive_data = _get_agent_data(agent_results, "Competitive Intelligence")
    demand_data = _get_agent_data(agent_results, "Demand Forecasting")
    market_data = _get_agent_data(agent_results, "Market Intelligence")

    # [C4 FIX] Sanitize MCP-sourced intelligence data before Strategy Synthesis.
    # Each specialist agent consumes MCP tool responses that could contain
    # adversarial content. While sanitize_agent_output catches injection in the
    # agent's final output, we also sanitize the extracted data dictionaries
    # before they're serialized into the Strategy Synthesis prompt.
    from backend.orchestration.input_sanitizer import sanitize_mcp_response
    if competitive_data:
        try:
            sanitize_mcp_response(competitive_data, "competitive_intelligence_output")
        except Exception as e:
            logger.warning("Injection detected in competitive data: %s", e)
            competitive_data = {}
            degraded_agents.append("Competitive Intelligence (sanitized)")
    if demand_data:
        try:
            sanitize_mcp_response(demand_data, "demand_forecasting_output")
        except Exception as e:
            logger.warning("Injection detected in demand data: %s", e)
            demand_data = {}
            degraded_agents.append("Demand Forecasting (sanitized)")
    if market_data:
        try:
            sanitize_mcp_response(market_data, "market_intelligence_output")
        except Exception as e:
            logger.warning("Injection detected in market data: %s", e)
            market_data = {}
            degraded_agents.append("Market Intelligence (sanitized)")

    logger.info(
        "Invoking Strategy Synthesis Agent with %d/%d intelligence inputs",
        len(successful_results),
        len(agent_results),
    )

    try:
        synthesis_result = synthesize_pricing_strategies(
            competitive_intelligence=competitive_data,
            demand_forecasting=demand_data,
            market_intelligence=market_data,
            product_costs=request.product_costs,
            cycle_id=cycle_id,
            objectives=request.objectives,
            constraints=request.constraints,
        )
    except Exception as e:
        logger.error("Strategy Synthesis failed for cycle %s: %s", cycle_id, e)
        return PricingCycleResult(
            cycle_id=cycle_id,
            status="FAILED",
            agent_results=agent_results,
            degraded_agents=degraded_agents,
            metadata={
                "duration_ms": int((time.time() - cycle_start) * 1000),
                "reason": f"Strategy Synthesis failed: {e}",
            },
        )

    # Build the final result
    ranked_scenarios = synthesis_result.get("ranked_scenarios", [])
    shortfall = synthesis_result.get("shortfall_notification")

    status = "COMPLETE"
    if degraded_agents:
        status = "DEGRADED"

    cycle_duration_ms = int((time.time() - cycle_start) * 1000)

    logger.info(
        "Pricing cycle %s completed with status %s: %d scenarios in %dms",
        cycle_id,
        status,
        len(ranked_scenarios),
        cycle_duration_ms,
    )

    return PricingCycleResult(
        cycle_id=cycle_id,
        status=status,
        ranked_scenarios=ranked_scenarios,
        agent_results=agent_results,
        degraded_agents=degraded_agents,
        shortfall_notification=shortfall,
        metadata={
            "duration_ms": cycle_duration_ms,
            "pricing_group": request.pricing_group,
            "objectives": request.objectives,
            "constraints": request.constraints,
            "synthesis_metadata": synthesis_result.get("synthesis_metadata", {}),
        },
    )


def _run_parallel_intelligence_agents(
    prompt: str,
    session_id: str | None = None,
) -> list[AgentResult]:
    """Run the three intelligence agents in parallel using ThreadPoolExecutor.

    Each agent is invoked via AgentCore Runtime API with the same analysis
    prompt. Agents that timeout (>120s) or fail are retried up to 2 times
    before being marked as degraded.

    Args:
        prompt: The analysis prompt to send to each agent.
        session_id: Optional session ID for AgentCore Runtime scoping.

    Returns:
        List of AgentResult objects (one per agent).
    """
    agent_configs = [
        {
            "name": "Competitive Intelligence",
            "arn": _get_agent_arn("COMPETITIVE_INTELLIGENCE_AGENT_ARN"),
        },
        {
            "name": "Demand Forecasting",
            "arn": _get_agent_arn("DEMAND_FORECASTING_AGENT_ARN"),
        },
        {
            "name": "Market Intelligence",
            "arn": _get_agent_arn("MARKET_INTELLIGENCE_AGENT_ARN"),
        },
    ]

    results: list[AgentResult] = []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                _invoke_agent_with_retry,
                agent_arn=config["arn"],
                prompt=prompt,
                agent_name=config["name"],
                max_retries=MAX_RETRIES,
                timeout_seconds=AGENT_TIMEOUT_SECONDS,
                session_id=session_id,
            ): config["name"]
            for config in agent_configs
        }

        for future in as_completed(futures):
            agent_name = futures[future]
            try:
                result = future.result(timeout=AGENT_TIMEOUT_SECONDS * (1 + MAX_RETRIES))
                results.append(result)
            except TimeoutError:
                logger.error(
                    "%s timed out at the executor level", agent_name
                )
                results.append(
                    AgentResult(
                        agent_name=agent_name,
                        success=False,
                        error=f"Executor-level timeout after {AGENT_TIMEOUT_SECONDS * (1 + MAX_RETRIES)}s",
                        retries_used=MAX_RETRIES,
                    )
                )
            except Exception as e:
                logger.error(
                    "%s raised unexpected exception: %s", agent_name, e
                )
                results.append(
                    AgentResult(
                        agent_name=agent_name,
                        success=False,
                        error=f"Unexpected error: {e}",
                        retries_used=MAX_RETRIES,
                    )
                )

    return results


def _get_agent_data(
    agent_results: list[AgentResult], agent_name: str
) -> dict[str, Any]:
    """Extract data from a specific agent's result.

    Returns the agent's output data if successful, or an empty dict
    with a degradation flag if the agent failed.

    Args:
        agent_results: List of all agent results.
        agent_name: Name of the agent to extract data for.

    Returns:
        Agent output data dict, or empty dict with _degraded flag.
    """
    for result in agent_results:
        if result.agent_name == agent_name:
            if result.success:
                return result.data
            else:
                return {"_degraded": True, "_error": result.error}
    return {"_degraded": True, "_error": "Agent not found in results"}


# ---------------------------------------------------------------------------
# Implementation handoff (post-approval)
# ---------------------------------------------------------------------------


def trigger_implementation(
    scenario: dict[str, Any],
    cycle_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Trigger the Implementation Monitoring Agent for an approved scenario.

    After a pricing scenario is approved, this function invokes the
    Implementation Monitoring Agent via AgentCore Runtime to:
    1. Execute price updates across all sales channels
    2. Begin tracking actual KPIs against projected values
    3. Monitor for variance and generate adjustment recommendations

    Args:
        scenario: The approved pricing scenario dict containing priceChanges,
            projectedRevenue, projectedMargin, etc.
        cycle_id: The parent pricing cycle ID.
        session_id: Optional session ID for AgentCore Runtime scoping.

    Returns:
        Dictionary with implementation status and details.
    """
    cycle_id = cycle_id or scenario.get("cycleId", str(uuid.uuid4()))
    scenario_id = scenario.get("scenarioId", str(uuid.uuid4()))

    logger.info(
        "Triggering implementation for scenario %s in cycle %s",
        scenario_id,
        cycle_id,
    )

    price_changes = scenario.get("priceChanges", [])
    projected_revenue = scenario.get("projectedRevenue", 0)
    projected_margin = scenario.get("projectedMargin", 0)

    prompt = (
        f"Execute price updates for approved scenario '{scenario_id}' "
        f"in pricing cycle '{cycle_id}'. "
        f"Price changes to implement: {price_changes}. "
        f"After implementation, begin monitoring with projected revenue "
        f"of {projected_revenue} and projected margin of {projected_margin}. "
        f"Track actual performance and report any variances."
    )

    try:
        runtime_session_id = _ensure_session_id(session_id)
        logger.info(
            "Invoking Implementation Monitoring Agent via AgentCore Runtime"
        )
        agent_response = _invoke_agent_runtime(
            agent_arn=_get_agent_arn("IMPLEMENTATION_MONITORING_AGENT_ARN"),
            prompt=prompt,
            session_id=runtime_session_id,
            timeout_seconds=AGENT_TIMEOUT_SECONDS,
        )

        logger.info(
            "Implementation triggered successfully for scenario %s",
            scenario_id,
        )

        return {
            "status": "IMPLEMENTATION_STARTED",
            "scenario_id": scenario_id,
            "cycle_id": cycle_id,
            "price_changes_count": len(price_changes),
            "agent_response": json.dumps(agent_response),
        }

    except Exception as e:
        logger.error(
            "Implementation trigger failed for scenario %s: %s",
            scenario_id,
            e,
        )
        return {
            "status": "IMPLEMENTATION_FAILED",
            "scenario_id": scenario_id,
            "cycle_id": cycle_id,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


def create_orchestrator_agent() -> Agent:
    """Create and configure the Orchestrator Agent.

    Creates a Strands Agent configured with:
    - Model: us.anthropic.claude-opus-4-7 (complex reasoning)
    - System prompt for orchestration (delegate, coordinate, assemble)

    The orchestrator agent itself is primarily used for complex reasoning
    about pricing strategy and coordination decisions. The actual parallel
    invocation logic is handled by run_pricing_cycle() which uses
    ThreadPoolExecutor for true parallelism.

    Returns:
        Configured Strands Agent instance for orchestration reasoning.
    """
    agent = Agent(
        model=ORCHESTRATOR_MODEL,
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
    )

    logger.info(
        "Orchestrator Agent created with model %s",
        ORCHESTRATOR_MODEL,
    )

    return agent
