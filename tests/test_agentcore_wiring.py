"""Tests for wiring the AgentCore runtimes to the gateway and memory.

Covers the deploy scripts (scripts/deploy_agentcore.py, setup_memory.py,
setup_gateway.py, create_agentcore_role.py, verify_deployment.py) and the runtime
code paths (backend/agents/agentcore/*). Everything runs offline: AWS clients are
replaced with fakes.
"""
import importlib
import inspect
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import create_agentcore_role  # noqa: E402
import deploy_agentcore  # noqa: E402
import setup_gateway  # noqa: E402
import setup_memory  # noqa: E402
import verify_deployment  # noqa: E402

ACCOUNT = "123456789012"
REGION = "us-east-1"
GATEWAY_URL = "https://retail-pricing-gateway-abc123.gateway.bedrock-agentcore.us-east-1.amazonaws.com"
GATEWAY_MCP = f"{GATEWAY_URL}/mcp"
MEMORY_ID = "RetailDynamicPricingMemory-Ab12Cd34Ef"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/RetailPricingAgentCoreRole"


def runtime_arn(agent):
    return (
        f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:runtime/"
        f"{agent['runtime_name']}-ID{agent['name'][:4]}"
    )


ALL_ARNS = {a["name"]: runtime_arn(a) for a in deploy_agentcore.AGENTS}
AGENT = {a["name"]: a for a in deploy_agentcore.AGENTS}


def client_error(code, message="boom", operation="Op"):
    return ClientError({"Error": {"Code": code, "Message": message}}, operation)


# ---------------------------------------------------------------------------
# deploy_agentcore: environment construction
# ---------------------------------------------------------------------------

BASE_ENV = {"AGENTCORE_GATEWAY_ENDPOINT": GATEWAY_MCP, "AGENTCORE_MEMORY_ID": MEMORY_ID}


class TestBuildEnvironment:
    @pytest.mark.parametrize("name", deploy_agentcore.SPECIALIST_AGENTS)
    def test_specialists_get_gateway_and_memory_only_from_base(self, name):
        env = deploy_agentcore.build_environment(AGENT[name], BASE_ENV, ALL_ARNS)

        assert env == BASE_ENV

    def test_orchestrator_gets_the_five_specialist_arns(self):
        env = deploy_agentcore.build_environment(AGENT["orchestrator"], BASE_ENV, ALL_ARNS)

        for name in deploy_agentcore.SPECIALIST_AGENTS:
            assert env[deploy_agentcore.AGENT_ARN_ENV_VARS[name]] == ALL_ARNS[name]
        # The orchestrator does not need its own ARN.
        assert "ORCHESTRATOR_AGENT_ARN" not in env
        assert env["AGENTCORE_GATEWAY_ENDPOINT"] == GATEWAY_MCP
        assert env["AGENTCORE_MEMORY_ID"] == MEMORY_ID

    def test_orchestrator_requires_every_specialist_arn(self):
        arns = dict(ALL_ARNS)
        del arns["market-intelligence"]

        with pytest.raises(deploy_agentcore.WiringError, match="market-intelligence"):
            deploy_agentcore.build_environment(AGENT["orchestrator"], BASE_ENV, arns)

    def test_orchestrator_rejects_placeholder_arn(self):
        arns = dict(ALL_ARNS)
        arns["demand-forecasting"] = (
            f"arn:aws:bedrock-agentcore:{REGION}:<ACCOUNT_ID>:runtime/retailPricing_demandForecasting"
        )

        with pytest.raises(deploy_agentcore.WiringError, match="demand-forecasting"):
            deploy_agentcore.build_environment(AGENT["orchestrator"], BASE_ENV, arns)

    def test_reserved_aws_names_are_rejected(self):
        with pytest.raises(ValueError):
            deploy_agentcore.build_environment(
                AGENT["competitive-intelligence"], {**BASE_ENV, "AWS_REGION": REGION}, ALL_ARNS
            )

    def test_orchestrator_env_names_match_what_the_runtime_reads(self):
        """orchestrator_runtime.py reads exactly these names at import time."""
        source = (PROJECT_ROOT / "backend/agents/agentcore/orchestrator_runtime.py").read_text()
        for name in deploy_agentcore.SPECIALIST_AGENTS:
            assert f'os.environ["{deploy_agentcore.AGENT_ARN_ENV_VARS[name]}"]' in source


# ---------------------------------------------------------------------------
# deploy_agentcore: gateway / memory discovery
# ---------------------------------------------------------------------------

class FakeControl:
    """Fake bedrock-agentcore-control client for discovery helpers."""

    def __init__(self, gateways=(), gateway_status="READY", gateway_url=GATEWAY_URL, memories=(), runtimes=()):
        self._gateways = list(gateways)
        self._gateway_status = gateway_status
        self._gateway_url = gateway_url
        self._memories = list(memories)
        self._runtimes = list(runtimes)

    def list_gateways(self, **kwargs):
        return {"items": self._gateways}

    def get_gateway(self, gatewayIdentifier):
        return {"status": self._gateway_status, "gatewayUrl": self._gateway_url, "gatewayId": gatewayIdentifier}

    def list_memories(self, **kwargs):
        return {"memories": self._memories}

    def list_agent_runtimes(self, **kwargs):
        return {"agentRuntimes": self._runtimes}


