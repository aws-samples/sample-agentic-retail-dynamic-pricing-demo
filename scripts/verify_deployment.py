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
from botocore.exceptions import ClientError


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
