"""Lambda handler for monitoring endpoints.

Handles:
- GET /monitoring/{scenarioId}: Get monitoring metrics for an approved scenario

Queries the PricingScenarios table for the scenario and returns monitoring
metrics including projected vs actual revenue/margin and variance status.

Requirements: 4.1, 9.6
"""

import json
import os
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr

try:
    from log_config import configure_logging
except ImportError:
    from backend.api_handlers.log_config import configure_logging

logger = configure_logging(__name__)

PRICING_SCENARIOS_TABLE = os.environ.get("PRICING_SCENARIOS_TABLE", "PricingScenarios")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Variance thresholds (matching shared/variance_detection.py)
REVENUE_VARIANCE_THRESHOLD = 0.10  # 10%
MARGIN_VARIANCE_THRESHOLD = 0.03  # 3 percentage points


def _get_dynamodb_resource():
    """Get a boto3 DynamoDB resource."""
    return boto3.resource("dynamodb", region_name=AWS_REGION)


def _convert_decimals(obj: Any) -> Any:
    """Recursively convert Decimal values to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimals(item) for item in obj]
    return obj


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for monitoring endpoint."""
    http_method = event.get("httpMethod", "")
    path = event.get("path", "")
    path_params = event.get("pathParameters") or {}

    logger.info("Monitoring handler: %s %s", http_method, path)

    try:
        if http_method == "GET" and path_params.get("scenarioId"):
            scenario_id = path_params["scenarioId"]
            return _get_monitoring_metrics(scenario_id)
        else:
            return _response(404, {"error": "Not found"})
    except Exception as e:
        logger.exception("Error handling request")
        return _response(500, {"error": str(e)})


def _get_monitoring_metrics(scenario_id: str) -> dict[str, Any]:
    """Handle GET /monitoring/{scenarioId} - return monitoring metrics.

    Queries the PricingScenarios table for the scenario and returns:
    - Projected metrics (revenue, margin)
    - Actual metrics (if available)
    - Variance calculations and status
    """
    resource = _get_dynamodb_resource()
    table = resource.Table(PRICING_SCENARIOS_TABLE)

    # Scan for the scenario by scenarioId (SK) since we don't know the cycleId (PK)
    # For an MVP demo this is acceptable; in production a GSI would be preferred
    response = table.scan(
        FilterExpression=Attr("scenarioId").eq(scenario_id),
        Limit=100,
    )

    items = response.get("Items", [])

    if not items:
        return _response(404, {"error": f"Scenario '{scenario_id}' not found"})

    scenario = _convert_decimals(items[0])

    # Check if scenario is approved (only approved scenarios have monitoring)
    approval_status = scenario.get("approvalStatus", "PENDING")

    # Extract projected metrics from the scenario
    projected_revenue = scenario.get("projectedRevenue", 0.0)
    projected_margin = scenario.get("projectedMargin", 0.0)

    # Extract actual metrics (populated by Implementation Monitoring Agent after approval)
    actual_revenue = scenario.get("actualRevenue")
    actual_margin = scenario.get("actualMargin")
    actual_conversion_rate = scenario.get("actualConversionRate")
    last_updated = scenario.get("monitoringUpdatedAt")

    # Determine monitoring status and compute variance
    if approval_status != "APPROVED":
        # Scenario not yet approved - return projected only
        return _response(200, {
            "scenarioId": scenario_id,
            "cycleId": scenario.get("cycleId"),
            "approvalStatus": approval_status,
            "status": "pending_approval",
            "metrics": {
                "projectedRevenue": projected_revenue,
                "projectedMargin": projected_margin,
                "actualRevenue": None,
                "actualMargin": None,
                "revenueVariance": None,
                "marginVariance": None,
                "conversionRate": None,
            },
            "varianceStatus": None,
            "lastUpdated": None,
        })

    if actual_revenue is None or actual_margin is None:
        # Approved but no actual metrics yet - monitoring is active
        return _response(200, {
            "scenarioId": scenario_id,
            "cycleId": scenario.get("cycleId"),
            "approvalStatus": approval_status,
            "status": "monitoring_active",
            "metrics": {
                "projectedRevenue": projected_revenue,
                "projectedMargin": projected_margin,
                "actualRevenue": None,
                "actualMargin": None,
                "revenueVariance": None,
                "marginVariance": None,
                "conversionRate": None,
            },
            "varianceStatus": None,
            "lastUpdated": last_updated,
        })

    # Compute variance metrics
    revenue_variance = (
        abs(actual_revenue - projected_revenue) / abs(projected_revenue)
        if projected_revenue != 0
        else 0.0
    )
    margin_variance = abs(actual_margin - projected_margin)

    # Determine variance status
    breached_thresholds = []
    if revenue_variance > REVENUE_VARIANCE_THRESHOLD:
        breached_thresholds.append("revenue")
    if margin_variance > MARGIN_VARIANCE_THRESHOLD:
        breached_thresholds.append("margin")

    if breached_thresholds:
        variance_status = "threshold_breached"
    else:
        variance_status = "within_bounds"

    return _response(200, {
        "scenarioId": scenario_id,
        "cycleId": scenario.get("cycleId"),
        "approvalStatus": approval_status,
        "status": "monitoring_active",
        "metrics": {
            "projectedRevenue": projected_revenue,
            "projectedMargin": projected_margin,
            "actualRevenue": actual_revenue,
            "actualMargin": actual_margin,
            "revenueVariance": round(revenue_variance, 4),
            "marginVariance": round(margin_variance, 4),
            "conversionRate": actual_conversion_rate,
        },
        "varianceStatus": variance_status,
        "breachedThresholds": breached_thresholds,
        "lastUpdated": last_updated,
    })


def _response(status_code: int, body: dict) -> dict[str, Any]:
    """Build API Gateway proxy response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }
