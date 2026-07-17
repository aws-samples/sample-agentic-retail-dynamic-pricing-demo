"""Unit tests for the resilience module.

Tests timeout, retry, and graceful degradation logic for:
- Sub-agent invocations (120s timeout, 2 retries)
- MCP Server calls (30s timeout, 1 retry after 2s wait)
- Graceful degradation assessment and context building

Requirements: 1.5, 1.8, 2.7, 2.8, 2.9
"""

import time
from unittest.mock import patch

import pytest

from backend.orchestration.resilience import (
    AGENT_MAX_RETRIES,
    AGENT_RETRY_CONFIG,
    AGENT_TIMEOUT_SECONDS,
    MCP_MAX_RETRIES,
    MCP_RETRY_CONFIG,
    MCP_RETRY_DELAY_SECONDS,
    MCP_TIMEOUT_SECONDS,
    DegradationLevel,
    DegradationStatus,
    InvocationResult,
    InvocationStatus,
    RetryConfig,
    assess_degradation,
    build_degraded_context,
    invoke_agent,
    invoke_mcp_server,
    invoke_with_retry,
    with_agent_resilience,
    with_mcp_resilience,
)


# ---------------------------------------------------------------------------
# Test configuration constants
# ---------------------------------------------------------------------------


class TestConfigConstants:
    """Verify configuration constants match requirements."""

    def test_agent_timeout_is_120_seconds(self):
        """Requirement 1.8: 120-second timeout per sub-agent."""
        assert AGENT_TIMEOUT_SECONDS == 120

    def test_agent_max_retries_is_2(self):
        """Requirement 1.5: Retry up to 2 times."""
        assert AGENT_MAX_RETRIES == 2

    def test_mcp_timeout_is_30_seconds(self):
        """Requirement 2.7: MCP Server 30s timeout."""
        assert MCP_TIMEOUT_SECONDS == 30

    def test_mcp_max_retries_is_1(self):
        """Requirement 2.7: Single retry for MCP Server."""
        assert MCP_MAX_RETRIES == 1

    def test_mcp_retry_delay_is_2_seconds(self):
        """Requirement 2.7: Wait 2 seconds before MCP retry."""
        assert MCP_RETRY_DELAY_SECONDS == 2.0

    def test_agent_retry_config(self):
        """AGENT_RETRY_CONFIG has correct values."""
        assert AGENT_RETRY_CONFIG.max_retries == 2
        assert AGENT_RETRY_CONFIG.timeout_seconds == 120
        assert AGENT_RETRY_CONFIG.retry_delay_seconds == 0.0
        assert AGENT_RETRY_CONFIG.name == "agent"

    def test_mcp_retry_config(self):
        """MCP_RETRY_CONFIG has correct values."""
        assert MCP_RETRY_CONFIG.max_retries == 1
        assert MCP_RETRY_CONFIG.timeout_seconds == 30
        assert MCP_RETRY_CONFIG.retry_delay_seconds == 2.0
        assert MCP_RETRY_CONFIG.name == "mcp_server"


# ---------------------------------------------------------------------------
# Test invoke_with_retry - success cases
# ---------------------------------------------------------------------------


class TestInvokeWithRetrySuccess:
    """Test successful invocations."""

    def test_success_on_first_attempt(self):
        """Function succeeds on first try, no retries needed."""

        def success_fn():
            return {"result": "ok"}

        result = invoke_with_retry(
            fn=success_fn,
            config=RetryConfig(max_retries=2, timeout_seconds=5, name="test"),
            target_name="test_target",
        )

        assert result.success is True
        assert result.data == {"result": "ok"}
        assert result.retries_used == 0
        assert len(result.attempts) == 1
        assert result.attempts[0].status == InvocationStatus.SUCCESS
        assert result.degraded is False
        assert result.target_name == "test_target"

    def test_success_with_args_and_kwargs(self):
        """Function receives positional and keyword arguments."""

        def add_fn(a, b, multiplier=1):
            return (a + b) * multiplier

        result = invoke_with_retry(
            fn=add_fn,
            args=(3, 4),
            kwargs={"multiplier": 2},
            config=RetryConfig(max_retries=0, timeout_seconds=5, name="test"),
            target_name="add_fn",
        )

        assert result.success is True
        assert result.data == 14

    def test_success_after_one_retry(self):
        """Function fails once then succeeds on retry."""
        call_count = {"n": 0}

        def flaky_fn():
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("Transient failure")
            return "recovered"

        result = invoke_with_retry(
            fn=flaky_fn,
            config=RetryConfig(max_retries=2, timeout_seconds=5, name="test"),
            target_name="flaky",
        )

        assert result.success is True
        assert result.data == "recovered"
        assert result.retries_used == 1
        assert len(result.attempts) == 2
        assert result.attempts[0].status == InvocationStatus.RETRYING
        assert result.attempts[1].status == InvocationStatus.SUCCESS

    def test_success_after_two_retries(self):
        """Function fails twice then succeeds on third attempt."""
        call_count = {"n": 0}

        def very_flaky_fn():
            call_count["n"] += 1
            if call_count["n"] <= 2:
                raise RuntimeError(f"Failure #{call_count['n']}")
            return "finally_ok"

        result = invoke_with_retry(
            fn=very_flaky_fn,
            config=RetryConfig(max_retries=2, timeout_seconds=5, name="test"),
            target_name="very_flaky",
        )

        assert result.success is True
        assert result.data == "finally_ok"
        assert result.retries_used == 2
        assert len(result.attempts) == 3


