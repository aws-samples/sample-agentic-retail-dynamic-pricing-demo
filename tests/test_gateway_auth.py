"""SigV4 (AWS_IAM) auth for the AgentCore Gateway: client signing and the safe cutover.

A gateway's authorizer cannot be changed, so the cutover replaces the gateway:
- backend/agents/agentcore/gateway_auth.py signs every MCP request, including
  through strands' adapter for the mcp 2.x (httpx2) transport.
- scripts/setup_gateway.py creates retail-pricing-gateway-iam with AWS_IAM on its
  own role, and keeps the open gateway of earlier versions working on that role.
- scripts/secure_gateway.py checks the new gateway, then deletes the open one,
  but only once every runtime signs its calls to the new one.
- scripts/verify_deployment.py fails while the open gateway exists.
- scripts/create_agentcore_role.py: confused-deputy conditions and a gateway role
  that can only invoke the MCP Lambdas.
"""

from __future__ import annotations

import asyncio
import datetime
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import botocore.auth
import httpx
import pytest
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import create_agentcore_role  # noqa: E402
import secure_gateway  # noqa: E402
import setup_gateway  # noqa: E402
from backend.agents.agentcore import gateway_auth  # noqa: E402

REGION = "us-east-1"
ACCOUNT = "123456789012"
GATEWAY_ID = "retail-pricing-gateway-iam-abc1234567"
GATEWAY_URL = f"https://{GATEWAY_ID}.gateway.bedrock-agentcore.{REGION}.amazonaws.com"
GATEWAY_MCP = f"{GATEWAY_URL}/mcp"
RUNTIME_ROLE = f"arn:aws:iam::{ACCOUNT}:role/RetailPricingAgentCoreRole"
GATEWAY_ROLE = f"arn:aws:iam::{ACCOUNT}:role/RetailPricingGatewayRole"
FIXED_NOW = datetime.datetime(2026, 10, 30, 12, 0, 0)
CREDS = Credentials("AKIDEXAMPLE", "secret", token="session-token")
BODY = b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}'


@pytest.fixture
def fixed_clock(monkeypatch):
    monkeypatch.setattr(botocore.auth, "get_current_datetime", lambda: FIXED_NOW)


class FakeSession:
    def __init__(self, credentials=CREDS):
        self.credentials = credentials
        self.calls = 0

    def get_credentials(self):
        self.calls += 1
        return self.credentials


def expected_signature_headers(method: str, url: str, body: bytes) -> dict:
    """Headers botocore produces for the same request, signed independently."""
    request = AWSRequest(method=method, url=url, data=body)
    SigV4Auth(CREDS, "bedrock-agentcore", REGION).add_auth(request)
    return dict(request.headers)


def sign(auth, request: httpx.Request) -> httpx.Request:
    flow = auth.sync_auth_flow(request)
    signed = next(flow)
    return signed


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------


class TestGatewaySigV4Auth:
    def test_region_comes_from_the_gateway_url(self, monkeypatch):
        monkeypatch.delenv("AWS_REGION", raising=False)
        assert gateway_auth.region_from_gateway_url(GATEWAY_MCP) == REGION
        assert gateway_auth.region_from_gateway_url(GATEWAY_MCP.replace(REGION, "eu-central-1")) == "eu-central-1"

    def test_region_falls_back_to_the_environment_then_fails(self, monkeypatch):
        monkeypatch.setenv("AWS_REGION", "eu-west-1")
        assert gateway_auth.region_from_gateway_url("https://localhost:8080/mcp") == "eu-west-1"
        monkeypatch.delenv("AWS_REGION")
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        with pytest.raises(ValueError, match="Region"):
            gateway_auth.region_from_gateway_url("https://localhost:8080/mcp")

    def test_signature_matches_botocore_and_covers_only_stable_headers(self, fixed_clock):
        auth = gateway_auth.GatewaySigV4Auth(REGION, session=FakeSession())
        request = httpx.Request("POST", GATEWAY_MCP, content=BODY,
                                headers={"Content-Type": "application/json", "mcp-session-id": "s1"})

        signed = sign(auth, request)

        expected = expected_signature_headers("POST", GATEWAY_MCP, BODY)
        assert signed.headers["Authorization"] == expected["Authorization"]
        assert signed.headers["X-Amz-Date"] == expected["X-Amz-Date"]
        assert signed.headers["X-Amz-Security-Token"] == "session-token"
        assert "SignedHeaders=host;x-amz-date;x-amz-security-token," in signed.headers["Authorization"]
        assert f"/{REGION}/bedrock-agentcore/aws4_request" in signed.headers["Authorization"]
        # Other headers are passed through untouched.
        assert signed.headers["mcp-session-id"] == "s1"

    def test_the_body_is_part_of_the_signature(self, fixed_clock):
        auth = gateway_auth.GatewaySigV4Auth(REGION, session=FakeSession())
        a = sign(auth, httpx.Request("POST", GATEWAY_MCP, content=BODY))
        b = sign(auth, httpx.Request("POST", GATEWAY_MCP, content=BODY.replace(b"tools/list", b"tools/call")))
        assert a.headers["Authorization"] != b.headers["Authorization"]

    @pytest.mark.parametrize("method", ["GET", "DELETE"])
    def test_bodyless_requests_are_signed_too(self, fixed_clock, method):
        """mcp opens a GET event stream and ends sessions with DELETE."""
        signed = sign(gateway_auth.GatewaySigV4Auth(REGION, session=FakeSession()), httpx.Request(method, GATEWAY_MCP))
        assert signed.headers["Authorization"] == expected_signature_headers(method, GATEWAY_MCP, b"")["Authorization"]

    def test_credentials_are_read_for_every_request(self, fixed_clock):
        session = FakeSession()
        auth = gateway_auth.GatewaySigV4Auth(REGION, session=session)
        sign(auth, httpx.Request("POST", GATEWAY_MCP, content=BODY))
        sign(auth, httpx.Request("POST", GATEWAY_MCP, content=BODY))
        assert session.calls == 2

    def test_missing_credentials_fail_loudly(self):
        auth = gateway_auth.GatewaySigV4Auth(REGION, session=FakeSession(credentials=None))
        with pytest.raises(RuntimeError, match="No AWS credentials"):
            sign(auth, httpx.Request("POST", GATEWAY_MCP, content=BODY))


