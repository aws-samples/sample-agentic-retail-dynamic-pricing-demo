"""Automated frontend configuration sync from CDK outputs.

Reads the CDK stack outputs (from cdk-outputs.json or CloudFormation API)
and writes .env files for both Dashboard and Storefront frontends.

Eliminates the need to manually copy-paste API URLs, Cognito IDs,
and CloudFront domains into frontend .env files.

Usage:
    python3 scripts/sync_frontend_config.py [--region us-east-1]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

PROJECT_ROOT = Path(__file__).parent.parent
CDK_OUTPUTS_FILE = PROJECT_ROOT / "cdk-outputs.json"
DASHBOARD_ENV = PROJECT_ROOT / "frontend" / "dashboard" / ".env"
STOREFRONT_ENV = PROJECT_ROOT / "frontend" / "storefront" / ".env"


def get_stack_outputs(region: str) -> dict[str, str]:
    """Get CDK stack outputs from cdk-outputs.json or CloudFormation API.

    Args:
        region: AWS region to query.

    Returns:
        Dictionary of output key-value pairs.
    """
    # Try cdk-outputs.json first (faster, no API call)
    if CDK_OUTPUTS_FILE.exists():
        with open(CDK_OUTPUTS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        stack_outputs = data.get("RetailDynamicPricing", {})
        if stack_outputs:
            print(f"  Read outputs from {CDK_OUTPUTS_FILE.name}")
            return stack_outputs

    # Fall back to CloudFormation API
    print("  Querying CloudFormation API for stack outputs...")
    cf = boto3.client("cloudformation", region_name=region)
    try:
        response = cf.describe_stacks(StackName="RetailDynamicPricing")
        stack = response["Stacks"][0]
        outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
        return outputs
    except ClientError as e:
        print(f"  ERROR: Could not read stack outputs: {e}")
        sys.exit(1)


def find_output(outputs: dict[str, str], *keywords: str) -> str:
    """Find a stack output by partial key match.

    Args:
        outputs: Dictionary of stack outputs.
        keywords: Keywords to search for in output keys.

    Returns:
        The output value, or empty string if not found.
    """
    for key, value in outputs.items():
        if all(kw in key for kw in keywords):
            return value
    return ""


def write_dashboard_env(outputs: dict[str, str], region: str) -> None:
    """Write the Dashboard frontend .env file.

    Args:
        outputs: CDK stack outputs.
        region: AWS region for Cognito domain construction.
    """
    api_url = find_output(outputs, "ApiGateway", "Url") or find_output(outputs, "PricingApi", "Endpoint")
    user_pool_id = find_output(outputs, "UserPool", "Id")
    client_id = find_output(outputs, "UserPoolClient", "Id")
    cognito_domain = find_output(outputs, "CognitoDomain")

    # Strip trailing slash from API URL for consistency
    api_url = api_url.rstrip("/")

    if not api_url:
        print("  WARNING: API Gateway URL not found in outputs")
    if not user_pool_id:
        print("  WARNING: Cognito User Pool ID not found in outputs")

    env_content = f"""VITE_API_URL={api_url}
VITE_COGNITO_USER_POOL_ID={user_pool_id}
VITE_COGNITO_CLIENT_ID={client_id}
VITE_COGNITO_DOMAIN={cognito_domain}
"""

    DASHBOARD_ENV.write_text(env_content)
    print(f"  Written: {DASHBOARD_ENV.relative_to(PROJECT_ROOT)}")
    print(f"    VITE_API_URL={api_url}")
    print(f"    VITE_COGNITO_USER_POOL_ID={user_pool_id}")
    print(f"    VITE_COGNITO_CLIENT_ID={client_id}")
    print(f"    VITE_COGNITO_DOMAIN={cognito_domain}")


def write_storefront_env(outputs: dict[str, str]) -> None:
    """Write the Storefront frontend .env file.

    Args:
        outputs: CDK stack outputs.
    """
    api_url = find_output(outputs, "ApiGateway", "Url") or find_output(outputs, "PricingApi", "Endpoint")
    api_url = api_url.rstrip("/")

    env_content = f"""VITE_API_URL={api_url}
"""

    STOREFRONT_ENV.write_text(env_content)
    print(f"  Written: {STOREFRONT_ENV.relative_to(PROJECT_ROOT)}")
    print(f"    VITE_API_URL={api_url}")


def main():
    parser = argparse.ArgumentParser(
        description="Sync frontend .env files from CDK stack outputs"
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    args = parser.parse_args()

    print("")
    print("=" * 60)
    print("  Frontend Config Sync")
    print("=" * 60)
    print("")

    outputs = get_stack_outputs(args.region)

    if not outputs:
        print("  ERROR: No stack outputs found. Deploy CDK first.")
        sys.exit(1)

    print(f"\n  Dashboard ({DASHBOARD_ENV.relative_to(PROJECT_ROOT)}):")
    write_dashboard_env(outputs, args.region)

    print(f"\n  Storefront ({STOREFRONT_ENV.relative_to(PROJECT_ROOT)}):")
    write_storefront_env(outputs)

    print("")
    print("  Done! Frontend .env files updated from CDK outputs.")
    print("  Run 'npm run build' in each frontend directory to rebuild.")
    print("")


if __name__ == "__main__":
    main()