# ---------------------------------------------------------------------------
# Test invoke_with_retry - failure cases
# ---------------------------------------------------------------------------


class TestInvokeWithRetryFailure:
    """Test failure scenarios after exhausting retries."""

    def test_failure_after_all_retries_exhausted(self):
        """Function fails on all attempts (1 initial + 2 retries)."""

        def always_fail():
            raise ValueError("Persistent error")

        result = invoke_with_retry(
            fn=always_fail,
            config=RetryConfig(max_retries=2, timeout_seconds=5, name="test"),
            target_name="always_fail",
        )

        assert result.success is False
        assert result.data is None
        assert result.retries_used == 2
        assert result.degraded is True
        assert "ValueError: Persistent error" in result.final_error
        assert len(result.attempts) == 3
        # First two should be RETRYING, last should be ERROR
        assert result.attempts[0].status == InvocationStatus.RETRYING
        assert result.attempts[1].status == InvocationStatus.RETRYING
        assert result.attempts[2].status == InvocationStatus.ERROR

    def test_failure_with_no_retries(self):
        """Function fails with max_retries=0 (no retries allowed)."""

        def fail_fn():
            raise RuntimeError("Immediate failure")

        result = invoke_with_retry(
            fn=fail_fn,
            config=RetryConfig(max_retries=0, timeout_seconds=5, name="test"),
            target_name="no_retry",
        )

        assert result.success is False
        assert result.retries_used == 0
        assert len(result.attempts) == 1
        assert result.attempts[0].status == InvocationStatus.ERROR
        assert result.degraded is True


# ---------------------------------------------------------------------------
# Test invoke_with_retry - timeout cases
# ---------------------------------------------------------------------------


class TestInvokeWithRetryTimeout:
    """Test timeout enforcement."""

    def test_timeout_triggers_on_slow_function(self):
        """Function exceeding timeout is terminated and retried."""

        def slow_fn():
            time.sleep(3)
            return "too_late"

        result = invoke_with_retry(
            fn=slow_fn,
            config=RetryConfig(max_retries=0, timeout_seconds=0.5, name="test"),
            target_name="slow_fn",
        )

        assert result.success is False
        assert result.degraded is True
        assert "Timeout" in result.final_error or "timeout" in result.final_error
        assert result.attempts[0].status == InvocationStatus.TIMEOUT

    def test_timeout_with_retry_succeeds(self):
        """Function times out once but succeeds on retry."""
        call_count = {"n": 0}

        def sometimes_slow():
            call_count["n"] += 1
            if call_count["n"] == 1:
                time.sleep(3)
            return "fast_this_time"

        result = invoke_with_retry(
            fn=sometimes_slow,
            config=RetryConfig(max_retries=1, timeout_seconds=0.5, name="test"),
            target_name="sometimes_slow",
        )

        assert result.success is True
        assert result.data == "fast_this_time"
        assert result.retries_used == 1
        assert result.attempts[0].status == InvocationStatus.RETRYING

    def test_timeout_all_attempts_exhausted(self):
        """Function times out on all attempts."""

        def always_slow():
            time.sleep(3)
            return "never_returned"

        result = invoke_with_retry(
            fn=always_slow,
            config=RetryConfig(max_retries=1, timeout_seconds=0.5, name="test"),
            target_name="always_slow",
        )

        assert result.success is False
        assert result.degraded is True
        assert len(result.attempts) == 2
        assert result.attempts[0].status == InvocationStatus.RETRYING
        assert result.attempts[1].status == InvocationStatus.TIMEOUT


