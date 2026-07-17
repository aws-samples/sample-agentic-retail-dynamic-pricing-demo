"""Create the IAM role required by Amazon Bedrock AgentCore Runtime.

This script creates an IAM role with:
- Trust policy allowing bedrock-agentcore.amazonaws.com to assume the role
- Permissions for: Bedrock model invocation, ECR image pull, CloudWatch Logs,
  DynamoDB access (for agents that need it)

Usage:
    python scripts/create_agentcore_role.py [--region us-east-1] [--role-name RetailPricingAgentCoreRole]
"""

from __future__ import annotations

import argparse
import json
import logging
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

ROLE_NAME_DEFAULT = "RetailPricingAgentCoreRole"

TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "bedrock-agentcore.amazonaws.com"
            },
            "Action": "sts:AssumeRole",
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
                    f"arn:aws:bedrock:{region}::foundation-model/*",
                    f"arn:aws:bedrock:us::{region}:foundation-model/*",
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
                "Sid": "LambdaInvokeMcpServers",
                "Effect": "Allow",
                "Action": [
                    "lambda:InvokeFunction",
                ],
                "Resource": [
                    f"arn:aws:lambda:{region}:{account_id}:function:rdp-mcp-*",
                ],
            },
        ],
    }


def create_role(
    session: boto3.Session, role_name: str, region: str
) -> str:
    """Create the IAM role for AgentCore Runtime. Returns the role ARN."""
    iam = session.client("iam")
    sts = session.client("sts")
    account_id = sts.get_caller_identity()["Account"]

    # Create the role
    try:
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(TRUST_POLICY),
            Description=(
                "IAM role for Retail Dynamic Pricing agents deployed to "
                "Amazon Bedrock AgentCore Runtime"
            ),
            Tags=[
                {"Key": "Project", "Value": "RetailDynamicPricing"},
                {"Key": "ManagedBy", "Value": "scripts/create_agentcore_role.py"},
            ],
        )
        role_arn = response["Role"]["Arn"]
        logger.info("Created IAM role: %s", role_arn)
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            response = iam.get_role(RoleName=role_name)
            role_arn = response["Role"]["Arn"]
            logger.info("Role already exists: %s", role_arn)

            # Update the trust policy in case it changed
            iam.update_assume_role_policy(
                RoleName=role_name,
                PolicyDocument=json.dumps(TRUST_POLICY),
            )
            logger.info("Updated trust policy for existing role")
        else:
            raise

    # Attach the inline policy
    inline_policy = get_inline_policy(account_id, region)
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName=INLINE_POLICY_NAME,
        PolicyDocument=json.dumps(inline_policy),
    )
    logger.info("Attached inline policy: %s", INLINE_POLICY_NAME)

    # Wait for role propagation
    logger.info("Waiting for IAM role propagation (10s)...")
    time.sleep(10)

    return role_arn


def main() -> None:
    """Create the AgentCore IAM role."""
    parser = argparse.ArgumentParser(
        description="Create IAM role for Bedrock AgentCore Runtime"
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )
    parser.add_argument(
        "--role-name",
        default=ROLE_NAME_DEFAULT,
        help=f"IAM role name (default: {ROLE_NAME_DEFAULT})",
    )
    args = parser.parse_args()

    session = boto3.Session(region_name=args.region)
    role_arn = create_role(session, args.role_name, args.region)

    logger.info("=" * 60)
    logger.info("IAM Role created successfully!")
    logger.info("Role ARN: %s", role_arn)
    logger.info("")
    logger.info("Use this ARN with deploy_agentcore.py:")
    logger.info(
        "  python scripts/deploy_agentcore.py --role-arn %s", role_arn
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
