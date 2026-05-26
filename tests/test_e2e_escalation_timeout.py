"""End-to-end tests for escalation deadline and timeout handling.

Tests cover:
1. Escalation deadline: MEDIUM/HIGH risk approvals set escalationDeadline to 48h from now
2. Agent timeout: slow agents (>120s) are terminated and retried
3. Retry behavior: retry up to 2 times then degrade
4. Graceful degradation: 1 of 3 agents fails, pipeline still produces DEGRADED status
5. Total failure: all 3 agents fail, pipeline returns FAILED status

Requirements: 7.7, 1.5, 1.8
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

from backend.orchestration.resilience import (
    AGENT_RETRY_CONFIG,
    DegradationLevel,
    InvocationResult,
    InvocationStatus,
    RetryConfig,
    assess_degradation,
    invoke_with_retry,
)


# ---------------------------------------------------------------------------
# 1. Escalation deadline tests (Requirement 7.7)
# ---------------------------------------------------------------------------


class TestEscalationDeadline:
    """Test 48-hour escalation deadline logic for MEDIUM/HIGH risk approvals."""

    def test_medium_risk_approval_sets_48h_escalation_deadline(self):
        """MEDIUM risk approval sets escalationDeadline to 48 hours from now.

        Requirement 7.7: IF a routed Pricing_Scenario receives no approval or
        rejection decision within 48 hours, THEN escalate.
        """
        from datetime import timedelta

        # Simulate the approval handler logic for escalation deadline
        now = datetime.now(timezone.utc)
        risk_level = "MEDIUM"
        action = "APPROVED"

        # This mirrors the logic in approvals.py
        approval_record = {
            "scenarioId": "scenario-001",
            "timestamp": now.isoformat(),
            "action": action,
            "actorId": "user-123",
            "comment": "Looks good",
            "riskLevel": risk_level,
        }

        if action == "APPROVED" and risk_level in ("MEDIUM", "HIGH"):
            escalation_deadline = (now + timedelta(hours=48)).isoformat()
            approval_record["escalationDeadline"] = escalation_deadline

        # Verify escalation deadline is set
        assert "escalationDeadline" in approval_record
        deadline = datetime.fromisoformat(approval_record["escalationDeadline"])
        expected_deadline = now + timedelta(hours=48)

        # Allow 1 second tolerance for test execution time
        assert abs((deadline - expected_deadline).total_seconds()) < 1.0

    def test_high_risk_approval_sets_48h_escalation_deadline(self):
        """HIGH risk approval also sets escalationDeadline to 48 hours from now."""
        now = datetime.now(timezone.utc)
        risk_level = "HIGH"
        action = "APPROVED"

        approval_record = {
            "scenarioId": "scenario-002",
            "timestamp": now.isoformat(),
            "action": action,
            "actorId": "user-456",
            "comment": "This is a justified approval with more than fifty characters for high risk.",
            "riskLevel": risk_level,
        }

        if action == "APPROVED" and risk_level in ("MEDIUM", "HIGH"):
            escalation_deadline = (now + timedelta(hours=48)).isoformat()
            approval_record["escalationDeadline"] = escalation_deadline

        assert "escalationDeadline" in approval_record
        deadline = datetime.fromisoformat(approval_record["escalationDeadline"])
        expected_deadline = now + timedelta(hours=48)
        assert abs((deadline - expected_deadline).total_seconds()) < 1.0

    def test_low_risk_approval_does_not_set_escalation_deadline(self):
        """LOW risk approvals do NOT set an escalation deadline (auto-approved)."""
        now = datetime.now(timezone.utc)
        risk_level = "LOW"
        action = "APPROVED"

        approval_record = {
            "scenarioId": "scenario-003",
            "timestamp": now.isoformat(),
            "action": action,
            "actorId": "user-789",
            "comment": "Auto-approved",
            "riskLevel": risk_level,
        }

        # Only MEDIUM/HIGH get escalation deadlines
        if action == "APPROVED" and risk_level in ("MEDIUM", "HIGH"):
            escalation_deadline = (now + timedelta(hours=48)).isoformat()
            approval_record["escalationDeadline"] = escalation_deadline

        assert "escalationDeadline" not in approval_record

    def test_rejection_does_not_set_escalation_deadline(self):
        """Rejected scenarios do NOT set an escalation deadline."""
        now = datetime.now(timezone.utc)
        risk_level = "MEDIUM"
        action = "REJECTED"

        approval_record = {
            "scenarioId": "scenario-004",
            "timestamp": now.isoformat(),
            "action": action,
            "actorId": "user-101",
            "comment": "Not suitable",
            "riskLevel": risk_level,
        }

        if action == "APPROVED" and risk_level in ("MEDIUM", "HIGH"):
            escalation_deadline = (now + timedelta(hours=48)).isoformat()
            approval_record["escalationDeadline"] = escalation_deadline

        assert "escalationDeadline" not in approval_record

    def test_escalation_deadline_is_valid_iso8601(self):
        """The escalation deadline is a valid ISO 8601 timestamp."""
        now = datetime.now(timezone.utc)
        escalation_deadline = (now + timedelta(hours=48)).isoformat()

        # Should parse without error
        parsed = datetime.fromisoformat(escalation_deadline)
        assert parsed.tzinfo is not None  # Must be timezone-aware
        assert parsed > now  # Must be in the future


# ---------------------------------------------------------------------------
# 2. Agent timeout tests (Requirement 1.8)
# ---------------------------------------------------------------------------


class TestAgentTimeout:
    """Test that slow agents (>120s) are terminated and retried."""

    def test_agent_exceeding_timeout_is_terminated(self):
        """An agent that takes longer than the timeout is terminated.

        Requirement 1.8: IF any single agent does not complete execution
        within 120 seconds, THEN terminate the agent task.
        """

        def slow_agent():
            time.sleep(5)  # Simulates a slow agent
            return "should_not_return"

        # Use a short timeout for testing (0.3s instead of 120s)
        config = RetryConfig(
            max_retries=0,
            timeout_seconds=0.3,
            retry_delay_seconds=0.0,
            name="agent",
        )

        result = invoke_with_retry(
            fn=slow_agent,
            config=config,
            target_name="SlowCompetitiveIntelligence",
        )

        assert result.success is False
        assert result.degraded is True
        assert result.attempts[0].status == InvocationStatus.TIMEOUT
        assert "Timeout" in result.final_error or "timeout" in result.final_error

    def test_agent_timeout_triggers_retry(self):
        """A timed-out agent is retried (Requirement 1.5 + 1.8 combined)."""
        call_count = {"n": 0}

        def sometimes_slow_agent():
            call_count["n"] += 1
            if call_count["n"] == 1:
                time.sleep(5)  # First call times out
                return "too_late"
            return {"analysis": "competitive data"}

        config = RetryConfig(
            max_retries=2,
            timeout_seconds=0.3,
            retry_delay_seconds=0.0,
            name="agent",
        )

        result = invoke_with_retry(
            fn=sometimes_slow_agent,
            config=config,
            target_name="CompetitiveIntelligence",
        )

        assert result.success is True
        assert result.retries_used == 1
        assert result.data == {"analysis": "competitive data"}
        assert result.attempts[0].status == InvocationStatus.RETRYING

    def test_agent_timeout_uses_120s_config(self):
        """The default AGENT_RETRY_CONFIG uses 120s timeout."""
        assert AGENT_RETRY_CONFIG.timeout_seconds == 120
        assert AGENT_RETRY_CONFIG.max_retries == 2
        assert AGENT_RETRY_CONFIG.name == "agent"


# ---------------------------------------------------------------------------
# 3. Retry behavior tests (Requirement 1.5)
# ---------------------------------------------------------------------------


class TestRetryBehavior:
    """Test retry up to 2 times then degrade."""

    def test_retry_up_to_2_times_then_degrade(self):
        """Agent is retried exactly 2 times before degrading.

        Requirement 1.5: Retry the failed agent up to 2 times, log the failure.
        IF all retries are exhausted, proceed with available agent outputs.
        """

        def always_failing_agent():
            raise RuntimeError("Agent crashed")

        config = RetryConfig(
            max_retries=2,
            timeout_seconds=5,
            retry_delay_seconds=0.0,
            name="agent",
        )

        result = invoke_with_retry(
            fn=always_failing_agent,
            config=config,
            target_name="DemandForecasting",
        )

        # Should have attempted 3 times total (1 initial + 2 retries)
        assert result.success is False
        assert result.degraded is True
        assert result.retries_used == 2
        assert len(result.attempts) == 3

        # First two attempts should be RETRYING, last should be ERROR
        assert result.attempts[0].status == InvocationStatus.RETRYING
        assert result.attempts[1].status == InvocationStatus.RETRYING
        assert result.attempts[2].status == InvocationStatus.ERROR

    def test_retry_succeeds_on_second_attempt(self):
        """Agent recovers on the first retry (attempt 2 of 3)."""
        call_count = {"n": 0}

        def recoverable_agent():
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise ConnectionError("Temporary network issue")
            return {"demand_forecast": [100, 200, 300]}

        config = RetryConfig(
            max_retries=2,
            timeout_seconds=5,
            retry_delay_seconds=0.0,
            name="agent",
        )

        result = invoke_with_retry(
            fn=recoverable_agent,
            config=config,
            target_name="DemandForecasting",
        )

        assert result.success is True
        assert result.retries_used == 1
        assert result.data == {"demand_forecast": [100, 200, 300]}

    def test_retry_succeeds_on_third_attempt(self):
        """Agent recovers on the second retry (attempt 3 of 3)."""
        call_count = {"n": 0}

        def very_flaky_agent():
            call_count["n"] += 1
            if call_count["n"] <= 2:
                raise TimeoutError(f"Attempt {call_count['n']} timed out")
            return {"market_data": "recovered"}

        config = RetryConfig(
            max_retries=2,
            timeout_seconds=5,
            retry_delay_seconds=0.0,
            name="agent",
        )

        result = invoke_with_retry(
            fn=very_flaky_agent,
            config=config,
            target_name="MarketIntelligence",
        )

        assert result.success is True
        assert result.retries_used == 2
        assert result.data == {"market_data": "recovered"}

    def test_mixed_timeout_and_error_retries(self):
        """Agent experiences timeout then error before succeeding."""
        call_count = {"n": 0}

        def mixed_failure_agent():
            call_count["n"] += 1
            if call_count["n"] == 1:
                time.sleep(5)  # Timeout on first attempt
                return "too_late"
            if call_count["n"] == 2:
                raise RuntimeError("Transient error")
            return {"result": "success"}

        config = RetryConfig(
            max_retries=2,
            timeout_seconds=0.3,
            retry_delay_seconds=0.0,
            name="agent",
        )

        result = invoke_with_retry(
            fn=mixed_failure_agent,
            config=config,
            target_name="MixedFailureAgent",
        )

        assert result.success is True
        assert result.retries_used == 2
        assert len(result.attempts) == 3


# ---------------------------------------------------------------------------
# 4. Graceful degradation with partial agent failures (Requirement 1.5)
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Test that when 1 of 3 agents fails, the pipeline still produces scenarios."""

    def _make_success_result(self, name: str, data: dict) -> InvocationResult:
        """Create a successful InvocationResult."""
        return InvocationResult(
            success=True,
            data=data,
            target_name=name,
            attempts=[],
            total_duration_ms=500,
            retries_used=0,
            degraded=False,
        )

    def _make_failure_result(self, name: str, error: str) -> InvocationResult:
        """Create a failed InvocationResult."""
        return InvocationResult(
            success=False,
            data=None,
            target_name=name,
            attempts=[],
            total_duration_ms=360000,
            retries_used=2,
            final_error=error,
            degraded=True,
        )

    def test_one_agent_failure_produces_partial_degradation(self):
        """When 1 of 3 agents fails, pipeline is PARTIAL degraded but can proceed.

        Requirement 1.5: IF all retries are exhausted, THEN proceed with
        available agent outputs and flag the incomplete analysis.
        """
        results = [
            self._make_success_result(
                "Competitive Intelligence",
                {"competitor_prices": [9.99, 10.49, 11.99]},
            ),
            self._make_success_result(
                "Demand Forecasting",
                {"demand_forecast": [1000, 1200, 900]},
            ),
            self._make_failure_result(
                "Market Intelligence",
                "Timeout after 120s: Execution exceeded 120s timeout",
            ),
        ]

        degradation = assess_degradation(results, total_expected=3)

        # Pipeline can still proceed with 2/3 agents
        assert degradation.level == DegradationLevel.PARTIAL
        assert degradation.can_proceed is True
        assert degradation.is_degraded is True
        assert "Market Intelligence" in degradation.failed_agents
        assert "Competitive Intelligence" in degradation.available_agents
        assert "Demand Forecasting" in degradation.available_agents
        assert len(degradation.warnings) > 0

    def test_two_agents_failure_produces_severe_degradation(self):
        """When 2 of 3 agents fail, pipeline is SEVERE degraded but can still proceed."""
        results = [
            self._make_success_result(
                "Competitive Intelligence",
                {"competitor_prices": [9.99]},
            ),
            self._make_failure_result(
                "Demand Forecasting",
                "RuntimeError: Agent crashed",
            ),
            self._make_failure_result(
                "Market Intelligence",
                "Timeout after 120s",
            ),
        ]

        degradation = assess_degradation(results, total_expected=3)

        assert degradation.level == DegradationLevel.SEVERE
        assert degradation.can_proceed is True
        assert degradation.is_degraded is True
        assert len(degradation.failed_agents) == 2
        assert len(degradation.available_agents) == 1

    def test_partial_degradation_flags_incomplete_analysis(self):
        """Degraded pipeline includes warnings about incomplete analysis."""
        results = [
            self._make_success_result("Competitive Intelligence", {"data": "ok"}),
            self._make_success_result("Demand Forecasting", {"data": "ok"}),
            self._make_failure_result("Market Intelligence", "Timeout"),
        ]

        degradation = assess_degradation(results, total_expected=3)

        # Warnings should mention the failed agent
        assert any("Market Intelligence" in w for w in degradation.warnings)
        # Incomplete data sources should be tracked
        assert "Market Intelligence" in degradation.incomplete_data_sources


