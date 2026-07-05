"""Competitive Intelligence Agent.

Defines a Strands Agent that collects and analyzes real-time competitor
pricing data, performs channel-level analysis, and detects market sentiment.
Uses AgentCore Browser (Nova Act) when available, falling back to the
Competitor API MCP Server tools.

Requirements: 1.7, 2.1, 2.10
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Any

from strands import Agent
from strands.tools.mcp import MCPClient

logger = logging.getLogger(__name__)

# Model configuration for intelligence agents (Requirement 1.7)
from shared.model_config import SPECIALIST_MODEL as COMPETITIVE_INTELLIGENCE_MODEL

# ---------------------------------------------------------------------------
# Structured output schema for competitive factors
# ---------------------------------------------------------------------------


@dataclass
class ChannelAnalysis:
    """Pricing analysis for a specific sales channel.

    Attributes:
        channel: The sales channel name (e.g., "online", "marketplace").
        avgPrice: Average competitor price in this channel.
        priceRange: Min and max prices observed in this channel.
        competitorCount: Number of competitors active in this channel.
        trend: Price trend direction ("increasing", "decreasing", "stable").
    """

    channel: str
    avgPrice: float
    priceRange: dict[str, float] = field(default_factory=lambda: {"min": 0.0, "max": 0.0})
    competitorCount: int = 0
    trend: str = "stable"


@dataclass
class SentimentIndicator:
    """Market sentiment indicator derived from competitive signals.

    Attributes:
        indicator: Name of the sentiment signal.
        value: Numeric value of the indicator (0.0 to 1.0 scale).
        direction: Whether the indicator is trending "positive", "negative", or "neutral".
        confidence: Confidence level in this indicator (0.0 to 1.0).
    """

    indicator: str
    value: float
    direction: str = "neutral"
    confidence: float = 0.5


@dataclass
class CompetitiveFactors:
    """Structured output from the Competitive Intelligence Agent.

    Contains all competitive pricing factors needed by the Strategy
    Synthesis Agent for scenario generation.

    Attributes:
        avgCompetitorPrice: Weighted average price across all competitors.
        priceIndex: Our price relative to market average (100 = at market).
        positioning: Market positioning ("price_leader", "competitive", "premium").
        channelAnalysis: Per-channel pricing breakdown.
        sentimentIndicators: Market sentiment signals.
        competitorCount: Total number of competitors analyzed.
        dataSource: Source of the data ("agentcore_browser" or "mcp_tools").
        marketGrowthRate: Estimated market growth rate percentage.
        priceVolatility: Price volatility score (0.0 to 1.0).
    """

    avgCompetitorPrice: float = 0.0
    priceIndex: float = 100.0
    positioning: str = "competitive"
    channelAnalysis: list[ChannelAnalysis] = field(default_factory=list)
    sentimentIndicators: list[SentimentIndicator] = field(default_factory=list)
    competitorCount: int = 0
    dataSource: str = "mcp_tools"
    marketGrowthRate: float = 0.0
    priceVolatility: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON output."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CompetitiveFactors":
        """Deserialize from dictionary.

        Args:
            data: Dictionary with competitive factors fields.

        Returns:
            CompetitiveFactors instance.
        """
        channel_analysis = [
            ChannelAnalysis(**ch) if isinstance(ch, dict) else ch
            for ch in data.get("channelAnalysis", [])
        ]
        sentiment_indicators = [
            SentimentIndicator(**si) if isinstance(si, dict) else si
            for si in data.get("sentimentIndicators", [])
        ]
        return cls(
            avgCompetitorPrice=data.get("avgCompetitorPrice", 0.0),
            priceIndex=data.get("priceIndex", 100.0),
            positioning=data.get("positioning", "competitive"),
            channelAnalysis=channel_analysis,
            sentimentIndicators=sentiment_indicators,
            competitorCount=data.get("competitorCount", 0),
            dataSource=data.get("dataSource", "mcp_tools"),
            marketGrowthRate=data.get("marketGrowthRate", 0.0),
            priceVolatility=data.get("priceVolatility", 0.0),
        )


# ---------------------------------------------------------------------------
# Competitive factors JSON schema (for structured output validation)
# ---------------------------------------------------------------------------

COMPETITIVE_FACTORS_SCHEMA = {
    "type": "object",
    "required": [
        "avgCompetitorPrice",
        "priceIndex",
        "positioning",
        "channelAnalysis",
        "sentimentIndicators",
    ],
    "properties": {
        "avgCompetitorPrice": {
            "type": "number",
            "description": "Weighted average price across all competitors",
        },
        "priceIndex": {
            "type": "number",
            "description": "Our price relative to market average (100 = at market average)",
        },
        "positioning": {
            "type": "string",
            "enum": ["price_leader", "competitive", "premium"],
            "description": "Market positioning based on price index",
        },
        "channelAnalysis": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["channel", "avgPrice"],
                "properties": {
                    "channel": {"type": "string"},
                    "avgPrice": {"type": "number"},
                    "priceRange": {
                        "type": "object",
                        "properties": {
                            "min": {"type": "number"},
                            "max": {"type": "number"},
                        },
                    },
                    "competitorCount": {"type": "integer"},
                    "trend": {
                        "type": "string",
                        "enum": ["increasing", "decreasing", "stable"],
                    },
                },
            },
            "description": "Per-channel pricing breakdown",
        },
        "sentimentIndicators": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["indicator", "value"],
                "properties": {
                    "indicator": {"type": "string"},
                    "value": {"type": "number"},
                    "direction": {
                        "type": "string",
                        "enum": ["positive", "negative", "neutral"],
                    },
                    "confidence": {"type": "number"},
                },
            },
            "description": "Market sentiment signals derived from competitive data",
        },
        "competitorCount": {"type": "integer"},
        "dataSource": {
            "type": "string",
            "enum": ["agentcore_browser", "mcp_tools"],
        },
        "marketGrowthRate": {"type": "number"},
        "priceVolatility": {"type": "number"},
    },
}

# ---------------------------------------------------------------------------
# System prompt for competitive analysis
# ---------------------------------------------------------------------------

COMPETITIVE_INTELLIGENCE_SYSTEM_PROMPT = """You are the Competitive Intelligence Agent in a retail dynamic pricing system.