class TestDiscovery:
    def test_gateway_endpoint_is_the_mcp_url(self):
        control = FakeControl(gateways=[{"gatewayId": "gw-1", "name": "retail-pricing-gateway"}])

        assert deploy_agentcore.resolve_gateway_endpoint(control, "retail-pricing-gateway") == GATEWAY_MCP

    def test_trailing_slash_in_gateway_url_is_normalised(self):
        control = FakeControl(
            gateways=[{"gatewayId": "gw-1", "name": "retail-pricing-gateway"}], gateway_url=GATEWAY_URL + "/"
        )

        assert deploy_agentcore.resolve_gateway_endpoint(control, "retail-pricing-gateway") == GATEWAY_MCP

    def test_missing_gateway_is_an_error(self):
        control = FakeControl(gateways=[{"gatewayId": "gw-2", "name": "something-else"}])

        with pytest.raises(deploy_agentcore.WiringError, match="not found"):
            deploy_agentcore.resolve_gateway_endpoint(control, "retail-pricing-gateway")

    def test_gateway_that_is_not_ready_is_an_error(self):
        control = FakeControl(
            gateways=[{"gatewayId": "gw-1", "name": "retail-pricing-gateway"}], gateway_status="CREATING"
        )

        with pytest.raises(deploy_agentcore.WiringError, match="not READY"):
            deploy_agentcore.resolve_gateway_endpoint(control, "retail-pricing-gateway")

    def test_memory_is_matched_by_id_prefix_not_name(self):
        control = FakeControl(
            memories=[
                {"id": "SomeOtherMemory-zzzzzzzzzz", "status": "ACTIVE"},
                {"id": MEMORY_ID, "arn": "arn:...", "status": "ACTIVE"},
            ]
        )

        assert deploy_agentcore.resolve_memory_id(control, "RetailDynamicPricingMemory") == MEMORY_ID

    def test_prefix_without_separator_does_not_match(self):
        control = FakeControl(memories=[{"id": "RetailDynamicPricingMemoryV2-abcdefghij", "status": "ACTIVE"}])

        with pytest.raises(deploy_agentcore.WiringError, match="not found"):
            deploy_agentcore.resolve_memory_id(control, "RetailDynamicPricingMemory")

    def test_missing_memory_is_an_error(self):
        with pytest.raises(deploy_agentcore.WiringError, match="not found"):
            deploy_agentcore.resolve_memory_id(FakeControl(), "RetailDynamicPricingMemory")

    def test_memory_that_is_not_active_is_an_error(self):
        control = FakeControl(memories=[{"id": MEMORY_ID, "status": "CREATING"}])

        with pytest.raises(deploy_agentcore.WiringError, match="not ACTIVE"):
            deploy_agentcore.resolve_memory_id(control, "RetailDynamicPricingMemory")

    def test_existing_runtime_arns_are_mapped_to_agent_names(self):
        runtimes = [
            {"agentRuntimeName": a["runtime_name"], "agentRuntimeArn": ALL_ARNS[a["name"]]}
            for a in deploy_agentcore.AGENTS
        ] + [{"agentRuntimeName": "unrelated", "agentRuntimeArn": "arn:x"}]

        assert deploy_agentcore.list_existing_agent_arns(FakeControl(runtimes=runtimes)) == ALL_ARNS

    def test_list_all_follows_pagination(self):
        pages = {
            None: {"items": [1, 2], "nextToken": "t1"},
            "t1": {"items": [3], "nextToken": "t2"},
            "t2": {"items": [4]},
        }

        def call(nextToken=None):
            return pages[nextToken]

        assert deploy_agentcore._list_all(call, ("items",)) == [1, 2, 3, 4]


class TestModelAndGuardrailEnvironment:
    def test_model_ids_come_from_model_config(self, tmp_path, monkeypatch):
        cfg = tmp_path / "model-config.json"
        cfg.write_text(json.dumps({"modelId": "orch-model", "specialistModelId": "spec-model"}))
        monkeypatch.setattr(deploy_agentcore, "MODEL_CONFIG_FILE", cfg)

        assert deploy_agentcore.load_model_environment() == {
            "ORCHESTRATOR_MODEL_ID": "orch-model",
            "SPECIALIST_MODEL_ID": "spec-model",
        }

    def test_missing_model_config_is_not_fatal(self, tmp_path, monkeypatch):
        monkeypatch.setattr(deploy_agentcore, "MODEL_CONFIG_FILE", tmp_path / "absent.json")

        assert deploy_agentcore.load_model_environment() == {}

    @staticmethod
    def session_with_bedrock(bedrock):
        return SimpleNamespace(client=lambda name, **kw: bedrock)

    def test_missing_guardrail_disables_guardrails(self, monkeypatch):
        monkeypatch.delenv("DISABLE_BEDROCK_GUARDRAILS", raising=False)
        bedrock = SimpleNamespace(
            get_guardrail=lambda **kw: (_ for _ in ()).throw(client_error("ResourceNotFoundException"))
        )

        env = deploy_agentcore.resolve_guardrail_environment(self.session_with_bedrock(bedrock), REGION)

        assert env == {"DISABLE_BEDROCK_GUARDRAILS": "true"}

    def test_existing_guardrail_is_attached(self, monkeypatch):
        monkeypatch.delenv("DISABLE_BEDROCK_GUARDRAILS", raising=False)
        monkeypatch.setenv("BEDROCK_GUARDRAIL_ID", "gr-123")
        monkeypatch.setenv("BEDROCK_GUARDRAIL_VERSION", "7")
        seen = {}
        bedrock = SimpleNamespace(get_guardrail=lambda **kw: seen.update(kw) or {})

        env = deploy_agentcore.resolve_guardrail_environment(self.session_with_bedrock(bedrock), REGION)

        assert env == {"BEDROCK_GUARDRAIL_ID": "gr-123", "BEDROCK_GUARDRAIL_VERSION": "7"}
        assert seen == {"guardrailIdentifier": "gr-123", "guardrailVersion": "7"}

    def test_unverifiable_guardrail_stays_enabled(self, monkeypatch):
        """Only a guardrail that definitively does not exist is switched off."""
        monkeypatch.delenv("DISABLE_BEDROCK_GUARDRAILS", raising=False)
        bedrock = SimpleNamespace(
            get_guardrail=lambda **kw: (_ for _ in ()).throw(client_error("AccessDeniedException"))
        )

        env = deploy_agentcore.resolve_guardrail_environment(self.session_with_bedrock(bedrock), REGION)

        assert "DISABLE_BEDROCK_GUARDRAILS" not in env
        assert env["BEDROCK_GUARDRAIL_ID"]

    def test_operator_kill_switch_is_passed_through(self, monkeypatch):
        monkeypatch.setenv("DISABLE_BEDROCK_GUARDRAILS", "true")

        env = deploy_agentcore.resolve_guardrail_environment(self.session_with_bedrock(None), REGION)

        assert env == {"DISABLE_BEDROCK_GUARDRAILS": "true"}


# ---------------------------------------------------------------------------
# deploy_agentcore: runtime create / update
# ---------------------------------------------------------------------------

