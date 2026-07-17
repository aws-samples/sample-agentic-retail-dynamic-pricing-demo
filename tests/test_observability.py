"""Unit tests for the observability and logging module.

Tests structured logging of agent interactions, CloudWatch metric emission,
trace context management, alarm configuration, and summary truncation.

Validates: Requirements 13.1, 13.2, 13.3, 13.4
"""

import json
import logging
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.orchestration.observability import (
    DEFAULT_ERROR_THRESHOLD,
    DEFAULT_EVALUATION_PERIOD_SECONDS,
    MAX_SUMMARY_LENGTH,
    METRICS_NAMESPACE,
    AgentInteractionLog,
    AgentLogger,
    AgentMetricsEmitter,
    ObservabilityManager,
    TraceContext,
    get_alarm_configuration,
    trace_pricing_cycle,
    truncate_summary,
)


# ---------------------------------------------------------------------------
# Tests for truncate_summary
# ---------------------------------------------------------------------------


class TestTruncateSummary:
    """Tests for the summary truncation helper."""

    def test_short_text_unchanged(self):
        text = "Short input"
        assert truncate_summary(text) == text

    def test_text_at_max_length_unchanged(self):
        text = "x" * MAX_SUMMARY_LENGTH
        assert truncate_summary(text) == text
        assert len(truncate_summary(text)) == MAX_SUMMARY_LENGTH

    def test_text_exceeding_max_length_truncated(self):
        text = "x" * (MAX_SUMMARY_LENGTH + 100)
        result = truncate_summary(text)
        assert len(result) <= MAX_SUMMARY_LENGTH
        assert result.endswith("...[truncated]")

    def test_custom_max_length(self):
        text = "Hello, this is a longer text that should be truncated"
        result = truncate_summary(text, max_length=20)
        assert len(result) <= 20
        assert result.endswith("...[truncated]")

    def test_none_input_returns_empty_string(self):
        assert truncate_summary(None) == ""

    def test_non_string_input_converted(self):
        result = truncate_summary(12345)
        assert result == "12345"

    def test_dict_input_converted(self):
        data = {"key": "value", "number": 42}
        result = truncate_summary(data)
        assert "key" in result
        assert "value" in result

    def test_empty_string_unchanged(self):
        assert truncate_summary("") == ""

    def test_very_small_max_length(self):
        text = "Hello World"
        result = truncate_summary(text, max_length=5)
        assert len(result) <= 5

    def test_truncation_preserves_beginning(self):
        text = "IMPORTANT_PREFIX_" + "x" * 2000
        result = truncate_summary(text, max_length=100)
        assert result.startswith("IMPORTANT_PREFIX_")


# ---------------------------------------------------------------------------
# Tests for AgentInteractionLog
# ---------------------------------------------------------------------------