class TestThroughTheStrandsHttpx2Adapter:
    """mcp 2.x uses httpx2; strands adapts an httpx.Auth and forwards the body only if requires_request_body."""

    def run_adapter(self, auth):
        import httpx2
        from strands.tools.mcp._compat import _wrap_auth_for_httpx2

        adapter = _wrap_auth_for_httpx2(auth)
        request = httpx2.Request("POST", GATEWAY_MCP, content=BODY, headers={"Content-Type": "application/json"})

        async def first_step():
            flow = adapter.async_auth_flow(request)
            return await flow.__anext__()

        return asyncio.run(first_step())

    def test_the_adapter_forwards_the_body_so_the_signature_is_valid(self, fixed_clock):
        signed = self.run_adapter(gateway_auth.GatewaySigV4Auth(REGION, session=FakeSession()))

        assert signed.headers["Authorization"] == expected_signature_headers("POST", GATEWAY_MCP, BODY)["Authorization"]
        assert signed.read() == BODY

    def test_without_requires_request_body_the_signature_would_be_wrong(self, fixed_clock):
        class BodylessAuth(gateway_auth.GatewaySigV4Auth):
            requires_request_body = False

        signed = self.run_adapter(BodylessAuth(REGION, session=FakeSession()))

        assert signed.headers["Authorization"] != expected_signature_headers("POST", GATEWAY_MCP, BODY)["Authorization"]


class TestClientFactory:
    @pytest.fixture
    def recorded(self, monkeypatch):
        calls = []
        monkeypatch.setattr(gateway_auth, "MCPClient", lambda **kw: calls.append(kw) or SimpleNamespace(**kw))
        return calls

    def test_default_signs(self, monkeypatch, recorded):
        monkeypatch.delenv(gateway_auth.GATEWAY_AUTH_ENV, raising=False)
        gateway_auth.create_gateway_mcp_client(GATEWAY_MCP)
        (kwargs,) = recorded
        assert kwargs["url"] == GATEWAY_MCP
        assert isinstance(kwargs["auth_provider"], gateway_auth.GatewaySigV4Auth)
        assert kwargs["auth_provider"].region == REGION

    def test_none_sends_unsigned_requests(self, monkeypatch, recorded):
        monkeypatch.setenv(gateway_auth.GATEWAY_AUTH_ENV, "none")
        gateway_auth.create_gateway_mcp_client(GATEWAY_MCP)
        assert recorded == [{"url": GATEWAY_MCP}]

    def test_unknown_mode_is_rejected(self, monkeypatch, recorded):
        monkeypatch.setenv(gateway_auth.GATEWAY_AUTH_ENV, "OAUTH")
        with pytest.raises(ValueError):
            gateway_auth.create_gateway_mcp_client(GATEWAY_MCP)

    def test_a_real_client_can_be_built(self, monkeypatch):
        from strands.tools.mcp import MCPClient

        monkeypatch.delenv(gateway_auth.GATEWAY_AUTH_ENV, raising=False)
        assert isinstance(gateway_auth.create_gateway_mcp_client(GATEWAY_MCP), MCPClient)

    @pytest.mark.parametrize("module", ["competitive_intelligence", "demand_forecasting", "market_intelligence",
                                        "strategy_synthesis"])
    def test_every_gateway_runtime_uses_the_signing_client(self, module):
        source = (PROJECT_ROOT / f"backend/agents/agentcore/{module}_runtime.py").read_text()
        assert "create_gateway_mcp_client(GATEWAY_ENDPOINT)" in source
        assert "MCPClient(url=" not in source


# ---------------------------------------------------------------------------
# secure_gateway: verify the SigV4 gateway, then delete the open one
# ---------------------------------------------------------------------------


def gateway_record(gateway_id: str, name: str, authorizer: str, role: str) -> dict:
    """What GetGateway returns (minus status, which FakeControl adds)."""
    return {
        "gatewayId": gateway_id,
        "gatewayArn": f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:gateway/{gateway_id}",
        "gatewayUrl": f"https://{gateway_id}.gateway.bedrock-agentcore.{REGION}.amazonaws.com",
        "name": name,
        "description": "Gateway for Retail Dynamic Pricing MCP tools",
        "roleArn": role,
        "protocolConfiguration": {"mcp": {"searchType": "SEMANTIC"}},
        "authorizerType": authorizer,
        "createdAt": "t0",
        "updatedAt": "t1",
        "workloadIdentityDetails": {"workloadIdentityArn": "arn:x"},
    }


LEGACY_ID = "retail-pricing-gateway-xyz7654321"
SIGV4_GATEWAY = gateway_record(GATEWAY_ID, secure_gateway.GATEWAY_NAME, "AWS_IAM", GATEWAY_ROLE)
OPEN_GATEWAY = gateway_record(LEGACY_ID, secure_gateway.LEGACY_GATEWAY_NAME, "NONE", RUNTIME_ROLE)
LEGACY_MCP = f"{OPEN_GATEWAY['gatewayUrl']}/mcp"
SIGNING_ENV = {"AGENTCORE_GATEWAY_ENDPOINT": GATEWAY_MCP, "AGENTCORE_GATEWAY_AUTH": "AWS_IAM"}
TARGETS = [{"targetId": "T1", "name": "competitor-api", "status": "READY"},
           {"targetId": "T2", "name": "erp-pos", "status": "READY"}]


def not_found(operation: str):
    from botocore.exceptions import ClientError

    return ClientError({"Error": {"Code": "ResourceNotFoundException", "Message": "not found"}}, operation)


