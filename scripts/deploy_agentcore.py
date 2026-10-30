"""Deploy Retail Dynamic Pricing agents to Amazon Bedrock AgentCore Runtime.

This script:
1. Discovers the AgentCore Gateway and Memory created by setup_gateway.py and
   setup_memory.py (run those FIRST; exits non-zero before building anything if
   either is missing, so agents are never deployed unwired)
2. Builds Docker images for each agent (ARM64 / linux/arm64)
3. Creates ECR repositories (if they don't exist)
4. Pushes images to ECR
5. Creates or updates AgentCore Runtimes via boto3 bedrock-agentcore-control client,
   setting the runtime environment variables on BOTH create and update:
     AGENTCORE_GATEWAY_ENDPOINT  gateway MCP URL (<gatewayUrl>/mcp)
     AGENTCORE_MEMORY_ID         AgentCore Memory ID
     ORCHESTRATOR_MODEL_ID / SPECIALIST_MODEL_ID   from model-config.json
     BEDROCK_GUARDRAIL_ID / BEDROCK_GUARDRAIL_VERSION, or
       DISABLE_BEDROCK_GUARDRAILS=true when the guardrail does not exist
     <AGENT>_AGENT_ARN x5        (orchestrator only) the specialist runtime ARNs
6. Saves the agent runtime ARNs to agent_config.json and scripts/agent_arns.env

Prerequisites:
- Docker installed and running (with buildx for multi-platform builds)
- AWS CLI configured with appropriate permissions
- Model access granted for the Bedrock models used by agents
- IAM role (scripts/create_agentcore_role.py), gateway (scripts/setup_gateway.py)
  and memory (scripts/setup_memory.py) already created

Usage:
    python scripts/deploy_agentcore.py --role-arn <arn> [--region us-east-1] [--account-id <id>]
        [--gateway-name NAME | --gateway-endpoint URL] [--memory-name NAME | --memory-id ID]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for shared/
from shared import cycle_timeouts  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Agent definitions matching the spec naming conventions
AGENTS = [
    {
        "name": "competitive-intelligence",
        "runtime_name": "retailPricing_competitiveIntelligence",
        "ecr_repo": "retail-pricing/competitive-intelligence",
        "module": "competitive_intelligence_runtime",
        "description": "Analyzes competitor pricing, market positioning, and channel dynamics",
    },
    {
        "name": "demand-forecasting",
        "runtime_name": "retailPricing_demandForecasting",
        "ecr_repo": "retail-pricing/demand-forecasting",
        "module": "demand_forecasting_runtime",
        "description": "Analyzes sales history, POS data, inventory levels, and price elasticity",
    },
    {
        "name": "market-intelligence",
        "runtime_name": "retailPricing_marketIntelligence",
        "ecr_repo": "retail-pricing/market-intelligence",
        "module": "market_intelligence_runtime",
        "description": "Analyzes market trends, consumer sentiment, and macroeconomic indicators",
    },
    {
        "name": "strategy-synthesis",
        "runtime_name": "retailPricing_strategySynthesis",
        "ecr_repo": "retail-pricing/strategy-synthesis",
        "module": "strategy_synthesis_runtime",
        "description": "Generates ranked pricing scenarios from combined intelligence outputs",
    },
    {
        "name": "implementation-monitoring",
        "runtime_name": "retailPricing_implementationMonitoring",
        "ecr_repo": "retail-pricing/implementation-monitoring",
        "module": "implementation_monitoring_runtime",
        "description": "Executes price updates and monitors KPI performance",
    },
    {
        "name": "orchestrator",
        "runtime_name": "retailPricing_orchestrator",
        "ecr_repo": "retail-pricing/orchestrator",
        "module": "orchestrator_runtime",
        "description": "Coordinates pricing cycles by delegating to intelligence agents and synthesizing results",
    },
]

CONFIG_FILE = Path(__file__).parent.parent / "backend" / "agents" / "agentcore" / "agent_config.json"
ENV_FILE = Path(__file__).parent / "agent_arns.env"
PROJECT_ROOT = Path(__file__).parent.parent
MODEL_CONFIG_FILE = PROJECT_ROOT / "model-config.json"
GUARDRAIL_CONFIG_FILE = PROJECT_ROOT / "backend" / "agents" / "agentcore" / "guardrail_config.py"

# Names used by scripts/setup_gateway.py and scripts/setup_memory.py. The memory
# ID is this name plus a random suffix (RetailDynamicPricingMemory-Ab12Cd34Ef).
DEFAULT_GATEWAY_NAME = "retail-pricing-gateway"
DEFAULT_MEMORY_NAME = "RetailDynamicPricingMemory"

# Env var that carries each agent's runtime ARN (agent_arns.env, the CDK Lambda
# and, for the five specialists, the orchestrator runtime).
AGENT_ARN_ENV_VARS = {
    "competitive-intelligence": "COMPETITIVE_INTELLIGENCE_AGENT_ARN",
    "demand-forecasting": "DEMAND_FORECASTING_AGENT_ARN",
    "market-intelligence": "MARKET_INTELLIGENCE_AGENT_ARN",
    "strategy-synthesis": "STRATEGY_SYNTHESIS_AGENT_ARN",
    "implementation-monitoring": "IMPLEMENTATION_MONITORING_AGENT_ARN",
    "orchestrator": "ORCHESTRATOR_AGENT_ARN",
}
ORCHESTRATOR = "orchestrator"
SPECIALIST_AGENTS = [a["name"] for a in AGENTS if a["name"] != ORCHESTRATOR]

RUNTIME_ARN_PATTERN = re.compile(
    r"^arn:aws[a-z-]*:bedrock-agentcore:[a-z0-9-]+:\d{12}:runtime/[A-Za-z0-9_-]+$"
)

# Runtime / endpoint states that will not become READY on their own.
_FAILED_STATES = {
    "FAILED", "CREATE_FAILED", "UPDATE_FAILED", "DELETING", "DELETE_FAILED",
}


class WiringError(RuntimeError):
    """The gateway/memory/ARNs the agents must be wired to could not be resolved."""


def get_account_id(session: boto3.Session) -> str:
    """Get the AWS account ID from STS."""
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    account_id = identity["Account"]
    logger.info("Detected AWS account: %s", account_id)
    return account_id


def ecr_login(region: str, account_id: str) -> str:
    """Authenticate Docker to ECR and return the registry URI."""
    registry_uri = f"{account_id}.dkr.ecr.{region}.amazonaws.com"

    cmd = ["aws", "ecr", "get-login-password", "--region", region]
    login_password = subprocess.check_output(cmd, text=True).strip()

    docker_login_cmd = [
        "docker", "login",
        "--username", "AWS",
        "--password-stdin",
        registry_uri,
    ]
    proc = subprocess.run(
        docker_login_cmd,
        input=login_password,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Docker login failed: {proc.stderr}")

    logger.info("Authenticated Docker to ECR: %s", registry_uri)
    return registry_uri


def ensure_ecr_repository(
    session: boto3.Session, region: str, repo_name: str
) -> str:
    """Create ECR repository if it doesn't exist. Returns the repository URI."""
    ecr = session.client("ecr", region_name=region)

    try:
        response = ecr.describe_repositories(repositoryNames=[repo_name])
        repo_uri = response["repositories"][0]["repositoryUri"]
        logger.info("ECR repository exists: %s", repo_uri)
    except ClientError as e:
        if e.response["Error"]["Code"] == "RepositoryNotFoundException":
            response = ecr.create_repository(
                repositoryName=repo_name,
                imageTagMutability="MUTABLE",
                imageScanningConfiguration={"scanOnPush": True},
            )
            repo_uri = response["repository"]["repositoryUri"]
            logger.info("Created ECR repository: %s", repo_uri)
        else:
            raise

    return repo_uri


