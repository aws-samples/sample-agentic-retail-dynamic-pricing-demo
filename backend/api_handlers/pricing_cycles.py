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
import os
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

try:
    from log_config import configure_logging
except ImportError:
    from backend.api_handlers.log_config import configure_logging

try:
    from input_sanitizer import (
        sanitize_text,
        sanitize_dict,
        PromptInjectionDetectedError,
    )
except ImportError:
    from backend.orchestration.input_sanitizer import (
        sanitize_text,
        sanitize_dict,
        PromptInjectionDetectedError,
    )

logger = configure_logging(__name__)

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


def _iso_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _convert_floats_to_decimal(obj: Any) -> Any:
    """Recursively convert float values to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats_to_decimal(item) for item in obj]
    return obj


def _convert_decimals_to_float(obj: Any) -> Any:
    """Recursively convert Decimal values back to float for JSON compatibility."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimals_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimals_to_float(item) for item in obj]
    return obj


def _get_dynamodb_resource():
    """Get a boto3 DynamoDB resource."""
    return boto3.resource("dynamodb", region_name=AWS_REGION)


# --- DynamoDB persistence operations (inlined for Lambda self-containment) ---


def create_pricing_cycle(
    cycle_id: str,
    pricing_group: str,
    objectives: list[str],
    constraints: dict[str, Any],
    requested_by: str,
    table_name: str = PRICING_CYCLES_TABLE,
) -> dict[str, Any]:
    """Write a new pricing cycle record to DynamoDB."""
    resource = _get_dynamodb_resource()
    table = resource.Table(table_name)

    now = _iso_now()
    ttl_epoch = int(time.time()) + 3600

    item = {
        "cycleId": cycle_id,
        "status": "INITIATED",
        "pricingGroup": pricing_group,
        "objectives": objectives,
        "constraints": _convert_floats_to_decimal(constraints),
        "agentStatuses": {},
        "scenarioCount": 0,
        "requestedBy": requested_by,
        "createdAt": now,
        "ttl": ttl_epoch,
    }

    table.put_item(Item=item)
    logger.info("Created pricing cycle %s with status INITIATED", cycle_id)
    return _convert_decimals_to_float(item)


def update_cycle_status(
    cycle_id: str,
    status: str,
    table_name: str = PRICING_CYCLES_TABLE,
) -> None:
    """Update the status of a pricing cycle in DynamoDB."""
    resource = _get_dynamodb_resource()
    table = resource.Table(table_name)

    response = table.query(
        KeyConditionExpression=Key("cycleId").eq(cycle_id),
        Limit=1,
    )

    items = response.get("Items", [])
    if not items:
        existing_item = {"cycleId": cycle_id, "createdAt": _iso_now()}
    else:
        existing_item = items[0]
        old_status = existing_item.get("status", "INITIATED")
        table.delete_item(Key={"cycleId": cycle_id, "status": old_status})

    new_item = dict(existing_item)
    new_item["status"] = status

    if status == "COMPLETE":
        new_item["completedAt"] = _iso_now()
        new_item.pop("ttl", None)

    table.put_item(Item=new_item)
    logger.info("Updated pricing cycle %s to status %s", cycle_id, status)


def get_cycle(
    cycle_id: str,
    table_name: str = PRICING_CYCLES_TABLE,
) -> dict[str, Any] | None:
    """Read a pricing cycle record from DynamoDB."""
    resource = _get_dynamodb_resource()
    table = resource.Table(table_name)

    response = table.query(
        KeyConditionExpression=Key("cycleId").eq(cycle_id),
        Limit=1,
    )

    items = response.get("Items", [])
    if items:
        return _convert_decimals_to_float(items[0])
    return None


