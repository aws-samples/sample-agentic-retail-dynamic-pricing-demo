"""Competitor API MCP Server Lambda handler.

Provides competitor pricing data as MCP tools accessible by the
Competitive Intelligence Agent. Returns randomized data within ±10%
variance from baseline to simulate real-world market volatility.

Tools exposed:
- get_competitor_prices: Returns current competitor prices for a product
- get_price_history: Returns historical price data for a product across competitors
- get_market_position: Returns market positioning data (market share, price index)
"""

import json
import logging
import random
import time
from datetime import datetime, timezone, timedelta

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Baseline product prices by category (realistic retail ranges)
PRODUCT_BASELINES = {
    # Electronics ($50-500)
    "ELEC-001": {"name": "Wireless Earbuds", "baseline_price": 79.99, "category": "electronics"},
    "ELEC-002": {"name": "Bluetooth Speaker", "baseline_price": 149.99, "category": "electronics"},
    "ELEC-003": {"name": "Smart Watch", "baseline_price": 299.99, "category": "electronics"},
    "ELEC-004": {"name": "Tablet 10-inch", "baseline_price": 449.99, "category": "electronics"},
    "ELEC-005": {"name": "Noise Cancelling Headphones", "baseline_price": 249.99, "category": "electronics"},
    # Groceries ($2-20)
    "GROC-001": {"name": "Organic Milk 1 Gallon", "baseline_price": 5.99, "category": "groceries"},
    "GROC-002": {"name": "Premium Coffee Beans 1lb", "baseline_price": 14.99, "category": "groceries"},
    "GROC-003": {"name": "Artisan Bread Loaf", "baseline_price": 4.49, "category": "groceries"},
    "GROC-004": {"name": "Greek Yogurt 32oz", "baseline_price": 6.99, "category": "groceries"},
    "GROC-005": {"name": "Organic Eggs Dozen", "baseline_price": 7.49, "category": "groceries"},
    # Home & Garden ($20-200)
    "HOME-001": {"name": "LED Desk Lamp", "baseline_price": 39.99, "category": "home"},
    "HOME-002": {"name": "Robot Vacuum", "baseline_price": 199.99, "category": "home"},
    "HOME-003": {"name": "Air Purifier", "baseline_price": 129.99, "category": "home"},
    "HOME-004": {"name": "Smart Thermostat", "baseline_price": 179.99, "category": "home"},
    "HOME-005": {"name": "Cordless Drill Set", "baseline_price": 89.99, "category": "home"},
}

# Competitor names for realistic data
COMPETITORS = [
    {"id": "COMP-001", "name": "MegaMart", "channel": "online"},
    {"id": "COMP-002", "name": "ValueStore", "channel": "online"},
    {"id": "COMP-003", "name": "PrimeShop", "channel": "online"},
    {"id": "COMP-004", "name": "QuickBuy", "channel": "marketplace"},
    {"id": "COMP-005", "name": "DealZone", "channel": "marketplace"},
]

# Variance bound for competitor prices: ±10%
PRICE_VARIANCE = 0.10


def _randomize_price(baseline_price: float) -> float:
    """Generate a randomized price within ±10% of baseline.

    Args:
        baseline_price: The baseline price to vary from.

    Returns:
        A price within ±10% of the baseline, rounded to 2 decimal places.
    """
    factor = 1.0 + random.uniform(-PRICE_VARIANCE, PRICE_VARIANCE)
    return round(baseline_price * factor, 2)


def _get_product_baseline(product_id: str) -> dict | None:
    """Look up product baseline data by ID.

    Args:
        product_id: The product identifier.

    Returns:
        Product baseline dict or None if not found.
    """
    return PRODUCT_BASELINES.get(product_id)


def _build_response(status: str, data: dict, source: str, start_time: float) -> dict:
    """Build a standardized MCP response with metadata.

    Args:
        status: "success" or "error"
        data: The response data payload.
        source: The data source identifier.
        start_time: The time.time() when processing started.

    Returns:
        Dict conforming to MCP Response Schema.
    """
    latency_ms = int((time.time() - start_time) * 1000)
    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": status,
            "data": data,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": source,
                "latencyMs": latency_ms,
            },
        }),
    }


def _build_error_response(code: str, message: str, start_time: float) -> dict:
    """Build a standardized MCP error response.

    Args:
        code: Error code string.
        message: Human-readable error message.
        start_time: The time.time() when processing started.

    Returns:
        Dict conforming to MCP Response Schema with error details.
    """
    latency_ms = int((time.time() - start_time) * 1000)
    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "error",
            "data": {},
            "error": {
                "code": code,
                "message": message,
            },
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "competitor_api_server",
                "latencyMs": latency_ms,
            },
        }),
    }


