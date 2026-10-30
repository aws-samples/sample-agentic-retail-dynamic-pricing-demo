"""Deployment validation script for Retail Dynamic Pricing.

Performs health checks on all deployed resources to verify
a successful deployment. Run after deploy.sh completes.

Usage:
    python3 scripts/verify_deployment.py [--region us-east-1]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for shared/
from shared import cycle_timeouts  # noqa: E402


def check_mark(passed: bool) -> str:
    return "✓" if passed else "✗"


def verify_cloudformation(region: str) -> tuple[bool, dict]:
    """Verify CDK stack is deployed and healthy."""
    cf = boto3.client("cloudformation", region_name=region)
    try:
        response = cf.describe_stacks(StackName="RetailDynamicPricing")
        stack = response["Stacks"][0]
        status = stack["StackStatus"]
        outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
        passed = "COMPLETE" in status and "ROLLBACK" not in status
        return passed, outputs
    except ClientError:
        return False, {}


def verify_dynamodb(region: str) -> list[tuple[str, bool, int]]:
    """Verify DynamoDB tables exist and are accessible."""
    dynamodb = boto3.client("dynamodb", region_name=region)
    tables = ["PricingCycles", "PricingScenarios", "Products", "Approvals", "AuditTrail"]
    results = []

    for table_name in tables:
        try:
            response = dynamodb.describe_table(TableName=table_name)
            status = response["Table"]["TableStatus"]
            count = response["Table"].get("ItemCount", 0)
            results.append((table_name, status == "ACTIVE", count))
        except ClientError:
            results.append((table_name, False, 0))

    return results


def verify_lambda_functions(region: str) -> list[tuple[str, bool]]:
    """Verify Lambda functions are deployed."""
    lambda_client = boto3.client("lambda", region_name=region)
    functions = [
        "rdp-api-pricing-cycles",
        "rdp-api-approvals",
        "rdp-api-agents-status",
        "rdp-api-monitoring",
        "rdp-api-products",
        "rdp-api-scenarios",
        "rdp-api-guardrails-demo",
        "rdp-mcp-competitor-api",
        "rdp-mcp-erp-pos",
        "rdp-mcp-market-signals",
        "rdp-mcp-cost-finance",
    ]
    results = []

    for fn_name in functions:
        try:
            response = lambda_client.get_function(FunctionName=fn_name)
            state = response["Configuration"]["State"]
            results.append((fn_name, state == "Active"))
        except ClientError:
            results.append((fn_name, False))

    return results


def verify_cognito(region: str) -> tuple[bool, str]:
    """Verify Cognito User Pool exists."""
    cognito = boto3.client("cognito-idp", region_name=region)
    try:
        response = cognito.list_user_pools(MaxResults=20)
        for pool in response.get("UserPools", []):
            if "retail-pricing" in pool["Name"]:
                return True, pool["Id"]
        return False, ""
    except ClientError:
        return False, ""


def verify_api_gateway(api_url: str) -> tuple[bool, int]:
    """Verify API Gateway is responding (public /products endpoint)."""
    try:
        url = f"{api_url}products"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            count = data.get("count", len(data.get("products", [])))
            return resp.status == 200, count
    except Exception:
        return False, 0


def verify_s3_buckets(region: str) -> list[tuple[str, bool]]:
    """Verify S3 hosting buckets exist."""
    s3 = boto3.client("s3", region_name=region)
    try:
        response = s3.list_buckets()
        bucket_names = [b["Name"] for b in response["Buckets"]]
        results = []

        dashboard = next((b for b in bucket_names if "dashboardbucket" in b), None)
        storefront = next((b for b in bucket_names if "storefrontbucket" in b), None)
        logs = next((b for b in bucket_names if "accesslogsbucket" in b), None)

        results.append(("Dashboard bucket", dashboard is not None))
        results.append(("Storefront bucket", storefront is not None))
        results.append(("Access logs bucket", logs is not None))
        return results
    except ClientError:
        return [("S3 access", False)]


def verify_agent_arns() -> tuple[bool, int]:
    """Verify agent ARNs file exists with valid entries."""
    env_file = Path(__file__).parent / "agent_arns.env"
    if not env_file.exists():
        return False, 0

    arns = []
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            _, value = line.split("=", 1)
            if value.strip():
                arns.append(value.strip())

    return len(arns) >= 6, len(arns)


# The six AgentCore runtimes deployed by scripts/deploy_agentcore.py
# (agent short name -> runtime name). Keep in sync with AGENTS there.
AGENT_RUNTIME_NAMES = {
    "competitive-intelligence": "retailPricing_competitiveIntelligence",
    "demand-forecasting": "retailPricing_demandForecasting",
    "market-intelligence": "retailPricing_marketIntelligence",
    "strategy-synthesis": "retailPricing_strategySynthesis",
    "implementation-monitoring": "retailPricing_implementationMonitoring",
    "orchestrator": "retailPricing_orchestrator",
}

# Names used by scripts/setup_gateway.py and scripts/setup_memory.py.
GATEWAY_NAME = "retail-pricing-gateway"
MEMORY_NAME = "RetailDynamicPricingMemory"

# Env vars deploy_agentcore.py must set on EVERY runtime. Without them the agents
# silently run with no gateway tools and no memory.
GATEWAY_ENV_VAR = "AGENTCORE_GATEWAY_ENDPOINT"
MEMORY_ENV_VAR = "AGENTCORE_MEMORY_ID"


def _list_all(call, keys: tuple[str, ...]) -> list[dict]:
    """Collect every item of a paginated bedrock-agentcore-control list_* call."""
    items: list[dict] = []
    token = None
    while True:
        response = call(nextToken=token) if token else call()
        for key in keys:
            items.extend(response.get(key, []))
        token = response.get("nextToken")
        if not token:
            return items


def _live_gateway_endpoint(client) -> str:
    """MCP endpoint (<gatewayUrl>/mcp) of the deployed gateway, or '' if not found."""
    for gateway in _list_all(client.list_gateways, ("items",)):
        if gateway.get("name") == GATEWAY_NAME:
            url = client.get_gateway(gatewayIdentifier=gateway["gatewayId"]).get("gatewayUrl", "")
            return f"{url.rstrip('/')}/mcp" if url else ""
    return ""


def _live_memory_id(client) -> str:
    """ID of the deployed AgentCore Memory, or '' if not found."""
    for memory in _list_all(client.list_memories, ("memories",)):
        memory_id = memory.get("id") or memory.get("memoryId") or ""
        if memory_id.startswith(f"{MEMORY_NAME}-"):
            return memory_id
    return ""


def verify_agent_wiring(region: str) -> tuple[bool, list[tuple[str, bool, str]], list[str]]:
    """Verify every AgentCore runtime is wired to the gateway and memory.

    For each of the six runtimes, reads the environment variables of the runtime
    version its DEFAULT endpoint actually serves (an update creates a new version
    while the endpoint may still point at the old one) and requires non-empty
    AGENTCORE_GATEWAY_ENDPOINT and AGENTCORE_MEMORY_ID. Also requires all six to
    agree with each other and with the live gateway and memory, so the gate fails
    if wiring regresses (unwired, stale or mismatched agents).

    Returns (passed, per-agent rows of (name, ok, detail), shared problems).
    """
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    rows: list[tuple[str, bool, str]] = []
    shared_problems: list[str] = []
    gateway_values: set[str] = set()
    memory_values: set[str] = set()

    try:
        runtime_ids = {
            r.get("agentRuntimeName"): r.get("agentRuntimeId")
            for r in _list_all(client.list_agent_runtimes, ("agentRuntimes",))
        }
    except (ClientError, BotoCoreError) as e:
        return False, [], [f"could not list AgentCore runtimes: {e}"]

    for agent, runtime_name in AGENT_RUNTIME_NAMES.items():
        runtime_id = runtime_ids.get(runtime_name)
        if not runtime_id:
            rows.append((agent, False, f"runtime {runtime_name} not found"))
            continue
        try:
            endpoint = client.get_agent_runtime_endpoint(
                agentRuntimeId=runtime_id, endpointName="DEFAULT"
            )
            live_version = str(endpoint.get("liveVersion") or "")
            target_version = str(endpoint.get("targetVersion") or live_version)
            if not live_version:
                rows.append((agent, False, f"DEFAULT endpoint serves no version yet (status {endpoint.get('status')})"))
                continue
            env = client.get_agent_runtime(
                agentRuntimeId=runtime_id, agentRuntimeVersion=live_version
            ).get("environmentVariables") or {}
        except (ClientError, BotoCoreError) as e:
            rows.append((agent, False, f"could not read runtime {runtime_id}: {e}"))
            continue

        problems = []
        gateway = (env.get(GATEWAY_ENV_VAR) or "").strip()
        memory = (env.get(MEMORY_ENV_VAR) or "").strip()
        if not gateway:
            problems.append(f"{GATEWAY_ENV_VAR} missing or empty")
        elif not (gateway.startswith("https://") and gateway.endswith("/mcp")):
            problems.append(f"{GATEWAY_ENV_VAR} is not a gateway MCP URL (must end with /mcp): {gateway}")
        else:
            gateway_values.add(gateway)
        if not memory:
            problems.append(f"{MEMORY_ENV_VAR} missing or empty")
        else:
            memory_values.add(memory)
        if target_version != live_version:
            problems.append(f"DEFAULT endpoint still moving from v{live_version} to v{target_version}")

        detail = f"v{live_version}: " + (
            "; ".join(problems) if problems else f"{GATEWAY_ENV_VAR} and {MEMORY_ENV_VAR} set"
        )
        rows.append((agent, not problems, detail))

    # All agents must be wired to the same gateway / memory ...
    if len(gateway_values) > 1:
        shared_problems.append(f"agents disagree on {GATEWAY_ENV_VAR}: {sorted(gateway_values)}")
    if len(memory_values) > 1:
        shared_problems.append(f"agents disagree on {MEMORY_ENV_VAR}: {sorted(memory_values)}")

    # ... and to the resources that actually exist.
    try:
        live_gateway = _live_gateway_endpoint(client)
        live_memory = _live_memory_id(client)
    except (ClientError, BotoCoreError) as e:
        shared_problems.append(f"could not look up the live gateway/memory: {e}")
    else:
        if not live_gateway:
            shared_problems.append(f"gateway '{GATEWAY_NAME}' not found")
        elif gateway_values and gateway_values != {live_gateway}:
            shared_problems.append(f"{GATEWAY_ENV_VAR} {sorted(gateway_values)} != live gateway {live_gateway}")
        if not live_memory:
            shared_problems.append(f"memory '{MEMORY_NAME}' not found")
        elif memory_values and memory_values != {live_memory}:
            shared_problems.append(f"{MEMORY_ENV_VAR} {sorted(memory_values)} != live memory {live_memory}")

    passed = all(ok for _, ok, _ in rows) and len(rows) == len(AGENT_RUNTIME_NAMES) and not shared_problems
    return passed, rows, shared_problems


PRICING_CYCLES_FUNCTION = "rdp-api-pricing-cycles"


def expected_lambda_timeouts(orchestrator_env: dict) -> tuple[cycle_timeouts.CycleTimeouts | None, str]:
    """Timeouts the Lambda must have for the orchestrator's deployed agent timeouts.

    A runtime deployed before the timeouts were configurable has neither env var;
    it uses the defaults, so the defaults are expected.
    """
    try:
        return cycle_timeouts.resolve(environ=orchestrator_env), ""
    except cycle_timeouts.InvalidTimeouts as e:
        return None, f"orchestrator has invalid timeouts: {e}"


def compare_cycle_timeouts(orchestrator_env: dict, lambda_config: dict) -> list[str]:
    """Problems if the Lambda's timeouts do not match the orchestrator's (empty if they do)."""
    timeouts, error = expected_lambda_timeouts(orchestrator_env)
    if timeouts is None:
        return [error]
    problems = []
    lambda_env = (lambda_config.get("Environment") or {}).get("Variables") or {}
    for key, expected in timeouts.lambda_environment().items():
        actual = lambda_env.get(key)
        if actual != expected:
            problems.append(f"{PRICING_CYCLES_FUNCTION} {key}={actual} (expected {expected})")
    if lambda_config.get("Timeout") != timeouts.lambda_timeout:
        problems.append(
            f"{PRICING_CYCLES_FUNCTION} timeout {lambda_config.get('Timeout')} s (expected {timeouts.lambda_timeout} s)"
        )
    return problems


def verify_cycle_timeouts(region: str) -> tuple[bool, str]:
    """Check the Lambda waits longer than the deployed orchestrator can take.

    The orchestrator (deploy_agentcore.py) and the Lambda (CDK) are deployed
    separately; if they were given different timeouts, the chain can break.
    """
    control = boto3.client("bedrock-agentcore-control", region_name=region)
    try:
        runtime_id = next(
            (r["agentRuntimeId"] for r in _list_all(control.list_agent_runtimes, ("agentRuntimes",))
             if r.get("agentRuntimeName") == AGENT_RUNTIME_NAMES["orchestrator"]),
            None,
        )
        if not runtime_id:
            return False, "orchestrator runtime not found"
        live = str(control.get_agent_runtime_endpoint(agentRuntimeId=runtime_id, endpointName="DEFAULT")
                   .get("liveVersion") or "")
        env = control.get_agent_runtime(agentRuntimeId=runtime_id, agentRuntimeVersion=live).get(
            "environmentVariables") or {}
        config = boto3.client("lambda", region_name=region).get_function_configuration(
            FunctionName=PRICING_CYCLES_FUNCTION)
    except (ClientError, BotoCoreError) as e:
        return False, f"could not read the timeouts: {e}"
    problems = compare_cycle_timeouts(env, config)
    if problems:
        return False, "; ".join(problems)
    return True, expected_lambda_timeouts(env)[0].describe()


def main():
    parser = argparse.ArgumentParser(description="Verify deployment health")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    args = parser.parse_args()

    print("")
    print("=" * 60)
    print("  Retail Dynamic Pricing — Deployment Validation")
    print("=" * 60)
    print("")

    all_passed = True

    # 1. CloudFormation stack
    print("  CloudFormation Stack:")
    cf_passed, outputs = verify_cloudformation(args.region)
    print(f"    {check_mark(cf_passed)} RetailDynamicPricing stack ({'healthy' if cf_passed else 'NOT FOUND'})")
    all_passed = all_passed and cf_passed

    # 2. DynamoDB tables
    print("\n  DynamoDB Tables:")
    db_results = verify_dynamodb(args.region)
    for table_name, passed, count in db_results:
        status = f"ACTIVE ({count} items)" if passed else "NOT FOUND"
        print(f"    {check_mark(passed)} {table_name}: {status}")
        all_passed = all_passed and passed

    # 3. Lambda functions
    print("\n  Lambda Functions:")
    lambda_results = verify_lambda_functions(args.region)
    for fn_name, passed in lambda_results:
        status = "Active" if passed else "NOT FOUND"
        print(f"    {check_mark(passed)} {fn_name}: {status}")
        all_passed = all_passed and passed

    # 4. Cognito
    print("\n  Cognito:")
    cognito_passed, pool_id = verify_cognito(args.region)
    print(f"    {check_mark(cognito_passed)} User Pool: {'found' if cognito_passed else 'NOT FOUND'}")
    all_passed = all_passed and cognito_passed

    # 5. API Gateway
    print("\n  API Gateway:")
    api_url = ""
    for key, value in outputs.items():
        if "ApiGatewayUrl" in key or "PricingApiEndpoint" in key:
            api_url = value
            break

    if api_url:
        api_passed, product_count = verify_api_gateway(api_url)
        print(f"    {check_mark(api_passed)} GET /products: {'OK' if api_passed else 'FAILED'} ({product_count} products)")
        all_passed = all_passed and api_passed
    else:
        print(f"    {check_mark(False)} API URL not found in stack outputs")
        all_passed = False

    # 6. S3 Buckets
    print("\n  S3 Hosting Buckets:")
    s3_results = verify_s3_buckets(args.region)
    for name, passed in s3_results:
        print(f"    {check_mark(passed)} {name}")
        all_passed = all_passed and passed

    # 7. Agent ARNs
    print("\n  AgentCore Agents:")
    agents_passed, agent_count = verify_agent_arns()
    print(f"    {check_mark(agents_passed)} Agent ARNs: {agent_count}/6 configured")
    all_passed = all_passed and agents_passed

    # 8. Agent wiring: every runtime must have the gateway + memory env vars
    print("\n  AgentCore Wiring (gateway + memory env vars on the served runtime version):")
    wiring_passed, wiring_rows, wiring_problems = verify_agent_wiring(args.region)
    for agent, ok, detail in wiring_rows:
        print(f"    {check_mark(ok)} {agent}: {detail}")
    for problem in wiring_problems:
        print(f"    {check_mark(False)} {problem}")
    if wiring_passed:
        print(f"    {check_mark(True)} All {len(wiring_rows)} runtimes wired to the live gateway and memory")
    all_passed = all_passed and wiring_passed

    # 9. Pricing-cycle timeouts: the Lambda (CDK) must match the orchestrator (deploy_agentcore.py)
    print("\n  Pricing-Cycle Timeouts (orchestrator vs rdp-api-pricing-cycles):")
    timeouts_passed, timeouts_detail = verify_cycle_timeouts(args.region)
    print(f"    {check_mark(timeouts_passed)} {timeouts_detail}")
    all_passed = all_passed and timeouts_passed

    # Summary
    print("")
    print("=" * 60)
    if all_passed:
        print("  RESULT: ALL CHECKS PASSED — deployment is healthy")
    else:
        print("  RESULT: SOME CHECKS FAILED — review issues above")
    print("=" * 60)
    print("")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