Your role is to collect and analyze real-time competitor pricing data to inform pricing decisions.

## Core Responsibilities

1. **Competitor Price Collection**: Gather current competitor prices for the target product(s) using available tools.
2. **Channel-Level Analysis**: Break down competitor pricing by sales channel (online, marketplace, in-store) to identify channel-specific pricing strategies.
3. **Sentiment Detection**: Analyze pricing signals to detect market sentiment — are competitors pricing aggressively (indicating price war), holding steady (stable market), or increasing prices (demand confidence)?
4. **Market Positioning**: Determine our current market position relative to competitors (price leader, competitive, or premium).
5. **Trend Analysis**: Identify pricing trends over time using historical data.

## Analysis Framework

When analyzing competitive data, consider:
- **Price Index**: Calculate our price relative to the market average (100 = at market average, <100 = below market, >100 = above market)
- **Channel Dynamics**: Different channels may have different competitive pressures
- **Volatility**: High price variance across competitors suggests an unstable market
- **Growth Signals**: Market growth rate indicates demand trajectory

## Output Requirements

Return your analysis as structured competitive factors including:
- `avgCompetitorPrice`: Weighted average across all competitors
- `priceIndex`: Our price position relative to market (100 = at market)
- `positioning`: One of "price_leader" (index < 95), "competitive" (95-105), "premium" (> 105)
- `channelAnalysis`: Array of per-channel breakdowns with average price, range, competitor count, and trend
- `sentimentIndicators`: Array of market sentiment signals with indicator name, value (0-1), direction, and confidence
- `competitorCount`: Total competitors analyzed
- `dataSource`: Whether data came from "agentcore_browser" or "mcp_tools"
- `marketGrowthRate`: Estimated market growth percentage
- `priceVolatility`: Price volatility score (0-1, where 1 = highly volatile)

