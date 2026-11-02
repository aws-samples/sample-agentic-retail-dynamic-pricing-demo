"""Verify SigV4 on the AgentCore Gateway and delete the open gateway of earlier versions.

A gateway's inbound authorizer is fixed when the gateway is created: UpdateGateway
rejects a change ("Authorizer type cannot be updated for an existing gateway").
Earlier versions of this sample created LEGACY_GATEWAY_NAME with no inbound auth
(authorizer NONE), so anyone with its URL could call every tool. It cannot be
switched in place, so scripts/setup_gateway.py creates GATEWAY_NAME with AWS_IAM
next to it and the agents are deployed against the new gateway.

deploy.sh runs this after the agents are deployed (Step 4.5). It:

1. Checks that GATEWAY_NAME uses AWS_IAM, rejects an unsigned call (401/403),
   answers a signed tools/list, and runs a signed tools/call through an MCP
   Lambda (proving the gateway can assume its service role).
2. If LEGACY_GATEWAY_NAME still exists, refuses to delete it while any runtime
   that calls the gateway serves a version that is not wired to GATEWAY_NAME
   with signing on (AGENTCORE_GATEWAY_ENDPOINT / AGENTCORE_GATEWAY_AUTH): those
   agents would lose their tools. Otherwise deletes its targets and then the
   gateway, and waits until both are gone.

The gateway names live here too, with the UpdateGateway helpers that
scripts/create_agentcore_role.py and scripts/setup_gateway.py use to move a
gateway to its own service role, and the check deploy.sh runs before Step 2
when --skip-agents is given (--check-skip-agents).

Usage:
    python scripts/secure_gateway.py [--region us-east-1] [--check-skip-agents]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for backend/

# The SigV4 gateway (scripts/setup_gateway.py) and the open one earlier versions
# created. Gateway IDs are <name>-<suffix>, so both match the IAM scoping
# gateway/retail-pricing-gateway-* in scripts/create_agentcore_role.py.
GATEWAY_NAME = "retail-pricing-gateway-iam"
LEGACY_GATEWAY_NAME = "retail-pricing-gateway"
GATEWAY_ROLE_NAME = "RetailPricingGatewayRole"
REQUIRED_AUTHORIZER = "AWS_IAM"
GATEWAY_AUTH_ENV = "AGENTCORE_GATEWAY_AUTH"
GATEWAY_ENDPOINT_ENV = "AGENTCORE_GATEWAY_ENDPOINT"

# Runtimes whose code calls the gateway (scripts/deploy_agentcore.py runtime names).
GATEWAY_CLIENT_RUNTIMES = (
    "retailPricing_competitiveIntelligence",
    "retailPricing_demandForecasting",
    "retailPricing_marketIntelligence",
    "retailPricing_strategySynthesis",
)

# UpdateGateway request members other than gatewayIdentifier (botocore model).
UPDATE_FIELDS = (
    "name", "description", "roleArn", "protocolType", "protocolConfiguration", "authorizerType",
    "authorizerConfiguration", "kmsKeyArn", "customTransformConfiguration", "interceptorConfigurations",
    "policyEngineConfiguration", "exceptionLevel", "wafConfiguration",
)
# Settings a role move must leave as they were.
KEPT_FIELDS = (
    "authorizerType", "authorizerConfiguration", "protocolConfiguration", "description", "kmsKeyArn",
    "interceptorConfigurations", "policyEngineConfiguration", "exceptionLevel",
)

READY = "READY"
DELETING = "DELETING"
FAILED_STATES = {"FAILED", "UPDATE_UNSUCCESSFUL", "CREATE_FAILED", "DELETE_FAILED"}

# A tool call that reaches an MCP Lambda through the gateway's service role.
PROBE_TOOL = "competitor-api___get_competitor_prices"
PROBE_ARGUMENTS = {"product_id": "prod-elec-001"}


class GatewayError(RuntimeError):
    """The gateway could not be secured or failed a check."""


def find_gateway(client, name: str = GATEWAY_NAME) -> dict | None:
    """Full GetGateway description of the named gateway, or None."""
    token = None
    while True:
        page = client.list_gateways(**({"nextToken": token} if token else {}))
        for item in page.get("items", []):
            if item.get("name") == name:
                return client.get_gateway(gatewayIdentifier=item["gatewayId"])
        token = page.get("nextToken")
        if not token:
            return None


def build_update_request(gateway: dict, *, role_arn: str) -> dict:
    """UpdateGateway request that keeps every current setting and changes only the service role.

    UpdateGateway replaces the whole configuration and resets any optional field
    left out (including protocolConfiguration.mcp.searchType), so every current
    setting is copied. The authorizer and protocol types cannot change on an
    existing gateway: authorizerType is required and is sent unchanged, and
    protocolType is left out because UpdateGateway rejects it even with the same
    value.
    """
    request = {
        field: gateway[field]
        for field in UPDATE_FIELDS
        if field != "protocolType" and gateway.get(field) not in (None, "", [], {})
    }
    request["gatewayIdentifier"] = gateway["gatewayId"]
    request["roleArn"] = role_arn
    return request


def wait_until_ready(client, gateway_id: str, timeout_seconds: int = 300, interval_seconds: int = 5) -> dict:
    """Poll GetGateway until READY. Raises GatewayError on a failed state or timeout."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        gateway = client.get_gateway(gatewayIdentifier=gateway_id)
        status = gateway.get("status", "")
        if status == READY:
            return gateway
        if status in FAILED_STATES:
            raise GatewayError(f"Gateway {gateway_id} is {status}: {gateway.get('statusReasons') or 'no reason given'}")
        if time.monotonic() >= deadline:
            raise GatewayError(f"Timed out after {timeout_seconds}s waiting for gateway {gateway_id} (last status {status}).")
        time.sleep(interval_seconds)


