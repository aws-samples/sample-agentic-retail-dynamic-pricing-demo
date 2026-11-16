"""Pricing cycle call chain: payload contract, timeouts and retry ownership.

rdp-api-pricing-cycles -> orchestrator runtime -> specialist runtimes. Before
this fix the cycle parameters were ignored (nested in "prompt"), every boto3
client kept botocore's 60 s read timeout and SDK retries, and a slow successful
specialist response was discarded and re-run.
"""

from __future__ import annotations

import importlib
import io
import json
import logging
import sys

import pytest
from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError

ARN_PREFIX = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/"
SPECIALIST_ENV = {
    "COMPETITIVE_INTELLIGENCE_AGENT_ARN": ARN_PREFIX + "ci-AAAAAAAAAA",
    "DEMAND_FORECASTING_AGENT_ARN": ARN_PREFIX + "df-AAAAAAAAAA",
    "MARKET_INTELLIGENCE_AGENT_ARN": ARN_PREFIX + "mi-AAAAAAAAAA",
    "STRATEGY_SYNTHESIS_AGENT_ARN": ARN_PREFIX + "ss-AAAAAAAAAA",
    "IMPLEMENTATION_MONITORING_AGENT_ARN": ARN_PREFIX + "im-AAAAAAAAAA",
}
ORCHESTRATOR_ARN = ARN_PREFIX + "orch-AAAAAAAAAA"
SYNC_INVOKE_LIMIT_SECONDS = 15 * 60  # synchronous InvokeAgentRuntime limit
LAMBDA_MAX_TIMEOUT_SECONDS = 900


@pytest.fixture
def orchestrator(monkeypatch):
    for name, value in SPECIALIST_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    sys.modules.pop("backend.agents.agentcore.orchestrator_runtime", None)
    module = importlib.import_module("backend.agents.agentcore.orchestrator_runtime")
    cached_client_factory = module._get_agentcore_client  # tests may monkeypatch it
    monkeypatch.setattr(module.time, "sleep", lambda _s: None)
    monkeypatch.setattr(module, "create_session_manager", lambda **_kw: None)
    yield module
    cached_client_factory.cache_clear()
    sys.modules.pop("backend.agents.agentcore.orchestrator_runtime", None)


@pytest.fixture
def pricing_cycles(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_AGENT_ARN", ORCHESTRATOR_ARN)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    sys.modules.pop("backend.api_handlers.pricing_cycles", None)
    yield importlib.import_module("backend.api_handlers.pricing_cycles")
    sys.modules.pop("backend.api_handlers.pricing_cycles", None)


def client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "InvokeAgentRuntime")