def build_and_push_image(
    agent: dict,
    registry_uri: str,
    region: str,
) -> str:
    """Build Docker image for an agent and push to ECR.

    Returns the full image URI with tag.
    """
    repo_name = agent["ecr_repo"]
    image_tag = "latest"
    full_image_uri = f"{registry_uri}/{repo_name}:{image_tag}"

    logger.info("Building image for %s (module: %s)...", agent["name"], agent["module"])

    build_cmd = [
        "docker", "buildx", "build",
        "--platform", "linux/arm64",
        # The Dockerfile declares ARG AGENT_ENTRYPOINT (its CMD runs that module).
        # A differently named build arg is silently ignored, which made every
        # image run the Dockerfile default (competitive_intelligence_runtime).
        "--build-arg", f"AGENT_ENTRYPOINT={agent['module']}",
        "-t", full_image_uri,
        "-f", "backend/agents/agentcore/Dockerfile",
        "--load",
        ".",
    ]

    proc = subprocess.run(
        build_cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Docker build failed for {agent['name']}:\n{proc.stderr}"
        )

    logger.info("Built image: %s", full_image_uri)

    push_cmd = ["docker", "push", full_image_uri]
    proc = subprocess.run(push_cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Docker push failed for {agent['name']}:\n{proc.stderr}"
        )

    logger.info("Pushed image: %s", full_image_uri)
    return full_image_uri