class FakeControl:
    """bedrock-agentcore-control: gateways with targets, and the runtimes that call them.

    Deletions take one poll: a deleted target is listed once as DELETING, and a
    deleted gateway reports DELETING once before GetGateway raises not found.
    """

    def __init__(self, gateways=(), targets=None, runtime_env=None, runtimes=secure_gateway.GATEWAY_CLIENT_RUNTIMES,
                 statuses=None, drop_on_update=(), endpoint=None, delete_status="DELETING", stuck_targets=False):
        self.gateways = {g["gatewayId"]: dict(g) for g in gateways}
        self.targets = {gid: [dict(t) for t in ts] for gid, ts in (targets or {}).items()}
        self.runtime_env = dict(SIGNING_ENV if runtime_env is None else runtime_env)
        self.runtimes = runtimes
        self.statuses = {gid: list(s) for gid, s in (statuses or {}).items()}
        self.drop_on_update = drop_on_update
        self.endpoint = endpoint or {"liveVersion": "7", "targetVersion": "7"}
        self.delete_status = delete_status
        self.stuck_targets = stuck_targets
        self.calls: list[tuple] = []
        self.updates: list[dict] = []
        self.created_targets: list[tuple[str, str]] = []

    # gateways
    def list_gateways(self, **kw):
        return {"items": [{"gatewayId": g["gatewayId"], "name": g["name"]} for g in self.gateways.values()]}

    def get_gateway(self, gatewayIdentifier):
        if gatewayIdentifier not in self.gateways:
            raise not_found("GetGateway")
        gateway = self.gateways[gatewayIdentifier]
        if gateway.get("_deleting"):
            if self.delete_status != "DELETING":
                return {**gateway, "status": self.delete_status}
            del self.gateways[gatewayIdentifier]
            return {**gateway, "status": "DELETING"}
        sequence = self.statuses.get(gatewayIdentifier)
        status = (sequence.pop(0) if len(sequence) > 1 else sequence[0]) if sequence else "READY"
        return {k: v for k, v in {**gateway, "status": status}.items() if not k.startswith("_")}

    def create_gateway(self, **kw):
        gateway_id = f"{kw['name']}-new0000001"
        self.calls.append(("create_gateway", kw["name"]))
        self.gateways[gateway_id] = {**gateway_record(gateway_id, kw["name"], kw["authorizerType"], kw["roleArn"]),
                                     "protocolConfiguration": kw.get("protocolConfiguration")}
        self.created = kw
        return {"gatewayId": gateway_id}

    def update_gateway(self, **request):
        self.updates.append(request)
        gateway_id = request["gatewayIdentifier"]
        accepted = {k: v for k, v in request.items() if k != "gatewayIdentifier" and k not in self.drop_on_update}
        kept = {k: v for k, v in self.gateways[gateway_id].items() if k not in secure_gateway.UPDATE_FIELDS}
        self.gateways[gateway_id] = {**kept, **accepted}

    def delete_gateway(self, gatewayIdentifier):
        if [t for t in self.targets.get(gatewayIdentifier, [])]:
            raise AssertionError("DeleteGateway called while the gateway still has targets")
        self.calls.append(("delete_gateway", gatewayIdentifier))
        self.gateways[gatewayIdentifier]["_deleting"] = True
        return {"gatewayId": gatewayIdentifier, "status": "DELETING"}

    # targets
    def list_gateway_targets(self, gatewayIdentifier, **kw):
        items = [dict(t) for t in self.targets.get(gatewayIdentifier, [])]
        if not self.stuck_targets:  # a target listed as DELETING is gone on the next call
            self.targets[gatewayIdentifier] = [t for t in self.targets.get(gatewayIdentifier, [])
                                               if t["status"] != "DELETING"]
        return {"items": items}

    def delete_gateway_target(self, gatewayIdentifier, targetId):
        self.calls.append(("delete_gateway_target", gatewayIdentifier, targetId))
        for target in self.targets[gatewayIdentifier]:
            if target["targetId"] == targetId:
                target["status"] = "DELETING"

    def create_gateway_target(self, **kw):
        self.created_targets.append((kw["gatewayIdentifier"], kw["name"]))
        return {"targetId": kw["name"]}

    def synchronize_gateway_targets(self, **kw):
        return {}

    # runtimes
    def list_agent_runtimes(self, **kw):
        return {"agentRuntimes": [{"agentRuntimeName": n, "agentRuntimeId": f"{n}-id"} for n in self.runtimes]}

    def get_agent_runtime_endpoint(self, agentRuntimeId, endpointName):
        return dict(self.endpoint)

    def get_agent_runtime(self, agentRuntimeId, agentRuntimeVersion):
        env = self.runtime_env.get(agentRuntimeId) if agentRuntimeId in self.runtime_env else self.runtime_env
        return {"environmentVariables": env}


class TestNames:
    def test_both_gateways_are_covered_by_the_iam_scoping(self):
        import fnmatch

        pattern = create_agentcore_role.gateway_trust_policy(ACCOUNT, REGION)["Statement"][0]["Condition"][
            "ArnLike"]["aws:SourceArn"]
        for gateway in (SIGV4_GATEWAY, OPEN_GATEWAY):
            assert fnmatch.fnmatchcase(gateway["gatewayArn"], pattern)

    def test_names_are_valid_gateway_names(self):
        import re

        for name in (secure_gateway.GATEWAY_NAME, secure_gateway.LEGACY_GATEWAY_NAME):
            assert re.fullmatch(r"([0-9a-zA-Z][-]?){1,48}", name)
        assert secure_gateway.GATEWAY_NAME != secure_gateway.LEGACY_GATEWAY_NAME

    def test_every_script_uses_the_same_gateway(self):
        import deploy_agentcore
        import verify_deployment

        assert deploy_agentcore.DEFAULT_GATEWAY_NAME == secure_gateway.GATEWAY_NAME
        assert verify_deployment.GATEWAY_NAME == secure_gateway.GATEWAY_NAME


