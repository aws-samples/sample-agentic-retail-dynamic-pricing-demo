"""Cost & Finance MCP Server Lambda handler.

Provides cost structures, margin targets, and financial constraints
as MCP tools accessible by the Strategy Synthesis Agent. Returns
randomized cost inputs within ±5% variance from baseline to simulate
real-world cost fluctuations.

Tools exposed:
- get_cost_structure: Returns cost breakdown (materials, labor, overhead, shipping)
- get_margin_targets: Returns target margins by category/channel
- get_financial_constraints: Returns budget limits, max discount percentages, channel-specific rules
"""

import json
import logging
import random
import time
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Variance bound for cost inputs (±5%)
COST_VARIANCE = 0.05

# Baseline cost structures by product category
BASELINE_COSTS = {
    "electronics": {
        "materials": 45.00,
        "labor": 12.50,
        "overhead": 8.75,
        "shipping": 5.25,
    },
    "apparel": {
        "materials": 15.00,
        "labor": 8.00,
        "overhead": 4.50,
        "shipping": 3.00,
    },
    "grocery": {
        "materials": 6.50,
        "labor": 2.25,
        "overhead": 1.75,
        "shipping": 1.50,
    },
    "home_garden": {
        "materials": 22.00,
        "labor": 10.00,
        "overhead": 6.00,
        "shipping": 7.50,
    },
    "sports_outdoors": {
        "materials": 30.00,
        "labor": 9.00,
        "overhead": 5.50,
        "shipping": 6.00,
    },
}

# Baseline margin targets by category and channel
BASELINE_MARGIN_TARGETS = {
    "electronics": {
        "online": 0.22,
        "retail_store": 0.28,
        "wholesale": 0.15,
        "marketplace": 0.18,
    },
    "apparel": {
        "online": 0.45,
        "retail_store": 0.55,
        "wholesale": 0.30,
        "marketplace": 0.35,
    },
    "grocery": {
        "online": 0.25,
        "retail_store": 0.30,
        "wholesale": 0.12,
        "marketplace": 0.20,
    },
    "home_garden": {
        "online": 0.35,
        "retail_store": 0.40,
        "wholesale": 0.20,
        "marketplace": 0.28,
    },
    "sports_outdoors": {
        "online": 0.38,
        "retail_store": 0.42,
        "wholesale": 0.22,
        "marketplace": 0.30,
    },
}

# Baseline financial constraints
BASELINE_FINANCIAL_CONSTRAINTS = {
    "max_discount_percent": 25.0,
    "min_margin_percent": 10.0,
    "quarterly_budget_limit": 500000.00,
    "monthly_promotion_budget": 75000.00,
    "max_loss_leader_items": 5,
    "channel_rules": {
        "online": {
            "max_discount_percent": 30.0,
            "free_shipping_threshold": 50.00,
            "dynamic_pricing_enabled": True,
        },
        "retail_store": {
            "max_discount_percent": 20.0,
            "price_match_guarantee": True,
            "dynamic_pricing_enabled": False,
        },
        "wholesale": {
            "max_discount_percent": 35.0,
            "volume_discount_tiers": [100, 500, 1000],
            "dynamic_pricing_enabled": True,
        },
        "marketplace": {
            "max_discount_percent": 15.0,
            "platform_fee_percent": 12.0,
            "dynamic_pricing_enabled": True,
        },
    },
}


def _apply_variance(value, variance=COST_VARIANCE):
    """Apply random variance within ±bounds to a numeric value.

    Args:
        value: The baseline numeric value.
        variance: The maximum fractional variance (default ±5%).

    Returns:
        The value with random variance applied, rounded to 4 decimal places.
    """
    factor = 1.0 + random.uniform(-variance, variance)
    return round(value * factor, 4)


def _build_response(data, start_time):
    """Build a standardized MCP response with metadata.

    Args:
        data: The response data payload.
        start_time: The start time of the request for latency calculation.

    Returns:
        Lambda response dict with statusCode and JSON body.
    """
    latency_ms = int((time.time() - start_time) * 1000)
    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "success",
            "data": data,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "cost_finance_server",
                "latencyMs": latency_ms,
            },
        }),
    }


def _build_error_response(code, message, start_time):
    """Build a standardized MCP error response.

    Args:
        code: Error code string.
        message: Human-readable error message.
        start_time: The start time of the request for latency calculation.

    Returns:
        Lambda response dict with statusCode and JSON body.
    """
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "cost_finance_server",
                "latencyMs": latency_ms,
            },
        }),
    }


