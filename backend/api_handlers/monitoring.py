"""Lambda handler for monitoring endpoints.

Handles:
- GET /monitoring/{scenarioId}: Get monitoring metrics for an approved scenario
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PRICING_SCENARIOS_TABLE = os.environ.get("PRICING_SCENARIOS_TABLE", "PricingScenarios")


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
    """Handle GET /monitoring/{scenarioId} - return monitoring metrics."""
    # TODO: Query actual vs. projected metrics for the approved scenario
    return _response(200, {
        "scenarioId": scenario_id,
        "metrics": {
            "projectedRevenue": 0.0,
            "actualRevenue": 0.0,
            "revenueVariance": 0.0,
            "projectedMargin": 0.0,
            "actualMargin": 0.0,
            "marginVariance": 0.0,
            "conversionRate": 0.0,
        },
        "status": "monitoring",
        "lastUpdated": None,
    })


def _response(status_code: int, body: dict) -> dict[str, Any]:
    """Build API Gateway proxy response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
