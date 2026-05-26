"""Lambda handler for pricing cycle endpoints.

Handles:
- POST /pricing-cycles: Initiate a new pricing cycle
- GET /pricing-cycles/{id}: Get cycle status and scenarios
- GET /pricing-cycles/{id}/scenarios: List scenarios (paginated)
"""

import json
import logging
import os
from typing import Any

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
import urllib3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PRICING_CYCLES_TABLE = os.environ.get("PRICING_CYCLES_TABLE", "PricingCycles")
PRICING_SCENARIOS_TABLE = os.environ.get("PRICING_SCENARIOS_TABLE", "PricingScenarios")
AGENTCORE_ENDPOINT = os.environ.get("AGENTCORE_ENDPOINT", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def _sign_request(method: str, url: str, body: str = "") -> dict[str, str]:
    """Sign an HTTP request with SigV4 for AgentCore invocations.

    Returns headers dict containing the Authorization and other SigV4 headers.
    """
    session = boto3.Session()
    credentials = session.get_credentials().get_frozen_credentials()

    request = AWSRequest(method=method, url=url, data=body)
    request.headers["Content-Type"] = "application/json"

    SigV4Auth(credentials, "bedrock", AWS_REGION).add_auth(request)
    return dict(request.headers)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for pricing cycle API endpoints."""
    http_method = event.get("httpMethod", "")
    path = event.get("path", "")
    path_params = event.get("pathParameters") or {}

    logger.info("Pricing cycles handler: %s %s", http_method, path)

    try:
        if http_method == "POST" and path == "/pricing-cycles":
            return _create_pricing_cycle(event)
        elif http_method == "GET" and "scenarios" in path:
            cycle_id = path_params.get("id", "")
            return _get_scenarios(cycle_id, event)
        elif http_method == "GET" and path_params.get("id"):
            cycle_id = path_params["id"]
            return _get_pricing_cycle(cycle_id)
        else:
            return _response(404, {"error": "Not found"})
    except Exception as e:
        logger.exception("Error handling request")
        return _response(500, {"error": str(e)})


def _create_pricing_cycle(event: dict[str, Any]) -> dict[str, Any]:
    """Handle POST /pricing-cycles - initiate a new pricing cycle."""
    # TODO: Parse request body, validate, invoke Orchestrator Agent via SigV4
    body = json.loads(event.get("body", "{}"))
    return _response(202, {
        "message": "Pricing cycle initiated",
        "cycleId": "placeholder-cycle-id",
        "status": "INITIATED",
    })


def _get_pricing_cycle(cycle_id: str) -> dict[str, Any]:
    """Handle GET /pricing-cycles/{id} - get cycle status."""
    # TODO: Query PricingCycles DynamoDB table
    return _response(200, {
        "cycleId": cycle_id,
        "status": "INITIATED",
        "agentStatuses": {},
    })


def _get_scenarios(cycle_id: str, event: dict[str, Any]) -> dict[str, Any]:
    """Handle GET /pricing-cycles/{id}/scenarios - list scenarios paginated."""
    # TODO: Query PricingScenarios DynamoDB table with pagination
    query_params = event.get("queryStringParameters") or {}
    page = int(query_params.get("page", "1"))
    page_size = 20

    return _response(200, {
        "cycleId": cycle_id,
        "scenarios": [],
        "page": page,
        "pageSize": page_size,
        "totalCount": 0,
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
