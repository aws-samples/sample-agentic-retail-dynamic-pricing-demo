"""Historical memory query and persistence for scenario generation.

This module provides long-term memory capabilities for the Retail Dynamic Pricing
system, simulating AgentCore Memory using DynamoDB as the backing store.

Key capabilities:
1. Query historical outcomes for a product/category (most recent 100 cycles)
2. Persist approved scenario outcomes to long-term memory within 60 seconds
3. Build historical context for inclusion in Strategy Synthesis Agent prompts

The long-term memory stores:
- Selected scenario details
- Projected metrics (revenue, margin, market share)
- Actual metrics (when available)
- Approval decision and timestamp

Requirements: 10.3, 10.5
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)

# DynamoDB table name for long-term memory
MEMORY_TABLE_NAME = "PricingMemory"

# Maximum number of historical cycles to retain per product/category
MAX_CYCLES_PER_KEY = 100

# Default query limit
DEFAULT_QUERY_LIMIT = 10


def _get_dynamodb_table(table_name: str = MEMORY_TABLE_NAME):
    """Get a DynamoDB Table resource.

    Args:
        table_name: Name of the DynamoDB table.

    Returns:
        boto3 DynamoDB Table resource.
    """
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(table_name)


def _convert_floats_to_decimal(obj: Any) -> Any:
    """Recursively convert float values to Decimal for DynamoDB compatibility.

    DynamoDB does not support Python float type directly; it requires Decimal.
    Also removes None values from dicts since DynamoDB doesn't support them.

    Args:
        obj: The object to convert (dict, list, float, or other).

    Returns:
        The converted object with floats replaced by Decimals.
    """
    if isinstance(obj, float):
        return Decimal(json.dumps(obj))
    elif isinstance(obj, dict):
        return {
            k: _convert_floats_to_decimal(v)
            for k, v in obj.items()
            if v is not None
        }
    elif isinstance(obj, list):
        return [_convert_floats_to_decimal(item) for item in obj]
    return obj


def query_historical_outcomes(
    product_id_or_category: str,
    limit: int = DEFAULT_QUERY_LIMIT,
    table_name: str = MEMORY_TABLE_NAME,
) -> list[dict[str, Any]]:
    """Retrieve past pricing outcomes from long-term memory.

    Queries DynamoDB for historical pricing cycle outcomes associated with
    the given product ID or category. Results are ordered by timestamp
    (most recent first) and limited to the specified count.

    Args:
        product_id_or_category: The product ID or category to query outcomes for.
        limit: Maximum number of outcomes to return (default: 10, max: 100).

    Returns:
        List of historical outcome records, each containing:
        - cycle_id: The pricing cycle identifier
        - product_or_category: The product/category key
        - timestamp: When the outcome was recorded (ISO 8601)
        - selected_scenario: The scenario that was selected/approved
        - projected_metrics: Projected revenue, margin, market share
        - actual_metrics: Actual observed metrics (may be None if not yet available)
        - approval_decision: The approval action taken

    Raises:
        ValueError: If product_id_or_category is empty or limit is invalid.
    """
    if not product_id_or_category:
        raise ValueError("product_id_or_category must not be empty")

    if limit < 1:
        raise ValueError("limit must be at least 1")

    # Cap at MAX_CYCLES_PER_KEY
    effective_limit = min(limit, MAX_CYCLES_PER_KEY)

    table = _get_dynamodb_table(table_name)

    try:
        response = table.query(
            KeyConditionExpression=Key("product_or_category").eq(
                product_id_or_category
            ),
            ScanIndexForward=False,  # Most recent first
            Limit=effective_limit,
        )
        items = response.get("Items", [])
        logger.info(
            "Retrieved %d historical outcomes for '%s'",
            len(items),
            product_id_or_category,
        )
        return items

    except Exception as e:
        logger.error(
            "Failed to query historical outcomes for '%s': %s",
            product_id_or_category,
            e,
        )
        raise


def persist_outcome(
    cycle_id: str,
    scenario: dict[str, Any],
    actual_metrics: dict[str, Any] | None = None,
    table_name: str = MEMORY_TABLE_NAME,
) -> dict[str, Any]:
    """Store an approved scenario outcome to long-term memory.

    Persists the selected scenario, its projected metrics, actual metrics
    (when available), and approval decision to DynamoDB. This must complete
    within 60 seconds of approval per Requirement 10.5.

    After persisting, enforces the 100-cycle limit per product/category by
    removing the oldest records if necessary.

    Args:
        cycle_id: The pricing cycle identifier.
        scenario: The approved scenario data containing at minimum:
            - scenarioId or scenario_id
            - priceChanges or price_changes (list with productId entries)
            - projectedRevenue or projected_revenue
            - projectedMargin or projected_margin
            - projectedMarketShare or projected_market_share (optional)
            - confidenceScore or confidence_score
            - riskLevel or risk_level
            - statusLabel or status_label
            - approvalStatus or approval_status
        actual_metrics: Optional dict with actual observed metrics:
            - actual_revenue
            - actual_margin
            - actual_market_share

    Returns:
        The persisted memory record.

    Raises:
        ValueError: If cycle_id or scenario is empty/invalid.
    """
    if not cycle_id:
        raise ValueError("cycle_id must not be empty")
    if not scenario:
        raise ValueError("scenario must not be empty")

    start_time = time.time()

    # Extract product/category key from scenario
    product_or_category = _extract_product_or_category(scenario)

    # Build the memory record
    timestamp = datetime.now(timezone.utc).isoformat()

    record = {
        "product_or_category": product_or_category,
        "timestamp": timestamp,
        "cycle_id": cycle_id,
        "selected_scenario": {
            "scenario_id": scenario.get("scenarioId", scenario.get("scenario_id", "")),
            "confidence_score": scenario.get(
                "confidenceScore", scenario.get("confidence_score", 0)
            ),
            "risk_level": scenario.get("riskLevel", scenario.get("risk_level", "")),
            "status_label": scenario.get(
                "statusLabel", scenario.get("status_label", "")
            ),
            "price_changes": scenario.get(
                "priceChanges", scenario.get("price_changes", [])
            ),
            "composite_score": scenario.get(
                "compositeScore", scenario.get("composite_score", 0)
            ),
        },
        "projected_metrics": {
            "revenue": scenario.get(
                "projectedRevenue", scenario.get("projected_revenue", 0)
            ),
            "margin": scenario.get(
                "projectedMargin", scenario.get("projected_margin", 0)
            ),
        },
        "approval_decision": scenario.get(
            "approvalStatus", scenario.get("approval_status", "APPROVED")
        ),
    }

    # Add optional fields only if they have values (DynamoDB doesn't store None)
    market_share = scenario.get(
        "projectedMarketShare", scenario.get("projected_market_share")
    )
    if market_share is not None:
        record["projected_metrics"]["market_share"] = market_share

    if actual_metrics is not None:
        record["actual_metrics"] = actual_metrics
    else:
        record["actual_metrics"] = None

    table = _get_dynamodb_table(table_name)

    try:
        # Convert floats to Decimal for DynamoDB compatibility
        dynamodb_record = _convert_floats_to_decimal(record)
        table.put_item(Item=dynamodb_record)

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Persisted outcome for cycle %s (product/category: '%s') in %dms",
            cycle_id,
            product_or_category,
            elapsed_ms,
        )

        # Enforce the 100-cycle limit
        _enforce_retention_limit(product_or_category, table_name)

        total_elapsed = time.time() - start_time
        if total_elapsed > 60:
            logger.warning(
                "persist_outcome took %.1fs, exceeding 60s SLA for cycle %s",
                total_elapsed,
                cycle_id,
            )

        return record

    except Exception as e:
        logger.error(
            "Failed to persist outcome for cycle %s: %s",
            cycle_id,
            e,
        )
        raise


def build_historical_context(outcomes: list[dict[str, Any]]) -> str:
    """Format historical outcome data for inclusion in Strategy Synthesis Agent context.

    Transforms raw historical outcome records into a structured text summary
    that can be included in the agent's prompt to inform scenario generation.

    Args:
        outcomes: List of historical outcome records from query_historical_outcomes.

    Returns:
        Formatted string containing historical context summary. Returns an
        empty string if no outcomes are provided.
    """
    if not outcomes:
        return ""

    lines = [
        f"## Historical Pricing Outcomes ({len(outcomes)} previous cycles)\n",
    ]

    for i, outcome in enumerate(outcomes, 1):
        cycle_id = outcome.get("cycle_id", "unknown")
        timestamp = outcome.get("timestamp", "unknown")
        selected = outcome.get("selected_scenario", {})
        projected = outcome.get("projected_metrics", {})
        actual = outcome.get("actual_metrics")
        approval = outcome.get("approval_decision", "unknown")

        lines.append(f"### Cycle {i} (ID: {cycle_id})")
        lines.append(f"- **Date**: {timestamp}")
        lines.append(f"- **Approval Decision**: {approval}")
        lines.append(
            f"- **Confidence Score**: {selected.get('confidence_score', 'N/A')}"
        )
        lines.append(f"- **Risk Level**: {selected.get('risk_level', 'N/A')}")
        lines.append(
            f"- **Composite Score**: {selected.get('composite_score', 'N/A')}"
        )

        # Projected metrics
        lines.append("- **Projected Metrics**:")
        lines.append(f"  - Revenue: {projected.get('revenue', 'N/A')}")
        lines.append(f"  - Margin: {projected.get('margin', 'N/A')}")
        if projected.get("market_share") is not None:
            lines.append(f"  - Market Share: {projected.get('market_share')}")

        # Actual metrics (if available)
        if actual:
            lines.append("- **Actual Metrics**:")
            lines.append(f"  - Revenue: {actual.get('actual_revenue', 'N/A')}")
            lines.append(f"  - Margin: {actual.get('actual_margin', 'N/A')}")
            if actual.get("actual_market_share") is not None:
                lines.append(
                    f"  - Market Share: {actual.get('actual_market_share')}"
                )

            # Calculate variance if both projected and actual are available
            proj_rev = projected.get("revenue")
            act_rev = actual.get("actual_revenue")
            if proj_rev and act_rev and proj_rev != 0:
                rev_variance = abs(float(act_rev) - float(proj_rev)) / abs(float(proj_rev)) * 100
                direction = "above" if float(act_rev) > float(proj_rev) else "below"
                lines.append(
                    f"  - Revenue Variance: {rev_variance:.1f}% {direction} projection"
                )
        else:
            lines.append("- **Actual Metrics**: Not yet available")

        # Price changes summary
        price_changes = selected.get("price_changes", [])
        if price_changes:
            lines.append(f"- **Price Changes**: {len(price_changes)} product(s)")
            for pc in price_changes[:3]:  # Show first 3
                product_id = pc.get("productId", pc.get("product_id", "unknown"))
                change_pct = pc.get("changePercent", pc.get("change_percent", 0))
                lines.append(f"  - {product_id}: {change_pct:+.1f}%")
            if len(price_changes) > 3:
                lines.append(f"  - ... and {len(price_changes) - 3} more")

        lines.append("")  # Blank line between cycles

    # Add summary insights
    lines.append("### Summary Insights")
    approved_count = sum(
        1 for o in outcomes if o.get("approval_decision") == "APPROVED"
    )
    rejected_count = sum(
        1 for o in outcomes if o.get("approval_decision") == "REJECTED"
    )
    lines.append(f"- Total cycles reviewed: {len(outcomes)}")
    lines.append(f"- Approved: {approved_count}")
    lines.append(f"- Rejected: {rejected_count}")

    # Average confidence score
    confidence_scores = [
        o.get("selected_scenario", {}).get("confidence_score")
        for o in outcomes
        if o.get("selected_scenario", {}).get("confidence_score") is not None
    ]
    if confidence_scores:
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        lines.append(f"- Average Confidence Score: {avg_confidence:.0f}")

    return "\n".join(lines)


def _extract_product_or_category(scenario: dict[str, Any]) -> str:
    """Extract the product or category key from a scenario.

    Looks for product IDs in price_changes, or falls back to category-level keys.

    Args:
        scenario: The scenario dictionary.

    Returns:
        A string key representing the product or category.
    """
    # Try to get from price_changes (first product)
    price_changes = scenario.get("priceChanges", scenario.get("price_changes", []))
    if price_changes and isinstance(price_changes, list) and len(price_changes) > 0:
        first_change = price_changes[0]
        product_id = first_change.get("productId", first_change.get("product_id"))
        if product_id:
            return product_id

    # Fall back to category or pricing_group
    for key in ["category", "pricing_group", "pricingGroup", "product_or_category"]:
        if key in scenario and scenario[key]:
            return scenario[key]

    # Last resort: use cycle_id or scenario_id
    return scenario.get(
        "cycleId", scenario.get("cycle_id", scenario.get("scenarioId", "unknown"))
    )


def _enforce_retention_limit(
    product_or_category: str,
    table_name: str = MEMORY_TABLE_NAME,
) -> None:
    """Enforce the 100-cycle retention limit per product/category.

    If there are more than MAX_CYCLES_PER_KEY records for a given key,
    delete the oldest ones to maintain the limit.

    Args:
        product_or_category: The partition key to check.
        table_name: DynamoDB table name.
    """
    table = _get_dynamodb_table(table_name)

    try:
        # Query all items for this key (sorted by timestamp ascending)
        response = table.query(
            KeyConditionExpression=Key("product_or_category").eq(
                product_or_category
            ),
            ScanIndexForward=True,  # Oldest first
        )
        items = response.get("Items", [])

        if len(items) > MAX_CYCLES_PER_KEY:
            # Delete the oldest items beyond the limit
            items_to_delete = items[: len(items) - MAX_CYCLES_PER_KEY]
            with table.batch_writer() as batch:
                for item in items_to_delete:
                    batch.delete_item(
                        Key={
                            "product_or_category": item["product_or_category"],
                            "timestamp": item["timestamp"],
                        }
                    )
            logger.info(
                "Pruned %d old records for '%s' to maintain %d-cycle limit",
                len(items_to_delete),
                product_or_category,
                MAX_CYCLES_PER_KEY,
            )

    except Exception as e:
        logger.warning(
            "Failed to enforce retention limit for '%s': %s",
            product_or_category,
            e,
        )