class FakeRuntimeClient:
    """Records create/update calls; behaves like a runtime that is immediately READY."""

    def __init__(self, existing=None, create_error=None, update_error=None):
        self.existing = existing
        self.create_error = create_error
        self.update_error = update_error
        self.created = []
        self.updated = []

    def list_agent_runtimes(self, **kwargs):
        return {"agentRuntimes": [self.existing] if self.existing else []}

    def create_agent_runtime(self, **kwargs):
        self.created.append(kwargs)
        if self.create_error:
            raise self.create_error
        return {
            "agentRuntimeArn": runtime_arn(AGENT["competitive-intelligence"]),
            "agentRuntimeId": "rt-new",
            "agentRuntimeVersion": "1",
        }

    def update_agent_runtime(self, **kwargs):
        self.updated.append(kwargs)
        if self.update_error:
            raise self.update_error
        return {"agentRuntimeVersion": "2"}

    def get_agent_runtime(self, agentRuntimeId, agentRuntimeVersion=None):
        env = (self.updated[-1] if self.updated else self.created[-1])["environmentVariables"]
        return {
            "status": "READY",
            "agentRuntimeVersion": agentRuntimeVersion or ("2" if self.updated else "1"),
            "environmentVariables": env,
        }

    def get_agent_runtime_endpoint(self, agentRuntimeId, endpointName):
        return {"status": "READY", "liveVersion": "2" if self.updated else "1"}


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(deploy_agentcore.time, "sleep", lambda s: None)


def deploy_with(client, environment, agent=None):
    session = SimpleNamespace(client=lambda name, **kw: client)
    return deploy_agentcore.create_or_update_agent_runtime(
        session, REGION, agent or AGENT["competitive-intelligence"], "img:latest", ROLE_ARN, environment
    )


EXISTING = {
    "agentRuntimeName": AGENT["competitive-intelligence"]["runtime_name"],
    "agentRuntimeId": "rt-existing",
    "agentRuntimeArn": runtime_arn(AGENT["competitive-intelligence"]),
}


class TestRuntimeEnvironmentOnCreateAndUpdate:
    def test_environment_is_set_on_create(self, no_sleep):
        client = FakeRuntimeClient()

        deploy_with(client, BASE_ENV)

        assert len(client.created) == 1
        assert client.created[0]["environmentVariables"] == BASE_ENV

    def test_environment_is_set_on_update(self, no_sleep):
        client = FakeRuntimeClient(existing=EXISTING)

        arn = deploy_with(client, BASE_ENV)

        assert client.created == []
        assert len(client.updated) == 1
        assert client.updated[0]["environmentVariables"] == BASE_ENV
        assert client.updated[0]["agentRuntimeId"] == "rt-existing"
        assert client.updated[0]["roleArn"] == ROLE_ARN
        assert arn == EXISTING["agentRuntimeArn"]

    def test_environment_is_set_on_the_conflict_recovery_update(self, no_sleep):
        client = FakeRuntimeClient(create_error=client_error("ConflictException"))
        # Not visible to get_existing_runtime, but visible to the recovery listing.
        listings = iter([{"agentRuntimes": []}, {"agentRuntimes": [EXISTING]}])
        client.list_agent_runtimes = lambda **kw: next(listings)

        deploy_with(client, BASE_ENV)

        assert len(client.created) == 1
        assert len(client.updated) == 1
        assert client.updated[0]["environmentVariables"] == BASE_ENV

    def test_failed_update_is_not_swallowed(self, no_sleep):
        """The old code logged 'continuing with existing' and reported success."""
        client = FakeRuntimeClient(existing=EXISTING, update_error=client_error("ValidationException"))

        with pytest.raises(ClientError):
            deploy_with(client, BASE_ENV)

    def test_update_waits_for_the_new_version_and_confirms_the_environment(self, no_sleep):
        client = FakeRuntimeClient(existing=EXISTING)
        # The runtime reports the env vars of an OLD version: the deploy must notice.
        client.get_agent_runtime = lambda agentRuntimeId, agentRuntimeVersion=None: {
            "status": "READY",
            "agentRuntimeVersion": "2",
            "environmentVariables": {},
        }

        with pytest.raises(RuntimeError, match="missing/has wrong env vars"):
            deploy_with(client, BASE_ENV)

    def test_failed_runtime_state_fails_fast(self, no_sleep):
        client = FakeRuntimeClient(existing=EXISTING)
        client.get_agent_runtime = lambda agentRuntimeId, agentRuntimeVersion=None: {
            "status": "UPDATE_FAILED",
            "agentRuntimeVersion": "2",
            "failureReason": "bad image",
        }

        with pytest.raises(RuntimeError, match="UPDATE_FAILED"):
            deploy_with(client, BASE_ENV)

    def test_unfindable_runtime_never_yields_a_placeholder_arn(self, no_sleep):
        client = FakeRuntimeClient(create_error=client_error("ConflictException"))

        with pytest.raises(RuntimeError, match="could not be found"):
            deploy_with(client, BASE_ENV)


# ---------------------------------------------------------------------------
# deploy_agentcore: image build and CLI fail-fast
# ---------------------------------------------------------------------------

class TestBuildArg:
    def test_build_arg_matches_the_dockerfile(self, monkeypatch):
        commands = []

        def fake_run(cmd, **kwargs):
            commands.append(cmd)
            return SimpleNamespace(returncode=0, stderr="")

        monkeypatch.setattr(deploy_agentcore.subprocess, "run", fake_run)

        deploy_agentcore.build_and_push_image(AGENT["orchestrator"], "registry", REGION)

        build = commands[0]
        assert "AGENT_ENTRYPOINT=orchestrator_runtime" in build
        assert not any("AGENT_MODULE" in part for part in build)

        # The Dockerfile must actually declare the arg the script passes.
        dockerfile = (PROJECT_ROOT / "backend/agents/agentcore/Dockerfile").read_text()
        assert "ARG AGENT_ENTRYPOINT" in dockerfile

    @pytest.mark.parametrize("agent", deploy_agentcore.AGENTS, ids=lambda a: a["name"])
    def test_every_agent_module_exists_and_is_in_the_dockerfile_cmd_namespace(self, agent):
        assert (PROJECT_ROOT / "backend/agents/agentcore" / f"{agent['module']}.py").exists()


