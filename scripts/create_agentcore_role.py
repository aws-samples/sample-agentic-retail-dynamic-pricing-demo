"""Create (or update in place) the IAM roles used by Amazon Bedrock AgentCore.

RetailPricingAgentCoreRole: execution role of the six agent runtimes. Bedrock model
    invocation (and ApplyGuardrail), ECR image pull, CloudWatch Logs, DynamoDB,
    AgentCore Memory data plane, AgentCore Gateway invocation (InvokeGateway, for
    the SigV4-signed MCP calls), and invoking the specialist runtimes
    (orchestrator -> specialists).
RetailPricingGatewayRole: service role of the AgentCore Gateway. Only invokes the
    four MCP server Lambdas (rdp-mcp-*) behind the gateway targets.

Both trust policies allow only bedrock-agentcore.amazonaws.com, and only for
resources in this account and Region (aws:SourceAccount / aws:SourceArn), so another
account's AgentCore resource cannot use them (confused-deputy protection).

Idempotent: existing roles get their trust policy and inline policy overwritten
with the current definitions, so rerunning this script is how permission changes
reach an existing deployment.

Usage:
    python scripts/create_agentcore_role.py [--region us-east-1] [--role-name RetailPricingAgentCoreRole]
        [--gateway-role-name RetailPricingGatewayRole]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for shared/
from shared.pricing_guardrail import guardrail_profile_for_region  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

ROLE_NAME_DEFAULT = "RetailPricingAgentCoreRole"
GATEWAY_ROLE_NAME_DEFAULT = "RetailPricingGatewayRole"
# Gateway IDs are <name>-<suffix>. The prefix matches the SigV4 gateway
# (retail-pricing-gateway-iam, scripts/setup_gateway.py) and the open
# retail-pricing-gateway of earlier versions, which uses the gateway role until
# deploy.sh deletes it (scripts/secure_gateway.py).
GATEWAY_ID_PREFIX = "retail-pricing-gateway"


def _service_trust_policy(sid: str, account_id: str, source_arn: str) -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": sid,
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {"aws:SourceArn": source_arn},
                },
            }
        ],
    }


def runtime_trust_policy(account_id: str, region: str) -> dict:
    """AgentCore resources in this account and Region (the documented runtime trust policy)."""
    return _service_trust_policy(
        "AgentCoreRuntimeAssumeRole", account_id, f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
    )


def gateway_trust_policy(account_id: str, region: str) -> dict:
    """Only the retail pricing gateways in this account and Region."""
    return _service_trust_policy(
        "AgentCoreGatewayAssumeRole",
        account_id,
        f"arn:aws:bedrock-agentcore:{region}:{account_id}:gateway/{GATEWAY_ID_PREFIX}-*",
    )


GATEWAY_POLICY_NAME = "RetailPricingGatewayPolicy"


def get_gateway_policy(account_id: str, region: str) -> dict:
    """The gateway invokes the MCP server Lambdas behind its targets, and nothing else."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "InvokeMcpServerLambdas",
                "Effect": "Allow",
                "Action": ["lambda:InvokeFunction"],
                "Resource": [f"arn:aws:lambda:{region}:{account_id}:function:rdp-mcp-*"],
            }
        ],
    }


INLINE_POLICY_NAME = "RetailPricingAgentCorePolicy"


