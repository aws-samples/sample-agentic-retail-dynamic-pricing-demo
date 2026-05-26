"""Resilience module for the Retail Dynamic Pricing orchestration layer.

Provides configurable timeout, retry, and graceful degradation logic for:
- Sub-agent invocations (120s timeout, 2 retries)
- MCP Server calls (30s timeout, 1 retry after 2s wait)
- Graceful degradation when agents fail (proceed with available outputs)

All timeout/retry/degradation events are logged for observability.

Requirements: 1.5, 1.8, 2.7, 2.8, 2.9
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from concurrent.futures import ThreadPoolExecutor, Future, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar, Generic

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

# Sub-agent timeout and retry (Requirements 1.5, 1.8)
AGENT_TIMEOUT_SECONDS: int = 120
AGENT_MAX_RETRIES: int = 2

# MCP Server timeout and retry (Requirements 2.7, 2.8)
MCP_TIMEOUT_SECONDS: int = 30
MCP_MAX_RETRIES: int = 1
MCP_RETRY_DELAY_SECONDS: float = 2.0


# ---------------------------------------------------------------------------
# Enums and data classes
# ---------------------------------------------------------------------------


class InvocationStatus(str, Enum):
    """Status of an invocation attempt."""

    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"
    RETRYING = "retrying"
    DEGRADED = "degraded"


class DegradationLevel(str, Enum):
    """Level of degradation in the orchestration pipeline.

    Determines how the system proceeds when agents fail:
    - NONE: All agents succeeded, full analysis available.
    - PARTIAL: 1-2 agents failed, proceed with available data.
    - SEVERE: Only 1 agent succeeded, limited analysis.
    - TOTAL: All agents failed, cycle cannot proceed.
    """

    NONE = "none"
    PARTIAL = "partial"
    SEVERE = "severe"
    TOTAL = "total"


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts.
        timeout_seconds: Timeout per invocation attempt in seconds.
        retry_delay_seconds: Delay between retries in seconds.
        name: Human-readable name for logging.
    """

    max_retries: int = AGENT_MAX_RETRIES
    timeout_seconds: float = AGENT_TIMEOUT_SECONDS
    retry_delay_seconds: float = 0.0
    name: str = "unnamed"


# Pre-configured retry configs
AGENT_RETRY_CONFIG = RetryConfig(
    max_retries=AGENT_MAX_RETRIES,
    timeout_seconds=AGENT_TIMEOUT_SECONDS,
    retry_delay_seconds=0.0,
    name="agent",
)

MCP_RETRY_CONFIG = RetryConfig(
    max_retries=MCP_MAX_RETRIES,
    timeout_seconds=MCP_TIMEOUT_SECONDS,
    retry_delay_seconds=MCP_RETRY_DELAY_SECONDS,
    name="mcp_server",
)


@dataclass
class InvocationAttempt:
    """Record of a single invocation attempt.

    Attributes:
        attempt_number: 1-based attempt number.
        status: Outcome of this attempt.
        duration_ms: How long the attempt took in milliseconds.
        error: Error message if the attempt failed.
        timestamp: Unix timestamp when the attempt started.
    """

    attempt_number: int
    status: InvocationStatus
    duration_ms: int = 0
    error: str | None = None
    timestamp: float = 0.0


@dataclass
class InvocationResult(Generic[T]):
    """Result of an invocation with full retry history.

    Attributes:
        success: Whether the invocation ultimately succeeded.
        data: The result data if successful.
        target_name: Name of the target (agent or MCP server).
        attempts: History of all attempts made.
        total_duration_ms: Total time across all attempts.
        retries_used: Number of retries that were attempted.
        final_error: The last error if all attempts failed.
        degraded: Whether this result represents a degraded state.
    """

    success: bool
    data: Any = None
    target_name: str = ""
    attempts: list[InvocationAttempt] = field(default_factory=list)
    total_duration_ms: int = 0
    retries_used: int = 0
    final_error: str | None = None
    degraded: bool = False


