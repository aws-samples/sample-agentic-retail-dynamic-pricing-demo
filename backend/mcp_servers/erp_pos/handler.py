"""ERP/POS MCP Server Lambda handler.

Provides ERP sales history and POS transaction data as MCP tools
accessible by the Demand Forecasting Agent. Returns randomized data
within ±20% variance for demand volumes to simulate real-world
market volatility.

Tools exposed:
- get_sales_history: Weekly/monthly sales data for a product
- get_pos_realtime: Recent POS transaction data
- get_inventory_levels: Current stock levels
- get_elasticity_data: Price elasticity coefficients by segment
"""

import json
import logging
import random
import time
from datetime import datetime, timedelta, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Tool definitions for MCP protocol
TOOL_DEFINITIONS = {
    "get_sales_history": {
        "name": "get_sales_history",
        "description": "Returns weekly or monthly sales data for a product including units sold, revenue, and average selling price.",
        "parameters": {
            "product_id": {"type": "string", "description": "Product identifier"},
            "period": {"type": "string", "description": "Time period: 'weekly' or 'monthly'", "default": "weekly"},
            "weeks": {"type": "integer", "description": "Number of weeks/months to return", "default": 12},
        },
    },
    "get_pos_realtime": {
        "name": "get_pos_realtime",
        "description": "Returns recent POS transaction data including transaction count, units, and revenue for the last N hours.",
        "parameters": {
            "product_id": {"type": "string", "description": "Product identifier"},
            "hours": {"type": "integer", "description": "Number of hours of recent data", "default": 24},
            "store_id": {"type": "string", "description": "Optional store filter", "default": None},
        },
    },
    "get_inventory_levels": {
        "name": "get_inventory_levels",
        "description": "Returns current stock levels across warehouses and stores for a product.",
        "parameters": {
            "product_id": {"type": "string", "description": "Product identifier"},
            "location_type": {"type": "string", "description": "Filter by 'warehouse', 'store', or 'all'", "default": "all"},
        },
    },
    "get_elasticity_data": {
        "name": "get_elasticity_data",
        "description": "Returns price elasticity coefficients by customer segment for a product.",
        "parameters": {
            "product_id": {"type": "string", "description": "Product identifier"},
            "category": {"type": "string", "description": "Product category for segment analysis", "default": None},
        },
    },
}

# Baseline values for randomization (±20% variance for demand volumes)
BASELINE_WEEKLY_UNITS = 1500
BASELINE_MONTHLY_UNITS = 6000
BASELINE_PRICE = 29.99
BASELINE_HOURLY_TRANSACTIONS = 45
BASELINE_WAREHOUSE_STOCK = 5000
BASELINE_STORE_STOCK = 200


def _apply_variance(baseline: float, variance_pct: float = 0.20) -> float:
    """Apply random variance within ±variance_pct of baseline."""
    factor = 1.0 + random.uniform(-variance_pct, variance_pct)
    return round(baseline * factor, 4)


def _apply_variance_int(baseline: int, variance_pct: float = 0.20) -> int:
    """Apply random variance within ±variance_pct of baseline, returning int."""
    factor = 1.0 + random.uniform(-variance_pct, variance_pct)
    return max(0, round(baseline * factor))


def _get_timestamp() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _build_response(data: dict, start_time: float) -> dict:
    """Build MCP-compliant response with metadata."""
    latency_ms = int((time.time() - start_time) * 1000)
    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "success",
            "data": data,
            "metadata": {
                "timestamp": _get_timestamp(),
                "source": "erp_pos_server",
                "latencyMs": latency_ms,
            },
        }),
    }


def _build_error_response(code: str, message: str, start_time: float) -> dict:
    """Build MCP-compliant error response."""
    latency_ms = int((time.time() - start_time) * 1000)
    return {
        "statusCode": 400,
        "body": json.dumps({
            "status": "error",
            "data": {},
            "error": {
                "code": code,
                "message": message,
            },
            "metadata": {
                "timestamp": _get_timestamp(),
                "source": "erp_pos_server",
                "latencyMs": latency_ms,
            },
        }),
    }