# ---------------------------------------------------------------------------
# Test retry delay
# ---------------------------------------------------------------------------


class TestRetryDelay:
    """Test that retry delay is respected."""

    def test_mcp_retry_delay_is_applied(self):
        """MCP retry waits 2 seconds between attempts."""
        call_count = {"n": 0}
        call_times = []

        def fail_then_succeed():
            call_times.append(time.time())
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("First call fails")
            return "ok"

        result = invoke_with_retry(
            fn=fail_then_succeed,
            config=RetryConfig(
                max_retries=1, timeout_seconds=5, retry_delay_seconds=2.0, name="mcp"
            ),
            target_name="mcp_test",
        )

        assert result.success is True
        assert len(call_times) == 2
        delay = call_times[1] - call_times[0]
        # Allow some tolerance for timing
        assert delay >= 1.9, f"Expected ~2s delay, got {delay:.2f}s"

    def test_agent_no_retry_delay(self):
        """Agent retries have no delay between attempts."""
        call_count = {"n": 0}
        call_times = []

        def fail_then_succeed():
            call_times.append(time.time())
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("First call fails")
            return "ok"

        result = invoke_with_retry(
            fn=fail_then_succeed,
            config=RetryConfig(
                max_retries=1, timeout_seconds=5, retry_delay_seconds=0.0, name="agent"
            ),
            target_name="agent_test",
        )

        assert result.success is True
        assert len(call_times) == 2
        delay = call_times[1] - call_times[0]
        # Should be nearly instant (no delay)
        assert delay < 1.0, f"Expected no delay, got {delay:.2f}s"


# ---------------------------------------------------------------------------
# Test invoke_agent convenience function
# ---------------------------------------------------------------------------


class TestInvokeAgent:
    """Test the invoke_agent convenience wrapper."""

    def test_invoke_agent_uses_agent_config(self):
        """invoke_agent uses 120s timeout and 2 retries."""

        def agent_fn():
            return {"analysis": "complete"}

        result = invoke_agent(fn=agent_fn, agent_name="TestAgent")

        assert result.success is True
        assert result.data == {"analysis": "complete"}
        assert result.target_name == "TestAgent"

    def test_invoke_agent_retries_on_failure(self):
        """invoke_agent retries up to 2 times on failure."""
        call_count = {"n": 0}

        def flaky_agent():
            call_count["n"] += 1
            if call_count["n"] <= 2:
                raise RuntimeError("Agent error")
            return {"status": "recovered"}

        result = invoke_agent(fn=flaky_agent, agent_name="FlakyAgent")

        assert result.success is True
        assert result.retries_used == 2
        assert call_count["n"] == 3

    def test_invoke_agent_fails_after_3_attempts(self):
        """invoke_agent fails after 1 initial + 2 retries = 3 attempts."""

        def broken_agent():
            raise RuntimeError("Always broken")

        result = invoke_agent(fn=broken_agent, agent_name="BrokenAgent")

        assert result.success is False
        assert result.retries_used == 2
        assert result.degraded is True
        assert len(result.attempts) == 3


# ---------------------------------------------------------------------------
# Test invoke_mcp_server convenience function
# ---------------------------------------------------------------------------


class TestInvokeMcpServer:
    """Test the invoke_mcp_server convenience wrapper."""

    def test_invoke_mcp_server_uses_mcp_config(self):
        """invoke_mcp_server uses 30s timeout and 1 retry."""

        def mcp_fn():
            return {"status": "success", "data": {"prices": [10.0]}}

        result = invoke_mcp_server(fn=mcp_fn, server_name="CompetitorAPI")

        assert result.success is True
        assert result.data == {"status": "success", "data": {"prices": [10.0]}}
        assert result.target_name == "CompetitorAPI"

    def test_invoke_mcp_server_retries_once_with_delay(self):
        """invoke_mcp_server retries once after 2s delay on failure."""
        call_count = {"n": 0}
        call_times = []

        def flaky_mcp():
            call_times.append(time.time())
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("MCP timeout")
            return {"status": "success", "data": {}}

        result = invoke_mcp_server(fn=flaky_mcp, server_name="FlakyMCP")

        assert result.success is True
        assert result.retries_used == 1
        assert len(call_times) == 2
        delay = call_times[1] - call_times[0]
        assert delay >= 1.9

    def test_invoke_mcp_server_fails_after_2_attempts(self):
        """invoke_mcp_server fails after 1 initial + 1 retry = 2 attempts."""

        def broken_mcp():
            raise RuntimeError("MCP unreachable")

        result = invoke_mcp_server(fn=broken_mcp, server_name="BrokenMCP")

        assert result.success is False
        assert result.retries_used == 1
        assert result.degraded is True
        assert len(result.attempts) == 2


# ---------------------------------------------------------------------------
# Test graceful degradation assessment
# ---------------------------------------------------------------------------


class TestAssessDegradation:
    """Test degradation level assessment."""

    def _make_result(self, name: str, success: bool, error: str | None = None):
        """Helper to create InvocationResult for testing."""
        return InvocationResult(
            success=success,
            data={"output": name} if success else None,
            target_name=name,
            total_duration_ms=100,
            retries_used=0 if success else 2,
            final_error=error,
            degraded=not success,
        )

    def test_all_agents_succeed_no_degradation(self):
        """3/3 agents succeed: DegradationLevel.NONE."""
        results = [
            self._make_result("Competitive Intelligence", True),
            self._make_result("Demand Forecasting", True),
            self._make_result("Market Intelligence", True),
        ]

        status = assess_degradation(results)

        assert status.level == DegradationLevel.NONE
        assert status.can_proceed is True
        assert status.is_degraded is False
        assert len(status.failed_agents) == 0
        assert len(status.available_agents) == 3
        assert len(status.warnings) == 0

    def test_one_agent_fails_partial_degradation(self):
        """2/3 agents succeed: DegradationLevel.PARTIAL."""
        results = [
            self._make_result("Competitive Intelligence", True),
            self._make_result("Demand Forecasting", True),
            self._make_result("Market Intelligence", False, "Timeout"),
        ]

        status = assess_degradation(results)

        assert status.level == DegradationLevel.PARTIAL
        assert status.can_proceed is True
        assert status.is_degraded is True
        assert status.failed_agents == ["Market Intelligence"]
        assert set(status.available_agents) == {
            "Competitive Intelligence",
            "Demand Forecasting",
        }
        assert len(status.warnings) == 1
        assert "Market Intelligence" in status.warnings[0]

    def test_two_agents_fail_partial_degradation(self):
        """1/3 agents succeed but only 1 left: DegradationLevel.SEVERE."""
        results = [
            self._make_result("Competitive Intelligence", True),
            self._make_result("Demand Forecasting", False, "Error"),
            self._make_result("Market Intelligence", False, "Timeout"),
        ]

        status = assess_degradation(results)

        assert status.level == DegradationLevel.SEVERE
        assert status.can_proceed is True
        assert status.is_degraded is True
        assert len(status.failed_agents) == 2
        assert status.available_agents == ["Competitive Intelligence"]
        assert "SEVERE" in status.warnings[0]

    def test_all_agents_fail_total_degradation(self):
        """0/3 agents succeed: DegradationLevel.TOTAL."""
        results = [
            self._make_result("Competitive Intelligence", False, "Error1"),
            self._make_result("Demand Forecasting", False, "Error2"),
            self._make_result("Market Intelligence", False, "Error3"),
        ]

        status = assess_degradation(results)

        assert status.level == DegradationLevel.TOTAL
        assert status.can_proceed is False
        assert status.is_degraded is True
        assert len(status.failed_agents) == 3
        assert len(status.available_agents) == 0
        assert "TOTAL FAILURE" in status.warnings[0]

    def test_custom_total_expected(self):
        """Works with non-default total_expected count."""
        results = [
            self._make_result("Agent1", True),
            self._make_result("Agent2", False, "Error"),
        ]

        status = assess_degradation(results, total_expected=2)

        assert status.level == DegradationLevel.SEVERE
        assert status.can_proceed is True


# ---------------------------------------------------------------------------
# Test build_degraded_context
# ---------------------------------------------------------------------------


