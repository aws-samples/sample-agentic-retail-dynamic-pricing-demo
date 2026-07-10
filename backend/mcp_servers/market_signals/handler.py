"""Market Signals MCP Server Lambda handler.

Provides market trend data, consumer sentiment, and macroeconomic
indicators as MCP tools accessible by the Market Intelligence Agent.
Returns randomized sentiment scores varying between invocations.

Tools exposed:
- get_market_trends: Returns trend indicators (growth rate, seasonality, category momentum)
- get_consumer_sentiment: Returns sentiment scores (0-1 scale) that vary between invocations
- get_macro_indicators: Returns economic indicators (CPI, consumer confidence, unemployment)
"""

import json
import logging
import random
import time
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# MCP tool definitions for discovery
TOOL_DEFINITIONS = {
    "get_market_trends": {
        "name": "get_market_trends",
        "description": "Returns market trend indicators including growth rate, seasonality index, and category momentum for a given product category.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Product category to analyze trends for",
                },
                "timeframe": {
                    "type": "string",
                    "description": "Analysis timeframe (e.g., '30d', '90d', '1y')",
                    "default": "90d",
                },
            },
            "required": ["category"],
        },
    },
    "get_consumer_sentiment": {
        "name": "get_consumer_sentiment",
        "description": "Returns consumer sentiment scores on a 0-1 scale that vary between invocations to simulate real-time sentiment shifts.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Product category to analyze sentiment for",
                },
                "channel": {
                    "type": "string",
                    "description": "Sales channel (e.g., 'online', 'retail', 'wholesale')",
                    "default": "online",
                },
            },
            "required": ["category"],
        },
    },
    "get_macro_indicators": {
        "name": "get_macro_indicators",
        "description": "Returns macroeconomic indicators including CPI, consumer confidence index, and unemployment rate.",
        "parameters": {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "description": "Geographic region for indicators (e.g., 'US', 'EU', 'APAC')",
                    "default": "US",
                },
            },
        },
    },
}


def _build_response(status, data, start_time, error=None):
    """Build a standardized MCP response conforming to the MCP Response Schema.

    Args:
        status: Response status ('success' or 'error').
        data: Response data payload.
        start_time: Request start time for latency calculation.
        error: Optional error details dict with 'code' and 'message'.

    Returns:
        Dict conforming to MCP Response Schema.
    """
    latency_ms = int((time.time() - start_time) * 1000)
    response = {
        "status": status,
        "data": data,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "market_signals_server",
            "latencyMs": latency_ms,
        },
    }
    if error:
        response["error"] = error
    return response


def _get_market_trends(params):
    """Generate randomized market trend indicators.

    Returns trend data including growth rate, seasonality index,
    and category momentum that vary between invocations.
    """
    category = params.get("category", "general")
    timeframe = params.get("timeframe", "90d")

    # Randomized growth rate between -5% and +15%
    growth_rate = round(random.uniform(-0.05, 0.15), 4)

    # Seasonality index between 0.5 and 1.5 (1.0 = no seasonal effect)
    seasonality_index = round(random.uniform(0.5, 1.5), 4)

    # Category momentum score between -1.0 and 1.0
    category_momentum = round(random.uniform(-1.0, 1.0), 4)

    # Market volatility index between 0 and 1
    volatility_index = round(random.uniform(0.0, 1.0), 4)

    # Trend direction probabilities
    trend_directions = ["accelerating", "stable", "decelerating", "reversing"]
    trend_direction = random.choice(trend_directions)

    # Demand shift indicator
    demand_shift = round(random.uniform(-0.20, 0.20), 4)

    return {
        "category": category,
        "timeframe": timeframe,
        "growthRate": growth_rate,
        "seasonalityIndex": seasonality_index,
        "categoryMomentum": category_momentum,
        "volatilityIndex": volatility_index,
        "trendDirection": trend_direction,
        "demandShift": demand_shift,
        "trendIndicators": {
            "shortTerm": round(random.uniform(-0.10, 0.10), 4),
            "mediumTerm": round(random.uniform(-0.08, 0.12), 4),
            "longTerm": round(random.uniform(-0.03, 0.08), 4),
        },
    }


def _get_consumer_sentiment(params):
    """Generate randomized consumer sentiment scores.

    Returns sentiment scores on a 0-1 scale that vary between
    invocations to demonstrate adaptive agent behavior.
    """
    category = params.get("category", "general")
    channel = params.get("channel", "online")

    # Overall sentiment score between 0 and 1
    overall_sentiment = round(random.uniform(0.0, 1.0), 4)

    # Channel-specific sentiment
    purchase_intent = round(random.uniform(0.0, 1.0), 4)
    brand_perception = round(random.uniform(0.0, 1.0), 4)
    price_sensitivity = round(random.uniform(0.0, 1.0), 4)
    satisfaction_score = round(random.uniform(0.0, 1.0), 4)

    # Sentiment trend (change from previous period)
    sentiment_trend = round(random.uniform(-0.3, 0.3), 4)

    # Social media buzz score
    social_buzz = round(random.uniform(0.0, 1.0), 4)

    # Review sentiment breakdown
    positive_ratio = round(random.uniform(0.3, 0.9), 4)
    negative_ratio = round(1.0 - positive_ratio - random.uniform(0.0, 0.2), 4)
    neutral_ratio = round(1.0 - positive_ratio - max(0, negative_ratio), 4)

    return {
        "category": category,
        "channel": channel,
        "overallSentiment": overall_sentiment,
        "purchaseIntent": purchase_intent,
        "brandPerception": brand_perception,
        "priceSensitivity": price_sensitivity,
        "satisfactionScore": satisfaction_score,
        "sentimentTrend": sentiment_trend,
        "socialBuzz": social_buzz,
        "reviewSentiment": {
            "positiveRatio": positive_ratio,
            "negativeRatio": max(0, negative_ratio),
            "neutralRatio": max(0, neutral_ratio),
        },
    }