class TestBuildUpdateRequest:
    def test_keeps_every_setting_and_changes_only_the_role(self):
        request = secure_gateway.build_update_request(OPEN_GATEWAY, role_arn=GATEWAY_ROLE)

        assert request == {
            "gatewayIdentifier": LEGACY_ID,
            "name": "retail-pricing-gateway",
            "description": "Gateway for Retail Dynamic Pricing MCP tools",
            "roleArn": GATEWAY_ROLE,
            "protocolConfiguration": {"mcp": {"searchType": "SEMANTIC"}},
            "authorizerType": "NONE",  # required by UpdateGateway, and cannot change
        }

    def test_protocol_type_is_never_sent(self):
        """UpdateGateway rejects protocolType on an existing gateway, even with the same value (live)."""
        request = secure_gateway.build_update_request({**OPEN_GATEWAY, "protocolType": "MCP"}, role_arn=GATEWAY_ROLE)
        assert "protocolType" not in request

    def test_only_update_gateway_fields_are_sent(self):
        import boto3

        model = boto3.client("bedrock-agentcore-control", region_name=REGION).meta.service_model
        members = set(model.operation_model("UpdateGateway").input_shape.members)
        assert set(secure_gateway.UPDATE_FIELDS) | {"gatewayIdentifier"} == members
        request = secure_gateway.build_update_request(
            {**OPEN_GATEWAY, "kmsKeyArn": "arn:aws:kms:k", "exceptionLevel": "DEBUG",
             "interceptorConfigurations": [{"x": 1}]}, role_arn=GATEWAY_ROLE)
        assert set(request) <= members
        assert request["kmsKeyArn"] == "arn:aws:kms:k" and request["exceptionLevel"] == "DEBUG"

    def test_jwt_settings_are_kept(self):
        gateway = {**OPEN_GATEWAY, "authorizerType": "CUSTOM_JWT", "authorizerConfiguration": {"customJWTAuthorizer": {}}}
        request = secure_gateway.build_update_request(gateway, role_arn=GATEWAY_ROLE)
        assert request["authorizerType"] == "CUSTOM_JWT"
        assert request["authorizerConfiguration"] == {"customJWTAuthorizer": {}}


class TestMoveGatewayToRole:
    @pytest.fixture(autouse=True)
    def no_sleep(self, monkeypatch):
        monkeypatch.setattr(secure_gateway.time, "sleep", lambda s: None)

    def test_moves_the_role_and_keeps_the_rest(self):
        control = FakeControl(gateways=[OPEN_GATEWAY])
        updated = secure_gateway.move_gateway_to_role(control, control.get_gateway(LEGACY_ID), GATEWAY_ROLE)
        assert updated["roleArn"] == GATEWAY_ROLE
        assert updated["authorizerType"] == "NONE"
        assert updated["protocolConfiguration"] == {"mcp": {"searchType": "SEMANTIC"}}

    def test_update_unsuccessful_is_a_failure(self):
        control = FakeControl(gateways=[OPEN_GATEWAY], statuses={LEGACY_ID: ["UPDATING", "UPDATE_UNSUCCESSFUL"]})
        with pytest.raises(secure_gateway.GatewayError, match="UPDATE_UNSUCCESSFUL"):
            secure_gateway.wait_until_ready(control, LEGACY_ID, interval_seconds=0)

    def test_timeout_is_a_failure(self, monkeypatch):
        clock = iter([0, 0, 1000])
        monkeypatch.setattr(secure_gateway.time, "monotonic", lambda: next(clock))
        control = FakeControl(gateways=[OPEN_GATEWAY], statuses={LEGACY_ID: ["UPDATING"]})
        with pytest.raises(secure_gateway.GatewayError, match="Timed out"):
            secure_gateway.wait_until_ready(control, LEGACY_ID, interval_seconds=0)

    def test_a_setting_lost_in_the_update_is_detected(self):
        control = FakeControl(gateways=[OPEN_GATEWAY], drop_on_update=("protocolConfiguration",))
        with pytest.raises(secure_gateway.GatewayError, match="protocolConfiguration changed"):
            secure_gateway.move_gateway_to_role(control, control.get_gateway(LEGACY_ID), GATEWAY_ROLE)