class TestAgentInteractionLog:
    """Tests for the structured log entry data class."""

    def test_create_log_entry(self):
        log = AgentInteractionLog(
            timestamp="2024-01-15T10:30:00Z",
            agent_id="competitive-intelligence",
            action="invoke",
            input_summary="Analyze pricing for electronics",
            output_summary='{"competitors": [...]}',
            duration_ms=1500,
        )
        assert log.agent_id == "competitive-intelligence"
        assert log.action == "invoke"
        assert log.duration_ms == 1500
        assert log.success is True

    def test_to_dict_excludes_none_values(self):
        log = AgentInteractionLog(
            timestamp="2024-01-15T10:30:00Z",
            agent_id="test-agent",
            action="invoke",
            input_summary="input",
            output_summary="output",
            duration_ms=100,
        )
        d = log.to_dict()
        assert "trace_id" not in d
        assert "error_category" not in d
        assert "cycle_id" not in d

    def test_to_dict_includes_set_values(self):
        log = AgentInteractionLog(
            timestamp="2024-01-15T10:30:00Z",
            agent_id="test-agent",
            action="error",
            input_summary="input",
            output_summary="error output",
            duration_ms=500,
            trace_id="trace-123",
            cycle_id="cycle-456",
            error_category="timeout",
            success=False,
        )
        d = log.to_dict()
        assert d["trace_id"] == "trace-123"
        assert d["cycle_id"] == "cycle-456"
        assert d["error_category"] == "timeout"
        assert d["success"] is False

    def test_to_json_produces_valid_json(self):
        log = AgentInteractionLog(
            timestamp="2024-01-15T10:30:00Z",
            agent_id="test-agent",
            action="invoke",
            input_summary="test input",
            output_summary="test output",
            duration_ms=200,
        )
        json_str = log.to_json()
        parsed = json.loads(json_str)
        assert parsed["agent_id"] == "test-agent"
        assert parsed["duration_ms"] == 200

    def test_to_json_contains_required_fields(self):
        log = AgentInteractionLog(
            timestamp="2024-01-15T10:30:00Z",
            agent_id="demand-forecasting",
            action="complete",
            input_summary="forecast request",
            output_summary="forecast result",
            duration_ms=3000,
        )
        json_str = log.to_json()
        parsed = json.loads(json_str)
        # Requirement 13.1: timestamp, agent_id, action, input_summary,
        # output_summary, duration_ms
        assert "timestamp" in parsed
        assert "agent_id" in parsed
        assert "action" in parsed
        assert "input_summary" in parsed
        assert "output_summary" in parsed
        assert "duration_ms" in parsed


# ---------------------------------------------------------------------------
# Tests for AgentLogger
# ---------------------------------------------------------------------------


class TestAgentLogger:
    """Tests for the structured agent logger (Requirement 13.1)."""

    def test_log_successful_interaction(self):
        test_logger = logging.getLogger("test.agent_logger")
        agent_logger = AgentLogger(logger_instance=test_logger)

        log_entry = agent_logger.log_interaction(
            agent_id="competitive-intelligence",
            action="invoke",
            input_data="Analyze electronics pricing",
            output_data='{"competitors": [{"name": "Store A"}]}',
            duration_ms=1500,
        )

        assert log_entry.agent_id == "competitive-intelligence"
        assert log_entry.action == "invoke"
        assert log_entry.duration_ms == 1500
        assert log_entry.success is True
        assert log_entry.error_category is None

    def test_log_failed_interaction(self):
        test_logger = logging.getLogger("test.agent_logger")
        agent_logger = AgentLogger(logger_instance=test_logger)

        log_entry = agent_logger.log_interaction(
            agent_id="demand-forecasting",
            action="error",
            input_data="Forecast demand",
            output_data="TimeoutError: exceeded 120s",
            duration_ms=120000,
            success=False,
            error_category="timeout",
        )

        assert log_entry.success is False
        assert log_entry.error_category == "timeout"

    def test_log_truncates_long_input(self):
        test_logger = logging.getLogger("test.agent_logger")
        agent_logger = AgentLogger(logger_instance=test_logger)

        long_input = "x" * 5000
        log_entry = agent_logger.log_interaction(
            agent_id="test-agent",
            action="invoke",
            input_data=long_input,
            output_data="short output",
            duration_ms=100,
        )

        assert len(log_entry.input_summary) <= MAX_SUMMARY_LENGTH

    def test_log_truncates_long_output(self):
        test_logger = logging.getLogger("test.agent_logger")
        agent_logger = AgentLogger(logger_instance=test_logger)

        long_output = "y" * 5000
        log_entry = agent_logger.log_interaction(
            agent_id="test-agent",
            action="complete",
            input_data="short input",
            output_data=long_output,
            duration_ms=100,
        )

        assert len(log_entry.output_summary) <= MAX_SUMMARY_LENGTH

    def test_log_includes_trace_id_when_trace_active(self):
        test_logger = logging.getLogger("test.agent_logger")
        agent_logger = AgentLogger(logger_instance=test_logger)

        trace = TraceContext(trace_id="trace-abc-123", cycle_id="cycle-1")
        agent_logger.current_trace = trace

        log_entry = agent_logger.log_interaction(
            agent_id="test-agent",
            action="invoke",
            input_data="input",
            output_data="output",
            duration_ms=50,
        )

        assert log_entry.trace_id == "trace-abc-123"

    def test_log_no_trace_id_when_no_trace(self):
        test_logger = logging.getLogger("test.agent_logger")
        agent_logger = AgentLogger(logger_instance=test_logger)

        log_entry = agent_logger.log_interaction(
            agent_id="test-agent",
            action="invoke",
            input_data="input",
            output_data="output",
            duration_ms=50,
        )

        assert log_entry.trace_id is None

    def test_log_adds_span_to_active_trace(self):
        test_logger = logging.getLogger("test.agent_logger")
        agent_logger = AgentLogger(logger_instance=test_logger)

        trace = TraceContext(trace_id="trace-xyz", cycle_id="cycle-2")
        agent_logger.current_trace = trace

        agent_logger.log_interaction(
            agent_id="market-intelligence",
            action="complete",
            input_data="market analysis",
            output_data="trends data",
            duration_ms=2000,
        )

        assert len(trace.spans) == 1
        assert trace.spans[0]["agent_id"] == "market-intelligence"
        assert trace.spans[0]["duration_ms"] == 2000

    def test_log_includes_cycle_id(self):
        test_logger = logging.getLogger("test.agent_logger")
        agent_logger = AgentLogger(logger_instance=test_logger)

        log_entry = agent_logger.log_interaction(
            agent_id="test-agent",
            action="invoke",
            input_data="input",
            output_data="output",
            duration_ms=100,
            cycle_id="cycle-789",
        )

        assert log_entry.cycle_id == "cycle-789"

    def test_log_includes_metadata(self):
        test_logger = logging.getLogger("test.agent_logger")
        agent_logger = AgentLogger(logger_instance=test_logger)

        log_entry = agent_logger.log_interaction(
            agent_id="test-agent",
            action="invoke",
            input_data="input",
            output_data="output",
            duration_ms=100,
            metadata={"retry_count": 2, "pricing_group": "electronics"},
        )

        assert log_entry.metadata["retry_count"] == 2
        assert log_entry.metadata["pricing_group"] == "electronics"