class TestBuildDegradedContext:
    """Test context building for degraded pipeline."""

    def test_full_context_no_degradation(self):
        """All agents succeed: context has all outputs."""
        results = [
            InvocationResult(
                success=True,
                data={"prices": [10, 20]},
                target_name="Competitive Intelligence",
                total_duration_ms=500,
                retries_used=0,
            ),
            InvocationResult(
                success=True,
                data={"demand": [100, 200]},
                target_name="Demand Forecasting",
                total_duration_ms=600,
                retries_used=0,
            ),
        ]
        degradation = DegradationStatus(
            level=DegradationLevel.NONE,
            available_agents=["Competitive Intelligence", "Demand Forecasting"],
        )

        context = build_degraded_context(results, degradation)

        assert context["degradation"]["level"] == "none"
        assert context["degradation"]["is_degraded"] is False
        assert context["degradation"]["can_proceed"] is True
        assert "Competitive Intelligence" in context["agent_outputs"]
        assert context["agent_outputs"]["Competitive Intelligence"]["status"] == "available"
        assert context["agent_outputs"]["Competitive Intelligence"]["data"] == {
            "prices": [10, 20]
        }

    def test_partial_context_with_degradation(self):
        """One agent failed: context marks it as unavailable."""
        results = [
            InvocationResult(
                success=True,
                data={"prices": [10]},
                target_name="Competitive Intelligence",
                total_duration_ms=500,
                retries_used=0,
            ),
            InvocationResult(
                success=False,
                data=None,
                target_name="Market Intelligence",
                total_duration_ms=360000,
                retries_used=2,
                final_error="Timeout after 120s",
                degraded=True,
            ),
        ]
        degradation = DegradationStatus(
            level=DegradationLevel.PARTIAL,
            failed_agents=["Market Intelligence"],
            available_agents=["Competitive Intelligence"],
            warnings=["Operating in degraded mode"],
        )

        context = build_degraded_context(results, degradation)

        assert context["degradation"]["level"] == "partial"
        assert context["degradation"]["is_degraded"] is True
        assert context["agent_outputs"]["Market Intelligence"]["status"] == "unavailable"
        assert context["agent_outputs"]["Market Intelligence"]["data"] is None
        assert "Timeout" in context["agent_outputs"]["Market Intelligence"]["error"]


# ---------------------------------------------------------------------------
# Test decorators
# ---------------------------------------------------------------------------


class TestDecorators:
    """Test the decorator-style wrappers."""

    def test_with_agent_resilience_success(self):
        """@with_agent_resilience wraps function with agent retry config."""

        @with_agent_resilience("TestAgent")
        def my_agent_call(prompt):
            return {"response": prompt}

        result = my_agent_call("analyze prices")

        assert result.success is True
        assert result.data == {"response": "analyze prices"}
        assert result.target_name == "TestAgent"

    def test_with_agent_resilience_retries(self):
        """@with_agent_resilience retries on failure."""
        call_count = {"n": 0}

        @with_agent_resilience("RetryAgent")
        def flaky_call():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise RuntimeError("Transient")
            return "ok"

        result = flaky_call()

        assert result.success is True
        assert result.retries_used == 2

    def test_with_mcp_resilience_success(self):
        """@with_mcp_resilience wraps function with MCP retry config."""

        @with_mcp_resilience("CompetitorAPI")
        def my_mcp_call(product_id):
            return {"status": "success", "data": {"price": 9.99}}

        result = my_mcp_call("prod-123")

        assert result.success is True
        assert result.data == {"status": "success", "data": {"price": 9.99}}
        assert result.target_name == "CompetitorAPI"

    def test_with_mcp_resilience_fails_after_one_retry(self):
        """@with_mcp_resilience fails after 1 initial + 1 retry."""

        @with_mcp_resilience("BrokenMCP")
        def broken_call():
            raise RuntimeError("MCP down")

        result = broken_call()

        assert result.success is False
        assert result.retries_used == 1
        assert result.degraded is True


# ---------------------------------------------------------------------------
# Test InvocationResult and DegradationStatus properties
# ---------------------------------------------------------------------------


class TestDataClasses:
    """Test data class properties and behavior."""

    def test_degradation_status_can_proceed_true(self):
        """can_proceed is True for NONE, PARTIAL, SEVERE."""
        for level in [DegradationLevel.NONE, DegradationLevel.PARTIAL, DegradationLevel.SEVERE]:
            status = DegradationStatus(level=level)
            assert status.can_proceed is True

    def test_degradation_status_can_proceed_false(self):
        """can_proceed is False for TOTAL."""
        status = DegradationStatus(level=DegradationLevel.TOTAL)
        assert status.can_proceed is False

    def test_degradation_status_is_degraded(self):
        """is_degraded is False only for NONE."""
        assert DegradationStatus(level=DegradationLevel.NONE).is_degraded is False
        assert DegradationStatus(level=DegradationLevel.PARTIAL).is_degraded is True
        assert DegradationStatus(level=DegradationLevel.SEVERE).is_degraded is True
        assert DegradationStatus(level=DegradationLevel.TOTAL).is_degraded is True

    def test_invocation_status_enum_values(self):
        """InvocationStatus has expected string values."""
        assert InvocationStatus.SUCCESS == "success"
        assert InvocationStatus.TIMEOUT == "timeout"
        assert InvocationStatus.ERROR == "error"
        assert InvocationStatus.RETRYING == "retrying"
        assert InvocationStatus.DEGRADED == "degraded"


