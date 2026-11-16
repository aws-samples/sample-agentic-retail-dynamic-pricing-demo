"""Configurable pricing-cycle timeouts (shared/cycle_timeouts.py).

Two settings (specialist and synthesis read timeouts); everything else is derived
and must keep each layer waiting longer than the one below it. The values flow
through deploy.sh -> deploy_agentcore.py (orchestrator env) and CDK (Lambda env and
timeout), and verify_deployment.py checks the two deployed halves agree.
"""

from __future__ import annotations

import importlib
import itertools
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from shared import cycle_timeouts as ct
from shared.cycle_timeouts import CycleTimeouts, InvalidTimeouts

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYNC_INVOKE_LIMIT_SECONDS = 15 * 60


def assert_chain(t: CycleTimeouts) -> None:
    assert t.orchestrator_worst_case >= t.specialist + t.synthesis + 2 * ct.MAX_RETRIES * ct.FAST_FAILURE_SECONDS
    assert t.orchestrator_worst_case < t.lambda_read_timeout
    assert t.lambda_read_timeout < t.lambda_timeout <= ct.LAMBDA_MAX_TIMEOUT_SECONDS
    assert t.lambda_read_timeout < SYNC_INVOKE_LIMIT_SECONDS
    assert t.stale_cycle_seconds > t.lambda_timeout


# ---------------------------------------------------------------------------
# Derivation and validation
# ---------------------------------------------------------------------------


class TestDerivation:
    def test_defaults_reproduce_the_values_measured_and_deployed(self):
        t = ct.DEFAULT
        assert (t.specialist, t.synthesis) == (300, 180)
        assert (t.orchestrator_worst_case, t.lambda_read_timeout, t.lambda_timeout, t.stale_cycle_seconds) == (
            546, 660, 720, 900)

    @pytest.mark.parametrize(
        "specialist,synthesis",
        [(s, y) for s, y in itertools.product(range(30, 700, 37), range(30, 700, 41)) if s + y <= 714]
        + [(684, 30), (30, 684), (534, 180)],
    )
    def test_every_valid_setting_keeps_the_chain(self, specialist, synthesis):
        assert_chain(CycleTimeouts(specialist, synthesis))

    def test_max_sum_is_the_exact_boundary(self):
        limit = ct.max_agent_seconds_total()
        assert CycleTimeouts(limit - 180, 180).lambda_timeout <= ct.LAMBDA_MAX_TIMEOUT_SECONDS
        with pytest.raises(InvalidTimeouts, match="Keep the sum at or below"):
            CycleTimeouts(limit - 180 + 1, 180)

    @pytest.mark.parametrize("value", [0, 29, -5])
    def test_too_short_is_rejected(self, value):
        with pytest.raises(InvalidTimeouts, match="at least"):
            CycleTimeouts(value, 180)

    @pytest.mark.parametrize("value", [300.5, "300", True, None])
    def test_non_integers_are_rejected(self, value):
        with pytest.raises(InvalidTimeouts):
            CycleTimeouts(300, value)

    def test_minimum_exceeds_the_fast_failure_window(self):
        """A call that times out must never count as a fast, retryable failure."""
        assert ct.MIN_AGENT_TIMEOUT_SECONDS > ct.FAST_FAILURE_SECONDS


class TestResolve:
    def test_explicit_values_win_over_the_environment(self):
        env = {ct.SPECIALIST_ENV: "400", ct.SYNTHESIS_ENV: "200"}
        assert ct.resolve("350", 150, environ=env) == CycleTimeouts(350, 150)

    def test_environment_is_used_when_no_value_is_given(self):
        env = {ct.SPECIALIST_ENV: "400", ct.SYNTHESIS_ENV: " 200 "}
        assert ct.resolve(environ=env) == CycleTimeouts(400, 200)

    @pytest.mark.parametrize("empty", [None, "", "  "])
    def test_empty_means_default(self, empty):
        env = {ct.SPECIALIST_ENV: empty} if empty is not None else {}
        assert ct.resolve(environ=env) == ct.DEFAULT

    @pytest.mark.parametrize("bad", ["abc", "3e2", "-300", "300s", "1.5"])
    def test_malformed_values_are_rejected(self, bad):
        with pytest.raises(InvalidTimeouts, match="whole number"):
            ct.resolve(environ={ct.SPECIALIST_ENV: bad})

    def test_env_dicts_for_both_halves(self):
        t = CycleTimeouts(360, 180)
        assert t.agent_environment() == {ct.SPECIALIST_ENV: "360", ct.SYNTHESIS_ENV: "180"}
        assert t.lambda_environment() == {"ORCHESTRATOR_READ_TIMEOUT_SECONDS": "720", "STALE_CYCLE_SECONDS": "960"}


