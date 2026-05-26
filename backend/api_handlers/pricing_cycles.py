"""Lambda handler for pricing cycle endpoints.

Handles:
- POST /pricing-cycles: Initiate a new pricing cycle
- GET /pricing-cycles/{id}: Get cycle status and scenarios
- GET /pricing-cycles/{id}/scenarios: List scenarios (paginated)

This Lambda is a thin wrapper: validate request → write to DynamoDB →
call orchestrator on AgentCore → return 202.

Requirements: 4.9, 1.1
"""

import json
import logging
import os
import uuid
from typing import Any

import boto3

from backend.orchestration.persistence import (
    create_pricing_cycle,
    get_cycle,
    get_scenarios,
    update_cycle_status,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PRICING_CYCLES_TABLE = os.environ.get("PRICING_CYCLES_TABLE", "PricingCycles")
PRICING_SCENARIOS_TABLE = os.environ.get("PRICING_SCENARIOS_TABLE", "PricingScenarios")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def _require_env(var_name: str) -> str:
    """Read a required environment variable or raise a clear error."""
    value = os.environ.get(var_name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{var_name}' is not set. "
            f"There is no local execution fallback."
        )
    return value


ORCHESTRATOR_AGENT_ARN = _require_env("ORCHESTRATOR_AGENT_ARN")

# Minimum session ID length required by AgentCore Runtime
_MIN_SESSION_ID_LENGTH = 33


def _ensure_session_id(session_id: str | None = None) -> str:
    """Ensure the session ID meets AgentCore's minimum length requirement (33+ chars)."""
    if not session_id:
        session_id = f"pricing-cycle-{uuid.uuid4().hex}"
    if len(session_id) < _MIN_SESSION_ID_LENGTH:
        padding = uuid.uuid4().hex
        session_id = f"{session_id}-{padding}"
    return session_id[:128]


def _invoke_orchestrator(
    pricing_group: str,
    objectives: list[str],
    constraints: dict[str, Any],
    session_id: str | None = None,
) -> dict[str, Any]:
    """Invoke the Orchestrator Agent via AgentCore Runtime API.

    Args:
        pricing_group: The product group to analyze.
        objectives: Strategic objectives for the cycle.
        constraints: Business constraints for the cycle.
        session_id: Optional session ID for AgentCore Runtime scoping.

    Returns:
        Parsed response from the orchestrator agent.
    """
    client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)

    payload = json.dumps({
        "prompt": json.dumps({
            "pricing_group": pricing_group,
            "objectives": objectives,
            "constraints": constraints,
        })
    }).encode()

    runtime_session_id = _ensure_session_id(session_id)

    response = client.invoke_agent_runtime(
        agentRuntimeArn=ORCHESTRATOR_AGENT_ARN,
        runtimeSessionId=runtime_session_id,
        payload=payload,
        qualifier="DEFAULT",
    )

    response_body = response["response"].read()

    try:
        return json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"raw_output": response_body.decode("utf-8", errors="replace")}


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
    to DynamoDB, calls the orchestrator on AgentCore, and returns 202
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

    # Invoke the orchestrator agent on AgentCore (async — fire and forget)
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
    """Invoke the orchestrator agent on AgentCore Runtime.

    This calls invoke_agent_runtime with the ORCHESTRATOR_AGENT_ARN.
    The Lambda returns 202 immediately; the orchestrator runs asynchronously
    on AgentCore and updates DynamoDB as it progresses.

    Args:
        cycle_id: The unique pricing cycle identifier.
        pricing_group: The product group to analyze.
        objectives: Strategic objectives for the cycle.
        constraints: Business constraints for the cycle.
    """
    try:
        logger.info("Invoking orchestrator agent on AgentCore for cycle %s", cycle_id)

        # Update status to ANALYZING
        update_cycle_status(
            cycle_id=cycle_id,
            status="ANALYZING",
            table_name=PRICING_CYCLES_TABLE,
        )

        # Invoke orchestrator via AgentCore Runtime
        _invoke_orchestrator(
            pricing_group=pricing_group,
            objectives=objectives,
            constraints=constraints,
            session_id=f"cycle-{cycle_id}",
        )

        logger.info("Orchestrator invoked for cycle %s", cycle_id)

    except Exception as e:
        logger.exception("Failed to invoke orchestrator for cycle %s: %s", cycle_id, e)
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