def _handle_get_sales_history(params: dict) -> dict:
    """Generate randomized sales history data.

    Returns weekly or monthly sales data with ±20% variance on demand volumes.
    """
    product_id = params.get("product_id", "PROD-001")
    period = params.get("period", "weekly")
    num_periods = params.get("weeks", 12)

    baseline_units = BASELINE_WEEKLY_UNITS if period == "weekly" else BASELINE_MONTHLY_UNITS
    now = datetime.now(timezone.utc)

    sales_data = []
    for i in range(num_periods):
        if period == "weekly":
            period_start = now - timedelta(weeks=num_periods - i)
            period_end = period_start + timedelta(weeks=1)
        else:
            period_start = now - timedelta(days=30 * (num_periods - i))
            period_end = period_start + timedelta(days=30)

        units_sold = _apply_variance_int(baseline_units)
        avg_price = round(_apply_variance(BASELINE_PRICE, 0.05), 2)
        revenue = round(units_sold * avg_price, 4)

        sales_data.append({
            "periodStart": period_start.strftime("%Y-%m-%d"),
            "periodEnd": period_end.strftime("%Y-%m-%d"),
            "unitsSold": units_sold,
            "revenue": revenue,
            "averageSellingPrice": avg_price,
            "returnRate": round(random.uniform(0.02, 0.08), 4),
            "promotionActive": random.choice([True, False]),
        })

    return {
        "productId": product_id,
        "period": period,
        "totalPeriods": num_periods,
        "salesHistory": sales_data,
        "summary": {
            "totalUnitsSold": sum(p["unitsSold"] for p in sales_data),
            "totalRevenue": round(sum(p["revenue"] for p in sales_data), 4),
            "averageUnitsPerPeriod": round(
                sum(p["unitsSold"] for p in sales_data) / num_periods, 4
            ),
            "trendDirection": random.choice(["increasing", "stable", "decreasing"]),
        },
    }


def _handle_get_pos_realtime(params: dict) -> dict:
    """Generate randomized real-time POS transaction data.

    Returns recent transaction data with ±20% variance on volumes.
    """
    product_id = params.get("product_id", "PROD-001")
    hours = params.get("hours", 24)
    store_id = params.get("store_id")

    now = datetime.now(timezone.utc)
    transactions = []

    for i in range(hours):
        hour_start = now - timedelta(hours=hours - i)
        tx_count = _apply_variance_int(BASELINE_HOURLY_TRANSACTIONS)
        units_per_tx = round(random.uniform(1.0, 3.0), 1)
        total_units = _apply_variance_int(round(tx_count * units_per_tx))
        avg_price = round(_apply_variance(BASELINE_PRICE, 0.05), 2)

        transactions.append({
            "hour": hour_start.strftime("%Y-%m-%dT%H:00:00Z"),
            "transactionCount": tx_count,
            "totalUnits": total_units,
            "revenue": round(total_units * avg_price, 4),
            "averageBasketSize": round(random.uniform(2.5, 5.5), 2),
            "averageTransactionValue": round(avg_price * units_per_tx, 2),
        })

    store_filter = store_id if store_id else "all_stores"

    return {
        "productId": product_id,
        "storeId": store_filter,
        "periodHours": hours,
        "transactions": transactions,
        "summary": {
            "totalTransactions": sum(t["transactionCount"] for t in transactions),
            "totalUnits": sum(t["totalUnits"] for t in transactions),
            "totalRevenue": round(sum(t["revenue"] for t in transactions), 4),
            "peakHour": max(transactions, key=lambda t: t["transactionCount"])["hour"],
            "averageHourlyUnits": round(
                sum(t["totalUnits"] for t in transactions) / hours, 4
            ),
        },
    }