def get_competitor_prices(params: dict, start_time: float) -> dict:
    """Get current competitor prices for a product.

    Returns 3-5 competitor entries with randomized prices within ±10% of baseline.

    Args:
        params: Dict with 'product_id' (required) and optional 'category'.
        start_time: Processing start time for latency calculation.

    Returns:
        MCP response with competitor pricing data.
    """
    product_id = params.get("product_id")
    if not product_id:
        return _build_error_response(
            "INVALID_PARAMS",
            "product_id is required",
            start_time,
        )

    product = _get_product_baseline(product_id)
    if not product:
        # If product not found, use a default baseline based on category
        category = params.get("category", "electronics")
        if category == "groceries":
            baseline_price = random.uniform(2.0, 20.0)
        elif category == "home":
            baseline_price = random.uniform(20.0, 200.0)
        else:
            baseline_price = random.uniform(50.0, 500.0)
        product = {
            "name": f"Unknown Product {product_id}",
            "baseline_price": round(baseline_price, 2),
            "category": category,
        }

    baseline_price = product["baseline_price"]

    # Generate 3-5 competitor entries
    num_competitors = random.randint(3, 5)
    selected_competitors = random.sample(COMPETITORS, num_competitors)

    competitor_prices = []
    for competitor in selected_competitors:
        price = _randomize_price(baseline_price)
        competitor_prices.append({
            "competitorId": competitor["id"],
            "competitorName": competitor["name"],
            "channel": competitor["channel"],
            "price": price,
            "currency": "USD",
            "inStock": random.choice([True, True, True, False]),  # 75% in stock
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
        })

    data = {
        "productId": product_id,
        "productName": product["name"],
        "category": product["category"],
        "baselinePrice": baseline_price,
        "competitors": competitor_prices,
        "averageCompetitorPrice": round(
            sum(c["price"] for c in competitor_prices) / len(competitor_prices), 2
        ),
        "priceRange": {
            "min": min(c["price"] for c in competitor_prices),
            "max": max(c["price"] for c in competitor_prices),
        },
    }

    return _build_response("success", data, "competitor_api_server", start_time)