@dataclass
class DegradationStatus:
    """Tracks the degradation state of the orchestration pipeline.

    Attributes:
        level: Current degradation level.
        failed_agents: Names of agents that failed.
        available_agents: Names of agents that succeeded.
        incomplete_data_sources: Data sources that are unavailable.
        warnings: Human-readable warnings about degraded state.
    """

    level: DegradationLevel = DegradationLevel.NONE
    failed_agents: list[str] = field(default_factory=list)
    available_agents: list[str] = field(default_factory=list)
    incomplete_data_sources: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def can_proceed(self) -> bool:
        """Whether the pipeline can proceed despite degradation."""
        return self.level != DegradationLevel.TOTAL

    @property
    def is_degraded(self) -> bool:
        """Whether the pipeline is operating in any degraded state."""
        return self.level != DegradationLevel.NONE


# ---------------------------------------------------------------------------
# Core resilience functions
# ---------------------------------------------------------------------------


def invoke_with_retry(
    fn: Callable[..., T],
    args: tuple = (),
    kwargs: dict[str, Any] | None = None,
    config: RetryConfig | None = None,
    target_name: str = "unknown",
) -> InvocationResult[T]:
    """Invoke a callable with timeout and retry logic.

    Executes the given function with configurable timeout and retry behavior.
    Each attempt is subject to the timeout. On failure or timeout, retries
    up to config.max_retries times with an optional delay between retries.

    All events (attempts, timeouts, retries, final outcomes) are logged.

    Args:
        fn: The callable to invoke.
        args: Positional arguments to pass to fn.
        kwargs: Keyword arguments to pass to fn.
        config: Retry configuration. Defaults to AGENT_RETRY_CONFIG.
        target_name: Name of the target for logging.

    Returns:
        InvocationResult with success/failure status, data, and attempt history.
    """
    if kwargs is None:
        kwargs = {}
    if config is None:
        config = AGENT_RETRY_CONFIG

    attempts: list[InvocationAttempt] = []
    total_start = time.time()
    last_error: str | None = None

    total_attempts = 1 + config.max_retries

    for attempt_num in range(1, total_attempts + 1):
        attempt_start = time.time()

        try:
            result = _execute_with_timeout(fn, args, kwargs, config.timeout_seconds)
            duration_ms = int((time.time() - attempt_start) * 1000)

            attempt = InvocationAttempt(
                attempt_number=attempt_num,
                status=InvocationStatus.SUCCESS,
                duration_ms=duration_ms,
                timestamp=attempt_start,
            )
            attempts.append(attempt)

            logger.info(
                "[resilience] %s '%s' succeeded on attempt %d/%d in %dms",
                config.name,
                target_name,
                attempt_num,
                total_attempts,
                duration_ms,
            )

            return InvocationResult(
                success=True,
                data=result,
                target_name=target_name,
                attempts=attempts,
                total_duration_ms=int((time.time() - total_start) * 1000),
                retries_used=attempt_num - 1,
            )

        except TimeoutError as e:
            duration_ms = int((time.time() - attempt_start) * 1000)
            last_error = f"Timeout after {config.timeout_seconds}s: {e}"

            status = InvocationStatus.TIMEOUT
            if attempt_num < total_attempts:
                status = InvocationStatus.RETRYING

            attempt = InvocationAttempt(
                attempt_number=attempt_num,
                status=status,
                duration_ms=duration_ms,
                error=last_error,
                timestamp=attempt_start,
            )
            attempts.append(attempt)

            logger.warning(
                "[resilience] %s '%s' timed out on attempt %d/%d after %dms",
                config.name,
                target_name,
                attempt_num,
                total_attempts,
                duration_ms,
            )

            if attempt_num < total_attempts and config.retry_delay_seconds > 0:
                logger.info(
                    "[resilience] Waiting %.1fs before retry for '%s'",
                    config.retry_delay_seconds,
                    target_name,
                )
                time.sleep(config.retry_delay_seconds)

        except Exception as e:
            duration_ms = int((time.time() - attempt_start) * 1000)
            last_error = f"{type(e).__name__}: {e}"

            status = InvocationStatus.ERROR
            if attempt_num < total_attempts:
                status = InvocationStatus.RETRYING

            attempt = InvocationAttempt(
                attempt_number=attempt_num,
                status=status,
                duration_ms=duration_ms,
                error=last_error,
                timestamp=attempt_start,
            )
            attempts.append(attempt)

            logger.warning(
                "[resilience] %s '%s' failed on attempt %d/%d after %dms: %s",
                config.name,
                target_name,
                attempt_num,
                total_attempts,
                duration_ms,
                last_error,
            )

            if attempt_num < total_attempts and config.retry_delay_seconds > 0:
                logger.info(
                    "[resilience] Waiting %.1fs before retry for '%s'",
                    config.retry_delay_seconds,
                    target_name,
                )
                time.sleep(config.retry_delay_seconds)

    # All attempts exhausted
    total_duration_ms = int((time.time() - total_start) * 1000)

    logger.error(
        "[resilience] %s '%s' failed after all %d attempts (%dms total). "
        "Last error: %s",
        config.name,
        target_name,
        total_attempts,
        total_duration_ms,
        last_error,
    )

    return InvocationResult(
        success=False,
        data=None,
        target_name=target_name,
        attempts=attempts,
        total_duration_ms=total_duration_ms,
        retries_used=config.max_retries,
        final_error=last_error,
        degraded=True,
    )