def move_gateway_to_role(client, gateway: dict, role_arn: str) -> dict:
    """Point the gateway at another service role, wait, and confirm nothing else changed."""
    client.update_gateway(**build_update_request(gateway, role_arn=role_arn))
    updated = wait_until_ready(client, gateway["gatewayId"])
    problems = []
    if updated.get("roleArn") != role_arn:
        problems.append(f"roleArn is {updated.get('roleArn')}")
    for field in KEPT_FIELDS:
        if gateway.get(field) != updated.get(field):
            problems.append(f"{field} changed from {gateway.get(field)!r} to {updated.get(field)!r}")
    if problems:
        raise GatewayError("Gateway update did not keep its configuration: " + "; ".join(problems))
    return updated


def move_legacy_gateway_to_role(control, role_arn: str) -> dict | None:
    """Put the open gateway of an earlier version on `role_arn`, if it exists and is not on it.

    That gateway invokes the MCP Lambdas with the agents' execution role, which
    loses Lambda invoke in this version. scripts/create_agentcore_role.py calls
    this before it updates that role, so the gateway keeps serving the agents
    until they are redeployed against GATEWAY_NAME and Step 4.5 deletes it.
    Returns the gateway after the move, or None if there was nothing to move.
    """
    try:
        legacy = find_gateway(control, LEGACY_GATEWAY_NAME)
        if legacy is None or legacy.get("roleArn") == role_arn:
            return None
        print(f"Moving the open gateway '{LEGACY_GATEWAY_NAME}' ({legacy['gatewayId']}) from "
              f"{legacy.get('roleArn', '').split('/')[-1]} to {role_arn.split('/')[-1]}, so its tools keep working "
              "until deploy.sh deletes it (Step 4.5)")
        wait_until_ready(control, legacy["gatewayId"])
        return move_gateway_to_role(control, control.get_gateway(gatewayIdentifier=legacy["gatewayId"]), role_arn)
    except ClientError as e:
        # For example AccessDenied on GetGateway/UpdateGateway, or iam:PassRole on the gateway role.
        raise GatewayError(f"{e.response.get('Error', {}).get('Code', 'Error')}: {e}") from e


def skip_agents_blockers(control) -> list[str]:
    """Why `./deploy.sh --skip-agents` cannot finish on this deployment (empty list: it can).

    Step 4.5 deletes the open gateway of an earlier version only once every
    gateway-calling runtime signs its calls to GATEWAY_NAME, and only an agent
    deploy (Step 4) puts them there. deploy.sh checks this before Step 2.
    """
    legacy = find_gateway(control, LEGACY_GATEWAY_NAME)
    if legacy is None:
        return []
    gateway = find_gateway(control, GATEWAY_NAME)
    if gateway is None:
        return [f"'{GATEWAY_NAME}' does not exist yet: the agents still use '{LEGACY_GATEWAY_NAME}' "
                f"({legacy['gatewayId']}, inbound auth {legacy.get('authorizerType')})"]
    return runtimes_not_using(control, mcp_endpoint(gateway))