class TestSecureGateway:
    @pytest.fixture
    def run(self, monkeypatch):
        checks = []
        sleeps = []

        def go(control, problems=()):
            """problems: one list per check attempt (the last repeats), or a flat list for every attempt."""
            rounds = [list(p) for p in problems] if problems and isinstance(problems[0], (list, tuple)) else [
                list(problems)]
            monkeypatch.setattr(secure_gateway.boto3, "client", lambda *a, **k: control)
            monkeypatch.setattr(secure_gateway.time, "sleep", lambda s: sleeps.append(s))

            def check(gateway, **kw):
                checks.append(gateway["gatewayId"])
                return rounds.pop(0) if len(rounds) > 1 else rounds[0]

            monkeypatch.setattr(secure_gateway, "check_gateway_auth", check)
            return secure_gateway.secure_gateway(REGION)

        go.checks = checks
        go.sleeps = sleeps
        return go

    def test_deletes_the_open_gateway_once_every_agent_signs_its_calls_to_the_new_one(self, run):
        control = FakeControl(gateways=[SIGV4_GATEWAY, OPEN_GATEWAY], targets={LEGACY_ID: TARGETS})

        gateway = run(control)

        assert gateway["gatewayId"] == GATEWAY_ID
        assert LEGACY_ID not in control.gateways and GATEWAY_ID in control.gateways
        assert control.calls == [
            ("delete_gateway_target", LEGACY_ID, "T1"),
            ("delete_gateway_target", LEGACY_ID, "T2"),
            ("delete_gateway", LEGACY_ID),
        ]
        assert control.updates == []
        assert run.checks == [GATEWAY_ID]

    def test_the_new_gateway_is_checked_before_anything_is_deleted(self, run):
        control = FakeControl(gateways=[SIGV4_GATEWAY, OPEN_GATEWAY], targets={LEGACY_ID: TARGETS})
        with pytest.raises(secure_gateway.GatewayError, match="unsigned tools/list returned HTTP 200"):
            run(control, problems=["unsigned tools/list returned HTTP 200"])
        assert control.calls == []
        assert len(run.checks) == 6  # retried, then failed

    def test_checks_are_retried_while_a_new_gateway_settles(self, run):
        control = FakeControl(gateways=[SIGV4_GATEWAY])
        run(control, problems=[["signed tools/list returned HTTP 503"], []])
        assert run.checks == [GATEWAY_ID, GATEWAY_ID]
        assert run.sleeps == [10]

    def test_refuses_while_an_agent_still_uses_the_open_gateway(self, run):
        control = FakeControl(gateways=[SIGV4_GATEWAY, OPEN_GATEWAY], targets={LEGACY_ID: TARGETS},
                              runtime_env={"AGENTCORE_GATEWAY_ENDPOINT": LEGACY_MCP})
        with pytest.raises(secure_gateway.GatewayError, match="would lose their MCP tools") as error:
            run(control)
        assert "retailPricing_competitiveIntelligence v7: AGENTCORE_GATEWAY_ENDPOINT=" in str(error.value)
        assert "--skip-agents" in str(error.value)
        assert control.calls == [] and LEGACY_ID in control.gateways

    def test_refuses_while_an_agent_calls_the_new_gateway_unsigned(self, run):
        control = FakeControl(gateways=[SIGV4_GATEWAY, OPEN_GATEWAY],
                              runtime_env={"AGENTCORE_GATEWAY_ENDPOINT": GATEWAY_MCP})
        with pytest.raises(secure_gateway.GatewayError, match="unsigned MCP calls"):
            run(control)
        assert control.calls == []

    def test_refuses_while_an_endpoint_is_still_moving_to_a_new_version(self, run):
        control = FakeControl(gateways=[SIGV4_GATEWAY, OPEN_GATEWAY],
                              endpoint={"liveVersion": "6", "targetVersion": "7"})
        with pytest.raises(secure_gateway.GatewayError, match="still moving from v6 to v7"):
            run(control)
        assert control.calls == []

    def test_agents_that_are_not_deployed_do_not_block_the_deletion(self, run):
        control = FakeControl(gateways=[SIGV4_GATEWAY, OPEN_GATEWAY], runtimes=())
        run(control)
        assert ("delete_gateway", LEGACY_ID) in control.calls

    def test_without_an_open_gateway_it_only_checks(self, run):
        control = FakeControl(gateways=[SIGV4_GATEWAY], runtime_env={})
        run(control)
        assert control.calls == [] and run.checks == [GATEWAY_ID]

    def test_a_missing_sigv4_gateway_fails(self, run):
        with pytest.raises(secure_gateway.GatewayError, match="not found"):
            run(FakeControl(gateways=[OPEN_GATEWAY]))

    def test_a_sigv4_gateway_name_without_aws_iam_fails(self, run):
        control = FakeControl(gateways=[{**SIGV4_GATEWAY, "authorizerType": "NONE"}, OPEN_GATEWAY])
        with pytest.raises(secure_gateway.GatewayError, match="cannot be changed"):
            run(control)
        assert control.calls == [] and run.checks == []

    def test_a_failed_deletion_fails_the_step(self, run):
        control = FakeControl(gateways=[SIGV4_GATEWAY, OPEN_GATEWAY], delete_status="FAILED")
        with pytest.raises(secure_gateway.GatewayError, match="Deleting gateway .* failed"):
            run(control)

    def test_targets_that_never_go_away_time_out(self, run, monkeypatch):
        clock = iter(range(0, 10_000, 100))
        monkeypatch.setattr(secure_gateway.time, "monotonic", lambda: next(clock))
        control = FakeControl(gateways=[SIGV4_GATEWAY, OPEN_GATEWAY], targets={LEGACY_ID: TARGETS},
                              stuck_targets=True)
        with pytest.raises(secure_gateway.GatewayError, match="Timed out .* targets"):
            run(control)
        assert ("delete_gateway", LEGACY_ID) not in control.calls


class TestCheckGatewayAuth:
    GATEWAY = {**SIGV4_GATEWAY, "status": "READY"}

    @pytest.fixture
    def probes(self, monkeypatch):
        def set_(unsigned, signed):
            monkeypatch.setattr(secure_gateway, "probe_unsigned", lambda url: unsigned)
            monkeypatch.setattr(secure_gateway, "probe_signed", lambda url, method, params=None: signed[method])
        return set_

    OK_SIGNED = {
        "tools/list": (200, {"result": {"tools": [{"name": "t"}]}}),
        "tools/call": (200, {"result": {"content": [{"type": "text", "text": "{}"}], "isError": False}}),
    }

    def test_enforced_and_working(self, probes):
        probes((403, '{"message":"Missing Authentication Token"}'), self.OK_SIGNED)
        assert secure_gateway.check_gateway_auth(self.GATEWAY) == []

    def test_an_open_gateway_is_a_problem(self, probes):
        probes((200, '{"result": {}}'), self.OK_SIGNED)
        problems = secure_gateway.check_gateway_auth({**self.GATEWAY, "authorizerType": "NONE"})
        assert any("authorizer is NONE" in p for p in problems)
        assert any("HTTP 200" in p for p in problems)

    def test_a_failing_tool_call_is_a_problem(self, probes):
        probes((401, ""), {**self.OK_SIGNED, "tools/call": (200, {"result": {"isError": True, "content": []}})})
        assert any("tools/call" in p for p in secure_gateway.check_gateway_auth(self.GATEWAY))

    def test_signed_checks_can_be_skipped(self, probes):
        probes((403, ""), {})
        assert secure_gateway.check_gateway_auth(self.GATEWAY, signed_checks=False) == []