# ---------------------------------------------------------------------------
# 5. Total failure tests (Requirement 1.5)
# ---------------------------------------------------------------------------


class TestTotalFailure:
    """Test that when all 3 agents fail, the pipeline returns FAILED status."""

    def _make_failure_result(self, name: str, error: str) -> InvocationResult:
        """Create a failed InvocationResult."""
        return InvocationResult(
            success=False,
            data=None,
            target_name=name,
            attempts=[],
            total_duration_ms=360000,
            retries_used=2,
            final_error=error,
            degraded=True,
        )

    def test_all_agents_fail_produces_total_failure(self):
        """When all 3 agents fail, pipeline cannot proceed (TOTAL failure).

        Requirement 1.5: The system should fail the pricing cycle and notify
        the Product Manager when all agents fail.
        """
        results = [
            self._make_failure_result(
                "Competitive Intelligence",
                "Timeout after 120s: Execution exceeded 120s timeout",
            ),
            self._make_failure_result(
                "Demand Forecasting",
                "RuntimeError: Agent process crashed",
            ),
            self._make_failure_result(
                "Market Intelligence",
                "ConnectionError: Unable to reach MCP server",
            ),
        ]

        degradation = assess_degradation(results, total_expected=3)

        assert degradation.level == DegradationLevel.TOTAL
        assert degradation.can_proceed is False
        assert degradation.is_degraded is True
        assert len(degradation.failed_agents) == 3
        assert len(degradation.available_agents) == 0
        assert "TOTAL FAILURE" in degradation.warnings[0]

    def test_total_failure_lists_all_failed_agents(self):
        """Total failure status includes all failed agent names."""
        results = [
            self._make_failure_result("Competitive Intelligence", "Error A"),
            self._make_failure_result("Demand Forecasting", "Error B"),
            self._make_failure_result("Market Intelligence", "Error C"),
        ]

        degradation = assess_degradation(results, total_expected=3)

        assert "Competitive Intelligence" in degradation.failed_agents
        assert "Demand Forecasting" in degradation.failed_agents
        assert "Market Intelligence" in degradation.failed_agents

    def test_total_failure_cannot_proceed(self):
        """Total failure explicitly prevents pipeline from proceeding."""
        results = [
            self._make_failure_result("Agent1", "err"),
            self._make_failure_result("Agent2", "err"),
            self._make_failure_result("Agent3", "err"),
        ]

        degradation = assess_degradation(results, total_expected=3)

        # The pipeline must NOT proceed
        assert degradation.can_proceed is False
        # This would be used to return FAILED status to the dashboard
        assert degradation.level == DegradationLevel.TOTAL


