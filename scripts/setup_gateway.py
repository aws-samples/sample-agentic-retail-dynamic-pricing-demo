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
    client = boto3.client("bedrock-agentcore-control", region_name=region)

    # Use the same AgentCore role for the gateway
    role_arn = os.environ.get(
        "AGENTCORE_ROLE_ARN",
        f"arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:role/RetailPricingAgentCoreRole"
    )

    # Create the gateway (idempotent — skip if already exists)
    print(f"Creating AgentCore Gateway in {region}...")
    from botocore.exceptions import ClientError

    gateway_id = None

    # Check if gateway already exists
    existing_gateways = client.list_gateways()
    for gw in existing_gateways.get("items", []):
        if gw.get("name") == "retail-pricing-gateway":
            gateway_id = gw["gatewayId"]
            print(f"  Gateway already exists: {gateway_id}")
            break

    if not gateway_id:
        gateway = client.create_gateway(
            name="retail-pricing-gateway",
            description="Gateway for Retail Dynamic Pricing MCP tools",
            roleArn=role_arn,
            authorizerType="NONE",
            protocolConfiguration={
                "mcp": {
                    "searchType": "SEMANTIC",
                }
            },
        )
        gateway_id = gateway["gatewayId"]
        print(f"  Created gateway: {gateway_id}")

    print(f"  Gateway ID: {gateway_id}")

    # Define MCP Server Lambda targets with their tool schemas
    mcp_targets = [
        {
            "name": "competitor-api",
            "description": "Competitor pricing data tools",
            "lambdaArn": os.environ["COMPETITOR_API_LAMBDA_ARN"],
            "toolSchema": {
                "inlinePayload": [
                    {"name": "get_competitor_prices", "description": "Get current competitor prices for a product", "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}},
                    {"name": "get_price_history", "description": "Get historical price data for a product", "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}, "days": {"type": "integer"}}, "required": ["product_id"]}},
                    {"name": "get_market_position", "description": "Get market positioning data for a product", "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}},
                ]
            },
        },
        {
            "name": "erp-pos",
            "description": "ERP/POS sales and inventory tools",
            "lambdaArn": os.environ["ERP_POS_LAMBDA_ARN"],
            "toolSchema": {
                "inlinePayload": [
                    {"name": "get_sales_history", "description": "Get weekly/monthly sales data", "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}, "period": {"type": "string"}}, "required": ["product_id"]}},
                    {"name": "get_pos_realtime", "description": "Get recent POS transaction data", "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}, "hours": {"type": "integer"}}, "required": ["product_id"]}},
                    {"name": "get_inventory_levels", "description": "Get current stock levels", "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}},
                    {"name": "get_elasticity_data", "description": "Get price elasticity by segment", "inputSchema": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}},
                ]
            },
        },
        {
            "name": "market-signals",
            "description": "Market trends and sentiment tools",
            "lambdaArn": os.environ["MARKET_SIGNALS_LAMBDA_ARN"],
            "toolSchema": {
                "inlinePayload": [
                    {"name": "get_market_trends", "description": "Get market trend indicators", "inputSchema": {"type": "object", "properties": {"category": {"type": "string"}}, "required": ["category"]}},
                    {"name": "get_consumer_sentiment", "description": "Get consumer sentiment scores", "inputSchema": {"type": "object", "properties": {"category": {"type": "string"}}, "required": ["category"]}},
                    {"name": "get_macro_indicators", "description": "Get macroeconomic indicators", "inputSchema": {"type": "object", "properties": {"region": {"type": "string"}}}},
                ]
            },
        },
        {
            "name": "cost-finance",
            "description": "Cost structure and financial constraints tools",
            "lambdaArn": os.environ["COST_FINANCE_LAMBDA_ARN"],
            "toolSchema": {
                "inlinePayload": [
                    {"name": "get_cost_structure", "description": "Get product cost breakdown", "inputSchema": {"type": "object", "properties": {"category": {"type": "string"}}}},
                    {"name": "get_margin_targets", "description": "Get target margins by channel", "inputSchema": {"type": "object", "properties": {"category": {"type": "string"}}}},
                    {"name": "get_financial_constraints", "description": "Get budget limits and rules", "inputSchema": {"type": "object", "properties": {"channel": {"type": "string"}}}},
                ]
            },
        },
    ]

    # Register each Lambda as a gateway target and collect target IDs
    print("\nRegistering MCP Server targets...")
    target_ids = []
    for target in mcp_targets:
        print(f"  Registering: {target['name']} ({target['lambdaArn']})")
        try:
            response = client.create_gateway_target(
                gatewayIdentifier=gateway_id,
                name=target["name"],
                description=target["description"],
                targetConfiguration={
                    "mcp": {
                        "lambda": {
                            "lambdaArn": target["lambdaArn"],
                            "toolSchema": target["toolSchema"],
                        }
                    }
                },
                credentialProviderConfigurations=[
                    {
                        "credentialProviderType": "GATEWAY_IAM_ROLE",
                    }
                ],
            )
            target_id = response.get("targetId", response.get("name", target["name"]))
            target_ids.append(target_id)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConflictException":
                print(f"    Target '{target['name']}' already exists — skipping")
                # Look up existing target ID for synchronization
                existing_targets = client.list_gateway_targets(gatewayIdentifier=gateway_id)
                for t in existing_targets.get("items", []):
                    if t.get("name") == target["name"]:
                        target_ids.append(t["targetId"])
                        break
            else:
                raise

    # Synchronize to discover tools from all targets
    print("\nSynchronizing gateway targets (discovering tools)...")
    client.synchronize_gateway_targets(
        gatewayIdentifier=gateway_id,
        targetIdList=target_ids,
    )

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