class TestVerifyDeploymentGatewayAuth:
    ALL_RUNTIMES = ("retailPricing_competitiveIntelligence", "retailPricing_demandForecasting",
                    "retailPricing_marketIntelligence", "retailPricing_strategySynthesis",
                    "retailPricing_implementationMonitoring", "retailPricing_orchestrator")

    def verify(self, monkeypatch, control):
        import verify_deployment

        monkeypatch.setattr(verify_deployment.boto3, "client", lambda *a, **k: control)
        monkeypatch.setattr(secure_gateway, "check_gateway_auth", lambda gw, **kw: [])
        return verify_deployment.verify_gateway_auth(REGION)

    def test_passes_with_only_the_sigv4_gateway(self, monkeypatch):
        assert self.verify(monkeypatch, FakeControl(gateways=[SIGV4_GATEWAY], runtimes=self.ALL_RUNTIMES)) == (True, [])

    def test_a_remaining_open_gateway_fails(self, monkeypatch):
        passed, problems = self.verify(monkeypatch, FakeControl(gateways=[SIGV4_GATEWAY, OPEN_GATEWAY],
                                                                runtimes=self.ALL_RUNTIMES))
        assert not passed
        assert problems == [f"open gateway 'retail-pricing-gateway' ({LEGACY_ID}, inbound auth NONE) still exists: "
                            "run scripts/secure_gateway.py"]

    def test_only_the_open_gateway_fails(self, monkeypatch):
        passed, problems = self.verify(monkeypatch, FakeControl(gateways=[OPEN_GATEWAY], runtimes=self.ALL_RUNTIMES))
        assert not passed and problems == ["gateway 'retail-pricing-gateway-iam' not found"]


# ---------------------------------------------------------------------------
# setup_gateway, roles, deploy and teardown wiring
# ---------------------------------------------------------------------------


