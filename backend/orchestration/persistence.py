"""DynamoDB persistence layer for pricing cycles, scenarios, and audit trails.

Provides functions to create, update, and query pricing cycle data stored in
DynamoDB tables:
- PricingCycles: Tracks cycle lifecycle and agent statuses
- PricingScenarios: Stores generated pricing scenarios
- AuditTrail: Records guardrail evaluation results

Uses boto3 DynamoDB resource for all operations.

Requirements: 8.5, 11.2
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3

logger = logging.getLogger(__name__)

# Default table names (can be overridden via environment or constructor)
DEFAULT_PRICING_CYCLES_TABLE = "PricingCycles"
DEFAULT_PRICING_SCENARIOS_TABLE = "PricingScenarios"
DEFAULT_AUDIT_TRAIL_TABLE = "AuditTrail"


def _get_dynamodb_resource(region_name: str | None = None):
    """Get a boto3 DynamoDB resource.

    Args:
        region_name: AWS region. Defaults to boto3 session default.

    Returns:
        boto3 DynamoDB resource.
    """
    kwargs = {}
    if region_name:
        kwargs["region_name"] = region_name
    return boto3.resource("dynamodb", **kwargs)


def _iso_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _convert_floats_to_decimal(obj: Any) -> Any:
    """Recursively convert float values to Decimal for DynamoDB compatibility.

    DynamoDB's boto3 resource interface does not accept Python float types.
    This function converts all floats in nested structures to Decimal.

    Args:
        obj: Any Python object (dict, list, float, etc.)

    Returns:
        The same structure with floats replaced by Decimals.
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats_to_decimal(item) for item in obj]
    return obj


def _convert_decimals_to_float(obj: Any) -> Any:
    """Recursively convert Decimal values back to float for JSON compatibility.

    Args:
        obj: Any Python object (dict, list, Decimal, etc.)

    Returns:
        The same structure with Decimals replaced by floats.
    """
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimals_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimals_to_float(item) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# PricingCycles table operations
# ---------------------------------------------------------------------------


def create_pricing_cycle(
    cycle_id: str,
    pricing_group: str,
    objectives: list[str],
    constraints: dict[str, Any],
    requested_by: str,
    *,
    dynamodb_resource=None,
    table_name: str = DEFAULT_PRICING_CYCLES_TABLE,
) -> dict[str, Any]:
    """Write a new pricing cycle initiation record to the PricingCycles table.

    Creates an item with status INITIATED and records the request metadata.

    Args:
        cycle_id: Unique identifier for the pricing cycle (ULID).
        pricing_group: The product group being analyzed.
        objectives: List of strategic objectives.
        constraints: Business constraints dict (minMargin, maxPriceChange, etc.).
        requested_by: Cognito user ID of the requester.
        dynamodb_resource: Optional boto3 DynamoDB resource (for testing).
        table_name: DynamoDB table name override.

    Returns:
        The item written to DynamoDB.
    """
    resource = dynamodb_resource or _get_dynamodb_resource()
    table = resource.Table(table_name)

    now = _iso_now()

    # TTL: auto-expire stuck cycles after 1 hour (3600 seconds)
    # Cycles that complete successfully have their TTL removed in update_cycle_status
    import time
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
    agent_statuses: dict[str, Any] | None = None,
    *,
    scenario_count: int | None = None,
    dynamodb_resource=None,
    table_name: str = DEFAULT_PRICING_CYCLES_TABLE,
) -> dict[str, Any]:
    """Update the status and agent statuses of a pricing cycle.

    Since 'status' is the sort key of the PricingCycles table, we cannot
    update it in-place. Instead, we read the existing item, delete it, and
    write a new item with the updated status.

    Args:
        cycle_id: The pricing cycle identifier.
        status: New status (INITIATED, ANALYZING, SYNTHESIZING, COMPLETE, FAILED).
        agent_statuses: Map of agent statuses {agentId: {status, startTime, endTime, error}}.
        scenario_count: Number of scenarios generated (set on COMPLETE).
        dynamodb_resource: Optional boto3 DynamoDB resource (for testing).
        table_name: DynamoDB table name override.

    Returns:
        The updated item dict.
    """
    resource = dynamodb_resource or _get_dynamodb_resource()
    table = resource.Table(table_name)

    # Query for the existing item (we need to find it by cycleId regardless of current status)
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("cycleId").eq(cycle_id),
        Limit=1,
    )

    items = response.get("Items", [])
    if not items:
        # If no existing item, create a minimal one
        existing_item = {"cycleId": cycle_id, "createdAt": _iso_now()}
    else:
        existing_item = items[0]
        # Delete the old item (since status is the sort key, we need to remove it)
        old_status = existing_item.get("status", "INITIATED")
        table.delete_item(Key={"cycleId": cycle_id, "status": old_status})

    # Build the new item with updated fields
    new_item = dict(existing_item)
    new_item["status"] = status

    if agent_statuses is not None:
        new_item["agentStatuses"] = _convert_floats_to_decimal(agent_statuses)

    if scenario_count is not None:
        new_item["scenarioCount"] = scenario_count

    if status == "COMPLETE":
        new_item["completedAt"] = _iso_now()
        # Remove TTL — completed cycles should not auto-expire
        new_item.pop("ttl", None)

    if status == "FAILED":
        # Keep TTL on failed cycles — they'll auto-expire after the original 1h window
        pass

    table.put_item(Item=new_item)

    logger.info("Updated pricing cycle %s to status %s", cycle_id, status)
    return _convert_decimals_to_float(new_item)