# ---------------------------------------------------------------------------
# Tests for AgentMetricsEmitter
# ---------------------------------------------------------------------------


class TestAgentMetricsEmitter:
    """Tests for CloudWatch metric emission (Requirement 13.3)."""

    def test_emit_agent_error_success(self):
        mock_client = MagicMock()
        mock_client.put_metric_data.return_value = {}

        emitter = AgentMetricsEmitter(cloudwatch_client=mock_client)
        result = emitter.emit_agent_error(
            agent_id="competitive-intelligence",
            error_category="timeout",
        )

        assert result is True
        mock_client.put_metric_data.assert_called_once()

    def test_emit_agent_error_correct_dimensions(self):
        mock_client = MagicMock()
        mock_client.put_metric_data.return_value = {}

        emitter = AgentMetricsEmitter(cloudwatch_client=mock_client)
        emitter.emit_agent_error(
            agent_id="demand-forecasting",
            error_category="runtime",
        )

        call_args = mock_client.put_metric_data.call_args
        metric_data = call_args[1]["MetricData"][0]

        assert metric_data["MetricName"] == "AgentErrors"
        dimensions = {d["Name"]: d["Value"] for d in metric_data["Dimensions"]}
        assert dimensions["AgentId"] == "demand-forecasting"
        assert dimensions["ErrorCategory"] == "runtime"

    def test_emit_agent_error_correct_namespace(self):
        mock_client = MagicMock()
        mock_client.put_metric_data.return_value = {}

        emitter = AgentMetricsEmitter(
            namespace="Custom/Namespace",
            cloudwatch_client=mock_client,
        )
        emitter.emit_agent_error(
            agent_id="test-agent",
            error_category="validation",
        )

        call_args = mock_client.put_metric_data.call_args
        assert call_args[1]["Namespace"] == "Custom/Namespace"

    def test_emit_agent_error_default_value_is_one(self):
        mock_client = MagicMock()
        mock_client.put_metric_data.return_value = {}

        emitter = AgentMetricsEmitter(cloudwatch_client=mock_client)
        emitter.emit_agent_error(
            agent_id="test-agent",
            error_category="timeout",
        )

        call_args = mock_client.put_metric_data.call_args
        metric_data = call_args[1]["MetricData"][0]
        assert metric_data["Value"] == 1.0
        assert metric_data["Unit"] == "Count"

    def test_emit_agent_error_custom_value(self):
        mock_client = MagicMock()
        mock_client.put_metric_data.return_value = {}

        emitter = AgentMetricsEmitter(cloudwatch_client=mock_client)
        emitter.emit_agent_error(
            agent_id="test-agent",
            error_category="timeout",
            value=3.0,
        )

        call_args = mock_client.put_metric_data.call_args
        metric_data = call_args[1]["MetricData"][0]
        assert metric_data["Value"] == 3.0

    def test_emit_agent_error_handles_client_error(self):
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        mock_client.put_metric_data.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Service error"}},
            "PutMetricData",
        )

        emitter = AgentMetricsEmitter(cloudwatch_client=mock_client)
        result = emitter.emit_agent_error(
            agent_id="test-agent",
            error_category="timeout",
        )

        assert result is False

    def test_emit_agent_error_handles_unexpected_error(self):
        mock_client = MagicMock()
        mock_client.put_metric_data.side_effect = RuntimeError("Unexpected")

        emitter = AgentMetricsEmitter(cloudwatch_client=mock_client)
        result = emitter.emit_agent_error(
            agent_id="test-agent",
            error_category="timeout",
        )

        assert result is False

    def test_default_namespace(self):
        mock_client = MagicMock()
        mock_client.put_metric_data.return_value = {}

        emitter = AgentMetricsEmitter(cloudwatch_client=mock_client)
        emitter.emit_agent_error(
            agent_id="test-agent",
            error_category="timeout",
        )

        call_args = mock_client.put_metric_data.call_args
        assert call_args[1]["Namespace"] == METRICS_NAMESPACE


