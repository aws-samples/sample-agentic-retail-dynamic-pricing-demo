"""Lambda handler for pricing cycle endpoints.

Handles:
- POST /pricing-cycles: Initiate a new pricing cycle
- GET /pricing-cycles/{id}: Get cycle status and scenarios
- GET /pricing-cycles/{id}/scenarios: List scenarios (paginated)

Requirements: 4.9, 1.1
"""

import json
import logging
import os
import threading
import uuid
from typing import Any

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
import urllib3

from backend.orchestration.persistence import (
    create_pricing_cycle,
    get_cycle,
    get_scenarios,
    update_cycle_status,
)
from backend.agents.orchestrator import run_pricing_cycle, PricingCycleRequest

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
    """Handle POST /pricing-cycles - initiate a new pricing cycle.

    Parses the request body for pricingGroup (required), objectives (list),
    and constraints (dict). Validates required fields, persists the cycle
    to DynamoDB, starts the orchestrator asynchronously, and returns 202
    with the cycleId and initial status.

    Requirements: 4.9, 1.1
    """
    # Parse request body
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return _response(400, {"error": "Invalid JSON in request body"})

    # Extract fields
    pricing_group = body.get("pricingGroup", "")
    objectives = body.get("objectives", [])
    constraints = body.get("constraints", {})

    # Validate required fields
    if not pricing_group or not isinstance(pricing_group, str) or not pricing_group.strip():
        return _response(400, {
            "error": "Field 'pricingGroup' is required and must be a non-empty string"
        })

    pricing_group = pricing_group.strip()

    # Validate objectives is a list
    if not isinstance(objectives, list):
        return _response(400, {
            "error": "Field 'objectives' must be a list"
        })

    # Validate constraints is a dict
    if not isinstance(constraints, dict):
        return _response(400, {
            "error": "Field 'constraints' must be an object"
        })

    # Generate unique cycle ID
    cycle_id = str(uuid.uuid4())

    # Extract requester info from Cognito authorizer claims (if available)
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    claims = authorizer.get("claims", {})
    requested_by = claims.get("sub", "anonymous")

    # Persist the pricing cycle to DynamoDB
    try:
        create_pricing_cycle(
            cycle_id=cycle_id,
            pricing_group=pricing_group,
            objectives=objectives,
            constraints=constraints,
            requested_by=requested_by,
            table_name=PRICING_CYCLES_TABLE,
        )
    except Exception as e:
        logger.error("Failed to persist pricing cycle %s: %s", cycle_id, e)
        return _response(500, {"error": "Failed to create pricing cycle"})

    # Start the orchestrator asynchronously via a background thread
    _start_orchestrator_async(cycle_id, pricing_group, objectives, constraints)

    logger.info(
        "Pricing cycle %s initiated for group '%s'", cycle_id, pricing_group
    )

    return _response(202, {
        "cycleId": cycle_id,
        "status": "INITIATED",
        "pricingGroup": pricing_group,
    })


def _start_orchestrator_async(
    cycle_id: str,
    pricing_group: str,
    objectives: list[str],
    constraints: dict[str, Any],
) -> None:
    """Start the orchestrator agent in a background thread.

    This allows the API to return 202 immediately while the pricing cycle
    runs asynchronously. The orchestrator updates the cycle status in
    DynamoDB as it progresses.

    Args:
        cycle_id: The unique pricing cycle identifier.
        pricing_group: The product group to analyze.
        objectives: Strategic objectives for the cycle.
        constraints: Business constraints for the cycle.
    """

    def _run():
        try:
            logger.info("Orchestrator starting for cycle %s", cycle_id)

            # Update status to ANALYZING
            update_cycle_status(
                cycle_id=cycle_id,
                status="ANALYZING",
                table_name=PRICING_CYCLES_TABLE,
            )

            # Build the request and run the pricing cycle
            request = PricingCycleRequest(
                pricing_group=pricing_group,
                objectives=objectives,
                constraints=constraints,
            )

            result = run_pricing_cycle(request=request)

            # Update cycle status based on result
            final_status = result.status  # COMPLETE, DEGRADED, or FAILED
            update_cycle_status(
                cycle_id=cycle_id,
                status=final_status,
                scenario_count=len(result.ranked_scenarios),
                table_name=PRICING_CYCLES_TABLE,
            )

            logger.info(
                "Orchestrator completed cycle %s with status %s (%d scenarios)",
                cycle_id,
                final_status,
                len(result.ranked_scenarios),
            )

        except Exception as e:
            logger.exception("Orchestrator failed for cycle %s: %s", cycle_id, e)
            try:
                update_cycle_status(
                    cycle_id=cycle_id,
                    status="FAILED",
                    table_name=PRICING_CYCLES_TABLE,
                )
            except Exception:
                logger.exception(
                    "Failed to update cycle %s status to FAILED", cycle_id
                )

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def _get_pricing_cycle(cycle_id: str) -> dict[str, Any]:
    """Handle GET /pricing-cycles/{id} - get cycle status and metadata."""
    cycle = get_cycle(cycle_id, table_name=PRICING_CYCLES_TABLE)

    if cycle is None:
        return _response(404, {"error": f"Pricing cycle '{cycle_id}' not found"})

    return _response(200, {
        "cycleId": cycle.get("cycleId"),
        "status": cycle.get("status"),
        "pricingGroup": cycle.get("pricingGroup"),
        "objectives": cycle.get("objectives", []),
        "constraints": cycle.get("constraints", {}),
        "agentStatuses": cycle.get("agentStatuses", {}),
        "scenarioCount": cycle.get("scenarioCount", 0),
        "requestedBy": cycle.get("requestedBy"),
        "createdAt": cycle.get("createdAt"),
        "completedAt": cycle.get("completedAt"),
    })


def _get_scenarios(cycle_id: str, event: dict[str, Any]) -> dict[str, Any]:
    """Handle GET /pricing-cycles/{id}/scenarios - list scenarios paginated."""
    # Verify the cycle exists first
    cycle = get_cycle(cycle_id, table_name=PRICING_CYCLES_TABLE)
    if cycle is None:
        return _response(404, {"error": f"Pricing cycle '{cycle_id}' not found"})

    # Parse page query parameter (default to 1)
    query_params = event.get("queryStringParameters") or {}
    try:
        page = int(query_params.get("page", "1"))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    page_size = 20

    result = get_scenarios(
        cycle_id=cycle_id,
        page=page,
        page_size=page_size,
        table_name=PRICING_SCENARIOS_TABLE,
    )

    return _response(200, {
        "cycleId": cycle_id,
        "scenarios": result["scenarios"],
        "page": result["page"],
        "pageSize": result["pageSize"],
        "totalCount": result["totalCount"],
        "totalPages": result["totalPages"],
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