def get_cycle(
    cycle_id: str,
    *,
    dynamodb_resource=None,
    table_name: str = DEFAULT_PRICING_CYCLES_TABLE,
) -> dict[str, Any] | None:
    """Read a pricing cycle record from the PricingCycles table.

    Args:
        cycle_id: The pricing cycle identifier.
        dynamodb_resource: Optional boto3 DynamoDB resource (for testing).
        table_name: DynamoDB table name override.

    Returns:
        The cycle item dict, or None if not found.
    """
    resource = dynamodb_resource or _get_dynamodb_resource()
    table = resource.Table(table_name)

    # Query by cycleId partition key to get the cycle regardless of status SK
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("cycleId").eq(cycle_id),
        Limit=1,
    )

    items = response.get("Items", [])
    if items:
        return _convert_decimals_to_float(items[0])
    return None


# ---------------------------------------------------------------------------
# PricingScenarios table operations
# ---------------------------------------------------------------------------


def store_scenarios(
    cycle_id: str,
    scenarios: list[dict[str, Any]],
    *,
    dynamodb_resource=None,
    table_name: str = DEFAULT_PRICING_SCENARIOS_TABLE,
) -> int:
    """Batch write generated scenarios to the PricingScenarios table.

    Each scenario must have a 'scenarioId' field. The cycle_id is used as
    the partition key.

    Args:
        cycle_id: The parent pricing cycle identifier.
        scenarios: List of scenario dicts to store.
        dynamodb_resource: Optional boto3 DynamoDB resource (for testing).
        table_name: DynamoDB table name override.

    Returns:
        Number of scenarios written.
    """
    resource = dynamodb_resource or _get_dynamodb_resource()
    table = resource.Table(table_name)

    now = _iso_now()
    written = 0

    # DynamoDB batch_writer handles batching into 25-item chunks automatically
    with table.batch_writer() as batch:
        for scenario in scenarios:
            item = {
                "cycleId": cycle_id,
                "scenarioId": scenario["scenarioId"],
                "createdAt": now,
            }
            # Copy all scenario fields into the item
            for key, value in scenario.items():
                if key not in ("cycleId",):
                    item[key] = value

            # Convert floats to Decimal for DynamoDB
            item = _convert_floats_to_decimal(item)

            batch.put_item(Item=item)
            written += 1

    logger.info(
        "Stored %d scenarios for cycle %s", written, cycle_id
    )
    return written


def get_scenarios(
    cycle_id: str,
    page: int = 1,
    page_size: int = 20,
    *,
    dynamodb_resource=None,
    table_name: str = DEFAULT_PRICING_SCENARIOS_TABLE,
) -> dict[str, Any]:
    """Paginated read of scenarios for a pricing cycle.

    Returns scenarios sorted by rank (if available) with pagination metadata.

    Args:
        cycle_id: The pricing cycle identifier.
        page: Page number (1-indexed).
        page_size: Number of scenarios per page (max 20 per design).
        dynamodb_resource: Optional boto3 DynamoDB resource (for testing).
        table_name: DynamoDB table name override.

    Returns:
        Dict with 'scenarios', 'page', 'pageSize', 'totalCount', 'totalPages'.
    """
    resource = dynamodb_resource or _get_dynamodb_resource()
    table = resource.Table(table_name)

    # Query all scenarios for this cycle
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("cycleId").eq(cycle_id),
    )

    all_items = response.get("Items", [])

    # Handle pagination for large result sets from DynamoDB
    while "LastEvaluatedKey" in response:
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("cycleId").eq(
                cycle_id
            ),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        all_items.extend(response.get("Items", []))

    # Convert Decimals back to floats for the caller
    all_items = [_convert_decimals_to_float(item) for item in all_items]

    # Sort by rank if available
    all_items.sort(key=lambda x: x.get("rank", float("inf")))

    total_count = len(all_items)
    total_pages = max(1, (total_count + page_size - 1) // page_size)

    # Apply pagination
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


# ---------------------------------------------------------------------------
# AuditTrail table operations
# ---------------------------------------------------------------------------


def write_audit_trail(
    scenario_id: str,
    guardrail_results: list[dict[str, Any]],
    agent_id: str,
    cycle_id: str,
    *,
    dynamodb_resource=None,
    table_name: str = DEFAULT_AUDIT_TRAIL_TABLE,
) -> int:
    """Write guardrail evaluation results to the AuditTrail table.

    Each guardrail result is written as a separate item with a composite
    sort key of timestamp#ruleId.

    Args:
        scenario_id: The scenario being evaluated (partition key).
        guardrail_results: List of guardrail result dicts with 'rule', 'passed',
            and optionally 'reason' fields.
        agent_id: The agent that triggered the evaluation.
        cycle_id: The parent pricing cycle identifier.
        dynamodb_resource: Optional boto3 DynamoDB resource (for testing).
        table_name: DynamoDB table name override.

    Returns:
        Number of audit trail entries written.
    """
    resource = dynamodb_resource or _get_dynamodb_resource()
    table = resource.Table(table_name)

    now = _iso_now()
    written = 0

    with table.batch_writer() as batch:
        for result in guardrail_results:
            rule_id = result.get("rule", "unknown")
            passed = result.get("passed", False)

            # Determine result status
            if passed:
                result_status = "PASSED"
            else:
                result_status = "REJECTED"

            # Composite sort key: timestamp#ruleId
            sort_key = f"{now}#{rule_id}"

            item = {
                "scenarioId": scenario_id,
                "timestamp#ruleId": sort_key,
                "guardrailRule": rule_id,
                "result": result_status,
                "violationReason": result.get("reason", ""),
                "agentId": agent_id,
                "cycleId": cycle_id,
            }

            batch.put_item(Item=item)
            written += 1

    logger.info(
        "Wrote %d audit trail entries for scenario %s", written, scenario_id
    )
    return written