# ---------------------------------------------------------------------------
# Tests for TraceContext
# ---------------------------------------------------------------------------


class TestTraceContext:
    """Tests for trace context management (Requirement 13.2)."""

    def test_create_trace_context(self):
        trace = TraceContext(trace_id="trace-123", cycle_id="cycle-456")
        assert trace.trace_id == "trace-123"
        assert trace.cycle_id == "cycle-456"
        assert trace.spans == []

    def test_add_span(self):
        trace = TraceContext(trace_id="trace-123")
        trace.add_span(
            agent_id="competitive-intelligence",
            action="invoke",
            duration_ms=1500,
            success=True,
        )

        assert len(trace.spans) == 1
        span = trace.spans[0]
        assert span["agent_id"] == "competitive-intelligence"
        assert span["action"] == "invoke"
        assert span["duration_ms"] == 1500
        assert span["success"] is True
        assert "span_id" in span
        assert "timestamp" in span

    def test_add_span_with_error(self):
        trace = TraceContext(trace_id="trace-123")
        trace.add_span(
            agent_id="demand-forecasting",
            action="error",
            duration_ms=120000,
            success=False,
            error="TimeoutError",
        )

        span = trace.spans[0]
        assert span["success"] is False
        assert span["error"] == "TimeoutError"

    def test_add_multiple_spans(self):
        trace = TraceContext(trace_id="trace-123")
        trace.add_span("agent-1", "invoke", 100)
        trace.add_span("agent-2", "invoke", 200)
        trace.add_span("agent-3", "invoke", 300)

        assert len(trace.spans) == 3

    def test_get_total_duration_ms(self):
        trace = TraceContext(
            trace_id="trace-123",
            start_time=time.time() - 2.0,  # Started 2 seconds ago
        )
        duration = trace.get_total_duration_ms()
        # Should be approximately 2000ms (allow some tolerance)
        assert 1900 <= duration <= 2200

    def test_span_ids_are_unique(self):
        trace = TraceContext(trace_id="trace-123")
        trace.add_span("agent-1", "invoke", 100)
        trace.add_span("agent-2", "invoke", 200)

        span_ids = [s["span_id"] for s in trace.spans]
        assert len(set(span_ids)) == 2  # All unique