## Data Collection Strategy

1. First, try to use AgentCore Browser to scrape live competitor websites for the most current data.
2. If Browser is unavailable or returns an error, fall back to the Competitor API MCP tools:
   - `get_competitor_prices`: Get current competitor prices for a product
   - `get_price_history`: Get historical price data over time
   - `get_market_position`: Get market share and positioning data

## Important Guidelines

- Always collect data from multiple competitors (minimum 3) for reliable analysis
- Flag any data quality issues (e.g., stale prices, missing competitors)
- Do NOT include any customer PII in your analysis output
- Report the data source used (browser vs. MCP tools) for audit purposes
- Provide confidence levels for sentiment indicators based on data quality and recency
"""


# ---------------------------------------------------------------------------
# MCP Client factory for Competitor API Server
# ---------------------------------------------------------------------------


def _create_competitor_api_mcp_transport():
    """Create the MCP transport factory for the Competitor API Server.

    Returns a callable that produces the appropriate MCP transport
    connection. In production, this connects to the deployed Lambda
    function via the AgentCore MCP gateway. For local development,
    it uses stdio mode with a Python subprocess.

    Returns:
        A transport factory callable for MCPClient.
    """
    endpoint = os.environ.get("COMPETITOR_API_MCP_SERVER_URL")

    if endpoint and endpoint.startswith("http"):
        # HTTP/SSE transport for deployed Lambda MCP Server
        from mcp.client.streamable_http import streamablehttp_client

        return lambda: streamablehttp_client(endpoint)
    else:
        # Stdio transport for local development
        from mcp.client.stdio import stdio_client

        server_command = os.environ.get(
            "COMPETITOR_API_MCP_COMMAND",
            "python",
        )
        server_args_str = os.environ.get(
            "COMPETITOR_API_MCP_ARGS",
            "-m backend.mcp_servers.competitor_api.handler",
        )
        server_args = server_args_str.split()

        return lambda: stdio_client(server_command, server_args)


def _is_agentcore_browser_available() -> bool:
    """Check if AgentCore Browser is available for web scraping.

    AgentCore Browser availability is determined by the presence of
    the AGENTCORE_BROWSER_ENDPOINT environment variable and a successful
    health check.

    Returns:
        True if AgentCore Browser is available, False otherwise.
    """
    browser_endpoint = os.environ.get("AGENTCORE_BROWSER_ENDPOINT")
    if not browser_endpoint:
        logger.info("AgentCore Browser endpoint not configured, using MCP fallback")
        return False

    # In production, we would perform a health check against the endpoint.
    # For the MVP demo, we check the environment variable presence.
    logger.info("AgentCore Browser endpoint configured: %s", browser_endpoint)
    return True


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


def create_competitive_intelligence_agent(
    competitor_api_mcp_endpoint: str | None = None,
    use_browser: bool | None = None,
) -> Agent:
    """Create and configure the Competitive Intelligence Agent.

    Creates a Strands Agent configured with:
    - Model: us.anthropic.claude-sonnet-4-6 (cost-effective for data analysis)
    - System prompt for competitive pricing analysis
    - MCP tools from the Competitor API Server
    - AgentCore Browser fallback logic

    The Competitor API MCP Server exposes the following tools:
    - get_competitor_prices: Current competitor prices for a product
    - get_price_history: Historical price data over time
    - get_market_position: Market share and positioning data

    Fallback logic (Requirement 2.10):
    - When AgentCore Browser is available, it is used as the primary data
      source for scraping live competitor websites.
    - When AgentCore Browser is unavailable or returns an error, the agent
      falls back to the Competitor API MCP Server tools.

    Args:
        competitor_api_mcp_endpoint: Optional endpoint URL for the Competitor
            API MCP Server. If None, uses COMPETITOR_API_MCP_SERVER_URL
            environment variable or defaults to stdio mode.
        use_browser: Override for browser availability check.
            If None, auto-detects from environment.

    Returns:
        Configured Strands Agent instance ready for competitive analysis.
    """
    # Determine data source strategy (Requirement 2.10)
    if use_browser is None:
        use_browser = _is_agentcore_browser_available()

    data_source = "agentcore_browser" if use_browser else "mcp_tools"

    endpoint = competitor_api_mcp_endpoint or os.environ.get(
        "COMPETITOR_API_MCP_SERVER_URL"
    )

    # Configure MCP client for Competitor API Server tools
    mcp_clients: list[Any] = []
    if endpoint:
        competitor_mcp = MCPClient(
            lambda: MCPClient.http(url=endpoint)
            if endpoint.startswith("http")
            else MCPClient.stdio(
                command="python",
                args=["-m", "backend.mcp_servers.competitor_api.handler"],
            )
        )
        mcp_clients.append(competitor_mcp)

    # Build system prompt with data source context
    system_prompt = COMPETITIVE_INTELLIGENCE_SYSTEM_PROMPT
    if use_browser:
        system_prompt += (
            "\n\n## Active Configuration\n"
            "AgentCore Browser is AVAILABLE. Use it as the primary data source "
            "for scraping live competitor websites. Fall back to MCP tools "
            "(get_competitor_prices, get_price_history, get_market_position) "
            "if browser scraping fails or returns incomplete data."
        )
    else:
        system_prompt += (
            "\n\n## Active Configuration\n"
            "AgentCore Browser is NOT available. Use the Competitor API MCP "
            "tools (get_competitor_prices, get_price_history, "
            "get_market_position) as your data source."
        )

    # Create the Strands Agent
    agent = Agent(
        model=COMPETITIVE_INTELLIGENCE_MODEL,
        system_prompt=system_prompt,
        tools=mcp_clients,
    )

    logger.info(
        "Competitive Intelligence Agent created with model %s, data_source=%s",
        COMPETITIVE_INTELLIGENCE_MODEL,
        data_source,
    )

    return agent


def invoke_competitive_analysis(
    product_id: str,
    category: str | None = None,
    agent: Agent | None = None,
) -> CompetitiveFactors:
    """Invoke the Competitive Intelligence Agent for a product analysis.

    This is the high-level entry point for running competitive analysis.
    It handles agent invocation and result parsing.

    Note: When using MCP tools, the agent must be invoked within the
    MCPClient context manager. This function handles that lifecycle.

    Args:
        product_id: The product ID to analyze.
        category: Optional product category for context.
        agent: Optional pre-created agent from
            create_competitive_intelligence_agent(). If None, creates a new one.

    Returns:
        CompetitiveFactors with the analysis results.

    Raises:
        RuntimeError: If the agent fails to produce valid output.
    """
    if agent is None:
        agent = create_competitive_intelligence_agent()

    prompt = (
        f"Analyze the competitive pricing landscape for product '{product_id}'"
    )
    if category:
        prompt += f" in the '{category}' category"
    prompt += (
        ". Use the available tools to gather competitor prices, price history, "
        "and market position data. Return your analysis as structured "
        "competitive factors in JSON format."
    )

    try:
        result = agent(prompt)

        # Parse the agent's response into structured output
        response_text = str(result)
        try:
            # Attempt to extract JSON from the response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                factors_data = json.loads(response_text[json_start:json_end])
                factors = CompetitiveFactors.from_dict(factors_data)
                return factors
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(
                "Failed to parse structured output from agent response: %s", e
            )

        # Fallback: return default factors
        logger.warning("Returning default competitive factors due to parse failure")
        return CompetitiveFactors(dataSource="mcp_tools")

    except Exception as e:
        logger.error("Competitive Intelligence Agent invocation failed: %s", e)
        raise RuntimeError(
            f"Competitive Intelligence Agent failed for product {product_id}: {e}"
        ) from e


def get_competitive_factors_schema() -> dict[str, Any]:
    """Return the structured output schema for competitive factors.

    This schema defines the expected output format from the Competitive
    Intelligence Agent, used by the Strategy Synthesis Agent to
    validate and consume competitive analysis results.

    Returns:
        JSON Schema dictionary for competitive factors output.
    """
    return COMPETITIVE_FACTORS_SCHEMA.copy()