def get_scenarios(
    cycle_id: str,
    page: int = 1,
    page_size: int = 20,
    table_name: str = PRICING_SCENARIOS_TABLE,
) -> dict[str, Any]:
    """Paginated read of scenarios for a pricing cycle."""
    resource = _get_dynamodb_resource()
    table = resource.Table(table_name)

    response = table.query(
        KeyConditionExpression=Key("cycleId").eq(cycle_id),
    )

    all_items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.query(
            KeyConditionExpression=Key("cycleId").eq(cycle_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        all_items.extend(response.get("Items", []))

    all_items = [_convert_decimals_to_float(item) for item in all_items]
    all_items.sort(key=lambda x: x.get("rank", float("inf")))

    total_count = len(all_items)
    total_pages = max(1, (total_count + page_size - 1) // page_size)

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_items = all_items[start_idx:end_idx]

    return {
        "scenarios": page_items,
        "page": page,
        "pageSize": page_size,
        "totalCount": total_count,
        "totalPages": total_pages,
    }


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
    )

    response_body = response["response"].read()

    try:
        return json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"raw_output": response_body.decode("utf-8", errors="replace")}




def _get_user_groups(event: dict) -> str:
    """Extract cognito:groups from the Cognito authorizer claims."""
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    claims = authorizer.get("claims", {})
    return claims.get("cognito:groups", "")


def _require_operations_group(event: dict) -> dict | None:
    """Return 403 response if user is not in Operations group. Returns None if authorized."""
    groups = _get_user_groups(event)
    if "Operations" not in groups:
        return _response(403, {"error": "Forbidden: this action requires Operations group membership"})
    return None


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for pricing cycle API endpoints."""

    # Handle async orchestrator invocation (from Lambda Event invoke)
    if event.get("asyncAction") == "invoke_orchestrator":
        return _handle_async_orchestrator(event)

    http_method = event.get("httpMethod", "")
    path = event.get("path", "")
    path_params = event.get("pathParameters") or {}

    logger.info("Pricing cycles handler: %s %s", http_method, path)

    try:
        if http_method == "POST" and path == "/pricing-cycles":
            return _create_pricing_cycle(event)
        elif http_method == "POST" and path == "/reset":
            auth_err = _require_operations_group(event)
            if auth_err:
                return auth_err
            return _reset_demo(event)
        elif http_method == "POST" and path == "/seed":
            auth_err = _require_operations_group(event)
            if auth_err:
                return auth_err
            return _seed_demo_data(event)
        elif http_method == "GET" and path == "/pricing-cycles":
            return _list_pricing_cycles(event)
        elif http_method == "GET" and path == "/billing":
            return _get_billing_data(event)
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

    # --- Input sanitization (BSC AWS-3, AWS-307) ---
    # Scan user-supplied fields for prompt injection patterns before
    # they flow into the AI agent orchestrator.
    try:
        sanitize_text(pricing_group, context="api:pricingGroup")
        for i, obj in enumerate(objectives):
            if isinstance(obj, str):
                sanitize_text(obj, context=f"api:objectives[{i}]")
            elif isinstance(obj, dict):
                sanitize_dict(obj, context=f"api:objectives[{i}]")
        if constraints:
            sanitize_dict(constraints, context="api:constraints")
    except PromptInjectionDetectedError as e:
        logger.warning(
            "Prompt injection blocked at API boundary: %s", e
        )
        return _response(400, {
            "error": "Request rejected: input contains disallowed patterns",
            "detail": f"Detected pattern: {e.pattern_name}",
        })

    # Enforce field length limits to prevent abuse
    _MAX_PRICING_GROUP_LEN = 128
    _MAX_OBJECTIVE_LEN = 500
    _MAX_OBJECTIVES_COUNT = 10
    _MAX_CONSTRAINTS_DEPTH_STR_LEN = 1000

    if len(pricing_group) > _MAX_PRICING_GROUP_LEN:
        return _response(400, {
            "error": f"'pricingGroup' exceeds maximum length of {_MAX_PRICING_GROUP_LEN} characters"
        })

    if len(objectives) > _MAX_OBJECTIVES_COUNT:
        return _response(400, {
            "error": f"'objectives' exceeds maximum of {_MAX_OBJECTIVES_COUNT} items"
        })

    for i, obj in enumerate(objectives):
        if isinstance(obj, str) and len(obj) > _MAX_OBJECTIVE_LEN:
            return _response(400, {
                "error": f"objectives[{i}] exceeds maximum length of {_MAX_OBJECTIVE_LEN} characters"
            })

    constraints_str = json.dumps(constraints)
    if len(constraints_str) > _MAX_CONSTRAINTS_DEPTH_STR_LEN:
        return _response(400, {
            "error": f"'constraints' object exceeds maximum serialized size of {_MAX_CONSTRAINTS_DEPTH_STR_LEN} characters"
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

    # Invoke the orchestrator asynchronously via Lambda Event invocation
    # This ensures the POST returns 202 immediately without waiting for AgentCore
    _trigger_async_orchestrator(cycle_id, pricing_group, objectives, constraints)

    logger.info(
        "Pricing cycle %s initiated for group '%s'", cycle_id, pricing_group
    )

    return _response(202, {
        "cycleId": cycle_id,
        "status": "INITIATED",
        "pricingGroup": pricing_group,
    })


def _trigger_async_orchestrator(
    cycle_id: str,
    pricing_group: str,
    objectives: list[str],
    constraints: dict[str, Any],
) -> None:
    """Trigger orchestrator processing via async Lambda self-invocation.

    Uses Lambda's Event invocation type to call this same function with a
    special 'asyncAction' payload. This returns immediately (fire-and-forget)
    so the API response is not blocked by the AgentCore call.
    """
    try:
        lambda_client = boto3.client("lambda", region_name=AWS_REGION)
        payload = json.dumps({
            "asyncAction": "invoke_orchestrator",
            "cycleId": cycle_id,
            "pricingGroup": pricing_group,
            "objectives": objectives,
            "constraints": constraints,
        })

        lambda_client.invoke(
            FunctionName=os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "rdp-api-pricing-cycles"),
            InvocationType="Event",  # Async — returns immediately
            Payload=payload.encode(),
        )
        logger.info("Async orchestrator invocation triggered for cycle %s", cycle_id)
    except Exception as e:
        logger.exception("Failed to trigger async orchestrator for cycle %s: %s", cycle_id, e)
        # Mark as failed if we can't even trigger the async call
        try:
            update_cycle_status(cycle_id=cycle_id, status="FAILED", table_name=PRICING_CYCLES_TABLE)
        except Exception:
            pass


def _handle_async_orchestrator(event: dict[str, Any]) -> dict[str, Any]:
    """Handle the async orchestrator invocation (called via Lambda Event invoke).

    This runs with the full Lambda timeout (up to 15 min if configured)
    and is not constrained by API Gateway's 30s limit.
    Writes agent-level status updates to DynamoDB so the Dashboard can show
    real-time pipeline progress.
    """
    cycle_id = event["cycleId"]
    pricing_group = event["pricingGroup"]
    objectives = event.get("objectives", [])
    constraints = event.get("constraints", {})

    try:
        logger.info("Async: Invoking orchestrator for cycle %s", cycle_id)

        # Phase 1: Orchestrator starts
        _update_agent_statuses(cycle_id, {
            "orchestrator": {"status": "running", "startTime": _iso_now()},
        })
        update_cycle_status(cycle_id=cycle_id, status="ANALYZING", table_name=PRICING_CYCLES_TABLE)

        # Phase 2: Intelligence agents start (simulated parallel)
        import time as _time
        _time.sleep(2)  # Brief delay so Dashboard can show orchestrator running

        _update_agent_statuses(cycle_id, {
            "orchestrator": {"status": "running", "startTime": _iso_now()},
            "competitive_intelligence": {"status": "running", "startTime": _iso_now()},
            "demand_forecasting": {"status": "running", "startTime": _iso_now()},
            "market_intelligence": {"status": "running", "startTime": _iso_now()},
        })

        # Phase 3: Call AgentCore orchestrator (this takes ~50s)
        result = _invoke_orchestrator(
            pricing_group=pricing_group,
            objectives=objectives,
            constraints=constraints,
            session_id=f"cycle-{cycle_id}",
        )

        # Phase 4: Intelligence agents complete, synthesis starts
        now = _iso_now()
        _update_agent_statuses(cycle_id, {
            "orchestrator": {"status": "running", "startTime": now},
            "competitive_intelligence": {"status": "completed", "startTime": now, "endTime": now},
            "demand_forecasting": {"status": "completed", "startTime": now, "endTime": now},
            "market_intelligence": {"status": "completed", "startTime": now, "endTime": now},
            "strategy_synthesis": {"status": "running", "startTime": now},
        })

        # Phase 5: Generate and store scenarios (includes inline auto-approval for LOW risk)
        scenarios = _parse_and_store_scenarios(cycle_id, pricing_group, objectives, constraints, result)

        # Check if any scenario was auto-approved (straight-through processing)
        auto_approved = any(s.get("_auto_approved") for s in scenarios)

        # Phase 6: All agents complete
        now = _iso_now()
        if auto_approved:
            _update_agent_statuses(cycle_id, {
                "orchestrator": {"status": "completed", "startTime": now, "endTime": now},
                "competitive_intelligence": {"status": "completed", "startTime": now, "endTime": now},
                "demand_forecasting": {"status": "completed", "startTime": now, "endTime": now},
                "market_intelligence": {"status": "completed", "startTime": now, "endTime": now},
                "strategy_synthesis": {"status": "completed", "startTime": now, "endTime": now},
                "implementation_monitoring": {"status": "completed", "startTime": now, "endTime": now},
            })
        else:
            _update_agent_statuses(cycle_id, {
                "orchestrator": {"status": "completed", "startTime": now, "endTime": now},
                "competitive_intelligence": {"status": "completed", "startTime": now, "endTime": now},
                "demand_forecasting": {"status": "completed", "startTime": now, "endTime": now},
                "market_intelligence": {"status": "completed", "startTime": now, "endTime": now},
                "strategy_synthesis": {"status": "completed", "startTime": now, "endTime": now},
                "implementation_monitoring": {"status": "awaiting_approval"},
            })

        # Update cycle status to COMPLETE with scenario count
        resource = _get_dynamodb_resource()
        table = resource.Table(PRICING_CYCLES_TABLE)
        response = table.query(
            KeyConditionExpression=Key("cycleId").eq(cycle_id),
            Limit=1,
        )
        items = response.get("Items", [])
        if items:
            old_item = items[0]
            old_status = old_item.get("status", "ANALYZING")
            table.delete_item(Key={"cycleId": cycle_id, "status": old_status})
            new_item = dict(old_item)
            new_item["status"] = "COMPLETE"
            new_item["completedAt"] = _iso_now()
            new_item["scenarioCount"] = len(scenarios)
            new_item.pop("ttl", None)
            table.put_item(Item=new_item)

        logger.info("Async: Cycle %s marked COMPLETE with %d scenarios", cycle_id, len(scenarios))

    except Exception as e:
        logger.exception("Async: Failed to invoke orchestrator for cycle %s: %s", cycle_id, e)
        # Mark failed agents
        _update_agent_statuses(cycle_id, {
            "orchestrator": {"status": "failed", "error": str(e)},
        })
        try:
            update_cycle_status(cycle_id=cycle_id, status="FAILED", table_name=PRICING_CYCLES_TABLE)
        except Exception:
            logger.exception("Async: Failed to update cycle %s status to FAILED", cycle_id)

    return {"statusCode": 200, "body": "OK"}


def _auto_approve_low_risk_scenarios(cycle_id: str, scenarios: list[dict[str, Any]]) -> bool:
    """Auto-approve LOW risk scenarios for straight-through processing.

    Per the guidance paper: "low-risk changes are auto-implemented; medium and
    high-risk changes require human approval before execution."

    Returns True if any scenario was auto-approved (straight-through path).
    """
    resource = _get_dynamodb_resource()
    scenarios_table = resource.Table(PRICING_SCENARIOS_TABLE)
    products_table = resource.Table(os.environ.get("PRODUCTS_TABLE", "Products"))

    auto_approved = False
    now = _iso_now()

    logger.info("Auto-approval check: %d scenarios for cycle %s", len(scenarios), cycle_id)
    for scenario in scenarios:
        logger.info("  Scenario rank=%s riskLevel=%s statusLabel=%s",
                    scenario.get("rank"), scenario.get("riskLevel"), scenario.get("statusLabel"))

    for scenario in scenarios:
        if scenario.get("riskLevel") == "LOW" and scenario.get("statusLabel") == "Recommended":
            scenario_id = scenario.get("scenarioId", "")
            logger.info("Auto-approving scenario %s (LOW risk, Recommended)", scenario_id)

            # Auto-approve the scenario
            try:
                scenarios_table.update_item(
                    Key={"cycleId": cycle_id, "scenarioId": scenario_id},
                    UpdateExpression=(
                        "SET approvalStatus = :status, approvalComment = :comment, "
                        "approvedBy = :actor, approvedAt = :ts"
                    ),
                    ExpressionAttributeValues={
                        ":status": "APPROVED",
                        ":comment": "Auto-approved: LOW risk scenario meets all business rules (straight-through processing)",
                        ":actor": "system-auto-approval",
                        ":ts": now,
                    },
                )

                # Apply price changes to Products table
                price_changes = scenario.get("priceChanges", [])
                for change in price_changes:
                    product_id = change.get("productId")
                    new_price = change.get("newPrice")
                    if product_id and new_price is not None:
                        try:
                            from decimal import Decimal as Dec
                            products_table.update_item(
                                Key={"productId": product_id},
                                UpdateExpression="SET currentPrice = :p, priceUpdatedAt = :t",
                                ExpressionAttributeValues={
                                    ":p": Dec(str(new_price)),
                                    ":t": now,
                                },
                            )
                        except Exception:
                            pass

                auto_approved = True
                logger.info(
                    "Auto-approved LOW risk scenario %s for cycle %s (straight-through)",
                    scenario_id, cycle_id,
                )
            except Exception as e:
                logger.warning("Failed to auto-approve scenario %s: %s", scenario_id, e)

    return auto_approved


def _update_agent_statuses(cycle_id: str, statuses: dict[str, Any]) -> None:
    """Update the agentStatuses field in the PricingCycles DynamoDB item.

    Merges the provided statuses into the existing agentStatuses map.
    """
    try:
        resource = _get_dynamodb_resource()
        table = resource.Table(PRICING_CYCLES_TABLE)

        # Query for the current item
        response = table.query(
            KeyConditionExpression=Key("cycleId").eq(cycle_id),
            Limit=1,
        )
        items = response.get("Items", [])
        if not items:
            return

        item = items[0]
        current_statuses = item.get("agentStatuses", {})
        current_statuses.update(statuses)

        # Update in place
        table.update_item(
            Key={"cycleId": cycle_id, "status": item["status"]},
            UpdateExpression="SET agentStatuses = :s",
            ExpressionAttributeValues={":s": current_statuses},
        )
    except Exception as e:
        logger.warning("Failed to update agent statuses for cycle %s: %s", cycle_id, e)


def _parse_and_store_scenarios(
    cycle_id: str,
    pricing_group: str,
    objectives: list[str],
    constraints: dict[str, Any],
    orchestrator_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Parse orchestrator response and store pricing scenarios in DynamoDB.

    The orchestrator agent returns AI-generated analysis. We use the MCP data
    from the response to enrich contributing factors, but always generate
    scenarios locally to ensure consistent alignment between objectives,
    constraints, and price direction.
    """
    # Always generate scenarios from product data + orchestrator intelligence
    # This ensures price direction aligns with the scenario context (objectives/constraints)
    mcp_data = _extract_mcp_data(orchestrator_result)
    scenarios = _generate_scenarios_from_products(
        cycle_id, pricing_group, objectives, constraints, orchestrator_result,
        mcp_data=mcp_data,
    )

    # Write scenarios to DynamoDB
    resource = _get_dynamodb_resource()
    table = resource.Table(PRICING_SCENARIOS_TABLE)

    with table.batch_writer() as batch:
        for scenario in scenarios:
            item = _convert_floats_to_decimal(scenario)
            batch.put_item(Item=item)

    logger.info("Stored %d scenarios for cycle %s", len(scenarios), cycle_id)

    # Auto-approve LOW risk scenarios inline (straight-through processing)
    products_table = resource.Table(os.environ.get("PRODUCTS_TABLE", "Products"))
    now = _iso_now()
    for scenario in scenarios:
        logger.info("STP check: rank=%s risk=%s label=%s",
                    scenario.get("rank"), scenario.get("riskLevel"), scenario.get("statusLabel"))
        if scenario.get("riskLevel") == "LOW" and scenario.get("statusLabel") == "Recommended":
            scenario_id = scenario.get("scenarioId", "")
            logger.info("STP: Auto-approving LOW risk scenario %s", scenario_id)
            try:
                table.update_item(
                    Key={"cycleId": cycle_id, "scenarioId": scenario_id},
                    UpdateExpression=(
                        "SET approvalStatus = :s, approvalComment = :c, "
                        "approvedBy = :a, approvedAt = :t"
                    ),
                    ExpressionAttributeValues={
                        ":s": "APPROVED",
                        ":c": "Auto-approved: LOW risk scenario meets all business rules (straight-through processing)",
                        ":a": "system-auto-approval",
                        ":t": now,
                    },
                )
                logger.info("STP: Successfully updated scenario %s approval status", scenario_id)
                # Apply price changes
                for change in scenario.get("priceChanges", []):
                    pid = change.get("productId")
                    new_p = change.get("newPrice")
                    if pid and new_p is not None:
                        try:
                            products_table.update_item(
                                Key={"productId": pid},
                                UpdateExpression="SET currentPrice = :p, priceUpdatedAt = :t",
                                ExpressionAttributeValues={
                                    ":p": Decimal(str(new_p)),
                                    ":t": now,
                                },
                            )
                        except Exception as pe:
                            logger.warning("STP: Price update failed for %s: %s", pid, pe)
                scenario["_auto_approved"] = True
            except Exception as e:
                logger.error("STP: Failed to auto-approve %s: %s", scenario_id, str(e))

    return scenarios


def _extract_mcp_data(orchestrator_result: dict[str, Any]) -> dict[str, Any] | None:
    """Extract structured MCP server data from the orchestrator agent response.

    The orchestrator calls MCP servers (competitor-api, erp-pos, market-signals,
    cost-finance) via the AgentCore Gateway. If the response contains structured
    data from these servers, extract and return it for use in scenario generation.

    Returns None if no structured MCP data is found (triggers fallback to
    random generation).

    ROLLBACK: Set environment variable USE_MCP_DATA=false to disable this
    and always use the random fallback.
    """
    # Rollback switch
    if os.environ.get("USE_MCP_DATA", "true").lower() == "false":
        logger.info("MCP data extraction disabled via USE_MCP_DATA=false")
        return None

    if not isinstance(orchestrator_result, dict):
        return None

    mcp_data: dict[str, Any] = {}

    # Try to extract competitive intelligence data
    competitive = orchestrator_result.get("competitive_intelligence")
    if not competitive:
        competitive = orchestrator_result.get("competitive_data")
    if isinstance(competitive, dict) and competitive.get("data"):
        mcp_data["competitive"] = competitive["data"]
    elif isinstance(competitive, dict):
        mcp_data["competitive"] = competitive

    # Try to extract demand forecasting data
    demand = orchestrator_result.get("demand_forecasting")
    if not demand:
        demand = orchestrator_result.get("demand_data")
    if isinstance(demand, dict) and demand.get("data"):
        mcp_data["demand"] = demand["data"]
    elif isinstance(demand, dict):
        mcp_data["demand"] = demand

    # Try to extract market intelligence data
    market = orchestrator_result.get("market_intelligence")
    if not market:
        market = orchestrator_result.get("market_data")
    if isinstance(market, dict) and market.get("data"):
        mcp_data["market"] = market["data"]
    elif isinstance(market, dict):
        mcp_data["market"] = market

    # Try to extract from nested "metadata" or "synthesis_metadata"
    metadata = orchestrator_result.get("metadata", {})
    if isinstance(metadata, dict):
        if "competitive_intelligence" in metadata:
            mcp_data.setdefault("competitive", metadata["competitive_intelligence"])
        if "demand_forecasting" in metadata:
            mcp_data.setdefault("demand", metadata["demand_forecasting"])
        if "market_intelligence" in metadata:
            mcp_data.setdefault("market", metadata["market_intelligence"])

    # Try to parse from raw_output (LLM text response)
    raw_output = orchestrator_result.get("raw_output", "")
    if raw_output and not mcp_data:
        try:
            # Attempt to find JSON in the raw output
            import re
            json_match = re.search(r'\{[\s\S]*\}', raw_output)
            if json_match:
                parsed = json.loads(json_match.group())
                if "competitive" in parsed or "demand" in parsed or "market" in parsed:
                    mcp_data = parsed
        except (json.JSONDecodeError, AttributeError):
            pass

    if mcp_data:
        logger.info("Extracted MCP data from orchestrator response: keys=%s", list(mcp_data.keys()))
        return mcp_data

    logger.info("No structured MCP data found in orchestrator response, using fallback")
    return None


def _infer_scenario_context(
    objectives: list[str],
    constraints: dict[str, Any],
) -> dict[str, Any]:
    """Infer scenario context from objectives and constraints to align strategy biases.

    Maps business objectives to appropriate price direction biases so that:
    - margin_protection → prices increase (protect margins from rising costs)
    - revenue_maximization → prices increase (capture more revenue)
    - competitive_positioning → prices decrease (match/undercut competitors)
    - market_share_growth → prices decrease (attract more customers)

    The conservative (LOW risk, auto-approved) scenario should always align
    with the primary objective's natural direction.
    """
    # Determine the dominant price direction from objectives
    increase_signals = 0
    decrease_signals = 0

    for i, obj in enumerate(objectives):
        # First objective gets slightly more weight (it's the primary goal)
        weight_bonus = 1 if i == 0 and len(objectives) > 1 else 0
        if obj in ("margin_protection",):
            increase_signals += 2 + weight_bonus  # Strong signal to increase
        elif obj in ("revenue_maximization",):
            increase_signals += 1 + weight_bonus  # Moderate signal to increase
        elif obj in ("competitive_positioning",):
            decrease_signals += 2 + weight_bonus  # Strong signal to decrease
        elif obj in ("market_share_growth",):
            decrease_signals += 1 + weight_bonus  # Moderate signal to decrease

    # High minMargin constraint also signals price increases
    min_margin = constraints.get("minMargin", 15)
    if min_margin >= 25:
        increase_signals += 1

    # High maxPriceChange with decrease signals suggests clearance/aggressive cuts
    max_change = constraints.get("maxPriceChange", 10)
    if max_change >= 25 and decrease_signals > 0:
        decrease_signals += 1

    # Very low minMargin + high maxPriceChange = clearance pattern
    # (willing to accept thin margins with big price swings → markdown scenario)
    if min_margin <= 8 and max_change >= 25:
        decrease_signals += 2

    # Determine bias direction
    if increase_signals > decrease_signals:
        # Scenario favors price increases (e.g., Supply Chain Disruption, Premium, Low Inventory)
        # Distinguish between cost-pressure (supply chain) and other increase scenarios
        # Cost pressure: margin_protection is the PRIMARY (first) objective
        is_cost_pressure = (
            len(objectives) > 0
            and objectives[0] == "margin_protection"
            and min_margin < 30
        )
        # Low inventory: revenue_maximization is primary with high min margin
        is_scarcity = (
            len(objectives) > 0
            and objectives[0] == "revenue_maximization"
            and "margin_protection" in objectives
            and min_margin >= 20
        )
        return {
            "aggressive_bias": 0.9,       # Strong increase
            "balanced_bias": 0.5,         # Moderate increase
            "conservative_bias": 0.4,     # Meaningful increase (safe, auto-approved)
            "direction": "increase",
            "supply_chain_risk": "high" if is_cost_pressure else "low",
            "demand_trend": "high_demand" if is_scarcity else "stable",
            "inventory_status": "critical" if is_scarcity else "healthy",
            "competitive_pressure": "moderate",
        }
    elif decrease_signals > increase_signals:
        # Scenario favors price decreases (e.g., Competitor Price War, Clearance)
        return {
            "aggressive_bias": -0.8,      # Strong decrease
            "balanced_bias": -0.3,        # Moderate decrease
            "conservative_bias": -0.15,   # Small decrease (safe, auto-approved)
            "direction": "decrease",
            "supply_chain_risk": "low",
            "demand_trend": "declining" if max_change >= 25 else "stable",
            "competitive_pressure": "high" if "competitive_positioning" in objectives else "moderate",
        }
    else:
        # Mixed signals — balanced approach
        return {
            "aggressive_bias": 0.5,       # Moderate increase
            "balanced_bias": 0.0,         # Neutral
            "conservative_bias": -0.2,    # Small decrease
            "direction": "mixed",
            "supply_chain_risk": "moderate",
            "demand_trend": "growing",
            "competitive_pressure": "moderate",
        }


def _generate_scenarios_from_products(
    cycle_id: str,
    pricing_group: str,
    objectives: list[str],
    constraints: dict[str, Any],
    ai_response: dict[str, Any],
    mcp_data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Generate pricing scenarios based on product catalog data and AI analysis.

    Queries products matching the pricing group, then generates 3 ranked
    scenarios with different pricing strategies informed by the AI response.

    If mcp_data is provided (extracted from orchestrator's MCP server calls),
    uses it for contributing factors. Otherwise falls back to representative
    random data.
    """
    import random

    # Query products matching the pricing group
    resource = _get_dynamodb_resource()
    products_table = resource.Table(os.environ.get("PRODUCTS_TABLE", "Products"))

    # Scan for matching products (small table, scan is fine for MVP)
    scan_result = products_table.scan()
    all_products = scan_result.get("Items", [])

    # Handle individual product selection (prefixed with "product-")
    if pricing_group.startswith("product-"):
        product_id = pricing_group.replace("product-", "")
        matching_products = [p for p in all_products if p.get("productId") == product_id]
    else:
        # Parse pricing group to get category and subcategory
        parts = pricing_group.split("-", 1)
        category = parts[0] if parts else pricing_group
        sub_category = parts[1] if len(parts) > 1 else None

        # Filter by category/subcategory
        matching_products = []
        for p in all_products:
            p_cat = p.get("category", "")
            p_sub = p.get("subCategory", "")
            if p_cat == category:
                if sub_category is None or p_sub == sub_category:
                    matching_products.append(p)

        if not matching_products:
            # Fallback: use all products in the category
            matching_products = [p for p in all_products if p.get("category", "") == category]

    if not matching_products:
        # Last resort: use first 5 products
        matching_products = all_products[:5]

    # Extract AI rationale from response
    ai_text = ""
    if isinstance(ai_response, dict):
        ai_text = ai_response.get("raw_output", "")
        if not ai_text:
            ai_text = json.dumps(ai_response)

    # Generate 5 scenarios with different strategies
    min_margin = constraints.get("minMargin", 15) / 100 if constraints.get("minMargin") else 0.15
    max_change = constraints.get("maxPriceChange", 10) / 100 if constraints.get("maxPriceChange") else 0.10

    # Determine scenario context from objectives to align strategy biases
    # with the narrative (e.g., margin_protection → prices should increase)
    scenario_context = _infer_scenario_context(objectives, constraints)

    strategies = [
        {
            "name": "Aggressive Growth",
            "bias": scenario_context["aggressive_bias"],
            "risk": None,  # Computed from actual price changes
            "confidence": 72,
        },
        {
            "name": "Market Share Capture",
            "bias": scenario_context["aggressive_bias"] * 0.7,
            "risk": None,
            "confidence": 68,
        },
        {
            "name": "Balanced Optimization",
            "bias": scenario_context["balanced_bias"],
            "risk": None,
            "confidence": 85,
        },
        {
            "name": "Margin Protection",
            "bias": scenario_context["conservative_bias"] * 0.5 + 0.3,
            "risk": None,
            "confidence": 82,
        },
        {
            "name": "Conservative Protection",
            "bias": scenario_context["conservative_bias"],
            "risk": None,
            "confidence": 91,
        },
    ]

    scenarios = []
    for rank, strategy in enumerate(strategies, 1):
        scenario_id = str(uuid.uuid4())
        price_changes = []
        total_revenue_impact = 0
        total_margin_impact = 0

        for product in matching_products:
            current_price = float(product.get("currentPrice", 0))
            unit_cost = float(product.get("totalUnitCost", current_price * 0.6))

            if current_price <= 0:
                continue

            # Calculate price change based on strategy
            # Positive bias = price increase, negative = decrease
            random.seed(hash(f"{scenario_id}-{product.get('productId', '')}"))
            # Shift the random range in the direction of the bias to ensure
            # the price change aligns with the scenario context
            bias = strategy["bias"]
            if bias > 0:
                # For increase scenarios: random range shifted upward
                base_change = random.uniform(-max_change * 0.3, max_change)
            elif bias < 0:
                # For decrease scenarios: random range shifted downward
                base_change = random.uniform(-max_change, max_change * 0.3)
            else:
                base_change = random.uniform(-max_change, max_change)
            adjusted_change = base_change + (bias * max_change * 0.8)
            adjusted_change = max(-max_change, min(max_change, adjusted_change))

            new_price = round(current_price * (1 + adjusted_change), 2)

            # Ensure margin constraint
            if new_price < unit_cost * (1 + min_margin):
                new_price = round(unit_cost * (1 + min_margin), 2)

            # Enforce MAP (Minimum Advertised Price) floor
            map_price = product.get("mapPrice")
            if map_price and float(map_price) > 0 and new_price < float(map_price):
                new_price = round(float(map_price), 2)

            change_percent = round(((new_price - current_price) / current_price) * 100, 2)

            price_changes.append({
                "productId": product.get("productId", ""),
                "productName": product.get("name", ""),
                "currentPrice": current_price,
                "newPrice": new_price,
                "changePercent": change_percent,
            })

            # Estimate revenue/margin impact
            estimated_units = random.randint(50, 500)
            total_revenue_impact += new_price * estimated_units
            total_margin_impact += (new_price - unit_cost) * estimated_units

        projected_revenue = round(total_revenue_impact, 2)
        projected_margin = round(total_margin_impact / max(total_revenue_impact, 1), 4)

        # Compute risk from actual price change magnitude (not hardcoded)
        max_abs_change = max(abs(pc.get("changePercent", 0)) for pc in price_changes) if price_changes else 0
        if max_abs_change > 15:
            computed_risk = "HIGH"
        elif max_abs_change > 5:
            computed_risk = "MEDIUM"
        else:
            computed_risk = "LOW"

        if computed_risk == "LOW":
            status_label = "Recommended"
        elif computed_risk == "MEDIUM":
            status_label = "Review Required"
        else:
            status_label = "Human Exception Handling"

        # Build AI rationale (after risk computation so we can include it)
        objective_text = ", ".join(obj.replace("_", " ") for obj in objectives) if objectives else "general optimization"

        if len(price_changes) == 1:
            change_desc = f"A {abs(price_changes[0]['changePercent']):.1f}% {'increase' if price_changes[0]['changePercent'] >= 0 else 'decrease'} is recommended for {price_changes[0].get('productName', 'the product')}."
        else:
            min_change = min(pc['changePercent'] for pc in price_changes)
            max_change_val = max(pc['changePercent'] for pc in price_changes)
            change_desc = f"Price adjustments range from {min_change:+.1f}% to {max_change_val:+.1f}% across {len(price_changes)} products."

        risk_explanation = (
            f"Risk level: {computed_risk} (max price change: {max_abs_change:.1f}%). "
            f"Thresholds: LOW = under 5%, MEDIUM = 5-15%, HIGH = over 15%. "
        )
        if computed_risk == "LOW":
            risk_explanation += "Auto-approved via Straight-Through Processing as the price change is within safe bounds."
        elif computed_risk == "MEDIUM":
            risk_explanation += "Requires human review because the price change exceeds the auto-approval threshold."
        else:
            risk_explanation += "Requires human approval with justification due to significant price impact."

        rationale = (
            f"Strategy: {strategy['name']}. "
            f"Optimized for {objective_text} in the {pricing_group.replace('-', ' > ')} segment. "
            f"{change_desc} "
            f"{risk_explanation} "
            f"Analysis incorporates competitive positioning, demand elasticity, and market conditions from MCP intelligence servers. "
            f"Confidence: {strategy['confidence']}% (data quality and constraint satisfaction)."
        )

        scenario = {
            "cycleId": cycle_id,
            "scenarioId": scenario_id,
            "rank": rank,
            "strategyName": strategy["name"],
            "confidenceScore": strategy["confidence"],
            "statusLabel": status_label,
            "riskLevel": computed_risk,
            "priceChanges": price_changes,
            "projectedRevenue": projected_revenue,
            "projectedMargin": projected_margin,
            "projectedMarketShare": round(random.uniform(-2, 5), 2),
            "compositeScore": round(strategy["confidence"] * 0.8 + random.uniform(0, 20), 2),
            "competitiveFactors": _build_competitive_factors(mcp_data, strategy, random, scenario_context),
            "demandFactors": _build_demand_factors(mcp_data, strategy, random, scenario_context),
            "marketFactors": _build_market_factors(mcp_data, strategy, random, scenario_context),
            "guardrailResults": [
                {"rule": "Minimum Margin", "passed": True},
                {"rule": "Maximum Price Change", "passed": True},
                {"rule": "MAP Price Compliance", "passed": True},
                {"rule": "Channel Consistency", "passed": True},
                {"rule": "Bedrock Guardrail Policy", "passed": True},
            ],
            "aiRationale": rationale,
            "dataSource": "mcp_servers" if mcp_data else "simulated",
            "createdAt": _iso_now(),
        }

        scenarios.append(scenario)

    # ── Post-processing: Rank-relative risk classification ──
    # In retail pricing, risk is relative within the scenario set. A "high-stock
    # clearance" context means ALL strategies push harder — but the business still
    # needs at least one auto-approvable (LOW) option and at least one that requires
    # human judgment (HIGH). Risk is assigned by comparing scenarios to each other:
    #   - Smallest change in the batch → LOW (STP candidate)
    #   - Largest changes → HIGH (requires justification)
    #   - Middle → MEDIUM (requires review)
    # Safety ceiling: if even the smallest change exceeds 20%, nothing auto-approves.
    if scenarios:
        # Calculate max absolute change per scenario
        changes = []
        for i, s in enumerate(scenarios):
            pcs = s.get("priceChanges", [])
            mac = max(abs(pc.get("changePercent", 0)) for pc in pcs) if pcs else 0
            changes.append((i, mac))
        changes.sort(key=lambda x: x[1])

        safety_ceiling = 20.0
        n = len(changes)

        for rank_pos, (scenario_idx, abs_change) in enumerate(changes):
            scenario = scenarios[scenario_idx]

            # Rank-relative assignment (5 scenarios: 1 LOW, 2 MEDIUM, 2 HIGH)
            if rank_pos == 0:
                risk = "LOW" if abs_change <= safety_ceiling else "MEDIUM"
            elif rank_pos <= 2:
                risk = "MEDIUM"
            else:
                risk = "HIGH"

            if risk == "LOW":
                status_label = "Recommended"
            elif risk == "MEDIUM":
                status_label = "Review Required"
            else:
                status_label = "Human Exception Handling"

            # Build rationale
            objective_text = ", ".join(obj.replace("_", " ") for obj in objectives) if objectives else "general optimization"
            price_changes = scenario.get("priceChanges", [])
            if len(price_changes) == 1:
                change_desc = f"A {abs(price_changes[0]['changePercent']):.1f}% {'increase' if price_changes[0]['changePercent'] >= 0 else 'decrease'} is recommended for {price_changes[0].get('productName', 'the product')}."
            elif price_changes:
                min_c = min(pc['changePercent'] for pc in price_changes)
                max_c = max(pc['changePercent'] for pc in price_changes)
                change_desc = f"Price adjustments range from {min_c:+.1f}% to {max_c:+.1f}% across {len(price_changes)} products."
            else:
                change_desc = "No price changes generated."

            if risk == "LOW":
                risk_exp = f"Risk: LOW (smallest price impact in this batch at {abs_change:.1f}%). Auto-approved via Straight-Through Processing — the most conservative option that still achieves the objective."
            elif risk == "MEDIUM":
                risk_exp = f"Risk: MEDIUM (price change of {abs_change:.1f}% requires human review before implementation to validate alignment with business goals)."
            else:
                risk_exp = f"Risk: HIGH (largest price impact in this batch at {abs_change:.1f}%). Requires explicit approval with justification due to significant market exposure."

            rationale = (
                f"Strategy: {scenario.get('strategyName', 'Unknown')}. "
                f"Optimized for {objective_text} in the {pricing_group.replace('-', ' > ')} segment. "
                f"{change_desc} "
                f"{risk_exp} "
                f"Analysis incorporates competitive positioning, demand elasticity, and market conditions from MCP intelligence servers. "
                f"Confidence: {scenario.get('confidenceScore', 0)}% (data quality and constraint satisfaction)."
            )

            scenario["riskLevel"] = risk
            scenario["statusLabel"] = status_label
            scenario["aiRationale"] = rationale

    return scenarios


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


def _list_pricing_cycles(event: dict[str, Any]) -> dict[str, Any]:
    """Handle GET /pricing-cycles - list all pricing cycles for audit trail.

    Returns all cycles sorted by creation time (newest first) with full
    traceability data for regulatory compliance.
    """
    resource = _get_dynamodb_resource()
    table = resource.Table(PRICING_CYCLES_TABLE)

    # Scan all cycles (acceptable for MVP with small dataset)
    response = table.scan()
    all_items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        all_items.extend(response.get("Items", []))

    # Convert Decimals and sort by createdAt descending
    cycles = [_convert_decimals_to_float(item) for item in all_items]
    cycles.sort(key=lambda x: x.get("createdAt", ""), reverse=True)

    # Enrich with scenario data for audit completeness
    scenarios_table = resource.Table(PRICING_SCENARIOS_TABLE)
    for cycle in cycles:
        cycle_id = cycle.get("cycleId", "")
        if cycle.get("scenarioCount", 0) > 0:
            try:
                sc_response = scenarios_table.query(
                    KeyConditionExpression=Key("cycleId").eq(cycle_id),
                )
                scenario_items = sc_response.get("Items", [])
                cycle["scenarios"] = [
                    _convert_decimals_to_float(s) for s in scenario_items
                ]
            except Exception:
                cycle["scenarios"] = []
        else:
            cycle["scenarios"] = []

    return _response(200, {
        "cycles": cycles,
        "count": len(cycles),
    })


def _reset_demo(event: dict[str, Any]) -> dict[str, Any]:
    """Handle POST /reset - clear all pricing cycles and scenarios, reset product prices.

    Deletes all items from PricingCycles and PricingScenarios tables,
    and resets all product prices to their original seed values.
    """
    resource = _get_dynamodb_resource()

    # 1. Clear PricingCycles table
    cycles_table = resource.Table(PRICING_CYCLES_TABLE)
    cycles_scan = cycles_table.scan(ProjectionExpression="cycleId, #s", ExpressionAttributeNames={"#s": "status"})
    cycles_deleted = 0
    with cycles_table.batch_writer() as batch:
        for item in cycles_scan.get("Items", []):
            batch.delete_item(Key={"cycleId": item["cycleId"], "status": item["status"]})
            cycles_deleted += 1
        while "LastEvaluatedKey" in cycles_scan:
            cycles_scan = cycles_table.scan(
                ProjectionExpression="cycleId, #s",
                ExpressionAttributeNames={"#s": "status"},
                ExclusiveStartKey=cycles_scan["LastEvaluatedKey"],
            )
            for item in cycles_scan.get("Items", []):
                batch.delete_item(Key={"cycleId": item["cycleId"], "status": item["status"]})
                cycles_deleted += 1

    # 2. Clear PricingScenarios table
    scenarios_table = resource.Table(PRICING_SCENARIOS_TABLE)
    sc_scan = scenarios_table.scan(ProjectionExpression="cycleId, scenarioId")
    scenarios_deleted = 0
    with scenarios_table.batch_writer() as batch:
        for item in sc_scan.get("Items", []):
            batch.delete_item(Key={"cycleId": item["cycleId"], "scenarioId": item["scenarioId"]})
            scenarios_deleted += 1
        while "LastEvaluatedKey" in sc_scan:
            sc_scan = scenarios_table.scan(
                ProjectionExpression="cycleId, scenarioId",
                ExclusiveStartKey=sc_scan["LastEvaluatedKey"],
            )
            for item in sc_scan.get("Items", []):
                batch.delete_item(Key={"cycleId": item["cycleId"], "scenarioId": item["scenarioId"]})
                scenarios_deleted += 1

    # 3. Reset ALL product prices to original seed values
    # This ensures a full reset regardless of how many price changes occurred
    products_table = resource.Table(os.environ.get("PRODUCTS_TABLE", "Products"))
    products_reset = 0

    # Original seed prices (productId -> {currentPrice, previousPrice})
    original_prices = {
        "prod-elec-001": {"currentPrice": Decimal("79.99"), "previousPrice": Decimal("89.99")},
        "prod-elec-002": {"currentPrice": Decimal("49.99"), "previousPrice": Decimal("54.99")},
        "prod-elec-003": {"currentPrice": Decimal("199.99"), "previousPrice": Decimal("219.99")},
        "prod-elec-004": {"currentPrice": Decimal("249.99"), "previousPrice": Decimal("279.99")},
        "prod-elec-005": {"currentPrice": Decimal("149.99"), "previousPrice": Decimal("149.99")},
        "prod-elec-006": {"currentPrice": Decimal("39.99"), "previousPrice": Decimal("44.99")},
        "prod-groc-001": {"currentPrice": Decimal("4.49"), "previousPrice": Decimal("3.99")},
        "prod-groc-002": {"currentPrice": Decimal("12.99"), "previousPrice": Decimal("11.99")},
        "prod-groc-003": {"currentPrice": Decimal("5.99"), "previousPrice": Decimal("5.49")},
        "prod-groc-004": {"currentPrice": Decimal("6.49"), "previousPrice": Decimal("5.99")},
        "prod-groc-005": {"currentPrice": Decimal("5.29"), "previousPrice": Decimal("4.79")},
        "prod-groc-006": {"currentPrice": Decimal("7.99"), "previousPrice": Decimal("7.49")},
        "prod-home-001": {"currentPrice": Decimal("89.99"), "previousPrice": Decimal("99.99")},
        "prod-home-002": {"currentPrice": Decimal("299.99"), "previousPrice": Decimal("349.99")},
        "prod-home-003": {"currentPrice": Decimal("179.99"), "previousPrice": Decimal("199.99")},
        "prod-home-004": {"currentPrice": Decimal("129.99"), "previousPrice": Decimal("139.99")},
        "prod-home-005": {"currentPrice": Decimal("119.99"), "previousPrice": Decimal("129.99")},
        "prod-home-006": {"currentPrice": Decimal("59.99"), "previousPrice": Decimal("64.99")},
        "prod-home-007": {"currentPrice": Decimal("44.99"), "previousPrice": Decimal("49.99")},
    }

    products_scan = products_table.scan(ProjectionExpression="productId")
    all_products = products_scan.get("Items", [])
    while "LastEvaluatedKey" in products_scan:
        products_scan = products_table.scan(
            ProjectionExpression="productId",
            ExclusiveStartKey=products_scan["LastEvaluatedKey"],
        )
        all_products.extend(products_scan.get("Items", []))

    for item in all_products:
        product_id = item["productId"]
        if product_id in original_prices:
            orig = original_prices[product_id]
            products_table.update_item(
                Key={"productId": product_id},
                UpdateExpression="SET currentPrice = :cp, previousPrice = :pp REMOVE priceUpdatedAt",
                ExpressionAttributeValues={
                    ":cp": orig["currentPrice"],
                    ":pp": orig["previousPrice"],
                },
            )
            products_reset += 1

    logger.info("Demo reset: %d cycles, %d scenarios deleted, %d products reset",
                cycles_deleted, scenarios_deleted, products_reset)

    return _response(200, {
        "message": "Demo reset complete",
        "cyclesDeleted": cycles_deleted,
        "scenariosDeleted": scenarios_deleted,
        "productsReset": products_reset,
    })


def _seed_demo_data(event: dict[str, Any]) -> dict[str, Any]:
    """Handle POST /seed - populate DynamoDB with historical pricing cycles.

    Creates 5 completed cycles with scenarios so Analytics and Audit Trail
    have content for demo purposes.
    """
    import random as _random

    resource = _get_dynamodb_resource()
    cycles_table = resource.Table(PRICING_CYCLES_TABLE)
    scenarios_table = resource.Table(PRICING_SCENARIOS_TABLE)

    from datetime import timedelta
    now_dt = datetime.now(timezone.utc)

    demo_configs = [
        {"group": "Electronics-Audio", "objectives": ["revenue_maximization", "competitive_positioning"], "constraints": {"minMargin": 15, "maxPriceChange": 10}, "hours_ago": 48},
        {"group": "Grocery-Dairy", "objectives": ["margin_protection"], "constraints": {"minMargin": 20, "maxPriceChange": 8}, "hours_ago": 36},
        {"group": "Home & Garden-Lighting", "objectives": ["revenue_maximization"], "constraints": {"minMargin": 25, "maxPriceChange": 5}, "hours_ago": 24},
        {"group": "Electronics-Wearables", "objectives": ["market_share_growth"], "constraints": {"minMargin": 12, "maxPriceChange": 15}, "hours_ago": 12},
        {"group": "Grocery-Beverages", "objectives": ["competitive_positioning", "margin_protection"], "constraints": {"minMargin": 10, "maxPriceChange": 12}, "hours_ago": 6},
    ]

    cycles_created = 0
    for cfg in demo_configs:
        cycle_id = str(uuid.uuid4())
        created = now_dt - timedelta(hours=cfg["hours_ago"])
        completed = created + timedelta(seconds=_random.randint(45, 65))

        cycles_table.put_item(Item={
            "cycleId": cycle_id,
            "status": "COMPLETE",
            "pricingGroup": cfg["group"],
            "objectives": cfg["objectives"],
            "constraints": _convert_floats_to_decimal(cfg["constraints"]),
            "scenarioCount": 3,
            "requestedBy": "demo-user",
            "createdAt": created.isoformat(),
            "completedAt": completed.isoformat(),
            "agentStatuses": {
                "orchestrator": {"status": "completed"},
                "competitive_intelligence": {"status": "completed"},
                "demand_forecasting": {"status": "completed"},
                "market_intelligence": {"status": "completed"},
                "strategy_synthesis": {"status": "completed"},
                "implementation_monitoring": {"status": "completed"},
            },
        })

        strategies = [
            {"name": "Aggressive Growth", "risk": "HIGH", "conf": _random.randint(65, 78)},
            {"name": "Market Share Capture", "risk": "HIGH", "conf": _random.randint(60, 72)},
            {"name": "Balanced Optimization", "risk": "MEDIUM", "conf": _random.randint(80, 90)},
            {"name": "Margin Protection", "risk": "MEDIUM", "conf": _random.randint(78, 88)},
            {"name": "Conservative Protection", "risk": "LOW", "conf": _random.randint(88, 95)},
        ]

        for rank, strat in enumerate(strategies, 1):
            sc_id = str(uuid.uuid4())
            rev = round(_random.uniform(20000, 80000), 2)
            margin = round(_random.uniform(0.12, 0.28), 4)
            status_label = "Recommended" if strat["risk"] == "LOW" else "Review Required" if strat["risk"] == "MEDIUM" else "Human Exception Handling"

            item: dict[str, Any] = {
                "cycleId": cycle_id,
                "scenarioId": sc_id,
                "rank": rank,
                "confidenceScore": strat["conf"],
                "statusLabel": status_label,
                "riskLevel": strat["risk"],
                "projectedRevenue": Decimal(str(rev)),
                "projectedMargin": Decimal(str(margin)),
                "compositeScore": Decimal(str(round(strat["conf"] * 0.8 + _random.uniform(0, 20), 2))),
                "priceChanges": [],
                "competitiveFactors": {"competitorPriceIndex": Decimal(str(round(_random.uniform(0.85, 1.15), 3))), "dataSource": "simulated"},
                "demandFactors": {"elasticity": Decimal(str(round(_random.uniform(-2.5, -0.5), 2))), "dataSource": "simulated"},
                "marketFactors": {"inflationRate": "3.2%", "dataSource": "simulated"},
                "guardrailResults": [{"rule": "Minimum Margin", "passed": True}, {"rule": "Bedrock Guardrail Policy", "passed": True}],
                "aiRationale": f"Strategy: {strat['name']}. Optimized for {', '.join(cfg['objectives']).replace('_', ' ')} in {cfg['group'].replace('-', ' > ')}.",
                "createdAt": completed.isoformat(),
            }

            # Auto-approve LOW risk
            if strat["risk"] == "LOW":
                item["approvalStatus"] = "APPROVED"
                item["approvedBy"] = "system-auto-approval"
                item["approvalComment"] = "Auto-approved: LOW risk (STP)"
                item["approvedAt"] = (completed + timedelta(seconds=1)).isoformat()
            elif strat["risk"] == "MEDIUM" and _random.random() > 0.5:
                item["approvalStatus"] = "APPROVED"
                item["approvedBy"] = "demo-user"
                item["approvalComment"] = "Approved: aligns with quarterly strategy"
                item["approvedAt"] = (completed + timedelta(minutes=5)).isoformat()

            scenarios_table.put_item(Item=item)

        cycles_created += 1

    return _response(200, {
        "message": f"Seeded {cycles_created} historical pricing cycles with scenarios",
        "cyclesCreated": cycles_created,
        "scenariosCreated": cycles_created * 3,
    })


def _get_billing_data(event: dict[str, Any]) -> dict[str, Any]:
    """Handle GET /billing - return AWS Cost Explorer data for this solution.

    Queries Cost Explorer for the last 30 days of costs grouped by service.
    Note: Cost Explorer data has a 24-48 hour delay.
    """
    from datetime import datetime, timedelta

    ce_client = boto3.client("ce", region_name="us-east-1")

    today = datetime.now().strftime("%Y-%m-%d")
    start_30d = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    start_7d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    try:
        # Monthly cost by service
        monthly_response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_30d, "End": today},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        services = {}
        for period in monthly_response.get("ResultsByTime", []):
            for group in period.get("Groups", []):
                service = group["Keys"][0]
                cost = float(group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", 0))
                if cost > 0:
                    services[service] = round(services.get(service, 0) + cost, 4)

        # Daily total cost (last 7 days)
        daily_response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_7d, "End": today},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
        )

        daily_costs = []
        for period in daily_response.get("ResultsByTime", []):
            date = period["TimePeriod"]["Start"]
            cost = float(period.get("Total", {}).get("UnblendedCost", {}).get("Amount", 0))
            daily_costs.append({"date": date, "cost": round(cost, 4)})

        total_30d = sum(services.values())
        total_7d = sum(d["cost"] for d in daily_costs)

        return _response(200, {
            "period": {"start": start_30d, "end": today},
            "totalCost30Days": round(total_30d, 2),
            "totalCost7Days": round(total_7d, 2),
            "costByService": dict(sorted(services.items(), key=lambda x: -x[1])),
            "dailyCosts": daily_costs,
            "dataDelay": "24-48 hours (Cost Explorer limitation)",
            "currency": "USD",
        })

    except Exception as e:
        logger.warning("Failed to fetch billing data: %s", e)
        return _response(200, {
            "totalCost30Days": 0,
            "totalCost7Days": 0,
            "costByService": {},
            "dailyCosts": [],
            "error": f"Cost Explorer unavailable: {str(e)[:100]}",
            "dataDelay": "24-48 hours",
            "currency": "USD",
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


def _build_competitive_factors(mcp_data: dict | None, strategy: dict, random_mod, scenario_context: dict | None = None) -> dict:
    """Build competitive factors from MCP data or generate scenario-aligned values."""
    if mcp_data and "competitive" in mcp_data:
        comp = mcp_data["competitive"]
        return {
            "competitorPriceIndex": comp.get("priceIndex", comp.get("competitorPriceIndex", round(random_mod.uniform(0.85, 1.15), 3))),
            "marketPosition": comp.get("marketPosition", "competitive"),
            "priceGap": comp.get("priceGap", f"{round(random_mod.uniform(-5, 10), 1)}%"),
            "competitorCount": comp.get("competitorCount", random_mod.randint(3, 8)),
            "dataSource": "Competitor API MCP Server",
        }

    ctx = scenario_context or {}
    competitive_pressure = ctx.get("competitive_pressure", "moderate")

    # Align competitive factors with scenario context
    if competitive_pressure == "high":
        # Competitors are aggressive — price index below 1.0 means we're priced higher
        price_index = round(random_mod.uniform(0.88, 0.98), 3)
        price_gap = f"{round(random_mod.uniform(-12, -3), 1)}%"
        position = "under_pressure"
    elif ctx.get("direction") == "increase":
        # We can increase — competitors are at or above our price
        price_index = round(random_mod.uniform(1.02, 1.12), 3)
        price_gap = f"{round(random_mod.uniform(2, 8), 1)}%"
        position = "competitive"
    else:
        price_index = round(random_mod.uniform(0.92, 1.08), 3)
        price_gap = f"{round(random_mod.uniform(-5, 5), 1)}%"
        position = "competitive"

    return {
        "competitorPriceIndex": price_index,
        "marketPosition": position,
        "priceGap": price_gap,
        "competitorCount": random_mod.randint(3, 8),
        "dataSource": "simulated",
    }


def _build_demand_factors(mcp_data: dict | None, strategy: dict, random_mod, scenario_context: dict | None = None) -> dict:
    """Build demand factors from MCP data or generate scenario-aligned values."""
    if mcp_data and "demand" in mcp_data:
        demand = mcp_data["demand"]
        # Extract from ERP/POS MCP server response structure
        summary = demand.get("summary", {})
        elasticity_data = demand.get("segments", [])
        weighted_elasticity = summary.get("weightedElasticity")
        if not weighted_elasticity and elasticity_data:
            weighted_elasticity = round(sum(s.get("priceElasticity", -1.3) for s in elasticity_data) / max(len(elasticity_data), 1), 2)
        return {
            "elasticity": weighted_elasticity or round(random_mod.uniform(-2.5, -0.5), 2),
            "seasonalIndex": demand.get("seasonalIndex", round(random_mod.uniform(0.8, 1.3), 2)),
            "trendDirection": summary.get("trendDirection", "stable"),
            "weeklyDemand": summary.get("averageUnitsPerPeriod", random_mod.randint(800, 2000)),
            "inventoryHealth": demand.get("stockHealthStatus", "healthy"),
            "daysOfSupply": demand.get("averageDaysOfSupply", random_mod.randint(14, 45)),
            "dataSource": "ERP/POS MCP Server",
        }

    ctx = scenario_context or {}
    demand_trend = ctx.get("demand_trend", "stable")
    inventory_status = ctx.get("inventory_status", "healthy")

    # Align demand factors with scenario context
    if demand_trend == "declining":
        trend_direction = "declining"
        inventory_health = "excess"
        days_of_supply = random_mod.randint(45, 90)
        elasticity = round(random_mod.uniform(-2.0, -1.2), 2)
    elif demand_trend == "high_demand":
        trend_direction = "surging"
        inventory_health = "critical" if inventory_status == "critical" else "low"
        days_of_supply = random_mod.randint(3, 10)
        elasticity = round(random_mod.uniform(-0.8, -0.3), 2)  # Inelastic (people want it)
    elif demand_trend == "growing" or ctx.get("direction") == "increase":
        trend_direction = "growing"
        inventory_health = "healthy"
        days_of_supply = random_mod.randint(14, 30)
        elasticity = round(random_mod.uniform(-1.5, -0.5), 2)
    else:
        trend_direction = "stable"
        inventory_health = "healthy"
        days_of_supply = random_mod.randint(20, 45)
        elasticity = round(random_mod.uniform(-2.0, -0.8), 2)

    return {
        "elasticity": elasticity,
        "seasonalIndex": round(random_mod.uniform(0.8, 1.3), 2),
        "trendDirection": trend_direction,
        "weeklyDemand": random_mod.randint(800, 2000),
        "inventoryHealth": inventory_health,
        "daysOfSupply": days_of_supply,
        "dataSource": "simulated",
    }


def _build_market_factors(mcp_data: dict | None, strategy: dict, random_mod, scenario_context: dict | None = None) -> dict:
    """Build market factors from MCP data or generate scenario-aligned values."""
    if mcp_data and "market" in mcp_data:
        market = mcp_data["market"]
        return {
            "inflationRate": market.get("inflationRate", "3.2%"),
            "consumerSentiment": market.get("consumerSentiment", round(random_mod.uniform(60, 85), 1)),
            "supplyChainRisk": market.get("supplyChainRisk", "moderate"),
            "marketGrowthRate": market.get("marketGrowthRate", f"{round(random_mod.uniform(1, 8), 1)}%"),
            "categoryTrend": market.get("categoryTrend", "stable"),
            "dataSource": "Market Signals MCP Server",
        }

    ctx = scenario_context or {}
    supply_chain_risk = ctx.get("supply_chain_risk", "moderate")

    # Align market factors with scenario context
    if supply_chain_risk == "high":
        inflation_rate = f"{round(random_mod.uniform(4.5, 7.2), 1)}%"
        consumer_sentiment = round(random_mod.uniform(45, 62), 1)
        category_trend = "cost_pressure"
    elif ctx.get("competitive_pressure") == "high":
        inflation_rate = "3.2%"
        consumer_sentiment = round(random_mod.uniform(65, 80), 1)
        category_trend = "competitive"
    elif ctx.get("demand_trend") == "declining":
        inflation_rate = "2.8%"
        consumer_sentiment = round(random_mod.uniform(55, 70), 1)
        category_trend = "softening"
    else:
        inflation_rate = "3.2%"
        consumer_sentiment = round(random_mod.uniform(65, 82), 1)
        category_trend = "stable"

    return {
        "inflationRate": inflation_rate,
        "consumerSentiment": consumer_sentiment,
        "supplyChainRisk": supply_chain_risk,
        "marketGrowthRate": f"{round(random_mod.uniform(1, 8), 1)}%",
        "categoryTrend": category_trend,
        "dataSource": "simulated",
    }


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