class TestCli:
    def run(self, *args, env=None):
        return subprocess.run([sys.executable, "-m", "shared.cycle_timeouts", *args], cwd=PROJECT_ROOT,
                              capture_output=True, text=True, timeout=60,
                              env={"PATH": "/usr/bin:/bin", **(env or {})})

    def test_valid_values_print_the_chain(self):
        result = self.run("--specialist", "360")
        assert result.returncode == 0
        assert "Lambda timeout 780 s" in result.stdout

    def test_environment_is_read(self):
        result = self.run(env={ct.SPECIALIST_ENV: "360"})
        assert result.returncode == 0 and "specialist 360 s" in result.stdout

    @pytest.mark.parametrize("args", [("--specialist", "abc"), ("--specialist", "600", "--synthesis", "200")])
    def test_invalid_values_exit_1(self, args):
        result = self.run(*args)
        assert result.returncode == 1
        assert "invalid pricing-cycle timeouts" in result.stderr


# ---------------------------------------------------------------------------
# Where the values are used
# ---------------------------------------------------------------------------

ARN = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/x-AAAAAAAAAA"
SPECIALIST_ARN_VARS = (
    "COMPETITIVE_INTELLIGENCE_AGENT_ARN", "DEMAND_FORECASTING_AGENT_ARN", "MARKET_INTELLIGENCE_AGENT_ARN",
    "STRATEGY_SYNTHESIS_AGENT_ARN", "IMPLEMENTATION_MONITORING_AGENT_ARN",
)


def fresh(module, monkeypatch, env):
    for name, value in env.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    sys.modules.pop(module, None)
    try:
        return importlib.import_module(module)
    finally:
        sys.modules.pop(module, None)


class TestOrchestratorReadsTheSettings:
    MODULE = "backend.agents.agentcore.orchestrator_runtime"

    def env(self, **timeouts):
        return {**{v: ARN for v in SPECIALIST_ARN_VARS}, ct.SPECIALIST_ENV: None, ct.SYNTHESIS_ENV: None, **timeouts}

    def test_defaults_without_env(self, monkeypatch):
        orch = fresh(self.MODULE, monkeypatch, self.env())
        assert (orch.SPECIALIST_TIMEOUT_SECONDS, orch.SYNTHESIS_TIMEOUT_SECONDS) == (300, 180)
        assert orch.ORCHESTRATOR_WORST_CASE_SECONDS == 546

    def test_env_values_are_used(self, monkeypatch):
        orch = fresh(self.MODULE, monkeypatch, self.env(**{ct.SPECIALIST_ENV: "360", ct.SYNTHESIS_ENV: "120"}))
        assert (orch.SPECIALIST_TIMEOUT_SECONDS, orch.SYNTHESIS_TIMEOUT_SECONDS) == (360, 120)
        assert orch.ORCHESTRATOR_WORST_CASE_SECONDS == CycleTimeouts(360, 120).orchestrator_worst_case

    def test_invalid_env_fails_the_import(self, monkeypatch):
        with pytest.raises(InvalidTimeouts):
            fresh(self.MODULE, monkeypatch, self.env(**{ct.SPECIALIST_ENV: "9999"}))