class TestMainFailsFastBeforeBuilding:
    @staticmethod
    def run_main(monkeypatch, control, extra_args=()):
        calls = []
        session = SimpleNamespace(client=lambda name, **kw: control)
        monkeypatch.setattr(deploy_agentcore.boto3, "Session", lambda **kw: session)
        monkeypatch.setattr(deploy_agentcore, "ecr_login", lambda *a: calls.append("ecr_login"))
        monkeypatch.setattr(deploy_agentcore, "build_and_push_image", lambda *a: calls.append("build"))
        monkeypatch.setattr(
            sys, "argv",
            ["deploy_agentcore.py", "--role-arn", ROLE_ARN, "--account-id", ACCOUNT, *extra_args],
        )
        with pytest.raises(SystemExit) as exc:
            deploy_agentcore.main()
        return exc.value.code, calls

    def test_missing_gateway_exits_non_zero_without_building(self, monkeypatch):
        control = FakeControl(memories=[{"id": MEMORY_ID, "status": "ACTIVE"}])

        code, calls = self.run_main(monkeypatch, control)

        assert code == 1
        assert calls == []

    def test_missing_memory_exits_non_zero_without_building(self, monkeypatch):
        control = FakeControl(gateways=[{"gatewayId": "gw-1", "name": "retail-pricing-gateway"}])

        code, calls = self.run_main(monkeypatch, control)

        assert code == 1
        assert calls == []

    def test_bare_gateway_url_override_is_rejected(self, monkeypatch):
        control = FakeControl(memories=[{"id": MEMORY_ID, "status": "ACTIVE"}])

        code, calls = self.run_main(monkeypatch, control, ["--gateway-endpoint", GATEWAY_URL])

        assert code == 1
        assert calls == []

    def test_orchestrator_alone_needs_the_specialists_to_exist(self, monkeypatch):
        control = FakeControl(
            gateways=[{"gatewayId": "gw-1", "name": "retail-pricing-gateway"}],
            memories=[{"id": MEMORY_ID, "status": "ACTIVE"}],
        )
        monkeypatch.setattr(
            deploy_agentcore, "resolve_guardrail_environment", lambda *a: {"DISABLE_BEDROCK_GUARDRAILS": "true"}
        )

        code, calls = self.run_main(monkeypatch, control, ["--agents", "orchestrator"])

        assert code == 1
        assert calls == []


# ---------------------------------------------------------------------------
# verify_deployment: the wiring gate
# ---------------------------------------------------------------------------

class FakeWiringClient:
    """Fake bedrock-agentcore-control client for verify_agent_wiring."""

    def __init__(self, env_by_agent=None, live_version="1", target_version=None, drop=(), gateway_url=GATEWAY_URL,
                 memories=None, versions=None):
        wired = {"AGENTCORE_GATEWAY_ENDPOINT": GATEWAY_MCP, "AGENTCORE_MEMORY_ID": MEMORY_ID}
        self.env_by_agent = env_by_agent or {}
        self.default_env = wired
        self.live_version = live_version
        self.target_version = target_version
        self.drop = set(drop)
        self.gateway_url = gateway_url
        self.memories = [{"id": MEMORY_ID, "status": "ACTIVE"}] if memories is None else memories
        self.versions = versions or {}  # {(runtime_id, version): env}

    def list_agent_runtimes(self, **kwargs):
        return {
            "agentRuntimes": [
                {"agentRuntimeName": a["runtime_name"], "agentRuntimeId": f"id-{a['name']}"}
                for a in deploy_agentcore.AGENTS
                if a["runtime_name"] not in self.drop
            ]
        }

    def get_agent_runtime_endpoint(self, agentRuntimeId, endpointName):
        assert endpointName == "DEFAULT"
        response = {"status": "READY", "liveVersion": self.live_version}
        if self.target_version:
            response["targetVersion"] = self.target_version
        return response

    def get_agent_runtime(self, agentRuntimeId, agentRuntimeVersion):
        key = (agentRuntimeId, agentRuntimeVersion)
        if key in self.versions:
            return {"environmentVariables": self.versions[key]}
        agent = agentRuntimeId.removeprefix("id-")
        return {"environmentVariables": self.env_by_agent.get(agent, self.default_env)}

    def list_gateways(self, **kwargs):
        return {"items": [{"gatewayId": "gw-1", "name": "retail-pricing-gateway"}]}

    def get_gateway(self, gatewayIdentifier):
        return {"gatewayUrl": self.gateway_url}

    def list_memories(self, **kwargs):
        return {"memories": self.memories}


def verify(monkeypatch, client):
    monkeypatch.setattr(verify_deployment.boto3, "client", lambda *a, **kw: client)
    return verify_deployment.verify_agent_wiring(REGION)


