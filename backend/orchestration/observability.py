"""Observability and logging module for the Retail Dynamic Pricing system.

Provides structured logging of agent interactions to CloudWatch, metric emission
for agent errors, and trace context management for end-to-end correlation using
Amazon Bedrock AgentCore Observability.

Requirements: 13.1, 13.2, 13.3, 13.4
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Generator

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum length for input/output summaries in log entries
MAX_SUMMARY_LENGTH = 1024

# CloudWatch namespace for agent metrics
METRICS_NAMESPACE = "RetailDynamicPricing/Agents"

# Default alarm threshold: 5 errors per 1-minute window
DEFAULT_ERROR_THRESHOLD = 5
DEFAULT_EVALUATION_PERIOD_SECONDS = 60


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class AgentInteractionLog:
    """Structured log entry for an agent interaction.

    Each log entry captures the full context of an agent invocation
    for CloudWatch logging and audit compliance.

    Attributes:
        timestamp: ISO 8601 timestamp of the interaction.
        agent_id: Identifier of the agent that performed the action.
        action: The action performed (e.g., 'invoke', 'retry', 'complete').
        input_summary: Truncated summary of the input to the agent.
        output_summary: Truncated summary of the agent's output.
        duration_ms: Execution duration in milliseconds.
        trace_id: Trace ID for end-to-end correlation.
        cycle_id: Parent pricing cycle ID (optional).
        success: Whether the interaction completed successfully.
        error_category: Category of error if failed (optional).
        metadata: Additional metadata (optional).
    """

    timestamp: str
    agent_id: str
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int
    trace_id: str | None = None
    cycle_id: str | None = None
    success: bool = True
    error_category: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def to_json(self) -> str:
        """Serialize to JSON string for CloudWatch logging."""
        return json.dumps(self.to_dict(), default=str)


@dataclass
class TraceContext:
    """Context for end-to-end trace correlation.

    Manages a trace ID that spans from pricing cycle initiation through
    to the final pricing decision output, correlating all participating
    agent invocations under a single trace identifier.

    Attributes:
        trace_id: Unique trace identifier for the full pricing cycle.
        cycle_id: Associated pricing cycle ID.
        start_time: Trace start time in seconds since epoch.
        spans: List of span records within this trace.
    """

    trace_id: str
    cycle_id: str | None = None
    start_time: float = field(default_factory=time.time)
    spans: list[dict[str, Any]] = field(default_factory=list)

    def add_span(
        self,
        agent_id: str,
        action: str,
        duration_ms: int,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """Add a span to this trace.

        Args:
            agent_id: The agent that performed the action.
            action: The action performed.
            duration_ms: Duration in milliseconds.
            success: Whether the span completed successfully.
            error: Error message if failed.
        """
        span = {
            "span_id": str(uuid.uuid4()),
            "agent_id": agent_id,
            "action": action,
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if error:
            span["error"] = error
        self.spans.append(span)

    def get_total_duration_ms(self) -> int:
        """Get total trace duration in milliseconds."""
        return int((time.time() - self.start_time) * 1000)


# ---------------------------------------------------------------------------
# Summary truncation helper
# ---------------------------------------------------------------------------


def truncate_summary(text: str | Any, max_length: int = MAX_SUMMARY_LENGTH) -> str:
    """Truncate input/output text to a reasonable length for logging.

    Ensures that log entries don't exceed CloudWatch limits and remain
    readable. Adds a truncation indicator when text is shortened.

    Args:
        text: The text to truncate. Non-string values are converted to string.
        max_length: Maximum allowed length. Defaults to MAX_SUMMARY_LENGTH (1024).

    Returns:
        Truncated string, with '...[truncated]' suffix if shortened.
    """
    if text is None:
        return ""

    if not isinstance(text, str):
        text = str(text)

    if len(text) <= max_length:
        return text

    # Reserve space for the truncation indicator
    indicator = "...[truncated]"
    truncated_length = max_length - len(indicator)

    if truncated_length <= 0:
        return text[:max_length]

    return text[:truncated_length] + indicator


# ---------------------------------------------------------------------------
# Structured logger
# ---------------------------------------------------------------------------


class AgentLogger:
    """Structured logger for agent interactions.

    Formats and emits structured log entries to CloudWatch containing
    timestamp, agent_id, action, input/output summary, and duration.

    Requirement 13.1: Log all agent interactions and decisions to CloudWatch.
    """

    def __init__(
        self,
        log_group_name: str = "/retail-dynamic-pricing/agents",
        logger_instance: logging.Logger | None = None,
    ):
        """Initialize the agent logger.

        Args:
            log_group_name: CloudWatch log group name.
            logger_instance: Optional custom logger. Defaults to module logger.
        """
        self._log_group_name = log_group_name
        self._logger = logger_instance or logging.getLogger(
            "retail_dynamic_pricing.agents"
        )
        self._current_trace: TraceContext | None = None

    @property
    def current_trace(self) -> TraceContext | None:
        """Get the current active trace context."""
        return self._current_trace

    @current_trace.setter
    def current_trace(self, trace: TraceContext | None) -> None:
        """Set the current active trace context."""
        self._current_trace = trace

    def log_interaction(
        self,
        agent_id: str,
        action: str,
        input_data: str | Any = "",
        output_data: str | Any = "",
        duration_ms: int = 0,
        success: bool = True,
        error_category: str | None = None,
        cycle_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentInteractionLog:
        """Log a structured agent interaction.

        Creates a structured log entry and emits it via the Python logger.
        The entry includes all required fields per Requirement 13.1.

        Args:
            agent_id: Identifier of the agent.
            action: Action performed (e.g., 'invoke', 'complete', 'error').
            input_data: Input to the agent (will be truncated).
            output_data: Output from the agent (will be truncated).
            duration_ms: Execution duration in milliseconds.
            success: Whether the interaction succeeded.
            error_category: Error category if failed.
            cycle_id: Parent pricing cycle ID.
            metadata: Additional metadata.

        Returns:
            The structured AgentInteractionLog entry.
        """
        log_entry = AgentInteractionLog(
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=agent_id,
            action=action,
            input_summary=truncate_summary(input_data),
            output_summary=truncate_summary(output_data),
            duration_ms=duration_ms,
            trace_id=self._current_trace.trace_id if self._current_trace else None,
            cycle_id=cycle_id,
            success=success,
            error_category=error_category,
            metadata=metadata or {},
        )

        # Emit structured log
        log_json = log_entry.to_json()

        if success:
            self._logger.info(log_json)
        else:
            self._logger.error(log_json)

        # Add span to current trace if active
        if self._current_trace:
            self._current_trace.add_span(
                agent_id=agent_id,
                action=action,
                duration_ms=duration_ms,
                success=success,
                error=error_category,
            )

        return log_entry


# ---------------------------------------------------------------------------
# CloudWatch metrics emission
# ---------------------------------------------------------------------------


class AgentMetricsEmitter:
    """Emits CloudWatch metrics for agent errors.

    Requirement 13.3: Emit a CloudWatch metric that includes the agent
    identifier and error category when an agent encounters an error.
    """

    def __init__(
        self,
        namespace: str = METRICS_NAMESPACE,
        cloudwatch_client: Any | None = None,
    ):
        """Initialize the metrics emitter.

        Args:
            namespace: CloudWatch metrics namespace.
            cloudwatch_client: Optional boto3 CloudWatch client (for testing).
        """
        self._namespace = namespace
        self._client = cloudwatch_client

    @property
    def client(self) -> Any:
        """Lazy-initialize the CloudWatch client."""
        if self._client is None:
            self._client = boto3.client("cloudwatch")
        return self._client

    def emit_agent_error(
        self,
        agent_id: str,
        error_category: str,
        value: float = 1.0,
    ) -> bool:
        """Emit a CloudWatch metric for an agent error.

        Publishes a metric with dimensions for agent_id and error_category,
        enabling per-agent error rate monitoring and alarming.

        Args:
            agent_id: Identifier of the agent that encountered the error.
            error_category: Category of the error (e.g., 'timeout', 'runtime',
                'mcp_failure', 'validation').
            value: Metric value (defaults to 1.0 for count-based metrics).

        Returns:
            True if the metric was emitted successfully, False otherwise.
        """
        try:
            self.client.put_metric_data(
                Namespace=self._namespace,
                MetricData=[
                    {
                        "MetricName": "AgentErrors",
                        "Dimensions": [
                            {"Name": "AgentId", "Value": agent_id},
                            {"Name": "ErrorCategory", "Value": error_category},
                        ],
                        "Timestamp": datetime.now(timezone.utc),
                        "Value": value,
                        "Unit": "Count",
                    }
                ],
            )
            logger.debug(
                "Emitted AgentErrors metric: agent_id=%s, error_category=%s",
                agent_id,
                error_category,
            )
            return True
        except ClientError as e:
            logger.warning(
                "Failed to emit CloudWatch metric: %s", e
            )
            return False
        except Exception as e:
            logger.warning(
                "Unexpected error emitting CloudWatch metric: %s", e
            )
            return False


# ---------------------------------------------------------------------------
# Trace context manager
# ---------------------------------------------------------------------------


@contextmanager
def trace_pricing_cycle(
    cycle_id: str | None = None,
    agent_logger: AgentLogger | None = None,
) -> Generator[TraceContext, None, None]:
    """Context manager for end-to-end trace correlation.

    Creates a trace context that spans from pricing cycle initiation through
    to the final pricing decision output. All agent invocations within the
    context are correlated under a single trace identifier.

    Requirement 13.2: Trace end-to-end Pricing_Cycle execution using
    AgentCore Observability for audit compliance.

    Args:
        cycle_id: Optional pricing cycle ID to associate with the trace.
        agent_logger: Optional AgentLogger to bind the trace to.

    Yields:
        TraceContext with a unique trace_id for correlation.

    Example:
        with trace_pricing_cycle(cycle_id="cycle-123", agent_logger=my_logger) as trace:
            # All agent interactions logged within this block
            # will be correlated under trace.trace_id
            logger.log_interaction(...)
    """
    trace = TraceContext(
        trace_id=str(uuid.uuid4()),
        cycle_id=cycle_id,
        start_time=time.time(),
    )

    # Bind trace to the agent logger if provided
    if agent_logger:
        previous_trace = agent_logger.current_trace
        agent_logger.current_trace = trace

    logger.info(
        "Trace started: trace_id=%s, cycle_id=%s",
        trace.trace_id,
        cycle_id,
    )

    try:
        yield trace
    finally:
        total_duration_ms = trace.get_total_duration_ms()

        logger.info(
            "Trace completed: trace_id=%s, cycle_id=%s, duration_ms=%d, spans=%d",
            trace.trace_id,
            cycle_id,
            total_duration_ms,
            len(trace.spans),
        )

        # Restore previous trace on the logger
        if agent_logger:
            agent_logger.current_trace = previous_trace


# ---------------------------------------------------------------------------
# CloudWatch alarm configuration (CDK documentation)
# ---------------------------------------------------------------------------

# The CloudWatch alarm for error rate threshold is configured in CDK.
# Below is the configuration specification for reference:
#
# Alarm: AgentErrorRateAlarm
# - Metric: AgentErrors (namespace: RetailDynamicPricing/Agents)
# - Statistic: Sum
# - Period: 60 seconds (1 minute)
# - Threshold: 5 errors
# - ComparisonOperator: GreaterThanOrEqualToThreshold
# - EvaluationPeriods: 1
# - TreatMissingData: notBreaching
#
# CDK construct (Python):
#
#   from aws_cdk import aws_cloudwatch as cloudwatch
#
#   agent_error_metric = cloudwatch.Metric(
#       namespace="RetailDynamicPricing/Agents",
#       metric_name="AgentErrors",
#       statistic="Sum",
#       period=Duration.minutes(1),
#   )
#
#   cloudwatch.Alarm(
#       self, "AgentErrorRateAlarm",
#       metric=agent_error_metric,
#       threshold=5,
#       evaluation_periods=1,
#       comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
#       treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
#       alarm_description="Triggers when agent error rate exceeds 5 errors per 1-minute window",
#   )


def get_alarm_configuration() -> dict[str, Any]:
    """Return the CloudWatch alarm configuration for agent error rate.

    Requirement 13.4: Trigger a CloudWatch alarm if the error rate for
    any single agent exceeds 5 errors per 1-minute sliding window.

    Returns:
        Dictionary describing the alarm configuration for CDK deployment.
    """
    return {
        "alarm_name": "AgentErrorRateAlarm",
        "namespace": METRICS_NAMESPACE,
        "metric_name": "AgentErrors",
        "statistic": "Sum",
        "period_seconds": DEFAULT_EVALUATION_PERIOD_SECONDS,
        "threshold": DEFAULT_ERROR_THRESHOLD,
        "comparison_operator": "GreaterThanOrEqualToThreshold",
        "evaluation_periods": 1,
        "treat_missing_data": "notBreaching",
        "alarm_description": (
            "Triggers when agent error rate exceeds "
            f"{DEFAULT_ERROR_THRESHOLD} errors per "
            f"{DEFAULT_EVALUATION_PERIOD_SECONDS}-second window"
        ),
    }


# ---------------------------------------------------------------------------
# Convenience: combined observability facade
# ---------------------------------------------------------------------------


class ObservabilityManager:
    """Facade combining logging, metrics, and tracing for agent observability.

    Provides a single entry point for all observability concerns, simplifying
    integration with the orchestrator and individual agents.
    """

    def __init__(
        self,
        log_group_name: str = "/retail-dynamic-pricing/agents",
        metrics_namespace: str = METRICS_NAMESPACE,
        cloudwatch_client: Any | None = None,
        logger_instance: logging.Logger | None = None,
    ):
        """Initialize the observability manager.

        Args:
            log_group_name: CloudWatch log group name for agent logs.
            metrics_namespace: CloudWatch namespace for metrics.
            cloudwatch_client: Optional boto3 CloudWatch client (for testing).
            logger_instance: Optional custom logger instance.
        """
        self.agent_logger = AgentLogger(
            log_group_name=log_group_name,
            logger_instance=logger_instance,
        )
        self.metrics_emitter = AgentMetricsEmitter(
            namespace=metrics_namespace,
            cloudwatch_client=cloudwatch_client,
        )

    def log_and_emit_error(
        self,
        agent_id: str,
        action: str,
        error_category: str,
        input_data: str | Any = "",
        output_data: str | Any = "",
        duration_ms: int = 0,
        cycle_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentInteractionLog:
        """Log an agent error and emit the corresponding CloudWatch metric.

        Combines logging (Req 13.1) and metric emission (Req 13.3) in a
        single call for error scenarios.

        Args:
            agent_id: Identifier of the agent.
            action: Action that failed.
            error_category: Category of the error.
            input_data: Input to the agent.
            output_data: Output/error from the agent.
            duration_ms: Execution duration in milliseconds.
            cycle_id: Parent pricing cycle ID.
            metadata: Additional metadata.

        Returns:
            The structured AgentInteractionLog entry.
        """
        # Log the interaction
        log_entry = self.agent_logger.log_interaction(
            agent_id=agent_id,
            action=action,
            input_data=input_data,
            output_data=output_data,
            duration_ms=duration_ms,
            success=False,
            error_category=error_category,
            cycle_id=cycle_id,
            metadata=metadata,
        )

        # Emit the metric
        self.metrics_emitter.emit_agent_error(
            agent_id=agent_id,
            error_category=error_category,
        )

        return log_entry

    def trace_cycle(
        self, cycle_id: str | None = None
    ) -> contextmanager:
        """Create a trace context for a pricing cycle.

        Args:
            cycle_id: Optional pricing cycle ID.

        Returns:
            Context manager yielding a TraceContext.
        """
        return trace_pricing_cycle(
            cycle_id=cycle_id,
            agent_logger=self.agent_logger,
        )