# ---------------------------------------------------------------------------
# Test duration tracking
# ---------------------------------------------------------------------------


class TestDurationTracking:
    """Test that durations are tracked correctly."""

    def test_total_duration_includes_all_attempts(self):
        """total_duration_ms covers the entire invocation including retries."""
        call_count = {"n": 0}

        def slow_then_fast():
            call_count["n"] += 1
            if call_count["n"] == 1:
                time.sleep(0.1)
                raise RuntimeError("Slow failure")
            return "fast"

        result = invoke_with_retry(
            fn=slow_then_fast,
            config=RetryConfig(max_retries=1, timeout_seconds=5, name="test"),
            target_name="duration_test",
        )

        assert result.success is True
        assert result.total_duration_ms >= 100  # At least the sleep time
        assert result.attempts[0].duration_ms >= 100

    def test_attempt_timestamps_are_recorded(self):
        """Each attempt records its start timestamp."""
        call_count = {"n": 0}

        def fail_once():
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("First fail")
            return "ok"

        result = invoke_with_retry(
            fn=fail_once,
            config=RetryConfig(max_retries=1, timeout_seconds=5, name="test"),
            target_name="timestamp_test",
        )

        assert result.success is True
        assert len(result.attempts) == 2
        assert result.attempts[0].timestamp > 0
        assert result.attempts[1].timestamp > 0
        assert result.attempts[1].timestamp >= result.attempts[0].timestamp


# ---------------------------------------------------------------------------
# Test logging
# ---------------------------------------------------------------------------


class TestLogging:
    """Test that resilience events are logged."""

    def test_success_is_logged(self, caplog):
        """Successful invocation logs at INFO level."""
        import logging

        with caplog.at_level(logging.INFO, logger="backend.orchestration.resilience"):

            def ok_fn():
                return "done"

            invoke_with_retry(
                fn=ok_fn,
                config=RetryConfig(max_retries=0, timeout_seconds=5, name="test"),
                target_name="log_test",
            )

        assert any("succeeded" in r.message and "log_test" in r.message for r in caplog.records)

    def test_failure_is_logged(self, caplog):
        """Failed invocation logs at ERROR level."""
        import logging

        with caplog.at_level(logging.WARNING, logger="backend.orchestration.resilience"):

            def fail_fn():
                raise RuntimeError("Oops")

            invoke_with_retry(
                fn=fail_fn,
                config=RetryConfig(max_retries=0, timeout_seconds=5, name="test"),
                target_name="fail_log_test",
            )

        assert any("failed" in r.message and "fail_log_test" in r.message for r in caplog.records)

    def test_timeout_is_logged(self, caplog):
        """Timeout events are logged at WARNING level."""
        import logging

        with caplog.at_level(logging.WARNING, logger="backend.orchestration.resilience"):

            def slow_fn():
                time.sleep(3)

            invoke_with_retry(
                fn=slow_fn,
                config=RetryConfig(max_retries=0, timeout_seconds=0.5, name="test"),
                target_name="timeout_log_test",
            )

        assert any(
            "timed out" in r.message and "timeout_log_test" in r.message
            for r in caplog.records
        )

    def test_degradation_warning_logged(self, caplog):
        """Degradation assessment logs warnings for degraded state."""
        import logging

        with caplog.at_level(logging.WARNING, logger="backend.orchestration.resilience"):
            results = [
                InvocationResult(success=True, target_name="A", data={}),
                InvocationResult(
                    success=False,
                    target_name="B",
                    final_error="err",
                    degraded=True,
                ),
                InvocationResult(
                    success=False,
                    target_name="C",
                    final_error="err",
                    degraded=True,
                ),
            ]
            assess_degradation(results)

        assert any("Degradation assessment" in r.message for r in caplog.records)