class TestLambdaReadsTheDerivedValues:
    MODULE = "backend.api_handlers.pricing_cycles"

    def test_env_values_are_used(self, monkeypatch):
        t = CycleTimeouts(360, 180)
        pc = fresh(self.MODULE, monkeypatch, {"ORCHESTRATOR_AGENT_ARN": ARN, **t.lambda_environment()})
        assert pc.ORCHESTRATOR_READ_TIMEOUT_SECONDS == t.lambda_read_timeout
        assert pc.STALE_CYCLE_SECONDS == t.stale_cycle_seconds
        assert pc._get_orchestrator_client().meta.config.read_timeout == t.lambda_read_timeout


class TestCdkUsesTheSettings:
    def function(self, context=None):
        import aws_cdk as cdk
        from aws_cdk.assertions import Template
        from stacks.pricing_stack import RetailDynamicPricingStack

        stack = RetailDynamicPricingStack(cdk.App(context=context or {}), "TimeoutsConfigStack")
        (fn,) = Template.from_stack(stack).find_resources(
            "AWS::Lambda::Function", {"Properties": {"FunctionName": "rdp-api-pricing-cycles"}}).values()
        return fn["Properties"]

    def assert_matches(self, props, t: CycleTimeouts):
        assert props["Timeout"] == t.lambda_timeout
        env = props["Environment"]["Variables"]
        for key, value in t.lambda_environment().items():
            assert env[key] == value

    def test_defaults(self, monkeypatch):
        monkeypatch.delenv(ct.SPECIALIST_ENV, raising=False)
        monkeypatch.delenv(ct.SYNTHESIS_ENV, raising=False)
        self.assert_matches(self.function(), ct.DEFAULT)

    def test_context_values(self, monkeypatch):
        monkeypatch.delenv(ct.SPECIALIST_ENV, raising=False)
        props = self.function({"specialistTimeoutSeconds": "360", "synthesisTimeoutSeconds": 200})
        self.assert_matches(props, CycleTimeouts(360, 200))

    def test_env_values_when_no_context(self, monkeypatch):
        monkeypatch.setenv(ct.SPECIALIST_ENV, "420")
        monkeypatch.delenv(ct.SYNTHESIS_ENV, raising=False)
        self.assert_matches(self.function(), CycleTimeouts(420, 180))

    def test_invalid_values_fail_synth(self, monkeypatch):
        monkeypatch.delenv(ct.SPECIALIST_ENV, raising=False)
        with pytest.raises(InvalidTimeouts):
            self.function({"specialistTimeoutSeconds": "800"})


class TestDeployAgentcoreSetsTheSettings:
    @pytest.fixture
    def deploy(self):
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        import deploy_agentcore

        return deploy_agentcore

    def run_main(self, deploy, monkeypatch, timeouts_env):
        from tests.test_agentcore_wiring import ACCOUNT, MEMORY_ID, ROLE_ARN, FakeControl

        for key, value in timeouts_env.items():
            monkeypatch.setenv(key, value)
        control = FakeControl(gateways=[{"gatewayId": "gw-1", "name": "retail-pricing-gateway"}],
                              memories=[{"id": MEMORY_ID, "name": "RetailDynamicPricingMemory", "status": "ACTIVE"}])
        session = SimpleNamespace(client=lambda name, **kw: control)
        calls, environments = [], []
        monkeypatch.setattr(deploy.boto3, "Session", lambda **kw: session)
        monkeypatch.setattr(deploy, "load_model_environment", lambda: {})
        monkeypatch.setattr(deploy, "resolve_guardrail_environment", lambda *a: {})
        monkeypatch.setattr(deploy, "list_existing_agent_arns", lambda c: {})
        monkeypatch.setattr(deploy, "ecr_login", lambda *a: calls.append("ecr_login") or "registry")
        monkeypatch.setattr(deploy, "ensure_ecr_repository", lambda *a: None)
        monkeypatch.setattr(deploy, "build_and_push_image", lambda *a: calls.append("build") or "image")
        monkeypatch.setattr(deploy, "create_or_update_agent_runtime",
                            lambda s, r, agent, img, role, env: environments.append(env) or ARN)
        monkeypatch.setattr(deploy, "save_config", lambda *a: None)
        monkeypatch.setattr(deploy, "save_env_file", lambda *a: None)
        monkeypatch.setattr(sys, "argv", ["deploy_agentcore.py", "--role-arn", ROLE_ARN, "--account-id", ACCOUNT,
                                          "--agents", "demand-forecasting"])
        code = 0
        try:
            deploy.main()
        except SystemExit as exc:
            code = exc.code or 0
        return code, calls, environments

    def test_invalid_settings_abort_before_building(self, deploy, monkeypatch):
        code, calls, environments = self.run_main(deploy, monkeypatch, {ct.SPECIALIST_ENV: "800"})
        assert code == 1
        assert calls == [] and environments == []

    def test_settings_are_set_on_the_runtime(self, deploy, monkeypatch):
        code, calls, environments = self.run_main(
            deploy, monkeypatch, {ct.SPECIALIST_ENV: "360", ct.SYNTHESIS_ENV: "200"})
        assert code == 0
        (env,) = environments
        assert env[ct.SPECIALIST_ENV] == "360" and env[ct.SYNTHESIS_ENV] == "200"