class TestVerifyAgentWiring:
    def test_all_six_wired_passes(self, monkeypatch):
        passed, rows, problems = verify(monkeypatch, FakeWiringClient())

        assert passed
        assert len(rows) == 6 and all(ok for _, ok, _ in rows)
        assert problems == []

    @pytest.mark.parametrize("missing", ["AGENTCORE_GATEWAY_ENDPOINT", "AGENTCORE_MEMORY_ID"])
    @pytest.mark.parametrize("how", ["absent", "empty"])
    def test_a_runtime_without_either_variable_fails_the_gate(self, monkeypatch, missing, how):
        env = {"AGENTCORE_GATEWAY_ENDPOINT": GATEWAY_MCP, "AGENTCORE_MEMORY_ID": MEMORY_ID}
        env.pop(missing) if how == "absent" else env.__setitem__(missing, "")
        client = FakeWiringClient(env_by_agent={"strategy-synthesis": env})

        passed, rows, _ = verify(monkeypatch, client)

        assert not passed
        failed = [name for name, ok, _ in rows if not ok]
        assert failed == ["strategy-synthesis"]

    def test_runtime_with_no_environment_at_all_fails(self, monkeypatch):
        """The state of the original deployment: get-agent-runtime returns no environmentVariables."""
        client = FakeWiringClient()
        client.get_agent_runtime = lambda agentRuntimeId, agentRuntimeVersion: {}

        passed, rows, _ = verify(monkeypatch, client)

        assert not passed
        assert not any(ok for _, ok, _ in rows)

    def test_missing_runtime_fails(self, monkeypatch):
        client = FakeWiringClient(drop=["retailPricing_orchestrator"])

        passed, rows, _ = verify(monkeypatch, client)

        assert not passed
        assert ("orchestrator", False) in [(n, ok) for n, ok, _ in rows]

    def test_the_served_version_is_checked_not_the_latest(self, monkeypatch):
        """DEFAULT still serves v1 (unwired) although a newer, wired version exists."""
        unwired, wired = {}, {"AGENTCORE_GATEWAY_ENDPOINT": GATEWAY_MCP, "AGENTCORE_MEMORY_ID": MEMORY_ID}
        versions = {}
        for a in deploy_agentcore.AGENTS:
            versions[(f"id-{a['name']}", "1")] = unwired
            versions[(f"id-{a['name']}", "2")] = wired
        client = FakeWiringClient(live_version="1", versions=versions)

        passed, _, _ = verify(monkeypatch, client)

        assert not passed

    def test_endpoint_still_moving_to_a_new_version_fails(self, monkeypatch):
        passed, rows, _ = verify(monkeypatch, FakeWiringClient(live_version="1", target_version="2"))

        assert not passed
        assert all("still moving" in detail for _, _, detail in rows)

    def test_bare_gateway_url_without_mcp_suffix_fails(self, monkeypatch):
        env = {"AGENTCORE_GATEWAY_ENDPOINT": GATEWAY_URL, "AGENTCORE_MEMORY_ID": MEMORY_ID}
        client = FakeWiringClient(env_by_agent={"competitive-intelligence": env})

        passed, rows, _ = verify(monkeypatch, client)

        assert not passed
        assert [n for n, ok, _ in rows if not ok] == ["competitive-intelligence"]

    def test_agents_that_disagree_fail(self, monkeypatch):
        env = {"AGENTCORE_GATEWAY_ENDPOINT": GATEWAY_MCP, "AGENTCORE_MEMORY_ID": "RetailDynamicPricingMemory-Other00000"}
        client = FakeWiringClient(env_by_agent={"orchestrator": env})

        passed, _, problems = verify(monkeypatch, client)

        assert not passed
        assert any("disagree" in p for p in problems)

    def test_stale_gateway_not_matching_the_live_one_fails(self, monkeypatch):
        client = FakeWiringClient(gateway_url="https://retail-pricing-gateway-NEW.gateway.example.com")

        passed, _, problems = verify(monkeypatch, client)

        assert not passed
        assert any("!= live gateway" in p for p in problems)

    def test_memory_that_does_not_exist_fails(self, monkeypatch):
        passed, _, problems = verify(monkeypatch, FakeWiringClient(memories=[]))

        assert not passed
        assert any("memory" in p and "not found" in p for p in problems)

    def test_api_errors_fail_closed(self, monkeypatch):
        client = FakeWiringClient()

        def boom(**kwargs):
            raise client_error("AccessDeniedException")

        client.list_agent_runtimes = boom

        passed, rows, problems = verify(monkeypatch, client)

        assert not passed and rows == [] and problems

    def test_main_exits_non_zero_when_wiring_fails(self, monkeypatch, capsys):
        """The wiring result must reach the process exit status (it gates deploy.sh)."""
        ok_checks = {
            "verify_cloudformation": (True, {"PricingApiEndpoint": "https://api/"}),
            "verify_dynamodb": [("PricingCycles", True, 0)],
            "verify_lambda_functions": [("fn", True)],
            "verify_cognito": (True, "pool"),
            "verify_api_gateway": (True, 19),
            "verify_s3_buckets": [("Dashboard bucket", True)],
            "verify_agent_arns": (True, 6),
            "verify_cycle_timeouts": (True, "timeouts match"),
        }
        for name, value in ok_checks.items():
            monkeypatch.setattr(verify_deployment, name, lambda *a, _v=value, **k: _v)
        monkeypatch.setattr(verify_deployment, "verify_agent_wiring", lambda region: (False, [("orchestrator", False, "x")], []))
        monkeypatch.setattr(sys, "argv", ["verify_deployment.py"])

        with pytest.raises(SystemExit) as exc:
            verify_deployment.main()

        assert exc.value.code == 1
        assert "SOME CHECKS FAILED" in capsys.readouterr().out

    def test_main_passes_when_everything_including_wiring_passes(self, monkeypatch, capsys):
        ok_checks = {
            "verify_cloudformation": (True, {"PricingApiEndpoint": "https://api/"}),
            "verify_dynamodb": [("PricingCycles", True, 0)],
            "verify_lambda_functions": [("fn", True)],
            "verify_cognito": (True, "pool"),
            "verify_api_gateway": (True, 19),
            "verify_s3_buckets": [("Dashboard bucket", True)],
            "verify_agent_arns": (True, 6),
            "verify_cycle_timeouts": (True, "timeouts match"),
        }
        for name, value in ok_checks.items():
            monkeypatch.setattr(verify_deployment, name, lambda *a, _v=value, **k: _v)
        monkeypatch.setattr(verify_deployment, "verify_agent_wiring", lambda region: (True, [("orchestrator", True, "ok")], []))
        monkeypatch.setattr(sys, "argv", ["verify_deployment.py"])

        with pytest.raises(SystemExit) as exc:
            verify_deployment.main()

        assert exc.value.code == 0
        assert "ALL CHECKS PASSED" in capsys.readouterr().out

    def test_runtime_names_match_the_deploy_script(self):
        assert verify_deployment.AGENT_RUNTIME_NAMES == {
            a["name"]: a["runtime_name"] for a in deploy_agentcore.AGENTS
        }


# ---------------------------------------------------------------------------
# create_agentcore_role: IAM policy
# ---------------------------------------------------------------------------