# ---------------------------------------------------------------------------
# Runtime wiring: gateway, memory, models, guardrail, specialist ARNs
# ---------------------------------------------------------------------------

def _list_all(call, keys: tuple[str, ...], **kwargs) -> list[dict]:
    """Collect every item of a paginated bedrock-agentcore-control list_* call."""
    items: list[dict] = []
    token = None
    while True:
        params = dict(kwargs)
        if token:
            params["nextToken"] = token
        response = call(**params)
        for key in keys:
            items.extend(response.get(key, []))
        token = response.get("nextToken")
        if not token:
            return items


def resolve_gateway_endpoint(client, gateway_name: str) -> str:
    """Return the MCP endpoint (<gatewayUrl>/mcp) of the named, READY gateway.

    The gateway serves MCP at <gatewayUrl>/mcp; POSTing to the bare gatewayUrl
    returns UnknownOperationException.
    """
    matches = [
        g for g in _list_all(client.list_gateways, ("items",))
        if g.get("name") == gateway_name
    ]
    if not matches:
        raise WiringError(
            f"AgentCore gateway '{gateway_name}' not found. Create it first with "
            "scripts/setup_gateway.py (deploy.sh does this before the agent deploy), "
            "or pass --gateway-name / --gateway-endpoint."
        )
    gateway_id = matches[0]["gatewayId"]
    gateway = client.get_gateway(gatewayIdentifier=gateway_id)
    status = gateway.get("status")
    if status != "READY":
        raise WiringError(
            f"AgentCore gateway {gateway_id} is {status}, not READY. Wait for it, then re-run."
        )
    url = (gateway.get("gatewayUrl") or "").rstrip("/")
    if not url:
        raise WiringError(f"AgentCore gateway {gateway_id} reports no gatewayUrl.")
    return f"{url}/mcp"


def resolve_memory_id(client, memory_name: str) -> str:
    """Return the ID of the ACTIVE AgentCore Memory created for ``memory_name``.

    list_memories summaries carry no name field and the memory ID is the name plus
    a random suffix, so match on the ID prefix.
    """
    matches = [
        m for m in _list_all(client.list_memories, ("memories",))
        if (m.get("id") or m.get("memoryId") or "").startswith(f"{memory_name}-")
    ]
    if not matches:
        raise WiringError(
            f"AgentCore memory '{memory_name}' not found. Create it first with "
            "scripts/setup_memory.py (deploy.sh does this before the agent deploy), "
            "or pass --memory-name / --memory-id."
        )
    # Same pick as setup_memory.py: ACTIVE first, then oldest.
    matches.sort(key=lambda m: (m.get("status") != "ACTIVE", str(m.get("createdAt", ""))))
    chosen = matches[0]
    memory_id = chosen.get("id") or chosen.get("memoryId")
    if chosen.get("status") != "ACTIVE":
        raise WiringError(
            f"AgentCore memory {memory_id} is {chosen.get('status')}, not ACTIVE. Wait for it, then re-run."
        )
    if len(matches) > 1:
        logger.warning("%d memories match '%s'; using %s", len(matches), memory_name, memory_id)
    return memory_id


def list_existing_agent_arns(client) -> dict[str, str]:
    """Map agent short name -> runtime ARN for the runtimes that already exist."""
    by_runtime_name = {a["runtime_name"]: a["name"] for a in AGENTS}
    arns: dict[str, str] = {}
    runtimes = _list_all(
        client.list_agent_runtimes,
        ("agentRuntimes", "agentRuntimeSummaries", "items"),
    )
    for runtime in runtimes:
        short_name = by_runtime_name.get(runtime.get("agentRuntimeName") or runtime.get("name"))
        arn = runtime.get("agentRuntimeArn") or runtime.get("arn") or ""
        if short_name and arn:
            arns[short_name] = arn
    return arns