def get_inline_policy(account_id: str, region: str) -> dict:
    """Build the inline policy document for AgentCore Runtime agents."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockModelInvocation",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                "Resource": [
                    # Foundation models in all regions (cross-region inference
                    # profiles route to the underlying model in several regions).
                    "arn:aws:bedrock:*::foundation-model/*",
                    # Cross-region inference profiles (the us.anthropic.* IDs the
                    # agents actually invoke) live in the caller's account.
                    f"arn:aws:bedrock:{region}:{account_id}:inference-profile/us.anthropic.*",
                ],
            },
            {
                "Sid": "ECRAuthToken",
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken",
                ],
                "Resource": "*",
            },
            {
                "Sid": "ECRImagePull",
                "Effect": "Allow",
                "Action": [
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:BatchCheckLayerAvailability",
                ],
                "Resource": [
                    f"arn:aws:ecr:{region}:{account_id}:repository/retail-pricing/*",
                ],
            },
            {
                "Sid": "CloudWatchLogs",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/*",
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/*:*",
                ],
            },
            {
                "Sid": "DynamoDBAccess",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:BatchGetItem",
                    "dynamodb:BatchWriteItem",
                ],
                "Resource": [
                    f"arn:aws:dynamodb:{region}:{account_id}:table/RetailPricing*",
                ],
            },
            {
                "Sid": "S3ReadAccess",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:ListBucket",
                ],
                "Resource": [
                    f"arn:aws:s3:::retail-pricing-{account_id}-{region}",
                    f"arn:aws:s3:::retail-pricing-{account_id}-{region}/*",
                ],
            },
            {
                # Data-plane calls the Strands AgentCoreMemorySessionManager makes
                # (CreateEvent/GetEvent/ListEvents/DeleteEvent for session state,
                # RetrieveMemoryRecords for long-term retrieval). Scoped to the
                # memory created by scripts/setup_memory.py (ID = name + suffix).
                "Sid": "AgentCoreMemoryDataPlane",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:GetEvent",
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:DeleteEvent",
                    "bedrock-agentcore:RetrieveMemoryRecords",
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:memory/RetailDynamicPricingMemory-*",
                ],
            },
            {
                # The orchestrator invokes the five specialist runtimes with
                # bedrock-agentcore InvokeAgentRuntime under this role. The trailing
                # wildcard also covers the .../runtime-endpoint/DEFAULT ARN.
                "Sid": "InvokeSpecialistRuntimes",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:InvokeAgentRuntime",
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:runtime/retailPricing_*",
                ],
            },
            {
                # The gateway uses AWS_IAM inbound authorization: the agents sign their
                # MCP requests with this role (backend/agents/agentcore/gateway_auth.py).
                # Scoped to the gateways from scripts/setup_gateway.py.
                "Sid": "InvokeRetailPricingGateway",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:InvokeGateway",
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:gateway/{GATEWAY_ID_PREFIX}-*",
                ],
            },
            {
                # The stack's guardrail is attached to every Converse call
                # (backend/agents/agentcore/guardrail_config.py). It uses the Standard
                # tier, which evaluates through the geography's cross-Region guardrail
                # profile, so ApplyGuardrail is also needed on that profile in every
                # destination Region of this account.
                "Sid": "BedrockApplyGuardrail",
                "Effect": "Allow",
                "Action": [
                    "bedrock:ApplyGuardrail",
                ],
                "Resource": [
                    f"arn:aws:bedrock:{region}:{account_id}:guardrail/*",
                    f"arn:aws:bedrock:*:{account_id}:guardrail-profile/{guardrail_profile_for_region(region)}",
                ],
            },
        ],
    }


def ensure_role(
    iam, role_name: str, trust_policy: dict, policy_name: str, policy: dict, description: str
) -> tuple[str, bool]:
    """Create the role, or update its trust policy if it exists; then apply the inline policy.

    Returns (role ARN, created).
    """
    created = False
    try:
        role_arn = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description=description,
            Tags=[
                {"Key": "Project", "Value": "RetailDynamicPricing"},
                {"Key": "ManagedBy", "Value": "scripts/create_agentcore_role.py"},
            ],
        )["Role"]["Arn"]
        created = True
        logger.info("Created IAM role: %s", role_arn)
    except ClientError as e:
        if e.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
        iam.update_assume_role_policy(RoleName=role_name, PolicyDocument=json.dumps(trust_policy))
        logger.info("Role already exists: %s (trust policy updated)", role_arn)

    # put_role_policy replaces the document, which is how permission changes reach
    # a role created by an earlier version of this script.
    iam.put_role_policy(RoleName=role_name, PolicyName=policy_name, PolicyDocument=json.dumps(policy))
    logger.info("Applied inline policy %s to %s (%d statements)", policy_name, role_name, len(policy["Statement"]))
    return role_arn, created


def create_roles(
    session: boto3.Session,
    region: str,
    role_name: str = ROLE_NAME_DEFAULT,
    gateway_role_name: str = GATEWAY_ROLE_NAME_DEFAULT,
) -> tuple[str, str]:
    """Create or update the runtime and gateway roles. Returns (runtime role ARN, gateway role ARN)."""
    iam = session.client("iam")
    account_id = session.client("sts").get_caller_identity()["Account"]

    runtime_arn, runtime_created = ensure_role(
        iam, role_name, runtime_trust_policy(account_id, region),
        INLINE_POLICY_NAME, get_inline_policy(account_id, region),
        "IAM role for Retail Dynamic Pricing agents deployed to Amazon Bedrock AgentCore Runtime",
    )
    gateway_arn, gateway_created = ensure_role(
        iam, gateway_role_name, gateway_trust_policy(account_id, region),
        GATEWAY_POLICY_NAME, get_gateway_policy(account_id, region),
        "Service role of the Retail Dynamic Pricing AgentCore Gateway (invokes the MCP server Lambdas)",
    )

    # New roles and trust-policy changes take a few seconds to propagate in IAM.
    logger.info("Waiting for IAM propagation (%ds)...", 15 if (runtime_created or gateway_created) else 10)
    time.sleep(15 if (runtime_created or gateway_created) else 10)
    return runtime_arn, gateway_arn


def create_role(session: boto3.Session, role_name: str, region: str) -> str:
    """Create or update both roles; returns the runtime role ARN (kept for existing callers)."""
    return create_roles(session, region, role_name=role_name)[0]


def main() -> None:
    """Create the AgentCore IAM roles."""
    parser = argparse.ArgumentParser(description="Create the IAM roles for Bedrock AgentCore")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument("--role-name", default=ROLE_NAME_DEFAULT,
                        help=f"runtime execution role name (default: {ROLE_NAME_DEFAULT})")
    parser.add_argument("--gateway-role-name", default=GATEWAY_ROLE_NAME_DEFAULT,
                        help=f"gateway service role name (default: {GATEWAY_ROLE_NAME_DEFAULT})")
    args = parser.parse_args()

    session = boto3.Session(region_name=args.region)
    runtime_arn, gateway_arn = create_roles(session, args.region, args.role_name, args.gateway_role_name)

    logger.info("=" * 60)
    logger.info("IAM roles ready (created, or updated in place)")
    logger.info("Runtime role: %s", runtime_arn)
    logger.info("Gateway role: %s", gateway_arn)
    logger.info("  python scripts/deploy_agentcore.py --role-arn %s", runtime_arn)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