# ---------------------------------------------------------------------------
# Tests for trace_pricing_cycle context manager
# ---------------------------------------------------------------------------


class TestTracePricingCycle:
    """Tests for the trace context manager (Requirement 13.2)."""

    def test_creates_trace_with_unique_id(self):
        with trace_pricing_cycle(cycle_id="cycle-1") as trace:
            assert trace.trace_id is not None
            assert len(trace.trace_id) > 0

    def test_trace_has_cycle_id(self):
        with trace_pricing_cycle(cycle_id="cycle-abc") as trace:
            assert trace.cycle_id == "cycle-abc"

    def test_trace_binds_to_agent_logger(self):
        test_logger = logging.getLogger("test.trace")
        agent_logger = AgentLogger(logger_instance=test_logger)

        with trace_pricing_cycle(
            cycle_id="cycle-1", agent_logger=agent_logger
        ) as trace:
            assert agent_logger.current_trace is trace

        # After context exits, trace should be restored
        assert agent_logger.current_trace is None

    def test_trace_restores_previous_trace(self):
        test_logger = logging.getLogger("test.trace")
        agent_logger = AgentLogger(logger_instance=test_logger)

        previous_trace = TraceContext(trace_id="previous-trace")
        agent_logger.current_trace = previous_trace

        with trace_pricing_cycle(
            cycle_id="cycle-1", agent_logger=agent_logger
        ) as trace:
            assert agent_logger.current_trace is trace
            assert trace.trace_id != "previous-trace"

        assert agent_logger.current_trace is previous_trace

    def test_trace_spans_accumulate(self):
        test_logger = logging.getLogger("test.trace")
        agent_logger = AgentLogger(logger_instance=test_logger)

        with trace_pricing_cycle(
            cycle_id="cycle-1", agent_logger=agent_logger
        ) as trace:
            agent_logger.log_interaction(
                agent_id="agent-1",
                action="invoke",
                input_data="input1",
                output_data="output1",
                duration_ms=100,
            )
            agent_logger.log_interaction(
                agent_id="agent-2",
                action="invoke",
                input_data="input2",
                output_data="output2",
                duration_ms=200,
            )

        assert len(trace.spans) == 2

    def test_trace_works_without_agent_logger(self):
        with trace_pricing_cycle(cycle_id="cycle-1") as trace:
            assert trace.trace_id is not None
            trace.add_span("agent-1", "invoke", 100)

        assert len(trace.spans) == 1

    def test_trace_survives_exception(self):
        test_logger = logging.getLogger("test.trace")
        agent_logger = AgentLogger(logger_instance=test_logger)

        with pytest.raises(ValueError):
            with trace_pricing_cycle(
                cycle_id="cycle-1", agent_logger=agent_logger
            ) as trace:
                agent_logger.log_interaction(
                    agent_id="agent-1",
                    action="invoke",
                    input_data="input",
                    output_data="output",
                    duration_ms=100,
                )
                raise ValueError("Test error")

        # Logger should be restored even after exception
        assert agent_logger.current_trace is None
        # Span should still be recorded
        assert len(trace.spans) == 1


# ---------------------------------------------------------------------------
# Tests for get_alarm_configuration
# ---------------------------------------------------------------------------