class TestSetupGateway:
    @pytest.fixture
    def setup(self, monkeypatch):
        def go(control):
            monkeypatch.setattr(setup_gateway.boto3, "client", lambda name, **kw: control if name != "sts"
                                else SimpleNamespace(get_caller_identity=lambda: {"Account": ACCOUNT}))
            monkeypatch.setattr(secure_gateway.time, "sleep", lambda s: None)
            monkeypatch.setattr(setup_gateway.time, "sleep", lambda s: None)
            monkeypatch.delenv("AGENTCORE_GATEWAY_ROLE_ARN", raising=False)
            for var in ("COMPETITOR_API_LAMBDA_ARN", "ERP_POS_LAMBDA_ARN", "MARKET_SIGNALS_LAMBDA_ARN",
                        "COST_FINANCE_LAMBDA_ARN"):
                monkeypatch.setenv(var, f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:x")
            return setup_gateway.setup_gateway(REGION)
        return go

    def test_a_new_gateway_uses_aws_iam_and_its_own_role(self, setup):
        control = FakeControl()

        gateway_id = setup(control)

        assert control.created["name"] == "retail-pricing-gateway-iam"
        assert control.created["authorizerType"] == "AWS_IAM"
        assert control.created["roleArn"] == GATEWAY_ROLE
        assert control.created["protocolConfiguration"] == {"mcp": {"searchType": "SEMANTIC"}}
        assert control.updates == []
        assert {g for g, _ in control.created_targets} == {gateway_id}
        assert len(control.created_targets) == 4

    def test_the_open_gateway_gets_the_gateway_role_and_is_otherwise_left_for_step_4_5(self, setup):
        control = FakeControl(gateways=[OPEN_GATEWAY], targets={LEGACY_ID: TARGETS})

        gateway_id = setup(control)

        assert gateway_id != LEGACY_ID and control.created["authorizerType"] == "AWS_IAM"
        (update,) = control.updates
        assert update["gatewayIdentifier"] == LEGACY_ID
        assert update["roleArn"] == GATEWAY_ROLE and update["authorizerType"] == "NONE"
        assert LEGACY_ID in control.gateways  # deleted by secure_gateway.py once the agents moved
        assert {g for g, _ in control.created_targets} == {gateway_id}

    def test_an_existing_sigv4_gateway_is_reused(self, setup):
        control = FakeControl(gateways=[SIGV4_GATEWAY])
        assert setup(control) == GATEWAY_ID
        assert control.calls == [] and control.updates == []

    def test_an_existing_sigv4_gateway_on_another_role_is_moved(self, setup):
        control = FakeControl(gateways=[{**SIGV4_GATEWAY, "roleArn": RUNTIME_ROLE}])
        setup(control)
        (update,) = control.updates
        assert update["roleArn"] == GATEWAY_ROLE and update["authorizerType"] == "AWS_IAM"

    def test_a_gateway_with_the_new_name_but_no_iam_auth_is_an_error(self, setup):
        control = FakeControl(gateways=[{**SIGV4_GATEWAY, "authorizerType": "NONE"}])
        with pytest.raises(RuntimeError, match="cannot be changed"):
            setup(control)
        assert control.created_targets == []

    def test_update_unsuccessful_counts_as_failed(self):
        assert "UPDATE_UNSUCCESSFUL" in setup_gateway._GATEWAY_FAILED_STATES


class TestRoles:
    def test_runtime_trust_is_limited_to_this_account_and_region(self):
        (stmt,) = create_agentcore_role.runtime_trust_policy(ACCOUNT, REGION)["Statement"]
        assert stmt["Principal"] == {"Service": "bedrock-agentcore.amazonaws.com"}
        assert stmt["Condition"] == {
            "StringEquals": {"aws:SourceAccount": ACCOUNT},
            "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:*"},
        }

    def test_gateway_trust_is_limited_to_the_retail_pricing_gateways(self):
        (stmt,) = create_agentcore_role.gateway_trust_policy(ACCOUNT, REGION)["Statement"]
        assert stmt["Condition"]["StringEquals"] == {"aws:SourceAccount": ACCOUNT}
        pattern = stmt["Condition"]["ArnLike"]["aws:SourceArn"]
        assert pattern == f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:gateway/retail-pricing-gateway-*"

    def test_gateway_role_can_only_invoke_the_mcp_lambdas(self):
        (stmt,) = create_agentcore_role.get_gateway_policy(ACCOUNT, REGION)["Statement"]
        assert stmt["Action"] == ["lambda:InvokeFunction"]
        assert stmt["Resource"] == [f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:rdp-mcp-*"]

    def test_runtime_role_no_longer_invokes_lambdas(self):
        policy = create_agentcore_role.get_inline_policy(ACCOUNT, REGION)
        actions = [a for s in policy["Statement"] for a in s["Action"]]
        assert not any(a.startswith("lambda:") for a in actions)
        assert "bedrock-agentcore:InvokeGateway" in actions

    def test_existing_roles_get_their_trust_and_policy_updated(self, monkeypatch):
        from botocore.exceptions import ClientError

        calls = []

        class Iam:
            def create_role(self, **kw):
                raise ClientError({"Error": {"Code": "EntityAlreadyExists"}}, "CreateRole")

            def get_role(self, RoleName):
                return {"Role": {"Arn": f"arn:aws:iam::{ACCOUNT}:role/{RoleName}"}}

            def update_assume_role_policy(self, RoleName, PolicyDocument):
                calls.append(("trust", RoleName, json.loads(PolicyDocument)))

            def put_role_policy(self, RoleName, PolicyName, PolicyDocument):
                calls.append(("policy", RoleName, PolicyName))

        clients = {"iam": Iam(), "bedrock-agentcore-control": FakeControl()}
        session = SimpleNamespace(client=lambda name, **kw: clients.get(name) or SimpleNamespace(
            get_caller_identity=lambda: {"Account": ACCOUNT}))
        monkeypatch.setattr(create_agentcore_role.time, "sleep", lambda s: None)

        runtime_arn, gateway_arn = create_agentcore_role.create_roles(session, REGION)

        assert (runtime_arn, gateway_arn) == (RUNTIME_ROLE, GATEWAY_ROLE)
        trusts = {c[1]: c[2] for c in calls if c[0] == "trust"}
        assert "aws:SourceArn" in json.dumps(trusts["RetailPricingAgentCoreRole"])
        assert "gateway/retail-pricing-gateway-*" in json.dumps(trusts["RetailPricingGatewayRole"])
        assert ("policy", "RetailPricingGatewayRole", "RetailPricingGatewayPolicy") in calls


class TestUpgradeOrder:
    """create_agentcore_role.py moves the open gateway onto the gateway role before the agents' role
    loses Lambda invoke, so the deployed agents keep their tools through Step 3 of an upgrade."""

    @pytest.fixture
    def roles(self, monkeypatch):
        calls = []

        def go(control):
            class Iam:
                def create_role(self, **kw):
                    from botocore.exceptions import ClientError
                    raise ClientError({"Error": {"Code": "EntityAlreadyExists"}}, "CreateRole")

                def get_role(self, RoleName):
                    return {"Role": {"Arn": f"arn:aws:iam::{ACCOUNT}:role/{RoleName}"}}

                def update_assume_role_policy(self, RoleName, PolicyDocument):
                    calls.append(("trust", RoleName))

                def put_role_policy(self, RoleName, PolicyName, PolicyDocument):
                    calls.append(("policy", RoleName))

            original = control.update_gateway

            def update_gateway(**request):
                calls.append(("move", request["gatewayIdentifier"], request["roleArn"]))
                return original(**request)

            control.update_gateway = update_gateway
            clients = {"iam": Iam(), "bedrock-agentcore-control": control}
            session = SimpleNamespace(client=lambda name, **kw: clients.get(name) or SimpleNamespace(
                get_caller_identity=lambda: {"Account": ACCOUNT}))
            monkeypatch.setattr(create_agentcore_role.time, "sleep", lambda s: None)
            monkeypatch.setattr(secure_gateway.time, "sleep", lambda s: None)
            return create_agentcore_role.create_roles(session, REGION)

        go.calls = calls
        return go

    def test_the_open_gateway_moves_before_the_agents_role_loses_lambda_invoke(self, roles):
        control = FakeControl(gateways=[OPEN_GATEWAY])

        assert roles(control) == (RUNTIME_ROLE, GATEWAY_ROLE)

        gateway_role = roles.calls.index(("policy", "RetailPricingGatewayRole"))
        move = roles.calls.index(("move", LEGACY_ID, GATEWAY_ROLE))
        runtime_role = roles.calls.index(("policy", "RetailPricingAgentCoreRole"))
        assert gateway_role < move < runtime_role
        assert control.gateways[LEGACY_ID]["roleArn"] == GATEWAY_ROLE
        assert control.gateways[LEGACY_ID]["authorizerType"] == "NONE"  # still serving the old agents

    def test_a_gateway_already_on_its_role_is_left_alone(self, roles):
        roles(FakeControl(gateways=[{**OPEN_GATEWAY, "roleArn": GATEWAY_ROLE}, SIGV4_GATEWAY]))
        assert not [c for c in roles.calls if c[0] == "move"]
        assert ("policy", "RetailPricingAgentCoreRole") in roles.calls

    def test_a_failed_move_leaves_the_agents_role_unchanged(self, roles):
        # find, wait and re-read see READY; after UpdateGateway the gateway is UPDATE_UNSUCCESSFUL.
        control = FakeControl(gateways=[OPEN_GATEWAY],
                              statuses={LEGACY_ID: ["READY", "READY", "READY", "UPDATE_UNSUCCESSFUL"]})

        with pytest.raises(secure_gateway.GatewayError, match="UPDATE_UNSUCCESSFUL"):
            roles(control)

        assert ("move", LEGACY_ID, GATEWAY_ROLE) in roles.calls
        assert ("policy", "RetailPricingAgentCoreRole") not in roles.calls
        assert ("trust", "RetailPricingAgentCoreRole") not in roles.calls

    def test_an_aws_error_on_the_move_becomes_a_gateway_error(self, roles):
        """For example AccessDenied on UpdateGateway or iam:PassRole: still stops before the agents' role changes."""
        from botocore.exceptions import ClientError

        control = FakeControl(gateways=[OPEN_GATEWAY])

        def denied(**request):
            raise ClientError({"Error": {"Code": "AccessDeniedException", "Message": "not authorized"}},
                              "UpdateGateway")

        control.update_gateway = denied
        with pytest.raises(secure_gateway.GatewayError, match="AccessDeniedException"):
            roles(control)
        assert ("policy", "RetailPricingAgentCoreRole") not in roles.calls

    def test_main_stops_with_the_agents_role_unchanged_when_the_move_fails(self, monkeypatch, caplog):
        def failing(*a, **k):
            raise secure_gateway.GatewayError("Gateway retail-pricing-gateway-x is UPDATE_UNSUCCESSFUL")

        monkeypatch.setattr(create_agentcore_role, "create_roles", failing)
        monkeypatch.setattr(create_agentcore_role.boto3, "Session", lambda **kw: None)
        monkeypatch.setattr(sys, "argv", ["create_agentcore_role.py"])
        with pytest.raises(SystemExit) as exit_info, caplog.at_level("ERROR"):
            create_agentcore_role.main()
        assert exit_info.value.code == 1
        assert "agents' role was not changed" in caplog.text


class TestSkipAgentsCheck:
    """deploy.sh --skip-agents stops before Step 2 if the upgrade still needs an agent deploy."""

    def test_nothing_blocks_without_an_open_gateway(self):
        assert secure_gateway.skip_agents_blockers(FakeControl(gateways=[SIGV4_GATEWAY])) == []

    def test_an_upgrade_that_has_not_created_the_new_gateway_is_blocked(self):
        (blocker,) = secure_gateway.skip_agents_blockers(FakeControl(gateways=[OPEN_GATEWAY]))
        assert "'retail-pricing-gateway-iam' does not exist yet" in blocker and LEGACY_ID in blocker

    def test_agents_still_on_the_open_gateway_block_it(self):
        control = FakeControl(gateways=[SIGV4_GATEWAY, OPEN_GATEWAY],
                              runtime_env={"AGENTCORE_GATEWAY_ENDPOINT": LEGACY_MCP})
        blockers = secure_gateway.skip_agents_blockers(control)
        assert len(blockers) == len(secure_gateway.GATEWAY_CLIENT_RUNTIMES)
        assert all("AGENTCORE_GATEWAY_ENDPOINT" in b for b in blockers)

    def test_agents_already_signing_to_the_new_gateway_do_not_block_it(self):
        """For example a deploy whose Step 4 finished but Step 4.5 did not: Step 4.5 can still delete it."""
        assert secure_gateway.skip_agents_blockers(FakeControl(gateways=[SIGV4_GATEWAY, OPEN_GATEWAY])) == []

    @pytest.fixture
    def main(self, monkeypatch, capsys):
        def go(control):
            monkeypatch.setattr(secure_gateway.boto3, "client", lambda *a, **k: control)
            monkeypatch.setattr(sys, "argv", ["secure_gateway.py", "--check-skip-agents"])
            monkeypatch.setattr(secure_gateway, "secure_gateway", lambda *a: pytest.fail("must only check"))
            try:
                secure_gateway.main()
                code = 0
            except SystemExit as e:
                code = e.code
            return code, capsys.readouterr().err
        return go

    def test_the_check_fails_with_what_to_do(self, main):
        code, err = main(FakeControl(gateways=[OPEN_GATEWAY]))
        assert code == 1
        assert "still uses the open gateway 'retail-pricing-gateway'" in err
        assert "Run ./deploy.sh without --skip-agents" in err

    def test_the_check_passes_without_an_open_gateway(self, main):
        assert main(FakeControl(gateways=[SIGV4_GATEWAY])) == (0, "")


DEPLOY_TEXT = (PROJECT_ROOT / "deploy.sh").read_text()
TEARDOWN_TEXT = (PROJECT_ROOT / "teardown.sh").read_text()


class TestDeployAndTeardownWiring:
    def test_gateway_is_secured_after_the_agents_and_before_the_cdk_relink(self):
        agents = DEPLOY_TEXT.index("scripts/deploy_agentcore.py \\")
        secure = DEPLOY_TEXT.index("python3 scripts/secure_gateway.py --region $REGION\n")
        relink = DEPLOY_TEXT.index("npx cdk deploy", agents)
        assert agents < secure < relink

    def test_skip_agents_is_checked_before_anything_is_deployed(self):
        check = DEPLOY_TEXT.index('if [ "$SKIP_AGENTS" = true ]; then\n'
                                  "    python3 scripts/secure_gateway.py --region $REGION --check-skip-agents\n")
        assert DEPLOY_TEXT.index("set -e") < check < DEPLOY_TEXT.index("npx cdk deploy")

    def test_secure_step_runs_even_with_skip_agents(self):
        """With --skip-agents on an old deployment it must refuse (fail the deploy), not be skipped."""
        block = DEPLOY_TEXT[DEPLOY_TEXT.index("# Step 4.5:"):DEPLOY_TEXT.index("# Step 5:")]
        assert "SKIP_AGENTS" not in block

    def test_deploy_agentcore_marks_the_runtimes_as_signing(self):
        source = (PROJECT_ROOT / "scripts/deploy_agentcore.py").read_text()
        assert '"AGENTCORE_GATEWAY_AUTH": "AWS_IAM"' in source

    def test_teardown_deletes_both_gateways(self):
        assert "items[?starts_with(name,'retail-pricing')].gatewayId" in TEARDOWN_TEXT
        for name in (secure_gateway.GATEWAY_NAME, secure_gateway.LEGACY_GATEWAY_NAME):
            assert name.startswith("retail-pricing")

    def test_teardown_deletes_both_roles(self):
        assert 'ROLE_NAMES=("RetailPricingAgentCoreRole" "RetailPricingGatewayRole")' in TEARDOWN_TEXT
        assert 'for ROLE_NAME in "${ROLE_NAMES[@]}"' in TEARDOWN_TEXT
