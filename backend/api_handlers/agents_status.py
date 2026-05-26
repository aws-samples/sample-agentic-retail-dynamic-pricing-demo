"""Lambda handler for agent status endpoints.

Handles:
- GET /agents/status: Get real-time agent execution status
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PRICING_CYCLES_TABLE = os.environ.get("PRICING_CYCLES_TABLE", "PricingCycles")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for agent status endpoint."""
    http_method = event.get("httpMethod", "")
    path = event.get("path", "")

    logger.info("Agents status handler: %s %s", http_method, path)

    try:
        if http_method == "GET" and path == "/agents/status":
            return _get_agents_status(event)
        else:
            return _response(404, {"error": "Not found"})
    except Exception as e:
        logger.exception("Error handling request")
        return _response(500, {"error": str(e)})


def _get_agents_status(event: dict[str, Any]) -> dict[str, Any]:
    """Handle GET /agents/status - return real-time agent execution status."""
    # TODO: Query PricingCycles table for active cycle agent statuses
    query_params = event.get("queryStringParameters") or {}
    cycle_id = query_params.get("cycleId", "")

    return _response(200, {
        "cycleId": cycle_id,
        "agents": {
            "orchestrator": {"status": "idle", "startTime": None, "endTime": None},
            "competitive_intelligence": {"status": "idle", "startTime": None, "endTime": None},
            "demand_forecasting": {"status": "idle", "startTime": None, "endTime": None},
            "market_intelligence": {"status": "idle", "startTime": None, "endTime": None},
            "strategy_synthesis": {"status": "idle", "startTime": None, "endTime": None},
            "implementation_monitoring": {"status": "idle", "startTime": None, "endTime": None},
        },
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
