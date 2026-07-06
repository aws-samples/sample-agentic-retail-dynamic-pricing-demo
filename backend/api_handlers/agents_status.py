"""Lambda handler for agent status endpoints.

Handles:
- GET /agents/status: Get real-time agent execution status

Queries the PricingCycles table for the cycle's agentStatuses field and returns
structured response with each agent's status (idle, running, completed, failed).

Requirements: 4.1, 9.6
"""

import json
import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

try:
    from log_config import configure_logging
except ImportError:
    from backend.api_handlers.log_config import configure_logging

logger = configure_logging(__name__)

PRICING_CYCLES_TABLE = os.environ.get("PRICING_CYCLES_TABLE", "PricingCycles")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# All known agents in the pricing system
AGENT_IDS = [
    "orchestrator",
    "competitive_intelligence",
    "demand_forecasting",
    "market_intelligence",
    "strategy_synthesis",
    "implementation_monitoring",
]


def _get_dynamodb_resource():
    """Get a boto3 DynamoDB resource."""
    return boto3.resource("dynamodb", region_name=AWS_REGION)


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
    """Handle GET /agents/status - return real-time agent execution status.

    Accepts a cycleId query parameter. Queries the PricingCycles table for
    the cycle's agentStatuses field and returns structured response with
    each agent's status.
    """
    query_params = event.get("queryStringParameters") or {}
    cycle_id = query_params.get("cycleId", "")

    if not cycle_id:
        return _response(400, {"error": "Missing required query parameter: cycleId"})

    # Query PricingCycles table for the cycle
    resource = _get_dynamodb_resource()
    table = resource.Table(PRICING_CYCLES_TABLE)

    response = table.query(
        KeyConditionExpression=Key("cycleId").eq(cycle_id),
        Limit=1,
    )

    items = response.get("Items", [])

    if not items:
        return _response(404, {"error": f"Pricing cycle '{cycle_id}' not found"})

    cycle = items[0]
    agent_statuses_raw = cycle.get("agentStatuses", {})
    cycle_status = cycle.get("status", "INITIATED")

    # Build structured agent status response
    # Ensure all known agents are represented, defaulting to idle
    agents = {}
    for agent_id in AGENT_IDS:
        if agent_id in agent_statuses_raw:
            agent_data = agent_statuses_raw[agent_id]
            agents[agent_id] = {
                "status": agent_data.get("status", "idle"),
                "startTime": agent_data.get("startTime"),
                "endTime": agent_data.get("endTime"),
                "error": agent_data.get("error"),
            }
        else:
            agents[agent_id] = {
                "status": "idle",
                "startTime": None,
                "endTime": None,
                "error": None,
            }

    return _response(200, {
        "cycleId": cycle_id,
        "cycleStatus": cycle_status,
        "agents": agents,
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
