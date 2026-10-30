"""Cost and reliability controls around pricing cycles.

- POST /pricing-cycles is capped at MAX_ACTIVE_CYCLES running cycles (429) and
  throttled at API Gateway; the stage has a default throttle.
- A cycle left INITIATED / ANALYZING past STALE_CYCLE_SECONDS (its async run
  died; async retries are off) is reported and recorded as FAILED on read.
- The Bedrock spend budget covers the services the model spend is billed under
  and alerts a real address that deploy.sh requires.
"""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATOR_ARN = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/orch-AAAAAAAAAA"


@pytest.fixture
def pc(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_AGENT_ARN", ORCHESTRATOR_ARN)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.delenv("MAX_ACTIVE_CYCLES", raising=False)
    sys.modules.pop("backend.api_handlers.pricing_cycles", None)
    yield importlib.import_module("backend.api_handlers.pricing_cycles")
    sys.modules.pop("backend.api_handlers.pricing_cycles", None)


def ago(seconds: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def post_event(body=None):
    return {
        "httpMethod": "POST",
        "path": "/pricing-cycles",
        "body": json.dumps(body or {"pricingGroup": "Electronics-Audio", "objectives": ["margin_protection"]}),
        "requestContext": {"authorizer": {"claims": {"sub": "user-1"}}},
    }


# ---------------------------------------------------------------------------
# Stale cycles
# ---------------------------------------------------------------------------


class TestStaleCycles:
    @pytest.mark.parametrize("status", ["INITIATED", "ANALYZING"])
    def test_an_old_active_cycle_is_stale(self, pc, status):
        assert pc._is_stale({"status": status, "createdAt": ago(pc.STALE_CYCLE_SECONDS + 60)})

    def test_a_recent_active_cycle_is_not_stale(self, pc):
        assert not pc._is_stale({"status": "ANALYZING", "createdAt": ago(60)})

    @pytest.mark.parametrize("status", ["COMPLETE", "FAILED"])
    def test_finished_cycles_are_never_stale(self, pc, status):
        assert not pc._is_stale({"status": status, "createdAt": ago(10 * pc.STALE_CYCLE_SECONDS)})

    @pytest.mark.parametrize("created", [None, "", "not-a-date", 12345])
    def test_unknown_age_is_not_stale(self, pc, created):
        assert not pc._is_stale({"status": "ANALYZING", "createdAt": created})

    def test_naive_timestamps_are_read_as_utc(self, pc):
        naive = (datetime.now(timezone.utc) - timedelta(seconds=pc.STALE_CYCLE_SECONDS + 60)).replace(tzinfo=None)
        assert pc._is_stale({"status": "ANALYZING", "createdAt": naive.isoformat()})

    def test_stale_threshold_exceeds_the_function_timeout(self, pc):
        """A cycle must not be declared dead while its async run can still finish."""
        from shared.cycle_timeouts import DEFAULT

        assert pc.STALE_CYCLE_SECONDS > DEFAULT.lambda_timeout

    def test_stale_cycle_is_recorded_and_reported_as_failed(self, pc, monkeypatch):
        writes, agent_updates = [], []
        monkeypatch.setattr(pc, "update_cycle_status", lambda **kw: writes.append(kw))
        monkeypatch.setattr(pc, "_update_agent_statuses", lambda cid, st: agent_updates.append((cid, st)))
        cycle = {"cycleId": "c-1", "status": "ANALYZING", "createdAt": ago(pc.STALE_CYCLE_SECONDS + 60)}

        result = pc._expire_if_stale(cycle)

        assert result["status"] == "FAILED"
        assert result["failureReason"]
        assert writes == [{"cycle_id": "c-1", "status": "FAILED", "table_name": pc.PRICING_CYCLES_TABLE,
                           "extra": {"failureReason": result["failureReason"]}}]
        assert agent_updates[0][1]["orchestrator"]["status"] == "failed"

    def test_stale_cycle_is_reported_failed_even_if_the_write_fails(self, pc, monkeypatch):
        def boom(**_kw):
            raise RuntimeError("dynamodb down")

        monkeypatch.setattr(pc, "update_cycle_status", boom)
        cycle = {"cycleId": "c-1", "status": "INITIATED", "createdAt": ago(pc.STALE_CYCLE_SECONDS + 60)}

        assert pc._expire_if_stale(cycle)["status"] == "FAILED"

    def test_active_cycle_is_left_alone(self, pc, monkeypatch):
        monkeypatch.setattr(pc, "update_cycle_status", lambda **kw: pytest.fail("must not write"))
        cycle = {"cycleId": "c-1", "status": "ANALYZING", "createdAt": ago(30)}

        assert pc._expire_if_stale(cycle) is cycle

    def test_get_reports_a_stale_cycle_as_failed(self, pc, monkeypatch):
        monkeypatch.setattr(pc, "get_cycle", lambda cid, table_name: {
            "cycleId": cid, "status": "ANALYZING", "createdAt": ago(pc.STALE_CYCLE_SECONDS + 60)})
        monkeypatch.setattr(pc, "update_cycle_status", lambda **kw: None)
        monkeypatch.setattr(pc, "_update_agent_statuses", lambda *a: None)

        response = pc._get_pricing_cycle("c-1")

        body = json.loads(response["body"])
        assert response["statusCode"] == 200
        assert body["status"] == "FAILED"
        assert body["failureReason"]

    def test_update_cycle_status_writes_extra_attributes(self, pc, monkeypatch):
        class Table:
            def __init__(self):
                self.put = None

            def query(self, **_kw):
                return {"Items": [{"cycleId": "c-1", "status": "ANALYZING", "createdAt": "t"}]}

            def delete_item(self, **_kw):
                pass

            def put_item(self, Item):
                self.put = Item

        table = Table()
        monkeypatch.setattr(pc, "_get_dynamodb_resource", lambda: type("R", (), {"Table": lambda self, n: table})())

        pc.update_cycle_status("c-1", "FAILED", extra={"failureReason": "why"})

        assert table.put["status"] == "FAILED"
        assert table.put["failureReason"] == "why"
        assert table.put["createdAt"] == "t"


# ---------------------------------------------------------------------------
# Active-cycle cap on POST /pricing-cycles
# ---------------------------------------------------------------------------


class FakeScanTable:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def scan(self, **kwargs):
        self.calls.append(kwargs)
        return self.pages.pop(0)


class TestActiveCycleCap:
    def use_table(self, pc, monkeypatch, table):
        monkeypatch.setattr(pc, "_get_dynamodb_resource", lambda: type("R", (), {"Table": lambda self, n: table})())

    def test_counts_active_cycles_across_pages_and_skips_stale_ones(self, pc, monkeypatch):
        stale = ago(pc.STALE_CYCLE_SECONDS + 60)
        table = FakeScanTable([
            {"Items": [{"status": "ANALYZING", "createdAt": ago(10)}, {"status": "ANALYZING", "createdAt": stale}],
             "LastEvaluatedKey": {"cycleId": "x"}},
            {"Items": [{"status": "INITIATED", "createdAt": ago(5)}]},
        ])
        self.use_table(pc, monkeypatch, table)

        assert pc._count_active_cycles() == 2
        assert table.calls[1]["ExclusiveStartKey"] == {"cycleId": "x"}
        assert "FilterExpression" in table.calls[0]

    def test_default_limit_is_three(self, pc):
        assert pc.MAX_ACTIVE_CYCLES == 3

    def test_limit_comes_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRATOR_AGENT_ARN", ORCHESTRATOR_ARN)
        monkeypatch.setenv("MAX_ACTIVE_CYCLES", "5")
        sys.modules.pop("backend.api_handlers.pricing_cycles", None)
        try:
            assert importlib.import_module("backend.api_handlers.pricing_cycles").MAX_ACTIVE_CYCLES == 5
        finally:
            sys.modules.pop("backend.api_handlers.pricing_cycles", None)

    def run_post(self, pc, monkeypatch, active):
        created, triggered = [], []
        if isinstance(active, Exception):
            def count():
                raise active
        else:
            def count():
                return active
        monkeypatch.setattr(pc, "_count_active_cycles", count)
        monkeypatch.setattr(pc, "create_pricing_cycle", lambda **kw: created.append(kw))
        monkeypatch.setattr(pc, "_trigger_async_orchestrator", lambda *a: triggered.append(a))
        response = pc.handler(post_event(), None)
        return response, created, triggered

    def test_post_is_rejected_at_the_limit(self, pc, monkeypatch):
        response, created, triggered = self.run_post(pc, monkeypatch, active=pc.MAX_ACTIVE_CYCLES)

        body = json.loads(response["body"])
        assert response["statusCode"] == 429
        assert body["activeCycles"] == pc.MAX_ACTIVE_CYCLES
        assert body["maxActiveCycles"] == pc.MAX_ACTIVE_CYCLES
        assert created == [] and triggered == []

    def test_post_is_accepted_below_the_limit(self, pc, monkeypatch):
        response, created, triggered = self.run_post(pc, monkeypatch, active=pc.MAX_ACTIVE_CYCLES - 1)

        assert response["statusCode"] == 202
        assert len(created) == 1 and len(triggered) == 1

    def test_post_fails_closed_if_the_count_cannot_be_read(self, pc, monkeypatch):
        response, created, triggered = self.run_post(pc, monkeypatch, active=RuntimeError("throttled"))

        assert response["statusCode"] == 503
        assert created == [] and triggered == []

    def test_invalid_requests_are_rejected_before_counting(self, pc, monkeypatch):
        monkeypatch.setattr(pc, "_count_active_cycles", lambda: pytest.fail("must not count"))

        response = pc.handler(post_event({"objectives": []}), None)

        assert response["statusCode"] == 400


# ---------------------------------------------------------------------------
# Infrastructure: API throttling, Lambda env, budget
# ---------------------------------------------------------------------------


def synth(context=None, monkeypatch=None):
    import aws_cdk as cdk
    from aws_cdk.assertions import Template
    from stacks.pricing_stack import RetailDynamicPricingStack

    app = cdk.App(context=context or {})
    stack = RetailDynamicPricingStack(app, "CostControlsTestStack")
    return Template.from_stack(stack), stack


@pytest.fixture(scope="module")
def template_with_email():
    return synth({"alertEmail": "pricing-ops@example.com"})[0]


class TestApiThrottling:
    def stage_settings(self, template):
        (stage,) = template.find_resources("AWS::ApiGateway::Stage", {"Properties": {"StageName": "prod"}}).values()
        return {(m["ResourcePath"], m["HttpMethod"]): m for m in stage["Properties"]["MethodSettings"]}

    def test_stage_has_a_default_throttle(self, template_with_email):
        from stacks.api_handlers import STAGE_THROTTLE_BURST, STAGE_THROTTLE_RATE

        default = self.stage_settings(template_with_email)[("/*", "*")]
        assert default["ThrottlingRateLimit"] == STAGE_THROTTLE_RATE
        assert default["ThrottlingBurstLimit"] == STAGE_THROTTLE_BURST

    def test_creating_a_cycle_has_a_tighter_throttle(self, template_with_email):
        from stacks.api_handlers import CREATE_CYCLE_THROTTLE_BURST, CREATE_CYCLE_THROTTLE_RATE, STAGE_THROTTLE_RATE

        post = self.stage_settings(template_with_email)[("/~1pricing-cycles", "POST")]
        assert post["ThrottlingRateLimit"] == CREATE_CYCLE_THROTTLE_RATE
        assert post["ThrottlingBurstLimit"] == CREATE_CYCLE_THROTTLE_BURST
        assert CREATE_CYCLE_THROTTLE_RATE < STAGE_THROTTLE_RATE

    def test_pricing_cycles_function_gets_the_active_cycle_limit(self, template_with_email):
        from stacks.api_handlers import MAX_ACTIVE_CYCLES

        (fn,) = template_with_email.find_resources(
            "AWS::Lambda::Function", {"Properties": {"FunctionName": "rdp-api-pricing-cycles"}}).values()
        assert fn["Properties"]["Environment"]["Variables"]["MAX_ACTIVE_CYCLES"] == str(MAX_ACTIVE_CYCLES)


class TestBedrockBudget:
    def budget(self, template):
        (budget,) = template.find_resources("AWS::Budgets::Budget").values()
        return budget["Properties"]

    def test_budget_covers_every_service_the_model_spend_is_billed_under(self, template_with_email):
        services = self.budget(template_with_email)["Budget"]["CostFilters"]["Service"]

        assert set(services) == {"Amazon Bedrock", "Amazon Bedrock Service", "Amazon Bedrock AgentCore"}

    def test_budget_alerts_the_configured_address(self, template_with_email):
        (notification,) = self.budget(template_with_email)["NotificationsWithSubscribers"]

        assert notification["Subscribers"] == [{"Address": "pricing-ops@example.com", "SubscriptionType": "EMAIL"}]
        assert notification["Notification"]["Threshold"] == 80

    def test_no_placeholder_address_anywhere(self, template_with_email):
        assert "admin@example.com" not in json.dumps(template_with_email.to_json())

    def test_without_an_email_the_budget_has_no_notifications_and_synth_warns(self, monkeypatch):
        from aws_cdk.assertions import Annotations, Match

        monkeypatch.delenv("ALERT_EMAIL", raising=False)
        template, stack = synth()

        assert "NotificationsWithSubscribers" not in self.budget(template)
        Annotations.from_stack(stack).has_warning("*", Match.string_like_regexp("No alert email set"))

    def test_env_var_is_used_when_context_is_absent(self, monkeypatch):
        monkeypatch.setenv("ALERT_EMAIL", "from-env@example.com")
        template, _ = synth()

        (notification,) = self.budget(template)["NotificationsWithSubscribers"]
        assert notification["Subscribers"][0]["Address"] == "from-env@example.com"

    def test_budget_name_changes_with_the_subscriber(self):
        """Notifications changes replace the budget; a new name lets the replacement succeed."""
        from stacks.pricing_stack import BUDGET_NAME_PREFIX, budget_name

        names = {budget_name("a@example.com"), budget_name("b@example.com"), budget_name(None)}
        assert len(names) == 3
        assert all(n.startswith(BUDGET_NAME_PREFIX + "-") for n in names)
        assert budget_name("A@Example.com") == budget_name("a@example.com")  # stable across deploys

    def test_template_uses_the_derived_name(self, template_with_email):
        from stacks.pricing_stack import budget_name

        assert self.budget(template_with_email)["Budget"]["BudgetName"] == budget_name("pricing-ops@example.com")

    @pytest.mark.parametrize("bad", ["not-an-email", "a@b", "two words@example.com", "x@@example.com"])
    def test_malformed_email_fails_synth(self, monkeypatch, bad):
        monkeypatch.delenv("ALERT_EMAIL", raising=False)
        with pytest.raises(ValueError):
            synth({"alertEmail": bad})


# ---------------------------------------------------------------------------
# deploy.sh requires the alert email
# ---------------------------------------------------------------------------

DEPLOY_SH = PROJECT_ROOT / "deploy.sh"
BASH = shutil.which("bash")


@pytest.mark.skipif(BASH is None, reason="bash not available")
class TestDeployRequiresAlertEmail:
    def run(self, tmp_path, args=(), env_email=None):
        """Run a copy of deploy.sh with an empty PATH: if the email check let it
        through, the script stops at its first external command instead of deploying."""
        script = tmp_path / "deploy.sh"
        script.write_text(DEPLOY_SH.read_text())
        env = {"PATH": str(tmp_path / "empty-path"), "HOME": str(tmp_path)}
        if env_email is not None:
            env["ALERT_EMAIL"] = env_email
        return subprocess.run([BASH, str(script), *args], cwd=tmp_path, env=env,
                              capture_output=True, text=True, timeout=60)

    def test_missing_email_stops_the_deploy(self, tmp_path):
        result = self.run(tmp_path)

        assert result.returncode == 1
        assert "alert email is required" in result.stderr
        assert "Step 0" not in result.stdout

    @pytest.mark.parametrize("bad", ["not-an-email", "a@b", ""])
    def test_malformed_email_stops_the_deploy(self, tmp_path, bad):
        result = self.run(tmp_path, args=("--alert-email", bad))

        assert result.returncode == 1
        assert "alert email is required" in result.stderr

    @pytest.mark.parametrize("how", ["flag", "env"])
    def test_valid_email_passes_the_check(self, tmp_path, how):
        if how == "flag":
            result = self.run(tmp_path, args=("--alert-email", "ops@example.com"))
        else:
            result = self.run(tmp_path, env_email="ops@example.com")

        assert "alert email is required" not in result.stderr

    def test_both_cdk_deploys_pass_the_email_as_context(self):
        deploys = [line for line in DEPLOY_SH.read_text().splitlines() if line.startswith("npx cdk deploy")]

        assert len(deploys) == 2
        assert all('-c alertEmail="$ALERT_EMAIL"' in line for line in deploys)
