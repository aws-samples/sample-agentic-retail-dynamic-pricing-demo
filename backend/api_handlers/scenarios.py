"""Lambda handler for scenario-related endpoints.

Handles scenario detail retrieval and scenario-specific operations
that are not covered by the pricing_cycles handler.
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


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for scenario detail endpoints."""
    http_method = event.get("httpMethod", "")
    path = event.get("path", "")
    path_params = event.get("pathParameters") or {}

    logger.info("Scenarios handler: %s %s", http_method, path)

    try:
        if http_method == "GET":
            scenario_id = path_params.get("scenarioId", "")
            if not scenario_id:
                return _response(400, {"error": "scenarioId is required"})
            return _get_scenario_detail(scenario_id)
        else:
            return _response(404, {"error": "Not found"})
    except Exception as e:
        logger.exception("Error handling request")
        return _response(500, {"error": "Internal server error"})


def _get_scenario_detail(scenario_id: str) -> dict[str, Any]:
    """Get detailed information for a specific scenario from DynamoDB.

    Scans the PricingScenarios table filtering by scenarioId (sort key).
    Suitable for demo-scale data; production would use a GSI.

    Args:
        scenario_id: The unique scenario identifier.

    Returns:
        API Gateway proxy response with scenario detail or 404.
    """
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(PRICING_SCENARIOS_TABLE)

    response = table.scan(
        FilterExpression=Attr("scenarioId").eq(scenario_id),
        Limit=1,
    )

    items = response.get("Items", [])
    if not items:
        return _response(404, {"error": f"Scenario '{scenario_id}' not found"})

    scenario = _convert_decimals_to_float(items[0])
    return _response(200, scenario)


def _convert_decimals_to_float(obj: Any) -> Any:
    """Recursively convert Decimal values to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimals_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimals_to_float(item) for item in obj]
    return obj


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
