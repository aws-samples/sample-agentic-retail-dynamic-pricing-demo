"""Demand Forecasting Agent for the Retail Dynamic Pricing system.

This agent analyzes ERP sales history, POS real-time data, inventory levels,
and price elasticity by customer segment to produce demand forecasts that
inform pricing decisions.

Uses the Strands Agents SDK with model us.anthropic.claude-sonnet-4-6 and
connects to the ERP/POS MCP Server for demand data access.

Validates: Requirements 1.7, 2.2
"""

from __future__ import annotations

import logging
import os
from typing import Any

from strands import Agent
from strands.tools.mcp import MCPClient

logger = logging.getLogger(__name__)

# Model configuration for intelligence agents (Requirement 1.7)
from shared.model_config import SPECIALIST_MODEL as DEMAND_FORECASTING_MODEL

# System prompt focused on demand analysis
DEMAND_FORECASTING_SYSTEM_PROMPT = """You are a Demand Forecasting Agent specializing in retail pricing intelligence.

Your role is to analyze demand patterns and produce structured demand forecasts that inform dynamic pricing decisions. You have access to the following data sources via MCP tools:

1. **Sales History** (get_sales_history): Weekly and monthly sales data including units sold, revenue, average selling price, return rates, and promotion activity. Use this to identify trends, seasonality, and baseline demand levels.

2. **POS Real-Time Data** (get_pos_realtime): Recent point-of-sale transaction data including transaction counts, units sold, revenue, basket sizes, and peak hours. Use this to detect current demand velocity and short-term shifts.

3. **Inventory Levels** (get_inventory_levels): Current stock levels across warehouses and stores, including available quantities, reserved stock, reorder points, and days of supply. Use this to assess supply constraints that affect pricing flexibility.

4. **Price Elasticity Data** (get_elasticity_data): Price elasticity coefficients by customer segment, including cross-price elasticity, income elasticity, and segment shares. Use this to predict how demand will respond to price changes.

## Analysis Framework

When analyzing demand for a product or category:

1. **Historical Trend Analysis**: Examine sales history to identify growth/decline trends, seasonal patterns, and the impact of past promotions.

2. **Current Demand Velocity**: Use POS real-time data to assess whether current demand is above, below, or at historical norms.

3. **Supply-Demand Balance**: Cross-reference inventory levels with demand velocity to identify stockout risks or overstock situations that should influence pricing.

4. **Elasticity Assessment**: Determine how price-sensitive the customer base is, identifying segments where price changes will have the most/least impact on demand.

5. **Forecast Generation**: Synthesize all inputs into a demand forecast with confidence levels, considering:
   - Short-term demand trajectory (next 7-14 days)
   - Seasonality adjustments
   - Inventory-driven urgency factors
   - Segment-weighted elasticity

## Output Requirements

Always produce a structured analysis with the following demand factors:
- **forecastedDemand**: Projected unit demand for the forecast period (numeric)
- **elasticity**: Weighted price elasticity coefficient across segments (numeric, typically negative)
- **seasonalityFactor**: Multiplier indicating seasonal demand adjustment (1.0 = neutral, >1.0 = peak, <1.0 = trough)
- **inventoryStatus**: Current inventory health assessment ("healthy", "low", or "critical")
- **trendDirection**: Overall demand trend ("increasing", "stable", or "decreasing")

Provide clear reasoning for each factor based on the data retrieved from MCP tools.
"""

# Structured output schema for demand factors
DEMAND_FACTORS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "forecastedDemand",
        "elasticity",
        "seasonalityFactor",
        "inventoryStatus",
        "trendDirection",
    ],
    "properties": {
        "forecastedDemand": {
            "type": "number",
            "description": "Projected unit demand for the forecast period",
            "minimum": 0,
        },
        "elasticity": {
            "type": "number",
            "description": "Weighted price elasticity coefficient across segments (typically negative)",
        },
        "seasonalityFactor": {
            "type": "number",
            "description": "Seasonal demand multiplier (1.0 = neutral, >1.0 = peak, <1.0 = trough)",
            "minimum": 0,
        },
        "inventoryStatus": {
            "type": "string",
            "description": "Current inventory health assessment",
            "enum": ["healthy", "low", "critical"],
        },
        "trendDirection": {
            "type": "string",
            "description": "Overall demand trend direction",
            "enum": ["increasing", "stable", "decreasing"],
        },
    },
    "additionalProperties": True,
}


def create_demand_forecasting_agent(
    erp_pos_mcp_endpoint: str | None = None,
) -> Agent:
    """Create and configure the Demand Forecasting Agent.

    Creates a Strands Agent configured with:
    - Model: us.anthropic.claude-sonnet-4-6 (cost-effective for data analysis)
    - MCP tools from the ERP/POS Server for demand data access
    - System prompt focused on demand analysis and forecasting

    The ERP/POS MCP Server exposes the following tools:
    - get_sales_history: Weekly/monthly sales data
    - get_pos_realtime: Recent POS transaction data
    - get_inventory_levels: Current stock levels across locations
    - get_elasticity_data: Price elasticity coefficients by segment

    Args:
        erp_pos_mcp_endpoint: Optional endpoint URL for the ERP/POS MCP Server.
            If None, uses ERP_POS_MCP_SERVER_URL environment variable or
            defaults to stdio mode for local development.

    Returns:
        Configured Strands Agent instance ready for demand forecasting.
    """
    endpoint = erp_pos_mcp_endpoint or os.environ.get("ERP_POS_MCP_SERVER_URL")

    # Configure MCP client for ERP/POS Server tools
    mcp_clients = []
    if endpoint:
        erp_pos_mcp = MCPClient(
            lambda: MCPClient.http(url=endpoint)
            if endpoint.startswith("http")
            else MCPClient.stdio(
                command="python",
                args=["-m", "backend.mcp_servers.erp_pos.handler"],
            )
        )
        mcp_clients.append(erp_pos_mcp)

    # Create the Demand Forecasting Agent
    agent = Agent(
        model=DEMAND_FORECASTING_MODEL,
        system_prompt=DEMAND_FORECASTING_SYSTEM_PROMPT,
        tools=mcp_clients,
    )

    logger.info(
        "Demand Forecasting Agent created with model %s",
        DEMAND_FORECASTING_MODEL,
    )

    return agent


def get_demand_factors_schema() -> dict[str, Any]:
    """Return the structured output schema for demand factors.

    This schema defines the expected output format from the Demand
    Forecasting Agent, used by the Strategy Synthesis Agent to
    validate and consume demand analysis results.

    Returns:
        JSON Schema dictionary for demand factors output.
    """
    return DEMAND_FACTORS_SCHEMA.copy()