def runtimes_not_using(control, endpoint: str) -> list[str]:
    """Gateway-calling runtimes whose served version does not sign its MCP calls to `endpoint`."""
    by_name = {}
    token = None
    while True:
        page = control.list_agent_runtimes(**({"nextToken": token} if token else {}))
        for runtime in page.get("agentRuntimes", []):
            by_name[runtime.get("agentRuntimeName")] = runtime.get("agentRuntimeId")
        token = page.get("nextToken")
        if not token:
            break
    problems = []
    for name in GATEWAY_CLIENT_RUNTIMES:
        runtime_id = by_name.get(name)
        if not runtime_id:
            continue  # not deployed: it calls no gateway
        default = control.get_agent_runtime_endpoint(agentRuntimeId=runtime_id, endpointName="DEFAULT")
        live = str(default.get("liveVersion") or "")
        target = str(default.get("targetVersion") or live)
        if not live:
            problems.append(f"{name}: DEFAULT endpoint serves no version yet")
            continue
        if target != live:
            problems.append(f"{name}: DEFAULT endpoint still moving from v{live} to v{target}")
            continue
        env = control.get_agent_runtime(agentRuntimeId=runtime_id, agentRuntimeVersion=live).get(
            "environmentVariables") or {}
        if env.get(GATEWAY_ENDPOINT_ENV) != endpoint:
            problems.append(f"{name} v{live}: {GATEWAY_ENDPOINT_ENV}={env.get(GATEWAY_ENDPOINT_ENV)!r}")
        elif env.get(GATEWAY_AUTH_ENV) != REQUIRED_AUTHORIZER:
            problems.append(f"{name} v{live}: {GATEWAY_AUTH_ENV}={env.get(GATEWAY_AUTH_ENV)!r} (unsigned MCP calls)")
    return problems


def list_targets(client, gateway_id: str) -> list[dict]:
    targets, token = [], None
    while True:
        page = client.list_gateway_targets(gatewayIdentifier=gateway_id, **({"nextToken": token} if token else {}))
        targets.extend(page.get("items", []))
        token = page.get("nextToken")
        if not token:
            return targets


def delete_gateway(client, gateway: dict, timeout_seconds: int = 300, interval_seconds: int = 5) -> None:
    """Delete the gateway's targets, then the gateway, waiting until each is gone."""
    gateway_id = gateway["gatewayId"]
    deadline = time.monotonic() + timeout_seconds
    for target in list_targets(client, gateway_id):
        if target.get("status") != DELETING:
            client.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=target["targetId"])
            print(f"  Deleted target {target.get('name', target['targetId'])}")
    while remaining := list_targets(client, gateway_id):
        if time.monotonic() >= deadline:
            raise GatewayError(
                f"Timed out after {timeout_seconds}s waiting for the targets of {gateway_id} to be deleted: "
                + ", ".join(f"{t.get('name')} ({t.get('status')})" for t in remaining)
            )
        time.sleep(interval_seconds)

    client.delete_gateway(gatewayIdentifier=gateway_id)
    while True:
        try:
            status = client.get_gateway(gatewayIdentifier=gateway_id).get("status", "")
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"  Deleted gateway {gateway_id}")
                return
            raise
        if status in FAILED_STATES:
            raise GatewayError(f"Deleting gateway {gateway_id} failed: it is {status}")
        if time.monotonic() >= deadline:
            raise GatewayError(f"Timed out after {timeout_seconds}s waiting for gateway {gateway_id} to be deleted "
                               f"(last status {status}).")
        time.sleep(interval_seconds)


def mcp_endpoint(gateway: dict) -> str:
    return f"{gateway['gatewayUrl'].rstrip('/')}/mcp"


def _jsonrpc(method: str, params: dict | None = None) -> bytes:
    message = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        message["params"] = params
    return json.dumps(message).encode()