class TestAlarmConfiguration:
    """Tests for CloudWatch alarm configuration (Requirement 13.4)."""

    def test_alarm_configuration_has_required_fields(self):
        config = get_alarm_configuration()
        assert "alarm_name" in config
        assert "namespace" in config
        assert "metric_name" in config
        assert "statistic" in config
        assert "period_seconds" in config
        assert "threshold" in config
        assert "comparison_operator" in config
        assert "evaluation_periods" in config

    def test_alarm_threshold_is_5(self):
        config = get_alarm_configuration()
        assert config["threshold"] == 5

    def test_alarm_period_is_60_seconds(self):
        config = get_alarm_configuration()
        assert config["period_seconds"] == 60

    def test_alarm_uses_sum_statistic(self):
        config = get_alarm_configuration()
        assert config["statistic"] == "Sum"

    def test_alarm_uses_correct_namespace(self):
        config = get_alarm_configuration()
        assert config["namespace"] == METRICS_NAMESPACE

    def test_alarm_metric_name_is_agent_errors(self):
        config = get_alarm_configuration()
        assert config["metric_name"] == "AgentErrors"

    def test_alarm_treats_missing_data_as_not_breaching(self):
        config = get_alarm_configuration()
        assert config["treat_missing_data"] == "notBreaching"

    def test_alarm_has_description(self):
        config = get_alarm_configuration()
        assert "alarm_description" in config
        assert "5 errors" in config["alarm_description"]
        assert "60-second" in config["alarm_description"]


# ---------------------------------------------------------------------------
# Tests for ObservabilityManager
# ---------------------------------------------------------------------------


class TestObservabilityManager:
    """Tests for the combined observability facade."""

    def test_create_manager(self):
        mock_client = MagicMock()
        manager = ObservabilityManager(cloudwatch_client=mock_client)
        assert manager.agent_logger is not None
        assert manager.metrics_emitter is not None

    def test_log_and_emit_error(self):
        mock_client = MagicMock()
        mock_client.put_metric_data.return_value = {}

        manager = ObservabilityManager(cloudwatch_client=mock_client)

        log_entry = manager.log_and_emit_error(
            agent_id="competitive-intelligence",
            action="invoke",
            error_category="timeout",
            input_data="Analyze pricing",
            output_data="TimeoutError",
            duration_ms=120000,
            cycle_id="cycle-123",
        )

        # Verify log entry
        assert log_entry.agent_id == "competitive-intelligence"
        assert log_entry.success is False
        assert log_entry.error_category == "timeout"

        # Verify metric was emitted
        mock_client.put_metric_data.assert_called_once()
        call_args = mock_client.put_metric_data.call_args
        metric_data = call_args[1]["MetricData"][0]
        dimensions = {d["Name"]: d["Value"] for d in metric_data["Dimensions"]}
        assert dimensions["AgentId"] == "competitive-intelligence"
        assert dimensions["ErrorCategory"] == "timeout"

    def test_trace_cycle_context_manager(self):
        mock_client = MagicMock()
        manager = ObservabilityManager(cloudwatch_client=mock_client)

        with manager.trace_cycle(cycle_id="cycle-456") as trace:
            assert trace.trace_id is not None
            assert trace.cycle_id == "cycle-456"

            # Log within the trace
            manager.agent_logger.log_interaction(
                agent_id="test-agent",
                action="invoke",
                input_data="input",
                output_data="output",
                duration_ms=100,
            )

        assert len(trace.spans) == 1

    def test_manager_with_custom_log_group(self):
        mock_client = MagicMock()
        manager = ObservabilityManager(
            log_group_name="/custom/log-group",
            cloudwatch_client=mock_client,
        )
        assert manager.agent_logger._log_group_name == "/custom/log-group"

    def test_manager_with_custom_namespace(self):
        mock_client = MagicMock()
        mock_client.put_metric_data.return_value = {}

        manager = ObservabilityManager(
            metrics_namespace="Custom/Metrics",
            cloudwatch_client=mock_client,
        )

        manager.metrics_emitter.emit_agent_error("agent-1", "error")

        call_args = mock_client.put_metric_data.call_args
        assert call_args[1]["Namespace"] == "Custom/Metrics"