def get_cost_structure(params):
    """Return cost breakdown with ±5% variance from baseline.

    Args:
        params: Dict with optional 'category' and 'product_id' fields.

    Returns:
        Dict with cost breakdown (materials, labor, overhead, shipping, total).
    """
    category = params.get("category", "electronics")
    product_id = params.get("product_id", "PROD-001")

    baseline = BASELINE_COSTS.get(category, BASELINE_COSTS["electronics"])

    materials = _apply_variance(baseline["materials"])
    labor = _apply_variance(baseline["labor"])
    overhead = _apply_variance(baseline["overhead"])
    shipping = _apply_variance(baseline["shipping"])
    total = round(materials + labor + overhead + shipping, 4)

    return {
        "product_id": product_id,
        "category": category,
        "cost_breakdown": {
            "materials": materials,
            "labor": labor,
            "overhead": overhead,
            "shipping": shipping,
        },
        "total_unit_cost": total,
        "currency": "USD",
        "cost_trend": random.choice(["stable", "increasing", "decreasing"]),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def get_margin_targets(params):
    """Return target margins by category and channel with ±5% variance.

    Args:
        params: Dict with optional 'category' field.

    Returns:
        Dict with margin targets per channel for the specified category.
    """
    category = params.get("category", "electronics")

    baseline = BASELINE_MARGIN_TARGETS.get(
        category, BASELINE_MARGIN_TARGETS["electronics"]
    )

    margin_targets = {}
    for channel, target in baseline.items():
        margin_targets[channel] = {
            "target_margin": _apply_variance(target),
            "min_acceptable_margin": _apply_variance(target * 0.7),
            "stretch_margin": _apply_variance(target * 1.2),
        }

    return {
        "category": category,
        "margin_targets": margin_targets,
        "fiscal_quarter": f"Q{random.randint(1, 4)} {datetime.now().year}",
        "strategy": random.choice([
            "margin_protection",
            "growth_focused",
            "competitive_response",
            "balanced",
        ]),
    }


def get_financial_constraints(params):
    """Return budget limits, max discount percentages, and channel-specific rules.

    Args:
        params: Dict with optional 'channel' field for channel-specific filtering.

    Returns:
        Dict with financial constraints and channel rules.
    """
    channel = params.get("channel")

    constraints = {
        "max_discount_percent": _apply_variance(
            BASELINE_FINANCIAL_CONSTRAINTS["max_discount_percent"]
        ),
        "min_margin_percent": _apply_variance(
            BASELINE_FINANCIAL_CONSTRAINTS["min_margin_percent"]
        ),
        "quarterly_budget_limit": _apply_variance(
            BASELINE_FINANCIAL_CONSTRAINTS["quarterly_budget_limit"]
        ),
        "monthly_promotion_budget": _apply_variance(
            BASELINE_FINANCIAL_CONSTRAINTS["monthly_promotion_budget"]
        ),
        "max_loss_leader_items": BASELINE_FINANCIAL_CONSTRAINTS[
            "max_loss_leader_items"
        ],
    }

    channel_rules = {}
    baseline_rules = BASELINE_FINANCIAL_CONSTRAINTS["channel_rules"]

    if channel and channel in baseline_rules:
        # Return rules for specific channel
        rule = baseline_rules[channel]
        channel_rules[channel] = {
            "max_discount_percent": _apply_variance(rule["max_discount_percent"]),
            **{k: v for k, v in rule.items() if k != "max_discount_percent"},
        }
    else:
        # Return rules for all channels
        for ch, rule in baseline_rules.items():
            channel_rules[ch] = {
                "max_discount_percent": _apply_variance(rule["max_discount_percent"]),
                **{k: v for k, v in rule.items() if k != "max_discount_percent"},
            }

    constraints["channel_rules"] = channel_rules

    return constraints


# Tool registry mapping tool names to handler functions
TOOLS = {
    "get_cost_structure": get_cost_structure,
    "get_margin_targets": get_margin_targets,
    "get_financial_constraints": get_financial_constraints,
}


def handler(event, context):
    """Lambda handler for Cost & Finance MCP Server.

    Dispatches to the appropriate tool function based on the 'tool' field
    in the event body.

    Args:
        event: Lambda event payload containing MCP tool invocation details.
            Expected format: {"tool": "<tool_name>", "params": {...}}
        context: Lambda context object.

    Returns:
        JSON response with status and data fields conforming to MCP Response Schema.
    """
    start_time = time.time()
    logger.info("Cost & Finance MCP Server invoked: %s", json.dumps(event))

    # Parse event body - handle both direct invocation and API Gateway format
    body = event
    if isinstance(event.get("body"), str):
        body = json.loads(event["body"])
    elif isinstance(event.get("body"), dict):
        body = event["body"]

    tool_name = body.get("tool")
    params = body.get("params", {})

    if not tool_name:
        return _build_error_response(
            "MISSING_TOOL",
            "Request must include a 'tool' field specifying the MCP tool to invoke.",
            start_time,
        )

    if tool_name not in TOOLS:
        return _build_error_response(
            "UNKNOWN_TOOL",
            f"Unknown tool '{tool_name}'. Available tools: {list(TOOLS.keys())}",
            start_time,
        )

    try:
        data = TOOLS[tool_name](params)
        return _build_response(data, start_time)
    except Exception as e:
        logger.error("Error executing tool '%s': %s", tool_name, str(e))
        return _build_error_response(
            "EXECUTION_ERROR",
            f"Error executing tool '{tool_name}': {str(e)}",
            start_time,
        )