_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def probe_unsigned(url: str, timeout: float = 30) -> tuple[int, str]:
    """POST an unsigned tools/list. Returns (HTTP status, body excerpt)."""
    request = urllib.request.Request(url, data=_jsonrpc("tools/list"), method="POST", headers=_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310: https gateway URL
            return response.status, response.read(300).decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(300).decode(errors="replace")


def probe_signed(url: str, method: str, params: dict | None = None, timeout: float = 60) -> tuple[int, dict]:
    """POST a SigV4-signed JSON-RPC call with this process's credentials. Returns (status, JSON body)."""
    import httpx

    from backend.agents.agentcore.gateway_auth import GatewaySigV4Auth, region_from_gateway_url

    response = httpx.post(url, content=_jsonrpc(method, params), headers=_HEADERS,
                          auth=GatewaySigV4Auth(region_from_gateway_url(url)), timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text[:300]}
    return response.status_code, body


def check_gateway_auth(gateway: dict, *, signed_checks: bool = True) -> list[str]:
    """Problems with the gateway's inbound auth (empty list if it is enforced and working)."""
    problems = []
    if gateway.get("authorizerType") != REQUIRED_AUTHORIZER:
        problems.append(f"inbound authorizer is {gateway.get('authorizerType')}, not {REQUIRED_AUTHORIZER}")
    url = mcp_endpoint(gateway)
    status, body = probe_unsigned(url)
    if status not in (401, 403):
        problems.append(f"unsigned tools/list returned HTTP {status} (expected 401/403): {body[:120]}")
    if not signed_checks:
        return problems
    status, body = probe_signed(url, "tools/list")
    tools = (body.get("result") or {}).get("tools") or []
    if status != 200 or not tools:
        problems.append(f"signed tools/list returned HTTP {status}: {json.dumps(body)[:160]}")
    status, body = probe_signed(url, "tools/call", {"name": PROBE_TOOL, "arguments": PROBE_ARGUMENTS})
    result = body.get("result") or {}
    if status != 200 or result.get("isError") or not result.get("content"):
        problems.append(f"signed tools/call {PROBE_TOOL} failed (HTTP {status}): {json.dumps(body)[:200]}")
    return problems


def secure_gateway(region: str) -> dict:
    """Verify the SigV4 gateway, then delete the open legacy gateway if no agent uses it. Returns the gateway."""
    control = boto3.client("bedrock-agentcore-control", region_name=region)
    gateway = find_gateway(control, GATEWAY_NAME)
    if gateway is None:
        raise GatewayError(f"Gateway '{GATEWAY_NAME}' not found. Run scripts/setup_gateway.py first.")
    if gateway.get("authorizerType") != REQUIRED_AUTHORIZER:
        raise GatewayError(
            f"Gateway '{GATEWAY_NAME}' ({gateway['gatewayId']}) uses inbound auth {gateway.get('authorizerType')}, "
            f"but the agents sign with SigV4, so it must be {REQUIRED_AUTHORIZER}. The authorizer of an existing "
            "gateway cannot be changed: delete the gateway and run scripts/setup_gateway.py again."
        )

    # A gateway that was just created can take a moment to accept calls.
    attempts = 6
    for attempt in range(1, attempts + 1):
        problems = check_gateway_auth(gateway)
        if not problems or attempt == attempts:
            break
        time.sleep(10)
    if problems:
        raise GatewayError(f"Gateway {gateway['gatewayId']} failed its auth check:\n  " + "\n  ".join(problems))
    print(f"Gateway {gateway['gatewayId']} (inbound auth {REQUIRED_AUTHORIZER}):")
    print("  unsigned tools/list: rejected (401/403)")
    print(f"  signed tools/list and tools/call {PROBE_TOOL}: OK")

    legacy = find_gateway(control, LEGACY_GATEWAY_NAME)
    if legacy is None:
        print(f"No '{LEGACY_GATEWAY_NAME}' gateway from an earlier version to delete.")
        return gateway
    still_on_legacy = runtimes_not_using(control, mcp_endpoint(gateway))
    if still_on_legacy:
        raise GatewayError(
            f"Not deleting the open gateway '{LEGACY_GATEWAY_NAME}' ({legacy['gatewayId']}, inbound auth "
            f"{legacy.get('authorizerType')}): these runtimes do not sign their calls to {GATEWAY_NAME} yet and "
            "would lose their MCP tools.\n  " + "\n  ".join(still_on_legacy)
            + "\nDeploy the agents first (./deploy.sh without --skip-agents, or scripts/deploy_agentcore.py)."
        )
    print(f"Deleting the open gateway '{LEGACY_GATEWAY_NAME}' ({legacy['gatewayId']}, inbound auth "
          f"{legacy.get('authorizerType')}): every agent now uses {gateway['gatewayId']}")
    delete_gateway(control, legacy)
    return gateway


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify SigV4 on the AgentCore Gateway and delete the open gateway of earlier versions")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--check-skip-agents", action="store_true",
                        help="only check that ./deploy.sh --skip-agents can finish here (exit 1 if not); "
                             "deploy.sh runs this before Step 2")
    args = parser.parse_args()
    if args.check_skip_agents:
        blockers = skip_agents_blockers(boto3.client("bedrock-agentcore-control", region_name=args.region))
        if blockers:
            print(
                f"Error: this deployment still uses the open gateway '{LEGACY_GATEWAY_NAME}' of an earlier version.\n"
                "  " + "\n  ".join(blockers) + "\n"
                f"Upgrading redeploys the agents so they sign their calls to '{GATEWAY_NAME}', and Step 4.5 then "
                "deletes the open gateway. Run ./deploy.sh without --skip-agents.",
                file=sys.stderr,
            )
            sys.exit(1)
        return
    try:
        secure_gateway(args.region)
    except GatewayError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
