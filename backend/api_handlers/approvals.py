"""Lambda handler for approval workflow endpoints.

Handles:
- POST /approvals: Approve, reject, or request modifications to a scenario

Requirements: 4.3, 7.1, 7.2, 7.3, 7.5
"""

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from shared.approval_routing import validate_approval
from shared.models.pricing_scenario import RiskLevel
from backend.agents.orchestrator import trigger_implementation

logger = logging.getLogger()
logger.setLevel(logging.INFO)

APPROVALS_TABLE = os.environ.get("APPROVALS_TABLE", "Approvals")
PRICING_SCENARIOS_TABLE = os.environ.get("PRICING_SCENARIOS_TABLE", "PricingScenarios")
PRODUCTS_TABLE = os.environ.get("PRODUCTS_TABLE", "Products")
AGENTCORE_ENDPOINT = os.environ.get("AGENTCORE_ENDPOINT", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


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
    risk_level = body.get("riskLevel", "")
    cycle_id = body.get("cycleId", "")

    # Validate required fields
    if not scenario_id:
        return _response(400, {"error": "scenarioId is required"})

    if action not in ("APPROVED", "REJECTED"):
        return _response(400, {
            "error": "action must be 'APPROVED' or 'REJECTED'",
        })

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

    now = _iso_now()
    dynamodb = _get_dynamodb_resource()

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
        # Build scenario dict for implementation trigger
        scenario_data = {
            "scenarioId": scenario_id,
            "cycleId": cycle_id,
        }

        # Try to fetch the full scenario for price changes
        if cycle_id:
            try:
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

        # Step 4: Update product prices in Products table on approval (Requirement 7.5)
        price_changes = scenario_data.get("priceChanges", [])
        if price_changes:
            _update_product_prices(dynamodb, price_changes)

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
