"""Lambda handler for approval workflow endpoints.

Handles:
- POST /approvals: Approve, reject, or request modifications to a scenario

Requirements: 4.3, 7.1, 7.2, 7.3, 7.5
"""

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

try:
    from log_config import configure_logging
except ImportError:
    from backend.api_handlers.log_config import configure_logging

logger = configure_logging(__name__)

APPROVALS_TABLE = os.environ.get("APPROVALS_TABLE", "Approvals")
PRICING_SCENARIOS_TABLE = os.environ.get("PRICING_SCENARIOS_TABLE", "PricingScenarios")
PRODUCTS_TABLE = os.environ.get("PRODUCTS_TABLE", "Products")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


# --- Inlined approval routing logic (from shared.approval_routing) ---

class RiskLevel(str, Enum):
    """Risk level classification for pricing scenarios."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


def validate_approval(risk_level: RiskLevel, justification: str | None = None) -> bool:
    """Validate whether an approval meets requirements for the given risk level.

    - LOW/MEDIUM: Always valid
    - HIGH: Requires justification of >= 50 characters
    """
    if risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM):
        return True
    if justification is None:
        return False
    return len(justification) >= 50


# --- Inlined implementation trigger (calls AgentCore Runtime directly) ---

# Minimum session ID length required by AgentCore Runtime
_MIN_SESSION_ID_LENGTH = 33


def _ensure_session_id(session_id: str | None = None) -> str:
    """Ensure the session ID meets AgentCore's minimum length requirement."""
    if not session_id:
        session_id = f"approval-impl-{uuid.uuid4().hex}"
    if len(session_id) < _MIN_SESSION_ID_LENGTH:
        padding = uuid.uuid4().hex
        session_id = f"{session_id}-{padding}"
    return session_id[:128]


def _require_env(var_name: str) -> str:
    """Read a required environment variable or raise a clear error."""
    value = os.environ.get(var_name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{var_name}' is not set."
        )
    return value


