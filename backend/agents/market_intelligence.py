"""Market Intelligence Agent for the Retail Dynamic Pricing system.

This agent performs cross-product analysis, market structure insights,
and opportunity detection using market trend data, consumer sentiment,
and macroeconomic indicators.

Uses the Strands Agents SDK with MCP tools from the Market Signals Server.

Requirements: 1.7, 2.3
"""

from __future__ import annotations

import os
from typing import Any

from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.tools.mcp import MCPClient

# Model configuration for intelligence agents (Requirement 1.7)
from shared.model_config import SPECIALIST_MODEL as MARKET_INTELLIGENCE_MODEL

# System prompt focused on market analysis and opportunity detection
MARKET_INTELLIGENCE_SYSTEM_PROMPT = """You are a Market Intelligence Agent specializing in retail market analysis and opportunity detection.

Your role is to analyze market conditions, consumer sentiment, and macroeconomic factors to identify pricing opportunities and risks. You have access to the following data sources via MCP tools:

1. **Market Trends** (get_market_trends): Market trend indicators including growth rate, seasonality index, category momentum, volatility, trend direction, and demand shift. Use this to understand the broader market dynamics affecting pricing decisions.

2. **Consumer Sentiment** (get_consumer_sentiment): Consumer sentiment scores on a 0-1 scale including overall sentiment, purchase intent, brand perception, price sensitivity, satisfaction, social buzz, and review sentiment breakdowns. Use this to gauge consumer willingness to accept price changes.

3. **Macro Indicators** (get_macro_indicators): Macroeconomic indicators including CPI, consumer confidence index, unemployment rate, GDP growth, interest rates, retail sales growth, and disposable income changes. Use this to assess the broader economic environment affecting purchasing power.

## Analysis Framework

When analyzing market conditions for a product or category:

1. **Cross-Product Analysis**: Examine how market trends affect the product category relative to adjacent categories. Identify cross-category demand shifts and substitution effects.

2. **Market Structure Assessment**: Evaluate the competitive landscape structure, market concentration, and barriers to price movement. Determine if the market favors price leadership or following.

3. **Opportunity Detection**: Identify pricing opportunities based on:
   - Positive sentiment trends indicating willingness to pay more
   - Market momentum suggesting growing demand
   - Macro conditions supporting consumer spending
   - Low volatility windows for safe price adjustments
   - Seasonal peaks where premium pricing is accepted

4. **Risk Assessment**: Identify pricing risks based on:
   - Negative sentiment shifts indicating price resistance
   - Economic headwinds reducing disposable income
   - High market volatility suggesting caution
   - Declining category momentum

5. **Timing Recommendations**: Synthesize all signals to recommend optimal timing for price changes, considering market momentum, sentiment cycles, and economic outlook.

## Output Requirements

Always produce a structured analysis with the following market factors:
- **trendScore**: Composite market trend score from -1.0 (strongly negative) to 1.0 (strongly positive), synthesizing growth rate, momentum, and trend direction
- **sentimentScore**: Weighted consumer sentiment score from 0.0 to 1.0, combining overall sentiment, purchase intent, and price sensitivity (inverted)
- **macroOutlook**: Economic outlook classification ("bullish", "neutral", or "bearish") based on macro indicators
- **opportunityIndicators**: List of identified pricing opportunities with brief descriptions
- **marketMomentum**: Overall market momentum assessment ("accelerating", "stable", or "decelerating") based on trend direction and category momentum

Provide clear reasoning for each factor based on the data retrieved from MCP tools. Highlight any conflicting signals between data sources and explain how you resolved them.
"""

# Structured output schema for market factors
MARKET_FACTORS_SCHEMA = {
    "type": "object",
    "required": [
        "trendScore",
        "sentimentScore",
        "macroOutlook",
        "opportunityIndicators",
        "marketMomentum",
    ],
    "properties": {
        "trendScore": {
            "type": "number",
            "description": "Composite market trend score from -1.0 (strongly negative) to 1.0 (strongly positive)",
            "minimum": -1.0,
            "maximum": 1.0,
        },
        "sentimentScore": {
            "type": "number",
            "description": "Weighted consumer sentiment score from 0.0 to 1.0",
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "macroOutlook": {
            "type": "string",
            "description": "Economic outlook classification based on macro indicators",
            "enum": ["bullish", "neutral", "bearish"],
        },
        "opportunityIndicators": {
            "type": "array",
            "description": "List of identified pricing opportunities",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "description": "Type of opportunity (e.g., 'premium_pricing', 'market_expansion', 'seasonal_peak')",
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief description of the opportunity",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence level for this opportunity (0.0 to 1.0)",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                },
                "required": ["type", "description", "confidence"],
            },
        },
        "marketMomentum": {
            "type": "string",
            "description": "Overall market momentum assessment",
            "enum": ["accelerating", "stable", "decelerating"],
        },
    },
    "additionalProperties": True,
}


def _get_market_signals_mcp_server_url() -> str:
    """Get the Market Signals MCP Server endpoint URL from environment.

    Returns:
        The URL for the Market Signals MCP Server Lambda function.
    """
    return os.environ.get(
        "MARKET_SIGNALS_MCP_SERVER_URL",
        "http://localhost:3002",
    )


def create_market_intelligence_agent(
    mcp_server_url: str | None = None,
    region: str | None = None,
) -> Agent:
    """Create and configure the Market Intelligence Agent.

    Creates a Strands Agent configured with:
    - Model: us.anthropic.claude-sonnet-4-6 (cost-effective for data analysis)
    - MCP tools from the Market Signals Server for market data access
    - System prompt focused on market analysis and opportunity detection

    Args:
        mcp_server_url: Optional override for the Market Signals MCP Server URL.
            If None, reads from MARKET_SIGNALS_MCP_SERVER_URL environment variable.
        region: AWS region for the Bedrock model. Defaults to us-east-1.

    Returns:
        Configured Strands Agent ready for market intelligence tasks.
    """
    server_url = mcp_server_url or _get_market_signals_mcp_server_url()
    model_region = region or os.environ.get("AWS_REGION", "us-east-1")

    # Configure the Bedrock model
    model = BedrockModel(
        model_id=MARKET_INTELLIGENCE_MODEL,
        region_name=model_region,
    )

    # Configure MCP client for Market Signals Server tools
    mcp_client = MCPClient(
        lambda: MCPClient.stdio_connection(
            "python",
            "-m",
            "backend.mcp_servers.market_signals.handler",
        )
    )

    # Create the agent with MCP tools
    agent = Agent(
        model=model,
        system_prompt=MARKET_INTELLIGENCE_SYSTEM_PROMPT,
        tools=[mcp_client],
    )

    return agent


# Export the structured output schema for use by other components
def get_market_factors_schema() -> dict[str, Any]:
    """Return the structured output schema for market factors.

    This schema defines the expected output format from the Market
    Intelligence Agent, used by the Strategy Synthesis Agent to
    validate and consume market analysis results.

    Returns:
        JSON Schema dictionary for market factors output.
    """
    return MARKET_FACTORS_SCHEMA.copy()