def invoke_agent(
    fn: Callable[..., T],
    args: tuple = (),
    kwargs: dict[str, Any] | None = None,
    agent_name: str = "unknown_agent",
) -> InvocationResult[T]:
    """Invoke a sub-agent with 120s timeout and up to 2 retries.

    Convenience wrapper around invoke_with_retry using AGENT_RETRY_CONFIG.

    Args:
        fn: The agent invocation callable.
        args: Positional arguments.
        kwargs: Keyword arguments.
        agent_name: Name of the agent for logging.

    Returns:
        InvocationResult with the agent's output or failure details.
    """
    return invoke_with_retry(
        fn=fn,
        args=args,
        kwargs=kwargs,
        config=AGENT_RETRY_CONFIG,
        target_name=agent_name,
    )


def invoke_mcp_server(
    fn: Callable[..., T],
    args: tuple = (),
    kwargs: dict[str, Any] | None = None,
    server_name: str = "unknown_mcp_server",
) -> InvocationResult[T]:
    """Invoke an MCP Server with 30s timeout and 1 retry after 2s wait.

    Convenience wrapper around invoke_with_retry using MCP_RETRY_CONFIG.

    Args:
        fn: The MCP server invocation callable.
        args: Positional arguments.
        kwargs: Keyword arguments.
        server_name: Name of the MCP server for logging.

    Returns:
        InvocationResult with the server's response or failure details.
    """
    return invoke_with_retry(
        fn=fn,
        args=args,
        kwargs=kwargs,
        config=MCP_RETRY_CONFIG,
        target_name=server_name,
    )


# ---------------------------------------------------------------------------
# Graceful degradation logic
# ---------------------------------------------------------------------------


def assess_degradation(
    results: list[InvocationResult],
    total_expected: int = 3,
) -> DegradationStatus:
    """Assess the degradation level based on agent invocation results.

    Determines how to proceed based on how many agents succeeded:
    - All succeed: NONE (full analysis)
    - 1-2 fail: PARTIAL (proceed with available data, flag missing)
    - Only 1 succeeds: SEVERE (limited analysis, prominent warning)
    - All fail: TOTAL (cannot proceed)

    Args:
        results: List of InvocationResult objects from agent invocations.
        total_expected: Total number of agents expected (default 3).

    Returns:
        DegradationStatus describing the current state.
    """
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    available_agents = [r.target_name for r in successful]
    failed_agents = [r.target_name for r in failed]

    success_count = len(successful)
    fail_count = len(failed)

    # Determine degradation level
    if fail_count == 0:
        level = DegradationLevel.NONE
        warnings = []
    elif success_count >= 2:
        level = DegradationLevel.PARTIAL
        warnings = [
            f"Operating in degraded mode: {fail_count} of {total_expected} "
            f"agents failed ({', '.join(failed_agents)}). "
            f"Proceeding with available data from {', '.join(available_agents)}."
        ]
    elif success_count == 1:
        level = DegradationLevel.SEVERE
        warnings = [
            f"SEVERE DEGRADATION: Only 1 of {total_expected} agents succeeded "
            f"({available_agents[0]}). Analysis will be significantly limited. "
            f"Failed agents: {', '.join(failed_agents)}."
        ]
    else:
        level = DegradationLevel.TOTAL
        warnings = [
            f"TOTAL FAILURE: All {total_expected} agents failed "
            f"({', '.join(failed_agents)}). Cannot proceed with pricing cycle."
        ]

    # Collect incomplete data sources from failed agents
    incomplete_sources = []
    for r in failed:
        incomplete_sources.append(r.target_name)

    status = DegradationStatus(
        level=level,
        failed_agents=failed_agents,
        available_agents=available_agents,
        incomplete_data_sources=incomplete_sources,
        warnings=warnings,
    )

    # Log the degradation assessment
    if status.is_degraded:
        log_fn = logger.error if level == DegradationLevel.TOTAL else logger.warning
        log_fn(
            "[resilience] Degradation assessment: level=%s, "
            "failed=%s, available=%s",
            level.value,
            failed_agents,
            available_agents,
        )
    else:
        logger.info(
            "[resilience] All %d agents succeeded, no degradation.",
            total_expected,
        )

    return status