class TestVerifyDeploymentComparesBothHalves:
    @pytest.fixture
    def verify(self):
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        import verify_deployment

        return verify_deployment

    def lambda_config(self, t: CycleTimeouts):
        return {"Timeout": t.lambda_timeout, "Environment": {"Variables": t.lambda_environment()}}

    def test_matching_halves_pass(self, verify):
        t = CycleTimeouts(360, 200)
        assert verify.compare_cycle_timeouts(t.agent_environment(), self.lambda_config(t)) == []

    def test_runtime_without_the_vars_is_compared_against_the_defaults(self, verify):
        assert verify.compare_cycle_timeouts({}, self.lambda_config(ct.DEFAULT)) == []

    def test_orchestrator_raised_but_lambda_not_redeployed_fails(self, verify):
        problems = verify.compare_cycle_timeouts(CycleTimeouts(500, 180).agent_environment(),
                                                 self.lambda_config(ct.DEFAULT))
        assert len(problems) == 3
        assert any("timeout 720 s (expected 900 s)" in p for p in problems)

    def test_invalid_orchestrator_values_fail(self, verify):
        assert verify.compare_cycle_timeouts({ct.SPECIALIST_ENV: "abc"}, self.lambda_config(ct.DEFAULT))


# ---------------------------------------------------------------------------
# deploy.sh
# ---------------------------------------------------------------------------

BASH = shutil.which("bash")


@pytest.mark.skipif(BASH is None, reason="bash not available")
class TestDeployScriptChecksTheSettings:
    def run(self, tmp_path, *args):
        """Run a copy of deploy.sh whose PATH holds only python3: once the checks pass,
        it stops at its first other external command instead of deploying."""
        (tmp_path / "shared").mkdir()
        for name in ("__init__.py", "cycle_timeouts.py"):
            shutil.copy(PROJECT_ROOT / "shared" / name, tmp_path / "shared" / name)
        script = tmp_path / "deploy.sh"
        script.write_text((PROJECT_ROOT / "deploy.sh").read_text())
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "python3").symlink_to(sys.executable)
        return subprocess.run([BASH, str(script), "--alert-email", "ops@example.com", *args], cwd=tmp_path,
                              env={"PATH": str(bin_dir), "HOME": str(tmp_path)},
                              capture_output=True, text=True, timeout=60)

    @pytest.mark.parametrize("args", [("--specialist-timeout", "abc"), ("--specialist-timeout", "20"),
                                      ("--specialist-timeout", "600", "--synthesis-timeout", "200")])
    def test_invalid_settings_stop_the_deploy_before_step_0(self, tmp_path, args):
        result = self.run(tmp_path, *args)
        assert result.returncode == 1
        assert "invalid pricing-cycle timeouts" in result.stderr
        assert "Step 0" not in result.stdout

    def test_valid_settings_pass_the_check(self, tmp_path):
        result = self.run(tmp_path, "--specialist-timeout", "360")
        assert "invalid pricing-cycle timeouts" not in result.stderr
        assert "Step 0" in result.stdout