def get_price_history(params: dict, start_time: float) -> dict:
    """Get historical price data for a product across competitors.

    Returns price history over the last 30 days with daily data points,
    randomized within ±10% of baseline.

    Args:
        params: Dict with 'product_id' (required) and optional 'days' (default 30).
        start_time: Processing start time for latency calculation.

    Returns:
        MCP response with historical pricing data.
    """
    product_id = params.get("product_id")
    if not product_id:
        return _build_error_response(
            "INVALID_PARAMS",
            "product_id is required",
            start_time,
        )

    product = _get_product_baseline(product_id)
    if not product:
        category = params.get("category", "electronics")
        if category == "groceries":
            baseline_price = random.uniform(2.0, 20.0)
        elif category == "home":
            baseline_price = random.uniform(20.0, 200.0)
        else:
            baseline_price = random.uniform(50.0, 500.0)
        product = {
            "name": f"Unknown Product {product_id}",
            "baseline_price": round(baseline_price, 2),
            "category": category,
        }

    baseline_price = product["baseline_price"]
    days = min(params.get("days", 30), 90)  # Cap at 90 days

    # Select 3 competitors for history
    selected_competitors = random.sample(COMPETITORS, 3)

    now = datetime.now(timezone.utc)
    history = []

    for day_offset in range(days):
        date = (now - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        daily_entry = {"date": date, "prices": []}

        for competitor in selected_competitors:
            price = _randomize_price(baseline_price)
            daily_entry["prices"].append({
                "competitorId": competitor["id"],
                "competitorName": competitor["name"],
                "price": price,
                "currency": "USD",
            })

        history.append(daily_entry)

    # Calculate trend metrics
    recent_avg = sum(
        p["price"]
        for entry in history[:7]
        for p in entry["prices"]
    ) / (7 * len(selected_competitors))

    older_avg = sum(
        p["price"]
        for entry in history[-7:]
        for p in entry["prices"]
    ) / (7 * len(selected_competitors))

    trend_direction = "increasing" if recent_avg > older_avg else "decreasing" if recent_avg < older_avg else "stable"
    trend_percentage = round(((recent_avg - older_avg) / older_avg) * 100, 2) if older_avg > 0 else 0.0

    data = {
        "productId": product_id,
        "productName": product["name"],
        "category": product["category"],
        "periodDays": days,
        "history": history,
        "trend": {
            "direction": trend_direction,
            "percentageChange": trend_percentage,
            "recentAverage": round(recent_avg, 2),
            "olderAverage": round(older_avg, 2),
        },
    }

    return _build_response("success", data, "competitor_api_server", start_time)


def get_market_position(params: dict, start_time: float) -> dict:
    """Get market positioning data for a product.

    Returns market share estimates, price index, and competitive positioning
    with randomized values within ±10% variance.

    Args:
        params: Dict with 'product_id' (required) and optional 'category'.
        start_time: Processing start time for latency calculation.

    Returns:
        MCP response with market positioning data.
    """
    product_id = params.get("product_id")
    if not product_id:
        return _build_error_response(
            "INVALID_PARAMS",
            "product_id is required",
            start_time,
        )

    product = _get_product_baseline(product_id)
    if not product:
        category = params.get("category", "electronics")
        if category == "groceries":
            baseline_price = random.uniform(2.0, 20.0)
        elif category == "home":
            baseline_price = random.uniform(20.0, 200.0)
        else:
            baseline_price = random.uniform(50.0, 500.0)
        product = {
            "name": f"Unknown Product {product_id}",
            "baseline_price": round(baseline_price, 2),
            "category": category,
        }

    baseline_price = product["baseline_price"]

    # Generate market share data (randomized, sums to ~100%)
    our_share = random.uniform(15.0, 35.0)
    remaining = 100.0 - our_share
    competitor_shares = []
    selected_competitors = random.sample(COMPETITORS, random.randint(3, 5))

    for i, competitor in enumerate(selected_competitors):
        if i == len(selected_competitors) - 1:
            share = remaining
        else:
            share = random.uniform(5.0, remaining / (len(selected_competitors) - i))
            remaining -= share
        competitor_shares.append({
            "competitorId": competitor["id"],
            "competitorName": competitor["name"],
            "marketShare": round(share, 2),
            "pricePoint": _randomize_price(baseline_price),
        })

    # Price index: our price relative to market average (100 = at market average)
    market_avg = sum(c["pricePoint"] for c in competitor_shares) / len(competitor_shares)
    our_price = _randomize_price(baseline_price)
    price_index = round((our_price / market_avg) * 100, 1) if market_avg > 0 else 100.0

    # Competitive positioning
    if price_index < 95:
        positioning = "price_leader"
    elif price_index > 105:
        positioning = "premium"
    else:
        positioning = "competitive"

    data = {
        "productId": product_id,
        "productName": product["name"],
        "category": product["category"],
        "ourPrice": our_price,
        "ourMarketShare": round(our_share, 2),
        "priceIndex": price_index,
        "positioning": positioning,
        "competitors": competitor_shares,
        "marketAverage": round(market_avg, 2),
        "marketSize": round(random.uniform(1_000_000, 50_000_000), 2),
        "marketGrowthRate": round(random.uniform(-5.0, 15.0), 2),
    }

    return _build_response("success", data, "competitor_api_server", start_time)


# Tool registry mapping tool names to handler functions
TOOL_REGISTRY = {
    "get_competitor_prices": get_competitor_prices,
    "get_price_history": get_price_history,
    "get_market_position": get_market_position,
}


def handler(event, context):
    """Lambda handler for Competitor API MCP Server.

    Dispatches tool invocations to the appropriate handler function based
    on the 'tool' field in the event body.

    Args:
        event: Lambda event payload. Expected format:
            {"tool": "get_competitor_prices", "params": {"product_id": "ELEC-001"}}
        context: Lambda context object.

    Returns:
        JSON response with status and data fields conforming to MCP Response Schema.
    """
    start_time = time.time()
    logger.info("Competitor API MCP Server invoked: %s", json.dumps(event))

    # Parse the event body
    try:
        if isinstance(event, str):
            body = json.loads(event)
        elif isinstance(event, dict) and "body" in event:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        elif isinstance(event, dict):
            body = event
        else:
            return _build_error_response(
                "INVALID_REQUEST",
                "Unable to parse request body",
                start_time,
            )
    except (json.JSONDecodeError, TypeError) as e:
        return _build_error_response(
            "INVALID_REQUEST",
            f"Failed to parse request body: {str(e)}",
            start_time,
        )

    # Extract tool name and params
    tool_name = body.get("tool")
    params = body.get("params", {})

    if not tool_name:
        return _build_error_response(
            "MISSING_TOOL",
            "No tool specified in request. Available tools: get_competitor_prices, get_price_history, get_market_position",
            start_time,
        )

    # Dispatch to the appropriate tool handler
    tool_handler = TOOL_REGISTRY.get(tool_name)
    if not tool_handler:
        return _build_error_response(
            "UNKNOWN_TOOL",
            f"Unknown tool: {tool_name}. Available tools: get_competitor_prices, get_price_history, get_market_position",
            start_time,
        )

    try:
        return tool_handler(params, start_time)
    except Exception as e:
        logger.error("Error executing tool %s: %s", tool_name, str(e), exc_info=True)
        return _build_error_response(
            "EXECUTION_ERROR",
            f"Error executing tool {tool_name}: {str(e)}",
            start_time,
        )