class TestRolePolicy:
    policy = create_agentcore_role.get_inline_policy(ACCOUNT, REGION)
    statements = {s["Sid"]: s for s in policy["Statement"]}

    def test_existing_statements_are_kept(self):
        for sid in (
            "BedrockModelInvocation", "ECRAuthToken", "ECRImagePull", "CloudWatchLogs",
            "DynamoDBAccess", "S3ReadAccess", "LambdaInvokeMcpServers",
        ):
            assert sid in self.statements

    def test_memory_data_plane_is_granted_and_scoped_to_the_memory(self):
        stmt = self.statements["AgentCoreMemoryDataPlane"]

        assert set(stmt["Action"]) == {
            "bedrock-agentcore:CreateEvent", "bedrock-agentcore:GetEvent", "bedrock-agentcore:ListEvents",
            "bedrock-agentcore:DeleteEvent", "bedrock-agentcore:RetrieveMemoryRecords",
        }
        assert stmt["Resource"] == [f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:memory/RetailDynamicPricingMemory-*"]

    def test_orchestrator_can_invoke_only_the_pricing_runtimes(self):
        stmt = self.statements["InvokeSpecialistRuntimes"]

        assert stmt["Action"] == ["bedrock-agentcore:InvokeAgentRuntime"]
        assert stmt["Resource"] == [f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:runtime/retailPricing_*"]

    def test_gateway_invocation_is_scoped_to_the_gateway(self):
        stmt = self.statements["InvokeRetailPricingGateway"]

        assert stmt["Action"] == ["bedrock-agentcore:InvokeGateway"]
        assert stmt["Resource"] == [f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:gateway/retail-pricing-gateway-*"]

    def test_apply_guardrail_is_scoped_to_guardrails_in_the_account(self):
        stmt = self.statements["BedrockApplyGuardrail"]

        assert stmt["Action"] == ["bedrock:ApplyGuardrail"]
        assert stmt["Resource"] == [f"arn:aws:bedrock:{REGION}:{ACCOUNT}:guardrail/*"]

    def test_no_new_wildcard_resources(self):
        """Only the pre-existing ECR auth-token statement may use Resource '*'."""
        wildcard = [s["Sid"] for s in self.policy["Statement"] if s["Resource"] == "*" or "*" in s["Resource"]]
        assert wildcard == ["ECRAuthToken"]

    def test_all_resources_belong_to_this_account_or_are_account_independent(self):
        for stmt in self.policy["Statement"]:
            if stmt["Sid"] in ("ECRAuthToken", "BedrockModelInvocation", "S3ReadAccess"):
                continue
            for resource in stmt["Resource"]:
                assert ACCOUNT in resource, stmt["Sid"]


class FakeIam:
    def __init__(self, exists):
        self.exists = exists
        self.put = []
        self.trust_updates = []

    def create_role(self, **kwargs):
        if self.exists:
            raise client_error("EntityAlreadyExists")
        return {"Role": {"Arn": ROLE_ARN}}

    def get_role(self, RoleName):
        return {"Role": {"Arn": ROLE_ARN}}

    def update_assume_role_policy(self, **kwargs):
        self.trust_updates.append(kwargs)

    def put_role_policy(self, **kwargs):
        self.put.append(kwargs)


class TestRoleUpdatedInPlace:
    @pytest.mark.parametrize("exists", [False, True], ids=["new-role", "existing-role"])
    def test_policy_is_applied_to_new_and_existing_roles(self, monkeypatch, exists):
        iam = FakeIam(exists)
        sts = SimpleNamespace(get_caller_identity=lambda: {"Account": ACCOUNT})
        session = SimpleNamespace(client=lambda name, **kw: iam if name == "iam" else sts)
        monkeypatch.setattr(create_agentcore_role.time, "sleep", lambda s: None)

        arn = create_agentcore_role.create_role(session, "RetailPricingAgentCoreRole", REGION)

        assert arn == ROLE_ARN
        assert len(iam.put) == 1
        applied = json.loads(iam.put[0]["PolicyDocument"])
        assert "AgentCoreMemoryDataPlane" in {s["Sid"] for s in applied["Statement"]}
        assert bool(iam.trust_updates) == exists


# ---------------------------------------------------------------------------
# setup_memory: idempotency
# ---------------------------------------------------------------------------

class FakeMemoryClient:
    def __init__(self, memories, statuses=None):
        self._memories = memories
        self._statuses = list(statuses or [])
        self.created = []
        self.gmcp_client = SimpleNamespace(get_memory=self._get_memory)

    def list_memories(self, max_results=100):
        return list(self._memories)

    def _get_memory(self, memoryId):
        return {"memory": {"status": self._statuses.pop(0)}}

    def create_memory_and_wait(self, **kwargs):
        self.created.append(kwargs)
        return {"id": "RetailDynamicPricingMemory-NEW0000000"}


class TestSetupMemoryIdempotent:
    def test_existing_memory_is_reused_and_nothing_is_created(self, monkeypatch, capsys):
        client = FakeMemoryClient(
            [
                {"id": "Unrelated-0000000000", "status": "ACTIVE"},
                {"id": MEMORY_ID, "memoryId": MEMORY_ID, "arn": "arn:...", "status": "ACTIVE"},
            ]
        )
        monkeypatch.setattr(setup_memory, "MemoryClient", lambda **kw: client)

        assert setup_memory.setup_memory(REGION) == MEMORY_ID

        assert client.created == []
        assert f"Memory already exists: {MEMORY_ID}" in capsys.readouterr().out

    def test_memory_is_created_when_none_exists(self, monkeypatch):
        client = FakeMemoryClient([])
        monkeypatch.setattr(setup_memory, "MemoryClient", lambda **kw: client)

        assert setup_memory.setup_memory(REGION) == "RetailDynamicPricingMemory-NEW0000000"

        assert len(client.created) == 1
        assert client.created[0]["name"] == "RetailDynamicPricingMemory"

    def test_a_failed_lookup_never_falls_through_to_create(self, monkeypatch):
        client = FakeMemoryClient([])
        client.list_memories = lambda max_results=100: (_ for _ in ()).throw(client_error("AccessDeniedException"))
        monkeypatch.setattr(setup_memory, "MemoryClient", lambda **kw: client)

        with pytest.raises(ClientError):
            setup_memory.setup_memory(REGION)

        assert client.created == []

    def test_a_memory_still_creating_is_waited_for_not_duplicated(self, monkeypatch):
        client = FakeMemoryClient([{"id": MEMORY_ID, "status": "CREATING"}], statuses=["CREATING", "ACTIVE"])
        monkeypatch.setattr(setup_memory, "MemoryClient", lambda **kw: client)
        monkeypatch.setattr(setup_memory.time, "sleep", lambda s: None)

        assert setup_memory.setup_memory(REGION) == MEMORY_ID
        assert client.created == []

    def test_a_failed_memory_is_reported_not_duplicated(self, monkeypatch):
        client = FakeMemoryClient([{"id": MEMORY_ID, "status": "FAILED"}], statuses=["FAILED"])
        monkeypatch.setattr(setup_memory, "MemoryClient", lambda **kw: client)

        with pytest.raises(RuntimeError, match="Refusing to create a duplicate"):
            setup_memory.setup_memory(REGION)
        assert client.created == []


# ---------------------------------------------------------------------------
# setup_gateway: prints the real MCP endpoint
# ---------------------------------------------------------------------------

class TestSetupGatewayOutput:
    def test_prints_the_real_mcp_endpoint_not_a_placeholder(self, monkeypatch, capsys):
        class Control:
            def list_gateways(self):
                return {"items": [{"gatewayId": "gw-1", "name": "retail-pricing-gateway"}]}

            def get_gateway(self, gatewayIdentifier):
                return {"status": "READY", "gatewayUrl": GATEWAY_URL}

            def create_gateway_target(self, **kwargs):
                raise client_error("ConflictException")

            def list_gateway_targets(self, gatewayIdentifier):
                return {"items": [{"name": n, "targetId": f"t-{n}"} for n in
                                  ("competitor-api", "erp-pos", "market-signals", "cost-finance")]}

            def synchronize_gateway_targets(self, **kwargs):
                raise client_error("ValidationException", "Target type LAMBDA is not supported for synchronization")

        monkeypatch.setattr(setup_gateway.boto3, "client", lambda name, **kw: (
            Control() if name == "bedrock-agentcore-control"
            else SimpleNamespace(get_caller_identity=lambda: {"Account": ACCOUNT})
        ))
        for var in ("COMPETITOR_API_LAMBDA_ARN", "ERP_POS_LAMBDA_ARN", "MARKET_SIGNALS_LAMBDA_ARN", "COST_FINANCE_LAMBDA_ARN"):
            monkeypatch.setenv(var, f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:x")

        assert setup_gateway.setup_gateway(REGION) == "gw-1"

        out = capsys.readouterr().out
        assert f"export AGENTCORE_GATEWAY_ENDPOINT={GATEWAY_MCP}" in out
        assert "<gateway-endpoint-url>" not in out


# ---------------------------------------------------------------------------
# Runtime code: guardrail, gateway tools, memory
# ---------------------------------------------------------------------------

from strands import Agent  # noqa: E402
from strands.models import BedrockModel  # noqa: E402
from strands.tools.mcp import MCPClient  # noqa: E402

from backend.agents.agentcore import guardrail_config  # noqa: E402
from backend.agents.agentcore import memory_config  # noqa: E402

SPECIALIST_RUNTIMES = [
    ("competitive_intelligence_runtime", "competitive_intelligence"),
    ("demand_forecasting_runtime", "demand_forecasting"),
    ("market_intelligence_runtime", "market_intelligence"),
    ("strategy_synthesis_runtime", "strategy_synthesis"),
]


class TestGuardrailConfig:
    def test_defaults_attach_the_default_guardrail_to_the_model(self, monkeypatch):
        for var in ("DISABLE_BEDROCK_GUARDRAILS", "BEDROCK_GUARDRAIL_ID", "BEDROCK_GUARDRAIL_VERSION"):
            monkeypatch.delenv(var, raising=False)

        assert guardrail_config.get_guardrail_model_kwargs() == {
            "guardrail_id": guardrail_config.GUARDRAIL_ID,
            "guardrail_version": guardrail_config.GUARDRAIL_VERSION,
            "guardrail_trace": "enabled",
        }

    def test_environment_overrides_the_guardrail(self, monkeypatch):
        monkeypatch.delenv("DISABLE_BEDROCK_GUARDRAILS", raising=False)
        monkeypatch.setenv("BEDROCK_GUARDRAIL_ID", "gr-abc")
        monkeypatch.setenv("BEDROCK_GUARDRAIL_VERSION", "9")

        kwargs = guardrail_config.get_guardrail_model_kwargs()

        assert kwargs["guardrail_id"] == "gr-abc" and kwargs["guardrail_version"] == "9"

    def test_kill_switch_returns_no_kwargs(self, monkeypatch):
        monkeypatch.setenv("DISABLE_BEDROCK_GUARDRAILS", "true")

        assert guardrail_config.get_guardrail_model_kwargs() == {}

    def test_empty_guardrail_id_returns_no_kwargs(self, monkeypatch):
        monkeypatch.delenv("DISABLE_BEDROCK_GUARDRAILS", raising=False)
        monkeypatch.setenv("BEDROCK_GUARDRAIL_ID", "")

        assert guardrail_config.get_guardrail_model_kwargs() == {}

    def test_kwargs_are_valid_bedrock_model_config(self, monkeypatch):
        monkeypatch.delenv("DISABLE_BEDROCK_GUARDRAILS", raising=False)

        model = BedrockModel(model_id="m", region_name=REGION, **guardrail_config.get_guardrail_model_kwargs())

        assert model.get_config()["guardrail_id"] == guardrail_config.get_guardrail_id()

    def test_strands_agent_has_no_guardrail_parameter(self):
        """Why the guardrail must go on the model: Agent(**kwargs) raised TypeError."""
        parameters = inspect.signature(Agent.__init__).parameters
        assert "guardrail_config" not in parameters
        assert not any(p.kind is p.VAR_KEYWORD for p in parameters.values())


def make_signature_checking_agent(record):
    """Fake Agent that rejects arguments the real strands.Agent would reject."""
    signature = inspect.signature(Agent.__init__)

    class FakeAgent:
        def __init__(self, **kwargs):
            signature.bind(None, **kwargs)  # TypeError on unknown kwargs, like the real class
            record["kwargs"] = kwargs
            record["cleaned_up"] = False

        def __call__(self, prompt):
            record["prompt"] = prompt
            return "analysis"

        def cleanup(self):
            record["cleaned_up"] = True

    return FakeAgent


@pytest.fixture
def region_env(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    monkeypatch.delenv("DISABLE_BEDROCK_GUARDRAILS", raising=False)


class TestSpecialistRuntimesGatewayPath:
    @pytest.mark.parametrize("module_name,agent_name", SPECIALIST_RUNTIMES)
    def test_gateway_path_builds_a_working_agent(self, monkeypatch, region_env, module_name, agent_name):
        runtime = importlib.import_module(f"backend.agents.agentcore.{module_name}")
        record = {}
        monkeypatch.setattr(runtime, "GATEWAY_ENDPOINT", GATEWAY_MCP)
        monkeypatch.setattr(runtime, "Agent", make_signature_checking_agent(record))
        monkeypatch.setattr(runtime, "create_session_manager", lambda **kw: None)

        result = runtime.invoke({"prompt": "analyse", "context": {"product_id": "p1"}})

        assert result["status"] == "success", result
        assert result["agent"] == agent_name
        kwargs = record["kwargs"]
        # Gateway tools: an MCPClient tool provider pointed at the gateway's MCP URL.
        (tool,) = kwargs["tools"]
        assert isinstance(tool, MCPClient)
        # The guardrail rides on the model, not on the Agent.
        assert isinstance(kwargs["model"], BedrockModel)
        assert kwargs["model"].get_config()["guardrail_id"] == guardrail_config.get_guardrail_id()
        assert set(kwargs) == {"model", "system_prompt", "tools", "session_manager"}
        # The per-invocation MCP connection is released.
        assert record["cleaned_up"] is True

    @pytest.mark.parametrize("module_name,agent_name", SPECIALIST_RUNTIMES)
    def test_cleanup_runs_even_if_the_model_call_fails(self, monkeypatch, region_env, module_name, agent_name):
        runtime = importlib.import_module(f"backend.agents.agentcore.{module_name}")
        record = {}
        fake = make_signature_checking_agent(record)
        fake.__call__ = lambda self, prompt: (_ for _ in ()).throw(RuntimeError("model down"))
        monkeypatch.setattr(runtime, "GATEWAY_ENDPOINT", GATEWAY_MCP)
        monkeypatch.setattr(runtime, "Agent", fake)
        monkeypatch.setattr(runtime, "create_session_manager", lambda **kw: None)

        result = runtime.invoke({"prompt": "analyse"})

        assert result["status"] == "error"
        assert record["cleaned_up"] is True

    @pytest.mark.parametrize("module_name,agent_name", SPECIALIST_RUNTIMES)
    def test_kill_switch_builds_the_model_without_a_guardrail(self, monkeypatch, region_env, module_name, agent_name):
        runtime = importlib.import_module(f"backend.agents.agentcore.{module_name}")
        record = {}
        monkeypatch.setenv("DISABLE_BEDROCK_GUARDRAILS", "true")
        monkeypatch.setattr(runtime, "GATEWAY_ENDPOINT", GATEWAY_MCP)
        monkeypatch.setattr(runtime, "Agent", make_signature_checking_agent(record))
        monkeypatch.setattr(runtime, "create_session_manager", lambda **kw: None)

        assert runtime.invoke({"prompt": "x"})["status"] == "success"
        assert "guardrail_id" not in record["kwargs"]["model"].get_config()

    def test_mcp_client_accepts_the_gateway_url(self):
        """MCPClient.streamable_http (used before) does not exist; url= does."""
        assert not hasattr(MCPClient, "streamable_http")
        assert "url" in inspect.signature(MCPClient.__init__).parameters
        MCPClient(url=GATEWAY_MCP)  # constructing does not connect

    def test_container_requirements_floor_strands_at_the_release_that_added_mcpclient_url(self):
        text = (PROJECT_ROOT / "backend/agents/agentcore/requirements.txt").read_text()
        assert "strands-agents>=1.53.0" in text


class TestImplementationMonitoringRuntime:
    def test_agent_is_built_with_a_guardrailed_model(self, monkeypatch, region_env):
        runtime = importlib.import_module("backend.agents.agentcore.implementation_monitoring_runtime")
        record = {}
        monkeypatch.setattr("strands.Agent", make_signature_checking_agent(record))
        monkeypatch.setattr(runtime, "create_session_manager", lambda **kw: None)

        result = runtime.invoke({"prompt": "monitor", "context": {"scenario_id": "s1"}})

        assert result["status"] == "success", result
        assert isinstance(record["kwargs"]["model"], BedrockModel)
        assert record["kwargs"]["model"].get_config()["guardrail_id"] == guardrail_config.get_guardrail_id()


class TestOrchestratorNeedsSpecialistArns:
    ENV = {name: ALL_ARNS[a] for a, name in
           [(a, deploy_agentcore.AGENT_ARN_ENV_VARS[a]) for a in deploy_agentcore.SPECIALIST_AGENTS]}

    def import_fresh(self):
        sys.modules.pop("backend.agents.agentcore.orchestrator_runtime", None)
        return importlib.import_module("backend.agents.agentcore.orchestrator_runtime")

    def test_import_fails_without_the_arn_variables(self, monkeypatch):
        for name in self.ENV:
            monkeypatch.delenv(name, raising=False)

        with pytest.raises(KeyError):
            self.import_fresh()

    def test_import_succeeds_with_the_variables_deploy_agentcore_sets(self, monkeypatch):
        for name, value in self.ENV.items():
            monkeypatch.setenv(name, value)

        runtime = self.import_fresh()

        assert runtime.SS_ARN == ALL_ARNS["strategy-synthesis"]
        sys.modules.pop("backend.agents.agentcore.orchestrator_runtime", None)


class TestMemoryConfig:
    def test_missing_memory_id_is_logged_visibly(self, monkeypatch, caplog):
        monkeypatch.setattr(memory_config, "MEMORY_ID", "")

        with caplog.at_level(logging.WARNING, logger=memory_config.logger.name):
            assert memory_config.create_session_manager(session_id="s", actor_id="a") is None

        assert any(
            r.levelno >= logging.WARNING and "AGENTCORE_MEMORY_ID not set; memory disabled" in r.getMessage()
            for r in caplog.records
        )

    def test_memory_id_builds_the_session_manager(self, monkeypatch):
        captured = {}

        class FakeSessionManager:
            def __init__(self, agentcore_memory_config, region_name=None, **kwargs):
                captured["config"] = agentcore_memory_config
                captured["region"] = region_name

        monkeypatch.setattr(memory_config, "MEMORY_ID", MEMORY_ID)
        monkeypatch.setattr(
            "bedrock_agentcore.memory.integrations.strands.session_manager.AgentCoreMemorySessionManager",
            FakeSessionManager,
        )

        manager = memory_config.create_session_manager(session_id="session-1", actor_id="pricing-system")

        assert isinstance(manager, FakeSessionManager)
        assert captured["config"].memory_id == MEMORY_ID
        assert captured["config"].session_id == "session-1"
        assert captured["config"].actor_id == "pricing-system"
