"""Register MCP Server Lambda functions as AgentCore Gateway targets.

This script creates an AgentCore Gateway and registers each MCP Server Lambda
as a target, enabling agents to discover and invoke tools through the gateway
endpoint rather than connecting to individual MCP servers directly.

Usage:
    python scripts/setup_gateway.py [--region us-east-1]

Required environment variables:
    COMPETITOR_API_LAMBDA_ARN: ARN of the Competitor API MCP Server Lambda
    ERP_POS_LAMBDA_ARN: ARN of the ERP/POS MCP Server Lambda
    MARKET_SIGNALS_LAMBDA_ARN: ARN of the Market Signals MCP Server Lambda
    COST_FINANCE_LAMBDA_ARN: ARN of the Cost/Finance MCP Server Lambda
"""

from __future__ import annotations

import argparse
import os
import sys

import boto3


def setup_gateway(region: str = "us-east-1") -> str:
    """Create an AgentCore Gateway and register MCP Server Lambda targets.

    Args:
        region: AWS region to create the gateway in.

    Returns:
        The gateway ID.
    """
    client = boto3.client("bedrock-agentcore", region_name=region)

    # Create the gateway
    print(f"Creating AgentCore Gateway in {region}...")
    gateway = client.create_gateway(
        name="retail-pricing-gateway",
        description="Gateway for Retail Dynamic Pricing MCP tools",
        protocolType="MCP",
    )
    gateway_id = gateway["gatewayId"]
    print(f"  Gateway ID: {gateway_id}")

    # Define MCP Server Lambda targets
    mcp_targets = [
        {
            "name": "competitor-api",
            "description": "Competitor pricing data tools",
            "lambdaArn": os.environ["COMPETITOR_API_LAMBDA_ARN"],
        },
        {
            "name": "erp-pos",
            "description": "ERP/POS sales and inventory tools",
            "lambdaArn": os.environ["ERP_POS_LAMBDA_ARN"],
        },
        {
            "name": "market-signals",
            "description": "Market trends and sentiment tools",
            "lambdaArn": os.environ["MARKET_SIGNALS_LAMBDA_ARN"],
        },
        {
            "name": "cost-finance",
            "description": "Cost structure and financial constraints tools",
            "lambdaArn": os.environ["COST_FINANCE_LAMBDA_ARN"],
        },
    ]

    # Register each Lambda as a gateway target
    print("\nRegistering MCP Server targets...")
    for target in mcp_targets:
        print(f"  Registering: {target['name']} ({target['lambdaArn']})")
        client.create_gateway_target(
            gatewayId=gateway_id,
            name=target["name"],
            description=target["description"],
            connectionConfiguration={
                "lambdaConnection": {
                    "lambdaArn": target["lambdaArn"],
                }
            },
        )

    # Synchronize to discover tools from all targets
    print("\nSynchronizing gateway targets (discovering tools)...")
    client.synchronize_gateway_targets(gatewayId=gateway_id)

    print(f"\nGateway setup complete!")
    print(f"  Gateway ID: {gateway_id}")
    print(f"  Targets registered: {len(mcp_targets)}")
    print(f"\nExport the gateway endpoint for your agent containers:")
    print(f"  export AGENTCORE_GATEWAY_ENDPOINT=<gateway-endpoint-url>")

    return gateway_id


def main():
    parser = argparse.ArgumentParser(
        description="Setup AgentCore Gateway for Retail Dynamic Pricing MCP tools"
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )
    args = parser.parse_args()

    # Validate required environment variables
    required_vars = [
        "COMPETITOR_API_LAMBDA_ARN",
        "ERP_POS_LAMBDA_ARN",
        "MARKET_SIGNALS_LAMBDA_ARN",
        "COST_FINANCE_LAMBDA_ARN",
    ]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        print(
            f"Error: Missing required environment variables: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        setup_gateway(region=args.region)
    except Exception as e:
        print(f"Error setting up gateway: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