def load_model_environment() -> dict[str, str]:
    """Model IDs from model-config.json (written by select_model.py).

    The file is not part of the container image, so the selected models reach
    the agents as env vars read by shared/model_config.py.
    """
    if not MODEL_CONFIG_FILE.exists():
        logger.warning(
            "%s not found; agents will use the default models from shared/model_config.py",
            MODEL_CONFIG_FILE.name,
        )
        return {}
    try:
        config = json.loads(MODEL_CONFIG_FILE.read_text())
    except json.JSONDecodeError as e:
        logger.warning("Could not parse %s (%s); agents will use default models", MODEL_CONFIG_FILE.name, e)
        return {}

    env: dict[str, str] = {}
    if config.get("modelId"):
        env["ORCHESTRATOR_MODEL_ID"] = config["modelId"]
    if config.get("specialistModelId"):
        env["SPECIALIST_MODEL_ID"] = config["specialistModelId"]
    return env


def _guardrail_defaults() -> tuple[str, str]:
    """Default guardrail ID/version, read from the runtime's own guardrail_config."""
    spec = importlib.util.spec_from_file_location("guardrail_config", GUARDRAIL_CONFIG_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.GUARDRAIL_ID, module.GUARDRAIL_VERSION


def resolve_guardrail_environment(session: boto3.Session, region: str) -> dict[str, str]:
    """Decide the guardrail env vars for the runtimes.

    The demo does not create a guardrail, so the default one may not exist in the
    target account. Attaching a missing guardrail would make every model call fail,
    so in that case the runtimes are deployed with DISABLE_BEDROCK_GUARDRAILS=true
    and a loud warning. Any other lookup problem keeps the guardrail enabled.
    """
    if os.environ.get("DISABLE_BEDROCK_GUARDRAILS", "").lower() == "true":
        logger.warning("DISABLE_BEDROCK_GUARDRAILS=true: deploying agents WITHOUT a Bedrock guardrail.")
        return {"DISABLE_BEDROCK_GUARDRAILS": "true"}

    default_id, default_version = _guardrail_defaults()
    guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID") or default_id
    guardrail_version = os.environ.get("BEDROCK_GUARDRAIL_VERSION") or default_version

    bedrock = session.client("bedrock", region_name=region)
    try:
        bedrock.get_guardrail(guardrailIdentifier=guardrail_id, guardrailVersion=guardrail_version)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("ResourceNotFoundException", "ValidationException"):
            logger.warning("=" * 60)
            logger.warning(
                "Bedrock guardrail %s (version %s) does not exist in this account/region.",
                guardrail_id, guardrail_version,
            )
            logger.warning(
                "Deploying agents with DISABLE_BEDROCK_GUARDRAILS=true: model calls are NOT "
                "screened by a Bedrock guardrail. Create one and pass BEDROCK_GUARDRAIL_ID / "
                "BEDROCK_GUARDRAIL_VERSION to re-enable it."
            )
            logger.warning("=" * 60)
            return {"DISABLE_BEDROCK_GUARDRAILS": "true"}
        logger.warning(
            "Could not verify guardrail %s (%s); leaving it enabled on the agents.", guardrail_id, code
        )
    return {
        "BEDROCK_GUARDRAIL_ID": guardrail_id,
        "BEDROCK_GUARDRAIL_VERSION": guardrail_version,
    }


def build_environment(
    agent: dict,
    base_environment: dict[str, str],
    agent_arns: dict[str, str],
) -> dict[str, str]:
    """Build the runtime environmentVariables for one agent.

    ``base_environment`` is common to all agents. The orchestrator additionally
    gets the five specialist runtime ARNs, which orchestrator_runtime.py reads at
    import time (the container cannot start without them).
    """
    environment = dict(base_environment)

    if agent["name"] == ORCHESTRATOR:
        for name in SPECIALIST_AGENTS:
            arn = agent_arns.get(name, "")
            if not RUNTIME_ARN_PATTERN.match(arn):
                raise WiringError(
                    f"Cannot configure the orchestrator: no valid runtime ARN for '{name}' "
                    f"(got {arn!r}). Deploy the specialist agents first."
                )
            environment[AGENT_ARN_ENV_VARS[name]] = arn

    # AWS_* names are reserved for the platform; never set them on a runtime.
    reserved = [k for k in environment if k.upper().startswith("AWS_")]
    if reserved:
        raise ValueError(f"Reserved environment variable names: {reserved}")
    return environment


def _wait_for_default_endpoint(
    client,
    runtime_id: str,
    expected_version: str | None,
    max_wait_seconds: int = 300,
) -> None:
    """Poll until the DEFAULT endpoint is READY and serving ``expected_version``.

    Every update creates a new runtime version and the DEFAULT endpoint moves to
    it asynchronously; until it has, invocations still run the old version.
    """
    start = time.time()
    last = "no response yet"
    while time.time() - start < max_wait_seconds:
        try:
            endpoint = client.get_agent_runtime_endpoint(
                agentRuntimeId=runtime_id, endpointName="DEFAULT"
            )
        except ClientError as e:
            last = e.response.get("Error", {}).get("Code", str(e))
            endpoint = None
        if endpoint:
            status = endpoint.get("status", "UNKNOWN")
            live = str(endpoint.get("liveVersion", ""))
            last = f"status={status} liveVersion={live} targetVersion={endpoint.get('targetVersion')}"
            if status in _FAILED_STATES:
                raise RuntimeError(
                    f"DEFAULT endpoint of {runtime_id} entered {status}: {endpoint.get('failureReason')}"
                )
            if status == "READY" and (expected_version is None or live == str(expected_version)):
                logger.info("DEFAULT endpoint of %s serves version %s", runtime_id, live)
                return
        time.sleep(5)

    raise TimeoutError(
        f"DEFAULT endpoint of {runtime_id} did not serve version {expected_version} "
        f"within {max_wait_seconds}s ({last})"
    )


def _check_runtime_environment(
    client, runtime_id: str, version: str | None, environment: dict[str, str]
) -> None:
    """Read the deployed version back and confirm the requested env vars landed."""
    params = {"agentRuntimeId": runtime_id}
    if version:
        params["agentRuntimeVersion"] = str(version)
    deployed = client.get_agent_runtime(**params).get("environmentVariables") or {}
    wrong = [k for k, v in environment.items() if deployed.get(k) != v]
    if wrong:
        raise RuntimeError(
            f"Runtime {runtime_id} (version {version}) is missing/has wrong env vars: {sorted(wrong)}"
        )
    logger.info("Verified %d environment variables on %s", len(environment), runtime_id)


def _update_runtime(
    client,
    runtime_id: str,
    runtime_name: str,
    role_arn: str,
    image_uri: str,
    environment: dict[str, str],
    description: str | None = None,
) -> dict:
    """Update an existing runtime in place (new version) and wait until it serves it."""
    extra = {"description": description} if description else {}
    try:
        response = client.update_agent_runtime(
            agentRuntimeId=runtime_id,
            roleArn=role_arn,
            networkConfiguration={"networkMode": "PUBLIC"},
            agentRuntimeArtifact={
                "containerConfiguration": {
                    "containerUri": image_uri,
                }
            },
            environmentVariables=environment,
            **extra,
        )
    except ClientError as e:
        # Do not "continue with existing": that would leave an unwired (or stale)
        # agent running and report success.
        logger.error("Could not update runtime %s: %s", runtime_name, e)
        raise

    version = str(response.get("agentRuntimeVersion", "")) or None
    logger.info("Updated runtime %s (version %s) with new image: %s", runtime_name, version, image_uri)
    _wait_for_runtime_active(client, runtime_id, expected_version=version)
    _wait_for_default_endpoint(client, runtime_id, version)
    _check_runtime_environment(client, runtime_id, version, environment)
    return response


def get_existing_runtime(
    client, runtime_name: str
) -> dict | None:
    """Check if an AgentCore Runtime already exists by listing and filtering by name."""
    try:
        response = client.list_agent_runtimes()
        # Handle various response formats
        runtimes = (
            response.get("agentRuntimeSummaries", [])
            or response.get("items", [])
            or response.get("agentRuntimes", [])
        )
        for runtime in runtimes:
            name = (
                runtime.get("agentRuntimeName")
                or runtime.get("name", "")
            )
            if name == runtime_name:
                return runtime

        # Paginate if needed
        while response.get("nextToken"):
            response = client.list_agent_runtimes(nextToken=response["nextToken"])
            runtimes = (
                response.get("agentRuntimeSummaries", [])
                or response.get("items", [])
                or response.get("agentRuntimes", [])
            )
            for runtime in runtimes:
                name = (
                    runtime.get("agentRuntimeName")
                    or runtime.get("name", "")
                )
                if name == runtime_name:
                    return runtime

        return None
    except ClientError as e:
        logger.warning("Failed to list runtimes: %s", e)
        return None


def create_or_update_agent_runtime(
    session: boto3.Session,
    region: str,
    agent: dict,
    image_uri: str,
    role_arn: str,
    environment: dict[str, str],
) -> str:
    """Create or update an AgentCore Runtime for the agent. Returns the runtime ARN.

    Idempotent: if the runtime already exists, updates it instead of failing.
    ``environment`` is set as the runtime's environmentVariables on BOTH create and
    update. Each update creates a new, self-contained runtime version, so the full
    environment must be supplied every time.
    """
    client = session.client("bedrock-agentcore-control", region_name=region)
    runtime_name = agent["runtime_name"]

    # Check if runtime already exists
    existing = get_existing_runtime(client, runtime_name)

    if existing:
        runtime_arn = existing.get("agentRuntimeArn", existing.get("arn", ""))
        runtime_id = existing.get("agentRuntimeId", existing.get("id", ""))
        if not runtime_id and runtime_arn:
            runtime_id = runtime_arn.split("/")[-1]
        logger.info(
            "Runtime %s already exists (ID: %s), updating container image and environment...",
            runtime_name,
            runtime_id,
        )
        # Update the existing runtime with the new container image + environment
        _update_runtime(
            client, runtime_id, runtime_name, role_arn, image_uri, environment,
            description=agent["description"],
        )
        return runtime_arn

    # Create new runtime
    logger.info("Creating AgentCore Runtime: %s", runtime_name)
    try:
        response = client.create_agent_runtime(
            agentRuntimeName=runtime_name,
            description=agent["description"],
            agentRuntimeArtifact={
                "containerConfiguration": {
                    "containerUri": image_uri,
                }
            },
            roleArn=role_arn,
            networkConfiguration={"networkMode": "PUBLIC"},
            environmentVariables=environment,
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ConflictException" or "already exists" in str(e):
            # Runtime exists but wasn't found by list — try to update by name
            logger.info("Runtime %s already exists, attempting update via list...", runtime_name)
            try:
                all_runtimes = _list_all(
                    client.list_agent_runtimes,
                    ("agentRuntimes", "agentRuntimeSummaries", "items"),
                )
            except ClientError as list_err:
                logger.error("Failed to list runtimes for recovery: %s", list_err)
                raise e
            for rt in all_runtimes:
                rt_name = rt.get("agentRuntimeName") or rt.get("name", "")
                rt_id = rt.get("agentRuntimeId") or rt.get("id", "")
                rt_arn = rt.get("agentRuntimeArn") or rt.get("arn", "")
                if rt_name == runtime_name:
                    logger.info("Found existing runtime: %s (ID: %s)", rt_name, rt_id)
                    # Update the container image + environment
                    _update_runtime(
                        client, rt_id, runtime_name, role_arn, image_uri, environment,
                        description=agent["description"],
                    )
                    return rt_arn
            # If we still can't find it, log all runtime names for debugging
            rt_names = [
                rt.get("agentRuntimeName") or rt.get("name", "UNKNOWN")
                for rt in all_runtimes
            ]
            logger.error(
                "Runtime %s exists per API but not found in list. Available: %s",
                runtime_name, rt_names,
            )
            # Never fabricate a placeholder ARN: it would be written to
            # agent_config.json/agent_arns.env and look like a real deployment.
            raise RuntimeError(
                f"Runtime {runtime_name} exists per the API but could not be found in "
                "list_agent_runtimes; cannot update it."
            )
        raise
    runtime_arn = response["agentRuntimeArn"]
    logger.info("Created AgentCore Runtime: %s -> %s", runtime_name, runtime_arn)

    # Wait for the runtime to become active
    logger.info("Waiting for runtime %s to become ACTIVE...", runtime_name)
    version = str(response.get("agentRuntimeVersion", "")) or None
    _wait_for_runtime_active(client, runtime_arn, expected_version=version)
    runtime_id = response.get("agentRuntimeId") or runtime_arn.split("/")[-1]
    _wait_for_default_endpoint(client, runtime_id, version)
    _check_runtime_environment(client, runtime_id, version, environment)

    return runtime_arn


def _wait_for_runtime_active(
    client,
    runtime_arn: str,
    max_wait_seconds: int = 300,
    expected_version: str | None = None,
) -> None:
    """Poll until the AgentCore Runtime reaches ACTIVE/READY.

    When ``expected_version`` is given, also wait until the runtime reports that
    version (right after an update the status can still read READY for the old one).
    """
    # Extract the runtime ID from the ARN (last segment)
    runtime_id = runtime_arn.split("/")[-1] if "/" in runtime_arn else runtime_arn

    start = time.time()
    while time.time() - start < max_wait_seconds:
        try:
            response = client.get_agent_runtime(agentRuntimeId=runtime_id)
            status = response.get("status", "UNKNOWN")
            version = str(response.get("agentRuntimeVersion", ""))
            if status in ("ACTIVE", "READY") and (
                expected_version is None or version == str(expected_version)
            ):
                logger.info("Runtime is ACTIVE: %s (version %s)", runtime_arn, version)
                return
            elif status in _FAILED_STATES:
                raise RuntimeError(
                    f"Runtime entered terminal state: {status} ({response.get('failureReason')})"
                )
            logger.info("Runtime status: %s (version %s), waiting...", status, version)
        except ClientError:
            pass
        time.sleep(10)

    raise TimeoutError(
        f"Runtime did not become ACTIVE within {max_wait_seconds}s"
    )


def save_config(agent_arns: dict[str, str]) -> None:
    """Save agent ARNs to the agent_config.json file."""
    config = {}
    for agent in AGENTS:
        config[agent["name"]] = {
            "arn": agent_arns.get(agent["name"], ""),
            "module": agent["module"],
        }

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n")
    logger.info("Saved agent config to %s", CONFIG_FILE)


def save_env_file(agent_arns: dict[str, str]) -> None:
    """Save agent ARNs to a .env file for orchestrator configuration."""
    env_lines = [
        "# Agent Runtime ARNs for Retail Dynamic Pricing",
        "# Generated by scripts/deploy_agentcore.py",
        "",
    ]

    for agent in AGENTS:
        var_name = AGENT_ARN_ENV_VARS[agent["name"]]
        arn = agent_arns.get(agent["name"], "")
        env_lines.append(f"{var_name}={arn}")

    ENV_FILE.write_text("\n".join(env_lines) + "\n")
    logger.info("Saved agent ARNs to %s", ENV_FILE)


def print_env_export(agent_arns: dict[str, str]) -> None:
    """Print agent ARNs in export format for shell usage."""
    print("\n# Export these environment variables for orchestrator configuration:")
    for agent in AGENTS:
        var_name = AGENT_ARN_ENV_VARS[agent["name"]]
        arn = agent_arns.get(agent["name"], "")
        print(f"export {var_name}={arn}")
    print()


def main() -> None:
    """Main deployment workflow."""
    parser = argparse.ArgumentParser(
        description="Deploy agents to Amazon Bedrock AgentCore Runtime"
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region for deployment (default: us-east-1)",
    )
    parser.add_argument(
        "--account-id",
        default=None,
        help="AWS account ID (auto-detected from STS if not provided)",
    )
    parser.add_argument(
        "--role-arn",
        required=True,
        help="IAM role ARN for AgentCore Runtime (created by create_agentcore_role.py)",
    )
    parser.add_argument(
        "--agents",
        nargs="*",
        help="Specific agents to deploy (default: all). Use agent short names like 'competitive-intelligence'",
    )
    parser.add_argument(
        "--gateway-name",
        default=DEFAULT_GATEWAY_NAME,
        help=f"Name of the AgentCore gateway to wire the agents to (default: {DEFAULT_GATEWAY_NAME})",
    )
    parser.add_argument(
        "--gateway-endpoint",
        default=None,
        help="Gateway MCP endpoint URL (<gatewayUrl>/mcp). Skips gateway discovery.",
    )
    parser.add_argument(
        "--memory-name",
        default=DEFAULT_MEMORY_NAME,
        help=f"Name of the AgentCore memory to wire the agents to (default: {DEFAULT_MEMORY_NAME})",
    )
    parser.add_argument(
        "--memory-id",
        default=None,
        help="AgentCore memory ID. Skips memory discovery.",
    )
    args = parser.parse_args()

    region = args.region
    role_arn = args.role_arn

    session = boto3.Session(region_name=region)

    # Auto-detect account ID if not provided
    account_id = args.account_id or get_account_id(session)

    logger.info("Deploying to account %s in region %s", account_id, region)
    logger.info("Using role ARN: %s", role_arn)

    # Filter agents if specific ones were requested
    agents_to_deploy = AGENTS
    if args.agents:
        agents_to_deploy = [a for a in AGENTS if a["name"] in args.agents]
        if not agents_to_deploy:
            logger.error("No matching agents found for: %s", args.agents)
            sys.exit(1)

    # Resolve what the agents must be wired to BEFORE building or pushing
    # anything: never deploy agents that are missing their gateway or memory.
    control = session.client("bedrock-agentcore-control", region_name=region)
    try:
        if args.gateway_endpoint:
            gateway_endpoint = args.gateway_endpoint.rstrip("/")
            if not (gateway_endpoint.startswith("https://") and gateway_endpoint.endswith("/mcp")):
                raise WiringError(
                    f"--gateway-endpoint must be the gateway's MCP URL "
                    f"(https://<gateway>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp), "
                    f"got {args.gateway_endpoint!r}."
                )
        else:
            gateway_endpoint = resolve_gateway_endpoint(control, args.gateway_name)
        memory_id = args.memory_id or resolve_memory_id(control, args.memory_name)

        # Specialist ARNs the orchestrator needs: those that already exist, then
        # (below) overridden by the ones created/updated in this run.
        known_arns = list_existing_agent_arns(control)
        deploying = {a["name"] for a in agents_to_deploy}
        if ORCHESTRATOR in deploying:
            unavailable = [n for n in SPECIALIST_AGENTS if n not in deploying and n not in known_arns]
            if unavailable:
                raise WiringError(
                    f"Cannot deploy the orchestrator: specialist runtimes {unavailable} do not "
                    "exist yet. Deploy them first (or deploy all agents)."
                )
    except (WiringError, ClientError) as e:
        logger.error("%s", e)
        logger.error("Aborting before any image is built: agents must not be deployed unwired.")
        sys.exit(1)

    # Agent read timeouts for the orchestrator (SPECIALIST_TIMEOUT_SECONDS /
    # SYNTHESIS_TIMEOUT_SECONDS). CDK derives the Lambda's timeouts from the same
    # values, so both deploys must see the same ones (deploy.sh exports them).
    try:
        timeouts = cycle_timeouts.resolve()
    except cycle_timeouts.InvalidTimeouts as e:
        logger.error("Invalid pricing-cycle timeouts: %s", e)
        logger.error("Aborting before any image is built.")
        sys.exit(1)
    logger.info("Pricing-cycle timeouts: %s", timeouts.describe())

    base_environment = {
        "AGENTCORE_GATEWAY_ENDPOINT": gateway_endpoint,
        "AGENTCORE_MEMORY_ID": memory_id,
        **load_model_environment(),
        **resolve_guardrail_environment(session, region),
        **timeouts.agent_environment(),
    }
    logger.info("Agent runtime wiring:")
    logger.info("  AGENTCORE_GATEWAY_ENDPOINT = %s", gateway_endpoint)
    logger.info("  AGENTCORE_MEMORY_ID        = %s", memory_id)
    for key in sorted(set(base_environment) - {"AGENTCORE_GATEWAY_ENDPOINT", "AGENTCORE_MEMORY_ID"}):
        logger.info("  %-26s = %s", key, base_environment[key])

    # Authenticate Docker to ECR
    registry_uri = ecr_login(region, account_id)

    agent_arns: dict[str, str] = {}

    for agent in agents_to_deploy:
        logger.info("=" * 60)
        logger.info("Deploying: %s (%s)", agent["runtime_name"], agent["name"])
        logger.info("=" * 60)

        # Ensure ECR repository exists
        ensure_ecr_repository(session, region, agent["ecr_repo"])

        # Build and push Docker image
        image_uri = build_and_push_image(agent, registry_uri, region)

        # Create or update AgentCore Runtime (idempotent)
        environment = build_environment(agent, base_environment, {**known_arns, **agent_arns})
        runtime_arn = create_or_update_agent_runtime(
            session, region, agent, image_uri, role_arn, environment
        )
        agent_arns[agent["name"]] = runtime_arn

    # Save outputs. A partial run (--agents ...) keeps the ARNs of the agents it
    # did not touch instead of overwriting them with empty values.
    all_arns = {**known_arns, **agent_arns}
    save_config(all_arns)
    save_env_file(all_arns)

    # Print summary
    logger.info("=" * 60)
    logger.info("Deployment complete! %d agent(s) deployed and wired.", len(agent_arns))
    logger.info("=" * 60)

    print_env_export(all_arns)

    logger.info("Config saved to: %s", CONFIG_FILE)
    logger.info("Env file saved to: %s", ENV_FILE)


if __name__ == "__main__":
    main()
