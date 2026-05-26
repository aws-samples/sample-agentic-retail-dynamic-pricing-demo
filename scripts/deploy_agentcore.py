"""Deploy Retail Dynamic Pricing agents to Amazon Bedrock AgentCore Runtime.

This script:
1. Builds Docker images for each agent (ARM64 / linux/arm64)
2. Creates ECR repositories (if they don't exist)
3. Pushes images to ECR
4. Creates or updates AgentCore Runtimes via boto3 bedrock-agentcore-control client
5. Saves the agent runtime ARNs to agent_config.json and scripts/agent_arns.env

Prerequisites:
- Docker installed and running (with buildx for multi-platform builds)
- AWS CLI configured with appropriate permissions
- Model access granted for the Bedrock models used by agents

Usage:
    python scripts/deploy_agentcore.py --role-arn <arn> [--region us-east-1] [--account-id <id>]
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Agent definitions matching the spec naming conventions
AGENTS = [
    {
        "name": "competitive-intelligence",
        "runtime_name": "retail-pricing-competitive-intelligence",
        "ecr_repo": "retail-pricing/competitive-intelligence",
        "module": "competitive_intelligence_runtime",
        "description": "Analyzes competitor pricing, market positioning, and channel dynamics",
    },
    {
        "name": "demand-forecasting",
        "runtime_name": "retail-pricing-demand-forecasting",
        "ecr_repo": "retail-pricing/demand-forecasting",
        "module": "demand_forecasting_runtime",
        "description": "Analyzes sales history, POS data, inventory levels, and price elasticity",
    },
    {
        "name": "market-intelligence",
        "runtime_name": "retail-pricing-market-intelligence",
        "ecr_repo": "retail-pricing/market-intelligence",
        "module": "market_intelligence_runtime",
        "description": "Analyzes market trends, consumer sentiment, and macroeconomic indicators",
    },
    {
        "name": "strategy-synthesis",
        "runtime_name": "retail-pricing-strategy-synthesis",
        "ecr_repo": "retail-pricing/strategy-synthesis",
        "module": "strategy_synthesis_runtime",
        "description": "Generates ranked pricing scenarios from combined intelligence outputs",
    },
    {
        "name": "implementation-monitoring",
        "runtime_name": "retail-pricing-implementation-monitoring",
        "ecr_repo": "retail-pricing/implementation-monitoring",
        "module": "implementation_monitoring_runtime",
        "description": "Executes price updates and monitors KPI performance",
    },
    {
        "name": "orchestrator",
        "runtime_name": "retail-pricing-orchestrator",
        "ecr_repo": "retail-pricing/orchestrator",
        "module": "orchestrator_runtime",
        "description": "Coordinates pricing cycles by delegating to intelligence agents and synthesizing results",
    },
]

CONFIG_FILE = Path(__file__).parent.parent / "backend" / "agents" / "agentcore" / "agent_config.json"
ENV_FILE = Path(__file__).parent / "agent_arns.env"
PROJECT_ROOT = Path(__file__).parent.parent


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
        "--build-arg", f"AGENT_MODULE={agent['module']}",
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


def get_existing_runtime(
    client, runtime_name: str
) -> dict | None:
    """Check if an AgentCore Runtime already exists. Returns runtime info or None."""
    try:
        response = client.get_agent_runtime(agentRuntimeName=runtime_name)
        return response
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code in ("ResourceNotFoundException", "NotFoundException"):
            return None
        raise


def create_or_update_agent_runtime(
    session: boto3.Session,
    region: str,
    agent: dict,
    image_uri: str,
    role_arn: str,
) -> str:
    """Create or update an AgentCore Runtime for the agent. Returns the runtime ARN.

    Idempotent: if the runtime already exists, updates it instead of failing.
    """
    client = session.client("bedrock-agentcore-control", region_name=region)
    runtime_name = agent["runtime_name"]

    # Check if runtime already exists
    existing = get_existing_runtime(client, runtime_name)

    if existing:
        runtime_arn = existing["agentRuntimeArn"]
        logger.info(
            "Runtime %s already exists (ARN: %s), updating...",
            runtime_name,
            runtime_arn,
        )
        try:
            client.update_agent_runtime(
                agentRuntimeName=runtime_name,
                description=agent["description"],
                agentRuntimeArtifact={
                    "containerConfiguration": {
                        "containerUri": image_uri,
                    }
                },
                roleArn=role_arn,
                networkConfiguration={"networkMode": "PUBLIC"},
            )
            logger.info("Updated AgentCore Runtime: %s", runtime_name)
        except ClientError as e:
            logger.warning(
                "Could not update runtime %s: %s. Using existing.",
                runtime_name,
                e,
            )
        return runtime_arn

    # Create new runtime
    logger.info("Creating AgentCore Runtime: %s", runtime_name)
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
    )
    runtime_arn = response["agentRuntimeArn"]
    logger.info("Created AgentCore Runtime: %s -> %s", runtime_name, runtime_arn)

    # Wait for the runtime to become active
    logger.info("Waiting for runtime %s to become ACTIVE...", runtime_name)
    _wait_for_runtime_active(client, runtime_arn)

    return runtime_arn


def _wait_for_runtime_active(
    client, runtime_arn: str, max_wait_seconds: int = 300
) -> None:
    """Poll until the AgentCore Runtime reaches ACTIVE status."""
    start = time.time()
    while time.time() - start < max_wait_seconds:
        try:
            response = client.get_agent_runtime(agentRuntimeArn=runtime_arn)
            status = response.get("status", "UNKNOWN")
            if status == "ACTIVE":
                logger.info("Runtime is ACTIVE: %s", runtime_arn)
                return
            elif status in ("FAILED", "DELETING"):
                raise RuntimeError(
                    f"Runtime entered terminal state: {status}"
                )
            logger.info("Runtime status: %s, waiting...", status)
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

    env_var_map = {
        "competitive-intelligence": "COMPETITIVE_INTELLIGENCE_AGENT_ARN",
        "demand-forecasting": "DEMAND_FORECASTING_AGENT_ARN",
        "market-intelligence": "MARKET_INTELLIGENCE_AGENT_ARN",
        "strategy-synthesis": "STRATEGY_SYNTHESIS_AGENT_ARN",
        "implementation-monitoring": "IMPLEMENTATION_MONITORING_AGENT_ARN",
        "orchestrator": "ORCHESTRATOR_AGENT_ARN",
    }

    for agent in AGENTS:
        var_name = env_var_map[agent["name"]]
        arn = agent_arns.get(agent["name"], "")
        env_lines.append(f"{var_name}={arn}")

    ENV_FILE.write_text("\n".join(env_lines) + "\n")
    logger.info("Saved agent ARNs to %s", ENV_FILE)


def print_env_export(agent_arns: dict[str, str]) -> None:
    """Print agent ARNs in export format for shell usage."""
    env_var_map = {
        "competitive-intelligence": "COMPETITIVE_INTELLIGENCE_AGENT_ARN",
        "demand-forecasting": "DEMAND_FORECASTING_AGENT_ARN",
        "market-intelligence": "MARKET_INTELLIGENCE_AGENT_ARN",
        "strategy-synthesis": "STRATEGY_SYNTHESIS_AGENT_ARN",
        "implementation-monitoring": "IMPLEMENTATION_MONITORING_AGENT_ARN",
        "orchestrator": "ORCHESTRATOR_AGENT_ARN",
    }

    print("\n# Export these environment variables for orchestrator configuration:")
    for agent in AGENTS:
        var_name = env_var_map[agent["name"]]
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
    args = parser.parse_args()

    region = args.region
    role_arn = args.role_arn

    session = boto3.Session(region_name=region)

    # Auto-detect account ID if not provided
    account_id = args.account_id or get_account_id(session)

    logger.info("Deploying to account %s in region %s", account_id, region)
    logger.info("Using role ARN: %s", role_arn)

    # Authenticate Docker to ECR
    registry_uri = ecr_login(region, account_id)

    # Filter agents if specific ones were requested
    agents_to_deploy = AGENTS
    if args.agents:
        agents_to_deploy = [a for a in AGENTS if a["name"] in args.agents]
        if not agents_to_deploy:
            logger.error("No matching agents found for: %s", args.agents)
            sys.exit(1)

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
        runtime_arn = create_or_update_agent_runtime(
            session, region, agent, image_uri, role_arn
        )
        agent_arns[agent["name"]] = runtime_arn

    # Save outputs
    save_config(agent_arns)
    save_env_file(agent_arns)

    # Print summary
    logger.info("=" * 60)
    logger.info("Deployment complete! All %d agents registered.", len(agent_arns))
    logger.info("=" * 60)

    print_env_export(agent_arns)

    logger.info("Config saved to: %s", CONFIG_FILE)
    logger.info("Env file saved to: %s", ENV_FILE)


if __name__ == "__main__":
    main()