def trigger_implementation(
    scenario: dict[str, Any],
    cycle_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Trigger the Implementation Monitoring Agent via AgentCore Runtime.

    After a pricing scenario is approved, invokes the agent to execute
    price updates and begin monitoring.
    """
    # Implementation agent ARN is optional — if not set, skip invocation
    impl_agent_arn = os.environ.get("IMPLEMENTATION_MONITORING_AGENT_ARN", "")
    if not impl_agent_arn:
        logger.warning(
            "IMPLEMENTATION_MONITORING_AGENT_ARN not set, skipping implementation trigger"
        )
        return {"status": "SKIPPED", "reason": "Agent ARN not configured"}

    cycle_id = cycle_id or scenario.get("cycleId", str(uuid.uuid4()))
    scenario_id = scenario.get("scenarioId", str(uuid.uuid4()))
    price_changes = scenario.get("priceChanges", [])

    prompt = (
        f"Execute price updates for approved scenario '{scenario_id}' "
        f"in pricing cycle '{cycle_id}'. "
        f"Price changes to implement: {json.dumps(price_changes)}. "
        f"Begin monitoring after implementation."
    )

    client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)
    runtime_session_id = _ensure_session_id(session_id)

    payload = json.dumps({"prompt": prompt}).encode()

    response = client.invoke_agent_runtime(
        agentRuntimeArn=impl_agent_arn,
        runtimeSessionId=runtime_session_id,
        payload=payload,
        qualifier="DEFAULT",
    )

    response_body = response["response"].read()

    try:
        result = json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        result = {"raw_output": response_body.decode("utf-8", errors="replace")}

    return {
        "status": "IMPLEMENTATION_STARTED",
        "scenario_id": scenario_id,
        "cycle_id": cycle_id,
        "price_changes_count": len(price_changes),
        "agent_response": result,
    }


def _get_dynamodb_resource():
    """Get a boto3 DynamoDB resource."""
    return boto3.resource("dynamodb", region_name=AWS_REGION)


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
    """Lambda handler for approval workflow endpoints."""
    http_method = event.get("httpMethod", "")
    path = event.get("path", "")

    logger.info("Approvals handler: %s %s", http_method, path)

    try:
        if http_method == "POST" and path == "/approvals":
            return _process_approval(event)
        else:
            return _response(404, {"error": "Not found"})
    except Exception as e:
        logger.exception("Error handling request")
        return _response(500, {"error": str(e)})


def _process_approval(event: dict[str, Any]) -> dict[str, Any]:
    """Handle POST /approvals - process approval/rejection of a scenario.

    Parses the request body, validates the approval against risk-based rules,
    writes the approval record, updates the scenario status, and triggers
    implementation on approval.

    Requirements: 4.3, 7.1, 7.2, 7.3, 7.5
    """
    body = json.loads(event.get("body", "{}"))

    # Parse required fields
    scenario_id = body.get("scenarioId")
    action = body.get("action", "")  # APPROVED or REJECTED
    comment = body.get("comment", "")
    cycle_id = body.get("cycleId", "")

    # Validate required fields
    if not scenario_id:
        return _response(400, {"error": "scenarioId is required"})

    if action not in ("APPROVED", "REJECTED"):
        return _response(400, {
            "error": "action must be 'APPROVED' or 'REJECTED'",
        })

    # [SECURITY FIX] Require non-empty cycleId to prevent governance bypass
    if not cycle_id:
        return _response(400, {
            "error": "cycleId is required for approval validation",
        })

    # [C1 FIX] Initialize DynamoDB resource BEFORE any table access
    dynamodb = _get_dynamodb_resource()

    # [C2 FIX] Fetch authoritative riskLevel from stored scenario data (server-side)
    # Do NOT trust client-supplied riskLevel — it could be tampered to bypass governance.
    risk_level = ""
    stored_scenario = None
    if cycle_id and scenario_id:
        scenarios_table = dynamodb.Table(PRICING_SCENARIOS_TABLE)
        try:
            scenario_response = scenarios_table.get_item(
                Key={"cycleId": cycle_id, "scenarioId": scenario_id}
            )
            if "Item" in scenario_response:
                stored_scenario = _convert_decimals_to_float(scenario_response["Item"])
                risk_level = stored_scenario.get("riskLevel", "")
                logger.info(
                    "Fetched authoritative riskLevel '%s' for scenario %s from DynamoDB",
                    risk_level, scenario_id,
                )
        except Exception as e:
            logger.error(
                "Failed to fetch scenario %s for risk validation: %s",
                scenario_id, e,
            )
            return _response(500, {
                "error": "Unable to validate scenario data. Please retry.",
            })

    # If we couldn't determine risk level, reject the request
    if not risk_level and action == "APPROVED":
        # Fall back to client-supplied only if scenario fetch wasn't possible
        client_risk = body.get("riskLevel", "")
        if not client_risk:
            return _response(400, {
                "error": "Unable to determine scenario risk level for approval validation",
            })
        risk_level = client_risk
        logger.warning(
            "Using client-supplied riskLevel '%s' for scenario %s (server-side fetch unavailable)",
            risk_level, scenario_id,
        )

    # Validate HIGH risk requires >= 50 character justification (Requirement 7.3)
    if risk_level == "HIGH" and action == "APPROVED":
        risk_enum = RiskLevel.HIGH
        if not validate_approval(risk_enum, comment):
            return _response(400, {
                "error": "High risk approvals require a justification of at least 50 characters",
            })

    # Extract actor ID from Cognito claims (if available)
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    claims = authorizer.get("claims", {})
    actor_id = claims.get("sub", claims.get("cognito:username", "system"))

    # --- [C1 FIX] Separation of Duties Check ---
    # The user who initiated the pricing cycle cannot approve their own scenarios.
    # Now uses the already-initialized dynamodb resource (fixes UnboundLocalError).
    # Fails CLOSED: if the check cannot be performed, the approval is rejected.
    if cycle_id:
        pricing_cycles_table_name = os.environ.get("PRICING_CYCLES_TABLE", "PricingCycles")
        cycles_table = dynamodb.Table(pricing_cycles_table_name)
        try:
            cycle_response = cycles_table.query(
                KeyConditionExpression="cycleId = :cid",
                ExpressionAttributeValues={":cid": cycle_id},
                Limit=1,
            )
            cycle_items = cycle_response.get("Items", [])
            if cycle_items:
                initiator_id = cycle_items[0].get("requestedBy", "")
                if initiator_id and initiator_id == actor_id:
                    return _response(403, {
                        "error": "Separation of duties violation: the cycle initiator cannot approve their own scenarios",
                    })
        except Exception as e:
            logger.error(
                "Separation of duties check failed for cycle %s: %s. "
                "Failing closed — approval rejected.",
                cycle_id, e,
            )
            return _response(500, {
                "error": "Unable to verify separation of duties. Please retry.",
            })

    now = _iso_now()

    # Step 1: Write approval record to Approvals table
    approvals_table = dynamodb.Table(APPROVALS_TABLE)
    approval_record = {
        "scenarioId": scenario_id,
        "timestamp": now,
        "action": action,
        "actorId": actor_id,
        "comment": comment,
        "riskLevel": risk_level,
    }

    # Add escalation deadline for routed scenarios (48h from now)
    if action == "APPROVED" and risk_level in ("MEDIUM", "HIGH"):
        from datetime import timedelta
        escalation_deadline = (
            datetime.now(timezone.utc) + timedelta(hours=48)
        ).isoformat()
        approval_record["escalationDeadline"] = escalation_deadline

    approvals_table.put_item(Item=approval_record)
    logger.info(
        "Wrote approval record for scenario %s: %s", scenario_id, action
    )

    # [SECURITY FIX] Write to AuditTrail table for immutable compliance record
    try:
        audit_table = dynamodb.Table(os.environ.get("AUDIT_TRAIL_TABLE", "AuditTrail"))
        audit_entry = {
            "scenarioId": scenario_id,
            "timestamp#ruleId": f"{now}#approval-{action.lower()}",
            "action": action,
            "actorId": actor_id,
            "cycleId": cycle_id,
            "riskLevel": risk_level,
            "comment": comment[:200] if comment else "",
            "eventType": "APPROVAL_DECISION",
        }
        audit_table.put_item(Item=audit_entry)
    except Exception as audit_err:
        logger.warning("Failed to write audit trail: %s", audit_err)

    # Step 2: Update scenario approvalStatus in PricingScenarios table
    scenarios_table = dynamodb.Table(PRICING_SCENARIOS_TABLE)

    # Determine the approval status to set
    approval_status = action  # APPROVED or REJECTED

    # We need the cycleId to update the scenario (it's the partition key)
    if cycle_id:
        scenarios_table.update_item(
            Key={"cycleId": cycle_id, "scenarioId": scenario_id},
            UpdateExpression=(
                "SET approvalStatus = :status, approvalComment = :comment, "
                "approvedBy = :actor, approvedAt = :ts"
            ),
            ExpressionAttributeValues={
                ":status": approval_status,
                ":comment": comment,
                ":actor": actor_id,
                ":ts": now,
            },
        )
        logger.info(
            "Updated scenario %s approvalStatus to %s",
            scenario_id,
            approval_status,
        )

    # Step 3: If APPROVED, trigger Implementation Monitoring Agent (Requirement 7.5)
    implementation_result = None
    if action == "APPROVED":
        # [C3 FIX] Use the already-fetched stored_scenario as the authoritative source
        # for price changes. Do NOT trust client-supplied price data.
        scenario_data = stored_scenario if stored_scenario else {
            "scenarioId": scenario_id,
            "cycleId": cycle_id,
        }

        # If we don't have the stored scenario yet, fetch it now
        if not stored_scenario and cycle_id:
            try:
                scenarios_table = dynamodb.Table(PRICING_SCENARIOS_TABLE)
                response = scenarios_table.get_item(
                    Key={"cycleId": cycle_id, "scenarioId": scenario_id}
                )
                if "Item" in response:
                    scenario_data = _convert_decimals_to_float(response["Item"])
            except Exception as e:
                logger.warning(
                    "Could not fetch scenario details for implementation: %s", e
                )

        # Trigger implementation monitoring agent
        try:
            implementation_result = trigger_implementation(
                scenario=scenario_data,
                cycle_id=cycle_id,
            )
            logger.info(
                "Implementation triggered for scenario %s: %s",
                scenario_id,
                implementation_result.get("status"),
            )
        except Exception as e:
            logger.error(
                "Failed to trigger implementation for scenario %s: %s",
                scenario_id,
                e,
            )
            implementation_result = {
                "status": "IMPLEMENTATION_FAILED",
                "error": str(e),
            }

        # [C3 FIX] Step 4: Update product prices ONLY from authoritative stored scenario data
        # Price changes come exclusively from the DynamoDB-stored scenario, never from
        # client request body. This prevents price manipulation via tampered requests.
        price_changes = scenario_data.get("priceChanges", [])
        if price_changes:
            _update_product_prices(dynamodb, price_changes)

        # Step 5: Update agent pipeline status to show Implementation Monitoring completed
        if cycle_id:
            _update_implementation_agent_status(cycle_id, implementation_result)

    # If REJECTED, update pipeline to show implementation is not needed
    if action == "REJECTED" and cycle_id:
        _update_implementation_agent_status(cycle_id, {"status": "REJECTED"})

    # If revertPrices flag is set, roll back product prices to previousPrice
    # [SECURITY FIX] Only Operations group can revert prices
    revert_prices = body.get("revertPrices", False)
    if revert_prices and cycle_id:
        revert_groups = claims.get("cognito:groups", "")
        if "Operations" not in revert_groups:
            return _response(403, {
                "error": "Forbidden: only Operations group can revert prices",
            })
        if stored_scenario and stored_scenario.get("approvalStatus") != "APPROVED":
            return _response(400, {
                "error": "Cannot revert prices for a scenario that was not previously approved",
            })
        _revert_product_prices(dynamodb, cycle_id, scenario_id)

    # Build response
    response_body: dict[str, Any] = {
        "message": f"Scenario {scenario_id} {action.lower()}",
        "scenarioId": scenario_id,
        "action": action,
        "timestamp": now,
    }

    if implementation_result:
        response_body["implementation"] = {
            "status": implementation_result.get("status"),
        }

    return _response(200, response_body)


def _update_product_prices(
    dynamodb, price_changes: list[dict[str, Any]]
) -> None:
    """Update product prices in the Products table after approval.

    For each price change in the approved scenario, updates the product's
    currentPrice, previousPrice, and priceUpdatedAt fields.

    Args:
        dynamodb: boto3 DynamoDB resource.
        price_changes: List of price change dicts with productId, currentPrice,
            newPrice, and changePercent.
    """
    products_table = dynamodb.Table(PRODUCTS_TABLE)
    now = _iso_now()

    for change in price_changes:
        product_id = change.get("productId")
        new_price = change.get("newPrice")
        current_price = change.get("currentPrice")

        if not product_id or new_price is None:
            logger.warning(
                "Skipping price update for invalid change: %s", change
            )
            continue

        try:
            # Convert to Decimal for DynamoDB
            new_price_decimal = Decimal(str(new_price))

            # Always read the current price from DynamoDB to ensure previousPrice is set
            if current_price is None:
                existing = products_table.get_item(Key={"productId": product_id})
                item = existing.get("Item", {})
                current_price = item.get("currentPrice")

            previous_price_decimal = (
                Decimal(str(current_price)) if current_price is not None else None
            )

            update_expr = (
                "SET currentPrice = :new_price, "
                "priceUpdatedAt = :updated_at"
            )
            expr_values: dict[str, Any] = {
                ":new_price": new_price_decimal,
                ":updated_at": now,
            }

            if previous_price_decimal is not None:
                update_expr += ", previousPrice = :prev_price"
                expr_values[":prev_price"] = previous_price_decimal

            products_table.update_item(
                Key={"productId": product_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
            )
            logger.info(
                "Updated product %s price: %s -> %s",
                product_id,
                current_price,
                new_price,
            )
        except Exception as e:
            logger.error(
                "Failed to update price for product %s: %s", product_id, e
            )


def _convert_decimals_to_float(obj: Any) -> Any:
    """Recursively convert Decimal values back to float for JSON compatibility."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimals_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimals_to_float(item) for item in obj]
    return obj


def _revert_product_prices(dynamodb, cycle_id: str, scenario_id: str) -> None:
    """Revert product prices to their previous values for a given scenario.

    Reads the scenario's priceChanges, then for each product sets
    currentPrice back to the value it was before the change (stored as
    currentPrice in the priceChanges record, which was the price at the
    time the scenario was generated).
    """
    try:
        scenarios_table = dynamodb.Table(PRICING_SCENARIOS_TABLE)
        products_table = dynamodb.Table(PRODUCTS_TABLE)
        now = _iso_now()

        # Fetch the scenario to get its price changes
        response = scenarios_table.get_item(
            Key={"cycleId": cycle_id, "scenarioId": scenario_id}
        )
        scenario = response.get("Item")
        if not scenario:
            logger.warning("Cannot revert: scenario %s not found", scenario_id)
            return

        price_changes = scenario.get("priceChanges", [])
        reverted_count = 0

        for change in price_changes:
            product_id = change.get("productId")
            original_price = change.get("currentPrice")  # This was the price BEFORE the change

            if not product_id or original_price is None:
                continue

            try:
                original_decimal = Decimal(str(float(original_price)))
                products_table.update_item(
                    Key={"productId": product_id},
                    UpdateExpression="SET currentPrice = :p, priceUpdatedAt = :t, previousPrice = :prev",
                    ExpressionAttributeValues={
                        ":p": original_decimal,
                        ":t": now,
                        ":prev": change.get("newPrice", original_decimal),
                    },
                )
                reverted_count += 1
            except Exception as e:
                logger.warning("Failed to revert price for %s: %s", product_id, e)

        # Update scenario approval status to indicate revert
        try:
            scenarios_table.update_item(
                Key={"cycleId": cycle_id, "scenarioId": scenario_id},
                UpdateExpression="SET approvalStatus = :s, approvalComment = :c",
                ExpressionAttributeValues={
                    ":s": "REVERTED",
                    ":c": f"Prices reverted to original values ({reverted_count} products)",
                },
            )
        except Exception:
            pass

        logger.info("Reverted %d product prices for scenario %s", reverted_count, scenario_id)
    except Exception as e:
        logger.error("Failed to revert prices for scenario %s: %s", scenario_id, e)


def _update_implementation_agent_status(cycle_id: str, impl_result: dict[str, Any] | None) -> None:
    """Update the Implementation Monitoring agent status in the PricingCycles table."""
    try:
        from boto3.dynamodb.conditions import Key as DDBKey

        dynamodb_resource = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb_resource.Table(os.environ.get("PRICING_CYCLES_TABLE", "PricingCycles"))

        response = table.query(
            KeyConditionExpression=DDBKey("cycleId").eq(cycle_id),
            Limit=1,
        )
        items = response.get("Items", [])
        if not items:
            return

        item = items[0]
        agent_statuses = item.get("agentStatuses", {})

        now = datetime.now(timezone.utc).isoformat()

        if impl_result and impl_result.get("status") in ("IMPLEMENTATION_STARTED", "SKIPPED"):
            agent_statuses["implementation_monitoring"] = {
                "status": "completed",
                "startTime": now,
                "endTime": now,
            }
        elif impl_result and impl_result.get("status") == "REJECTED":
            agent_statuses["implementation_monitoring"] = {
                "status": "idle",
                "endTime": now,
            }
        elif impl_result and "FAILED" in impl_result.get("status", ""):
            agent_statuses["implementation_monitoring"] = {
                "status": "failed",
                "startTime": now,
                "endTime": now,
                "error": impl_result.get("error", "Implementation failed"),
            }
        else:
            agent_statuses["implementation_monitoring"] = {
                "status": "completed",
                "startTime": now,
                "endTime": now,
            }

        table.update_item(
            Key={"cycleId": cycle_id, "status": item["status"]},
            UpdateExpression="SET agentStatuses = :s",
            ExpressionAttributeValues={":s": agent_statuses},
        )
        logger.info("Updated implementation_monitoring agent status for cycle %s", cycle_id)
    except Exception as e:
        logger.warning("Failed to update implementation agent status: %s", e)


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