def _handle_get_inventory_levels(params: dict) -> dict:
    """Generate randomized inventory level data.

    Returns current stock levels with ±20% variance on quantities.
    """
    product_id = params.get("product_id", "PROD-001")
    location_type = params.get("location_type", "all")

    warehouses = [
        {"locationId": "WH-EAST-01", "name": "East Coast DC", "region": "us-east"},
        {"locationId": "WH-WEST-01", "name": "West Coast DC", "region": "us-west"},
        {"locationId": "WH-CENT-01", "name": "Central DC", "region": "us-central"},
    ]

    stores = [
        {"locationId": "STR-001", "name": "Downtown Flagship", "region": "us-east"},
        {"locationId": "STR-002", "name": "Mall Location A", "region": "us-east"},
        {"locationId": "STR-003", "name": "Suburban Store B", "region": "us-west"},
        {"locationId": "STR-004", "name": "Airport Outlet", "region": "us-central"},
        {"locationId": "STR-005", "name": "Online Fulfillment", "region": "us-east"},
    ]

    inventory = []

    if location_type in ("warehouse", "all"):
        for wh in warehouses:
            stock = _apply_variance_int(BASELINE_WAREHOUSE_STOCK)
            inventory.append({
                "locationId": wh["locationId"],
                "locationName": wh["name"],
                "locationType": "warehouse",
                "region": wh["region"],
                "quantityOnHand": stock,
                "quantityReserved": _apply_variance_int(round(stock * 0.15)),
                "quantityAvailable": stock - _apply_variance_int(round(stock * 0.15)),
                "reorderPoint": round(stock * 0.2),
                "daysOfSupply": _apply_variance_int(30),
            })

    if location_type in ("store", "all"):
        for store in stores:
            stock = _apply_variance_int(BASELINE_STORE_STOCK)
            inventory.append({
                "locationId": store["locationId"],
                "locationName": store["name"],
                "locationType": "store",
                "region": store["region"],
                "quantityOnHand": stock,
                "quantityReserved": _apply_variance_int(round(stock * 0.1)),
                "quantityAvailable": stock - _apply_variance_int(round(stock * 0.1)),
                "reorderPoint": round(stock * 0.25),
                "daysOfSupply": _apply_variance_int(14),
            })

    total_on_hand = sum(loc["quantityOnHand"] for loc in inventory)
    total_available = sum(loc["quantityAvailable"] for loc in inventory)

    return {
        "productId": product_id,
        "locationType": location_type,
        "locations": inventory,
        "summary": {
            "totalLocations": len(inventory),
            "totalOnHand": total_on_hand,
            "totalAvailable": total_available,
            "totalReserved": total_on_hand - total_available,
            "stockHealthStatus": (
                "healthy" if total_available > 1000
                else "low" if total_available > 200
                else "critical"
            ),
            "averageDaysOfSupply": round(
                sum(loc["daysOfSupply"] for loc in inventory) / len(inventory), 1
            ) if inventory else 0,
        },
    }