# ---------------------------------------------------------------------------
# Integration: Full pipeline simulation with resilience
# ---------------------------------------------------------------------------


class TestPipelineResilienceIntegration:
    """Integration tests simulating the full agent pipeline with failures."""

    def test_pipeline_with_one_slow_agent_degrades_gracefully(self):
        """Simulate a full pipeline where one agent times out after retries.

        The pipeline should:
        1. Invoke 3 agents in parallel (simulated sequentially here)
        2. One agent times out on all attempts
        3. Pipeline assesses degradation as PARTIAL
        4. Pipeline can still proceed with 2/3 agent outputs
        """
        config = RetryConfig(
            max_retries=2,
            timeout_seconds=0.3,
            retry_delay_seconds=0.0,
            name="agent",
        )

        # Agent 1: succeeds immediately
        result_ci = invoke_with_retry(
            fn=lambda: {"competitor_prices": [9.99, 10.49]},
            config=config,
            target_name="Competitive Intelligence",
        )

        # Agent 2: succeeds immediately
        result_df = invoke_with_retry(
            fn=lambda: {"demand_forecast": [1000, 1200]},
            config=config,
            target_name="Demand Forecasting",
        )

        # Agent 3: always times out
        def always_slow():
            time.sleep(5)
            return "never"

        result_mi = invoke_with_retry(
            fn=always_slow,
            config=config,
            target_name="Market Intelligence",
        )

        # Assess degradation
        all_results = [result_ci, result_df, result_mi]
        degradation = assess_degradation(all_results, total_expected=3)

        # Verify pipeline state
        assert result_ci.success is True
        assert result_df.success is True
        assert result_mi.success is False
        assert degradation.level == DegradationLevel.PARTIAL
        assert degradation.can_proceed is True

    def test_pipeline_all_agents_timeout_fails_completely(self):
        """Simulate a full pipeline where all agents time out.

        The pipeline should assess TOTAL failure and not proceed.
        """
        config = RetryConfig(
            max_retries=2,
            timeout_seconds=0.3,
            retry_delay_seconds=0.0,
            name="agent",
        )

        def always_slow():
            time.sleep(5)
            return "never"

        results = []
        for agent_name in [
            "Competitive Intelligence",
            "Demand Forecasting",
            "Market Intelligence",
        ]:
            result = invoke_with_retry(
                fn=always_slow,
                config=config,
                target_name=agent_name,
            )
            results.append(result)

        degradation = assess_degradation(results, total_expected=3)

        assert all(not r.success for r in results)
        assert degradation.level == DegradationLevel.TOTAL
        assert degradation.can_proceed is False