def build_degraded_context(
    results: list[InvocationResult],
    degradation: DegradationStatus,
) -> dict[str, Any]:
    """Build a context dict for downstream agents incorporating degradation info.

    Creates a structured context that includes available agent outputs and
    flags for missing/degraded data sources. This context is passed to the
    Strategy Synthesis Agent so it can adjust its behavior accordingly.

    Args:
        results: List of InvocationResult objects from agent invocations.
        degradation: The assessed degradation status.

    Returns:
        Dictionary with agent outputs and degradation metadata.
    """
    context: dict[str, Any] = {
        "degradation": {
            "level": degradation.level.value,
            "is_degraded": degradation.is_degraded,
            "can_proceed": degradation.can_proceed,
            "failed_agents": degradation.failed_agents,
            "available_agents": degradation.available_agents,
            "incomplete_data_sources": degradation.incomplete_data_sources,
            "warnings": degradation.warnings,
        },
        "agent_outputs": {},
    }

    for result in results:
        if result.success:
            context["agent_outputs"][result.target_name] = {
                "status": "available",
                "data": result.data,
                "duration_ms": result.total_duration_ms,
                "retries_used": result.retries_used,
            }
        else:
            context["agent_outputs"][result.target_name] = {
                "status": "unavailable",
                "data": None,
                "error": result.final_error,
                "duration_ms": result.total_duration_ms,
                "retries_used": result.retries_used,
            }

    return context


# ---------------------------------------------------------------------------
# Timeout execution helper
# ---------------------------------------------------------------------------


def _execute_with_timeout(
    fn: Callable[..., T],
    args: tuple,
    kwargs: dict[str, Any],
    timeout_seconds: float,
) -> T:
    """Execute a function with a timeout using ThreadPoolExecutor.

    Submits the function to a thread pool and waits up to timeout_seconds
    for it to complete. Raises TimeoutError if the function doesn't finish
    in time.

    Args:
        fn: The callable to execute.
        args: Positional arguments.
        kwargs: Keyword arguments.
        timeout_seconds: Maximum time to wait in seconds.

    Returns:
        The function's return value.

    Raises:
        TimeoutError: If the function exceeds the timeout.
        Exception: Any exception raised by the function.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future: Future = executor.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            future.cancel()
            raise TimeoutError(
                f"Execution exceeded {timeout_seconds}s timeout"
            )


# ---------------------------------------------------------------------------
# Decorator-style wrappers
# ---------------------------------------------------------------------------


def with_agent_resilience(agent_name: str = "unknown"):
    """Decorator that wraps a function with agent resilience (120s timeout, 2 retries).

    Usage:
        @with_agent_resilience("Competitive Intelligence")
        def invoke_competitive_agent(prompt):
            agent = create_competitive_intelligence_agent()
            return agent(prompt)

    Args:
        agent_name: Name of the agent for logging.

    Returns:
        Decorator function.
    """

    def decorator(fn: Callable[..., T]) -> Callable[..., InvocationResult[T]]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> InvocationResult[T]:
            return invoke_agent(
                fn=fn,
                args=args,
                kwargs=kwargs,
                agent_name=agent_name,
            )

        return wrapper

    return decorator


def with_mcp_resilience(server_name: str = "unknown"):
    """Decorator that wraps a function with MCP server resilience (30s timeout, 1 retry after 2s).

    Usage:
        @with_mcp_resilience("Competitor API Server")
        def call_competitor_api(product_id):
            return mcp_client.invoke("get_competitor_prices", product_id=product_id)

    Args:
        server_name: Name of the MCP server for logging.

    Returns:
        Decorator function.
    """

    def decorator(fn: Callable[..., T]) -> Callable[..., InvocationResult[T]]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> InvocationResult[T]:
            return invoke_mcp_server(
                fn=fn,
                args=args,
                kwargs=kwargs,
                server_name=server_name,
            )

        return wrapper

    return decorator