def _handle_get_elasticity_data(params: dict) -> dict:
    """Generate randomized price elasticity data by customer segment.

    Returns elasticity coefficients with ±20% variance.
    """
    product_id = params.get("product_id", "PROD-001")
    category = params.get("category", "general_retail")

    segments = [
        {
            "segmentId": "SEG-PREMIUM",
            "segmentName": "Premium Shoppers",
            "description": "High-income, brand-loyal customers",
            "baselineElasticity": -0.8,
        },
        {
            "segmentId": "SEG-VALUE",
            "segmentName": "Value Seekers",
            "description": "Price-sensitive, deal-driven customers",
            "baselineElasticity": -2.1,
        },
        {
            "segmentId": "SEG-MAINSTREAM",
            "segmentName": "Mainstream Buyers",
            "description": "Average price sensitivity, convenience-driven",
            "baselineElasticity": -1.3,
        },
        {
            "segmentId": "SEG-LOYAL",
            "segmentName": "Brand Loyalists",
            "description": "Low price sensitivity, repeat purchasers",
            "baselineElasticity": -0.5,
        },
        {
            "segmentId": "SEG-OCCASIONAL",
            "segmentName": "Occasional Buyers",
            "description": "Infrequent purchasers, moderate sensitivity",
            "baselineElasticity": -1.6,
        },
    ]

    elasticity_data = []
    for seg in segments:
        base = seg["baselineElasticity"]
        # Apply ±20% variance to the elasticity coefficient
        elasticity = round(_apply_variance(abs(base), 0.20) * (-1 if base < 0 else 1), 4)
        cross_elasticity = round(random.uniform(0.1, 0.8), 4)
        segment_share = round(random.uniform(0.10, 0.35), 4)

        elasticity_data.append({
            "segmentId": seg["segmentId"],
            "segmentName": seg["segmentName"],
            "description": seg["description"],
            "priceElasticity": elasticity,
            "crossPriceElasticity": cross_elasticity,
            "incomeElasticity": round(random.uniform(0.3, 1.5), 4),
            "segmentShare": segment_share,
            "sampleSize": _apply_variance_int(5000),
            "confidenceInterval": round(random.uniform(0.90, 0.99), 2),
            "lastUpdated": (
                datetime.now(timezone.utc) - timedelta(days=random.randint(1, 7))
            ).strftime("%Y-%m-%d"),
        })

    # Normalize segment shares to sum to 1.0
    total_share = sum(s["segmentShare"] for s in elasticity_data)
    for s in elasticity_data:
        s["segmentShare"] = round(s["segmentShare"] / total_share, 4)

    return {
        "productId": product_id,
        "category": category,
        "segments": elasticity_data,
        "summary": {
            "weightedElasticity": round(
                sum(s["priceElasticity"] * s["segmentShare"] for s in elasticity_data), 4
            ),
            "mostElasticSegment": min(elasticity_data, key=lambda s: s["priceElasticity"])["segmentName"],
            "leastElasticSegment": max(elasticity_data, key=lambda s: s["priceElasticity"])["segmentName"],
            "totalSegments": len(elasticity_data),
            "dataFreshness": "current",
        },
    }


# Tool dispatch map
TOOL_HANDLERS = {
    "get_sales_history": _handle_get_sales_history,
    "get_pos_realtime": _handle_get_pos_realtime,
    "get_inventory_levels": _handle_get_inventory_levels,
    "get_elasticity_data": _handle_get_elasticity_data,
}


def handler(event, context):
    """Lambda handler for ERP/POS MCP Server.

    Dispatches to the appropriate tool handler based on the 'tool' field
    in the event body. Each tool returns randomized data within ±20%
    variance for demand volumes.

    Args:
        event: Lambda event payload containing MCP tool invocation details.
            Expected format: {"tool": "<tool_name>", "params": {...}}
        context: Lambda context object.

    Returns:
        JSON response with status and data fields conforming to MCP Response Schema.
    """
    start_time = time.time()
    logger.info("ERP/POS MCP Server invoked: %s", json.dumps(event))

    # Parse the event body
    try:
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        elif isinstance(event.get("body"), dict):
            body = event["body"]
        else:
            body = event
    except (json.JSONDecodeError, TypeError) as e:
        logger.error("Failed to parse event body: %s", str(e))
        return _build_error_response(
            "INVALID_REQUEST",
            f"Failed to parse request body: {str(e)}",
            start_time,
        )

    tool_name = body.get("tool")
    params = body.get("params", {})

    # Validate tool name
    if not tool_name:
        return _build_error_response(
            "MISSING_TOOL",
            "Request must include a 'tool' field specifying the MCP tool to invoke.",
            start_time,
        )

    if tool_name not in TOOL_HANDLERS:
        return _build_error_response(
            "UNKNOWN_TOOL",
            f"Unknown tool '{tool_name}'. Available tools: {list(TOOL_HANDLERS.keys())}",
            start_time,
        )

    # Dispatch to tool handler
    try:
        data = TOOL_HANDLERS[tool_name](params)
        logger.info("Tool '%s' executed successfully", tool_name)
        return _build_response(data, start_time)
    except Exception as e:
        logger.error("Tool '%s' failed: %s", tool_name, str(e))
        return _build_error_response(
            "TOOL_EXECUTION_ERROR",
            f"Tool '{tool_name}' failed: {str(e)}",
            start_time,
        )