def _get_macro_indicators(params):
    """Generate randomized macroeconomic indicators.

    Returns economic indicators including CPI, consumer confidence,
    and unemployment rate that vary between invocations.
    """
    region = params.get("region", "US")

    # CPI (Consumer Price Index) - baseline around 3.0%, varies ±1.5%
    cpi = round(random.uniform(1.5, 4.5), 4)

    # Consumer Confidence Index - baseline around 100, varies between 70-130
    consumer_confidence = round(random.uniform(70.0, 130.0), 2)

    # Unemployment rate - baseline around 4%, varies between 3-7%
    unemployment_rate = round(random.uniform(3.0, 7.0), 4)

    # GDP growth rate - varies between -1% and 5%
    gdp_growth = round(random.uniform(-1.0, 5.0), 4)

    # Interest rate - varies between 2% and 7%
    interest_rate = round(random.uniform(2.0, 7.0), 4)

    # Retail sales growth - varies between -3% and 8%
    retail_sales_growth = round(random.uniform(-3.0, 8.0), 4)

    # Disposable income change - varies between -2% and 5%
    disposable_income_change = round(random.uniform(-2.0, 5.0), 4)

    return {
        "region": region,
        "cpi": cpi,
        "consumerConfidence": consumer_confidence,
        "unemploymentRate": unemployment_rate,
        "gdpGrowth": gdp_growth,
        "interestRate": interest_rate,
        "retailSalesGrowth": retail_sales_growth,
        "disposableIncomeChange": disposable_income_change,
        "economicOutlook": random.choice(["bullish", "neutral", "bearish"]),
    }


# Tool dispatch map
_TOOL_HANDLERS = {
    "get_market_trends": _get_market_trends,
    "get_consumer_sentiment": _get_consumer_sentiment,
    "get_macro_indicators": _get_macro_indicators,
}


def handler(event, context):
    """Lambda handler for Market Signals MCP Server.

    Dispatches to the appropriate tool handler based on the 'tool' field
    in the event body. Each tool returns randomized data that varies
    between invocations to simulate real-world market volatility.

    Args:
        event: Lambda event payload containing MCP tool invocation details.
               Expected format: {"tool": "<tool_name>", "params": {...}}
        context: Lambda context object.

    Returns:
        JSON response with status and data fields conforming to MCP Response Schema.
    """
    start_time = time.time()
    logger.info("Market Signals MCP Server invoked: %s", json.dumps(event))

    try:
        # Parse the event body
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event

        tool_name = body.get("tool")
        params = body.get("params", {})

        # Validate tool name
        if not tool_name:
            error_response = _build_response(
                status="error",
                data={},
                start_time=start_time,
                error={
                    "code": "MISSING_TOOL",
                    "message": "The 'tool' field is required in the request body.",
                },
            )
            return {
                "statusCode": 400,
                "body": json.dumps(error_response),
            }

        if tool_name not in _TOOL_HANDLERS:
            error_response = _build_response(
                status="error",
                data={},
                start_time=start_time,
                error={
                    "code": "UNKNOWN_TOOL",
                    "message": f"Unknown tool '{tool_name}'. Available tools: {list(_TOOL_HANDLERS.keys())}",
                },
            )
            return {
                "statusCode": 400,
                "body": json.dumps(error_response),
            }

        # Execute the tool handler
        tool_handler = _TOOL_HANDLERS[tool_name]
        data = tool_handler(params)

        response = _build_response(
            status="success",
            data=data,
            start_time=start_time,
        )

        return {
            "statusCode": 200,
            "body": json.dumps(response),
        }

    except json.JSONDecodeError as e:
        error_response = _build_response(
            status="error",
            data={},
            start_time=start_time,
            error={
                "code": "INVALID_JSON",
                "message": f"Failed to parse request body as JSON: {str(e)}",
            },
        )
        return {
            "statusCode": 400,
            "body": json.dumps(error_response),
        }
    except Exception as e:
        logger.error("Unexpected error in Market Signals MCP Server: %s", str(e))
        error_response = _build_response(
            status="error",
            data={},
            start_time=start_time,
            error={
                "code": "INTERNAL_ERROR",
                "message": f"An unexpected error occurred: {str(e)}",
            },
        )
        return {
            "statusCode": 500,
            "body": json.dumps(error_response),
        }