class FakeAgentCoreClient:
    """Records invoke_agent_runtime calls; replies from a queue of results or exceptions."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def invoke_agent_runtime(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return {"response": io.BytesIO(json.dumps(reply).encode())}


# ---------------------------------------------------------------------------
# Payload contract
# ---------------------------------------------------------------------------


class TestCycleRequestParsing:
    REQUEST = {"pricing_group": "Electronics", "objectives": ["margin_protection"], "constraints": {"min_margin": 0.2}}

    def test_top_level_fields_are_read(self, orchestrator):
        parsed = orchestrator._parse_cycle_request(self.REQUEST)

        assert parsed["pricing_group"] == "Electronics"
        assert parsed["objectives"] == ["margin_protection"]
        assert parsed["constraints"] == {"min_margin": 0.2}

    def test_legacy_prompt_json_is_still_accepted(self, orchestrator):
        """The Lambda deployed before this fix nests the fields in a JSON 'prompt' string."""
        parsed = orchestrator._parse_cycle_request({"prompt": json.dumps(self.REQUEST)})

        assert parsed["pricing_group"] == "Electronics"
        assert parsed["objectives"] == ["margin_protection"]
        assert parsed["constraints"] == {"min_margin": 0.2}

    def test_top_level_fields_win_over_prompt(self, orchestrator):
        payload = {**self.REQUEST, "prompt": json.dumps({"pricing_group": "Toys"})}

        assert orchestrator._parse_cycle_request(payload)["pricing_group"] == "Electronics"

    def test_missing_group_falls_back_to_default_and_warns(self, orchestrator, caplog):
        with caplog.at_level(logging.WARNING, logger=orchestrator.logger.name):
            parsed = orchestrator._parse_cycle_request({"prompt": "not json"})

        assert parsed["pricing_group"] == "default_category"
        assert parsed["objectives"] == ["balanced"]
        assert any("no pricing_group" in r.getMessage() for r in caplog.records)

    @pytest.mark.parametrize(
        "payload",
        [
            {"pricing_group": 42},
            {"pricing_group": ""},
            {"pricing_group": "Electronics", "objectives": "balanced"},
            {"pricing_group": "Electronics", "objectives": [1]},
            {"pricing_group": "Electronics", "constraints": ["min_margin"]},
            {"pricing_group": "Electronics", "product_costs": {}},
            {"pricing_group": "Electronics", "session_id": 7},
        ],
    )
    def test_wrong_types_are_rejected(self, orchestrator, payload):
        with pytest.raises(ValueError):
            orchestrator._parse_cycle_request(payload)

    def test_invoke_reports_failed_for_an_invalid_request(self, orchestrator):
        result = orchestrator.invoke({"pricing_group": "Electronics", "objectives": "balanced"})

        assert result["status"] == "FAILED"
        assert "objectives" in result["error"]

    def test_lambda_sends_the_fields_at_the_top_level(self, pricing_cycles, monkeypatch):
        fake = FakeAgentCoreClient([{"status": "COMPLETE"}])
        monkeypatch.setattr(pricing_cycles, "_get_orchestrator_client", lambda: fake)

        pricing_cycles._invoke_orchestrator(
            pricing_group="Electronics",
            objectives=["margin_protection"],
            constraints={"min_margin": 0.2},
            session_id="cycle-1234",
        )

        (call,) = fake.calls
        assert call["agentRuntimeArn"] == ORCHESTRATOR_ARN
        assert json.loads(call["payload"]) == self.REQUEST

    def test_lambda_payload_round_trips_through_the_orchestrator(self, pricing_cycles, orchestrator, monkeypatch):
        fake = FakeAgentCoreClient([{"status": "COMPLETE"}])
        monkeypatch.setattr(pricing_cycles, "_get_orchestrator_client", lambda: fake)
        pricing_cycles._invoke_orchestrator("Electronics", ["margin_protection"], {}, session_id=None)

        parsed = orchestrator._parse_cycle_request(json.loads(fake.calls[0]["payload"]))

        assert parsed["pricing_group"] == "Electronics"
        assert parsed["objectives"] == ["margin_protection"]


class TestCycleUsesRequestedParameters:
    def test_specialists_are_asked_about_the_requested_group(self, orchestrator, monkeypatch):
        prompts = {}

        def fake_invoke(agent_arn, prompt, session_id, timeout_seconds=0):
            prompts[agent_arn] = (prompt, timeout_seconds)
            if agent_arn == orchestrator.SS_ARN:
                return {"ranked_scenarios": [{"rank": 1}]}
            return {"analysis": "ok"}

        monkeypatch.setattr(orchestrator, "_invoke_agent_runtime", fake_invoke)

        # Old Lambda payload shape, still in flight during a rolling deploy.
        result = orchestrator.invoke({"prompt": json.dumps({"pricing_group": "Electronics", "objectives": ["margin_protection"]})})

        assert result["status"] == "COMPLETE"
        assert result["metadata"]["pricing_group"] == "Electronics"
        for arn in (orchestrator.CI_ARN, orchestrator.DF_ARN, orchestrator.MI_ARN):
            prompt, timeout = prompts[arn]
            assert "'Electronics'" in prompt and "margin_protection" in prompt
            assert timeout == orchestrator.SPECIALIST_TIMEOUT_SECONDS
        synthesis_prompt, synthesis_timeout = prompts[orchestrator.SS_ARN]
        assert json.loads(synthesis_prompt)["objectives"] == ["margin_protection"]
        assert synthesis_timeout == orchestrator.SYNTHESIS_TIMEOUT_SECONDS

    def test_synthesis_failure_fails_the_cycle(self, orchestrator, monkeypatch):
        def fake_invoke(agent_arn, prompt, session_id, timeout_seconds=0):
            if agent_arn == orchestrator.SS_ARN:
                raise ReadTimeoutError(endpoint_url="https://example.invalid")
            return {"analysis": "ok"}

        monkeypatch.setattr(orchestrator, "_invoke_agent_runtime", fake_invoke)

        result = orchestrator.invoke({"pricing_group": "Electronics"})

        assert result["status"] == "FAILED"
        assert "Strategy Synthesis" in result["degraded_agents"]


# ---------------------------------------------------------------------------
# Retry ownership
# ---------------------------------------------------------------------------


class TestSpecialistRetries:
    def run(self, orchestrator, monkeypatch, replies):
        fake = FakeAgentCoreClient(replies)
        monkeypatch.setattr(orchestrator, "_get_agentcore_client", lambda _timeout: fake)
        result = orchestrator._invoke_with_retry(
            agent_arn=orchestrator.DF_ARN, prompt="p", agent_name="Demand Forecasting", session_id=None
        )
        return result, fake

    def test_read_timeout_is_not_retried(self, orchestrator, monkeypatch):
        """The agent probably ran; a retry would run (and bill) it again."""
        result, fake = self.run(orchestrator, monkeypatch, [ReadTimeoutError(endpoint_url="https://x.invalid")])

        assert result["success"] is False
        assert len(fake.calls) == 1

    @pytest.mark.parametrize("code", ["ThrottlingException", "ServiceUnavailableException", "InternalServerException"])
    def test_fast_retryable_errors_are_retried(self, orchestrator, monkeypatch, code):
        result, fake = self.run(orchestrator, monkeypatch, [client_error(code), {"analysis": "ok"}])

        assert result["success"] is True
        assert result["data"] == {"analysis": "ok"}
        assert result["retries_used"] == 1
        assert len(fake.calls) == 2
        # Same runtime session for the retry.
        assert fake.calls[0]["runtimeSessionId"] == fake.calls[1]["runtimeSessionId"]

    def test_connect_timeout_is_retried(self, orchestrator, monkeypatch):
        result, fake = self.run(
            orchestrator, monkeypatch, [ConnectTimeoutError(endpoint_url="https://x.invalid"), {"analysis": "ok"}]
        )

        assert result["success"] is True
        assert len(fake.calls) == 2

    @pytest.mark.parametrize("code", ["ValidationException", "AccessDeniedException", "RuntimeClientError"])
    def test_non_retryable_errors_are_not_retried(self, orchestrator, monkeypatch, code):
        result, fake = self.run(orchestrator, monkeypatch, [client_error(code)])

        assert result["success"] is False
        assert len(fake.calls) == 1

    def test_slow_retryable_failure_is_not_retried(self, orchestrator, monkeypatch):
        monkeypatch.setattr(orchestrator, "FAST_FAILURE_SECONDS", 0)

        result, fake = self.run(orchestrator, monkeypatch, [client_error("InternalServerException")])

        assert result["success"] is False
        assert len(fake.calls) == 1

    def test_retries_stop_after_max_retries(self, orchestrator, monkeypatch):
        replies = [client_error("ThrottlingException")] * (orchestrator.MAX_RETRIES + 1)

        result, fake = self.run(orchestrator, monkeypatch, replies)

        assert result["success"] is False
        assert len(fake.calls) == orchestrator.MAX_RETRIES + 1

    def test_slow_successful_response_is_kept(self, orchestrator, monkeypatch):
        """The old code discarded any result that arrived after 120 s and re-ran the agent."""
        clock = iter([0.0, 0.0, 250.0, 250.0, 250.0])
        monkeypatch.setattr(orchestrator.time, "time", lambda: next(clock, 250.0))

        result, fake = self.run(orchestrator, monkeypatch, [{"analysis": "slow but fine"}])

        assert result["success"] is True
        assert result["data"] == {"analysis": "slow but fine"}
        assert len(fake.calls) == 1


# ---------------------------------------------------------------------------
# Client configuration and the timeout chain
# ---------------------------------------------------------------------------


def assert_no_sdk_retries(client):
    assert client.meta.config.retries["total_max_attempts"] == 1


class TestClientConfiguration:
    def test_orchestrator_clients_use_the_call_timeout_and_no_sdk_retries(self, orchestrator):
        orchestrator._get_agentcore_client.cache_clear()
        specialist = orchestrator._get_agentcore_client(orchestrator.SPECIALIST_TIMEOUT_SECONDS)
        synthesis = orchestrator._get_agentcore_client(orchestrator.SYNTHESIS_TIMEOUT_SECONDS)

        assert specialist.meta.config.read_timeout == orchestrator.SPECIALIST_TIMEOUT_SECONDS
        assert synthesis.meta.config.read_timeout == orchestrator.SYNTHESIS_TIMEOUT_SECONDS
        assert_no_sdk_retries(specialist)
        assert_no_sdk_retries(synthesis)
        assert orchestrator._get_agentcore_client(orchestrator.SPECIALIST_TIMEOUT_SECONDS) is specialist

    def test_lambda_orchestrator_client_uses_its_read_timeout_and_no_sdk_retries(self, pricing_cycles):
        client = pricing_cycles._get_orchestrator_client()

        assert client.meta.config.read_timeout == pricing_cycles.ORCHESTRATOR_READ_TIMEOUT_SECONDS
        assert_no_sdk_retries(client)


class TestTimeoutChain:
    def test_specialist_timeout_covers_the_slowest_measured_run(self, orchestrator):
        # Sandbox runs: Demand Forecasting took up to 240 s, Strategy Synthesis up to 83 s.
        assert orchestrator.SPECIALIST_TIMEOUT_SECONDS > 240
        assert orchestrator.SYNTHESIS_TIMEOUT_SECONDS > 83

    def test_each_layer_waits_longer_than_the_one_below(self, orchestrator, pricing_cycles):
        from shared.cycle_timeouts import DEFAULT

        assert orchestrator.ORCHESTRATOR_WORST_CASE_SECONDS < pricing_cycles.ORCHESTRATOR_READ_TIMEOUT_SECONDS
        assert pricing_cycles.ORCHESTRATOR_READ_TIMEOUT_SECONDS < SYNC_INVOKE_LIMIT_SECONDS
        assert pricing_cycles.ORCHESTRATOR_READ_TIMEOUT_SECONDS < DEFAULT.lambda_timeout
        assert DEFAULT.lambda_timeout <= LAMBDA_MAX_TIMEOUT_SECONDS

    def test_lambda_defaults_match_the_derived_defaults(self, pricing_cycles):
        """The Lambda's fallbacks (used if CDK did not set the env vars) must equal the derived defaults."""
        from shared.cycle_timeouts import DEFAULT

        assert pricing_cycles.ORCHESTRATOR_READ_TIMEOUT_SECONDS == DEFAULT.lambda_read_timeout
        assert pricing_cycles.STALE_CYCLE_SECONDS == DEFAULT.stale_cycle_seconds

    def test_worst_case_counts_both_phases_and_their_retries(self, orchestrator):
        assert orchestrator.ORCHESTRATOR_WORST_CASE_SECONDS >= (
            orchestrator.SPECIALIST_TIMEOUT_SECONDS
            + orchestrator.SYNTHESIS_TIMEOUT_SECONDS
            + 2 * orchestrator.MAX_RETRIES * orchestrator.FAST_FAILURE_SECONDS
        )


class TestLambdaDoesNotRetryCycles:
    def test_pricing_cycles_function_has_no_async_retries(self):
        import aws_cdk as cdk
        from aws_cdk.assertions import Match, Template
        from shared.cycle_timeouts import DEFAULT
        from stacks.pricing_stack import RetailDynamicPricingStack

        PRICING_CYCLES_TIMEOUT_SECONDS = DEFAULT.lambda_timeout
        template = Template.from_stack(RetailDynamicPricingStack(cdk.App(), "TimeoutTestStack"))

        functions = template.find_resources(
            "AWS::Lambda::Function", {"Properties": {"FunctionName": "rdp-api-pricing-cycles"}}
        )
        (logical_id,) = functions
        assert functions[logical_id]["Properties"]["Timeout"] == PRICING_CYCLES_TIMEOUT_SECONDS
        template.has_resource_properties(
            "AWS::Lambda::EventInvokeConfig",
            {"FunctionName": {"Ref": logical_id}, "MaximumRetryAttempts": 0, "Qualifier": Match.any_value()},
        )
