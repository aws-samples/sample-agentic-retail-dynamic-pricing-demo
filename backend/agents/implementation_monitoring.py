"""Implementation Monitoring Agent for the Retail Dynamic Pricing system.

This agent executes approved price changes across sales channels, tracks
post-implementation KPIs (revenue, conversion rate, margin), detects variances
against projections, and generates adjustment recommendations when thresholds
are breached.

Uses the Strands Agents SDK with model us.anthropic.claude-sonnet-4-6.

Validates: Requirements 1.4, 9.1, 9.2, 9.3, 9.4
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from strands import Agent, tool

from shared.model_config import SPECIALIST_MODEL
from shared.variance_detection import VarianceResult, detect_variance

logger = logging.getLogger(__name__)

# Configuration
PRODUCTS_TABLE = os.environ.get("PRODUCTS_TABLE", "Products")
PRICING_SCENARIOS_TABLE = os.environ.get("PRICING_SCENARIOS_TABLE", "PricingScenarios")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Monitoring configuration
MONITORING_INTERVAL_MINUTES = 60  # Evaluate metrics at intervals <= 60 minutes
REVENUE_VARIANCE_THRESHOLD = 0.10  # 10% variance on revenue
MARGIN_VARIANCE_THRESHOLD = 0.03  # 3 percentage points on margin

# System prompt for the Implementation Monitoring Agent
IMPLEMENTATION_MONITORING_SYSTEM_PROMPT = """You are the Implementation Monitoring Agent for a retail dynamic pricing system.

Your responsibilities:
1. Execute approved price updates across all sales channels associated with a pricing scenario.
2. Track post-implementation KPIs including actual revenue, conversion rate, and margin against projected values from the pricing scenario.
3. Evaluate performance metrics at intervals no greater than 60 minutes.
4. Detect variances when actual performance deviates from projections beyond configured thresholds:
   - Revenue variance threshold: 10% (relative)
   - Margin variance threshold: 3 percentage points (absolute)
5. When variance is detected, generate adjustment recommendations including:
   - The specific metric that deviated
   - The magnitude of deviation
   - Possible contributing factors
   - 2-3 recommended corrective actions

When executing price updates:
- Update prices in the Products DynamoDB table for each product in the scenario.
- Record the previous price and update timestamp.
- Confirm successful updates across all channels.

When tracking KPIs:
- Compare actual revenue against projected revenue from the scenario.
- Compare actual margin against projected margin.
- Track conversion rate changes.
- Report status to the Dashboard at intervals no greater than 30 seconds during active monitoring.

When variance is detected:
- Use the detect_variance tool to check thresholds.
- If thresholds are breached, use generate_adjustment tool to create recommendations.
- Route adjustment recommendations to the Product Manager via the Dashboard.

Always provide clear, data-driven analysis with specific numbers and percentages."""


def _get_dynamodb_resource():
    """Get a DynamoDB resource, allowing for test injection."""
    return boto3.resource("dynamodb", region_name=AWS_REGION)


@tool
def execute_price_update(
    scenario_id: str,
    cycle_id: str,
    price_changes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Execute price updates in the DynamoDB Products table for an approved scenario.

    Updates the current price for each product specified in the pricing scenario,
    records the previous price, and sets the update timestamp.

    Args:
        scenario_id: The unique identifier of the approved pricing scenario.
        cycle_id: The parent pricing cycle identifier.
        price_changes: List of price change objects, each containing:
            - productId: The product identifier
            - currentPrice: The current price (before update)
            - newPrice: The new price to set
            - changePercent: The percentage change

    Returns:
        Dictionary with update results including success count, failures, and details.
    """
    dynamodb = _get_dynamodb_resource()
    table = dynamodb.Table(PRODUCTS_TABLE)

    results = {
        "scenario_id": scenario_id,
        "cycle_id": cycle_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_updates": len(price_changes),
        "successful": 0,
        "failed": 0,
        "details": [],
    }

    for change in price_changes:
        product_id = change.get("productId", change.get("product_id"))
        new_price = change.get("newPrice", change.get("new_price"))
        current_price = change.get("currentPrice", change.get("current_price"))

        if not product_id or new_price is None:
            results["failed"] += 1
            results["details"].append({
                "productId": product_id,
                "status": "failed",
                "reason": "Missing productId or newPrice",
            })
            continue

        try:
            table.update_item(
                Key={"productId": product_id},
                UpdateExpression=(
                    "SET currentPrice = :new_price, "
                    "previousPrice = :prev_price, "
                    "priceUpdatedAt = :updated_at"
                ),
                ExpressionAttributeValues={
                    ":new_price": str(round(new_price, 4)),
                    ":prev_price": str(round(current_price, 4)) if current_price else "0",
                    ":updated_at": datetime.now(timezone.utc).isoformat(),
                },
                ReturnValues="UPDATED_NEW",
            )
            results["successful"] += 1
            results["details"].append({
                "productId": product_id,
                "status": "success",
                "previousPrice": current_price,
                "newPrice": new_price,
            })
            logger.info(
                "Updated price for product %s: %s -> %s",
                product_id,
                current_price,
                new_price,
            )
        except Exception as e:
            results["failed"] += 1
            results["details"].append({
                "productId": product_id,
                "status": "failed",
                "reason": str(e),
            })
            logger.error("Failed to update price for product %s: %s", product_id, e)

    return results


@tool
def track_kpis(
    scenario_id: str,
    actual_revenue: float,
    actual_margin: float,
    actual_conversion_rate: float,
    projected_revenue: float,
    projected_margin: float,
    projected_conversion_rate: float,
) -> dict[str, Any]:
    """Track KPIs by comparing actual vs projected metrics for an implemented scenario.

    Evaluates performance metrics and compares actual results against the
    projected values from the pricing scenario.

    Args:
        scenario_id: The scenario being monitored.
        actual_revenue: Actual revenue observed since implementation.
        actual_margin: Actual margin observed (as decimal, e.g. 0.25 for 25%).
        actual_conversion_rate: Actual conversion rate (as decimal).
        projected_revenue: Revenue projected by the pricing scenario.
        projected_margin: Margin projected by the pricing scenario (as decimal).
        projected_conversion_rate: Conversion rate projected by the scenario.

    Returns:
        Dictionary with KPI comparison results including variances and status.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Calculate variances
    revenue_variance = (
        abs(actual_revenue - projected_revenue) / abs(projected_revenue)
        if projected_revenue != 0
        else 0.0
    )
    margin_variance = abs(actual_margin - projected_margin)
    conversion_variance = (
        abs(actual_conversion_rate - projected_conversion_rate)
        / abs(projected_conversion_rate)
        if projected_conversion_rate != 0
        else 0.0
    )

    # Determine direction
    revenue_direction = "above" if actual_revenue >= projected_revenue else "below"
    margin_direction = "above" if actual_margin >= projected_margin else "below"
    conversion_direction = (
        "above" if actual_conversion_rate >= projected_conversion_rate else "below"
    )

    kpi_report = {
        "scenario_id": scenario_id,
        "timestamp": timestamp,
        "monitoring_interval_minutes": MONITORING_INTERVAL_MINUTES,
        "metrics": {
            "revenue": {
                "actual": round(actual_revenue, 4),
                "projected": round(projected_revenue, 4),
                "variance_percent": round(revenue_variance * 100, 2),
                "direction": revenue_direction,
                "threshold_percent": REVENUE_VARIANCE_THRESHOLD * 100,
                "threshold_breached": revenue_variance > REVENUE_VARIANCE_THRESHOLD,
            },
            "margin": {
                "actual": round(actual_margin, 4),
                "projected": round(projected_margin, 4),
                "variance_pp": round(margin_variance * 100, 2),
                "direction": margin_direction,
                "threshold_pp": MARGIN_VARIANCE_THRESHOLD * 100,
                "threshold_breached": margin_variance > MARGIN_VARIANCE_THRESHOLD,
            },
            "conversion_rate": {
                "actual": round(actual_conversion_rate, 4),
                "projected": round(projected_conversion_rate, 4),
                "variance_percent": round(conversion_variance * 100, 2),
                "direction": conversion_direction,
            },
        },
        "overall_status": "on_track",
    }

    # Determine overall status
    if (
        kpi_report["metrics"]["revenue"]["threshold_breached"]
        or kpi_report["metrics"]["margin"]["threshold_breached"]
    ):
        kpi_report["overall_status"] = "variance_detected"

    return kpi_report


@tool
def detect_performance_variance(
    actual_revenue: float,
    projected_revenue: float,
    actual_margin: float,
    projected_margin: float,
    revenue_threshold: float = REVENUE_VARIANCE_THRESHOLD,
    margin_threshold: float = MARGIN_VARIANCE_THRESHOLD,
) -> dict[str, Any]:
    """Detect performance variance using the shared variance detection module.

    Uses configurable thresholds to determine if actual performance has deviated
    significantly from projections. Default thresholds: 10% revenue, 3pp margin.

    Args:
        actual_revenue: Actual revenue observed.
        projected_revenue: Revenue projected by the pricing scenario.
        actual_margin: Actual margin observed (as decimal, e.g. 0.25 for 25%).
        projected_margin: Projected margin (as decimal).
        revenue_threshold: Relative threshold for revenue variance (default 0.10).
        margin_threshold: Absolute threshold for margin variance (default 0.03).

    Returns:
        Dictionary with variance detection results including whether variance
        was detected, which thresholds were breached, and a recommendation.
    """
    try:
        result: VarianceResult = detect_variance(
            actual_revenue=actual_revenue,
            projected_revenue=projected_revenue,
            actual_margin=actual_margin,
            projected_margin=projected_margin,
            revenue_threshold=revenue_threshold,
            margin_threshold=margin_threshold,
        )
    except ValueError as e:
        return {
            "error": str(e),
            "variance_detected": False,
        }

    return {
        "variance_detected": result.variance_detected,
        "revenue_variance": round(result.revenue_variance, 4),
        "margin_variance": round(result.margin_variance, 4),
        "breached_thresholds": result.breached_thresholds,
        "recommendation": result.recommendation,
        "thresholds_used": {
            "revenue_threshold": revenue_threshold,
            "margin_threshold": margin_threshold,
        },
    }


@tool
def generate_adjustment(
    scenario_id: str,
    deviated_metric: str,
    deviation_magnitude: float,
    actual_value: float,
    projected_value: float,
    contributing_factors: list[str] | None = None,
) -> dict[str, Any]:
    """Generate an adjustment recommendation when performance variance is detected.

    Creates a structured recommendation with the specific metric that deviated,
    magnitude of deviation, possible contributing factors, and 2-3 corrective actions.

    Args:
        scenario_id: The scenario experiencing variance.
        deviated_metric: The metric that deviated (e.g., "revenue", "margin").
        deviation_magnitude: The magnitude of deviation (as decimal for percentage).
        actual_value: The actual observed value.
        projected_value: The projected value from the scenario.
        contributing_factors: Optional list of possible contributing factors.

    Returns:
        Dictionary with the adjustment recommendation including corrective actions.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Determine direction
    direction = "below" if actual_value < projected_value else "above"

    # Default contributing factors if none provided
    if not contributing_factors:
        contributing_factors = _infer_contributing_factors(
            deviated_metric, direction, deviation_magnitude
        )

    # Generate corrective actions based on the deviation
    corrective_actions = _generate_corrective_actions(
        deviated_metric, direction, deviation_magnitude
    )

    recommendation = {
        "scenario_id": scenario_id,
        "timestamp": timestamp,
        "deviated_metric": deviated_metric,
        "deviation": {
            "magnitude": round(deviation_magnitude, 4),
            "direction": direction,
            "actual_value": round(actual_value, 4),
            "projected_value": round(projected_value, 4),
        },
        "contributing_factors": contributing_factors,
        "corrective_actions": corrective_actions,
        "urgency": _assess_urgency(deviation_magnitude, deviated_metric),
        "requires_approval": True,
        "abbreviated_cycle": True,  # Bypass full parallel analysis phase
    }

    logger.info(
        "Generated adjustment recommendation for scenario %s: %s %s by %.2f%%",
        scenario_id,
        deviated_metric,
        direction,
        deviation_magnitude * 100,
    )

    return recommendation


def _infer_contributing_factors(
    metric: str, direction: str, magnitude: float
) -> list[str]:
    """Infer possible contributing factors based on the deviation pattern."""
    factors = []

    if metric == "revenue":
        if direction == "below":
            factors = [
                "Competitor price reduction may have shifted demand",
                "Seasonal demand patterns not fully captured in projection",
                "Customer price sensitivity higher than estimated",
            ]
        else:
            factors = [
                "Competitor stock-out driving additional demand",
                "Market demand growth exceeding projections",
                "Price elasticity lower than estimated (inelastic demand)",
            ]
    elif metric == "margin":
        if direction == "below":
            factors = [
                "Input cost increases not reflected in projections",
                "Higher promotional discount utilization than expected",
                "Channel mix shift toward lower-margin channels",
            ]
        else:
            factors = [
                "Supply chain cost reductions realized faster than projected",
                "Channel mix shift toward higher-margin channels",
                "Lower return rate than projected",
            ]
    else:
        factors = [
            "Market conditions changed since scenario generation",
            "External factors not captured in original analysis",
            "Model assumptions may need recalibration",
        ]

    return factors


def _generate_corrective_actions(
    metric: str, direction: str, magnitude: float
) -> list[dict[str, str]]:
    """Generate 2-3 corrective actions based on the deviation."""
    actions = []

    if metric == "revenue":
        if direction == "below":
            actions = [
                {
                    "action": "Reduce price by 2-3% to stimulate demand",
                    "expected_impact": "Recover projected volume within 48-72 hours",
                    "risk": "Low - within original scenario bounds",
                },
                {
                    "action": "Increase promotional visibility on high-traffic channels",
                    "expected_impact": "Boost conversion rate by 5-10%",
                    "risk": "Low - no price change required",
                },
                {
                    "action": "Bundle with complementary products at slight discount",
                    "expected_impact": "Increase average order value by 8-12%",
                    "risk": "Medium - may affect margin on bundled items",
                },
            ]
        else:
            actions = [
                {
                    "action": "Maintain current pricing to capture upside",
                    "expected_impact": "Continue above-projection revenue",
                    "risk": "Low - no change needed",
                },
                {
                    "action": "Increase price by 1-2% to optimize margin",
                    "expected_impact": "Improve margin while maintaining demand",
                    "risk": "Medium - may reduce volume slightly",
                },
            ]
    elif metric == "margin":
        if direction == "below":
            actions = [
                {
                    "action": "Increase price by 1-2% to restore target margin",
                    "expected_impact": "Restore margin within 1-2 percentage points of target",
                    "risk": "Medium - may reduce conversion rate",
                },
                {
                    "action": "Shift promotional spend to higher-margin channels",
                    "expected_impact": "Improve blended margin by 0.5-1 percentage points",
                    "risk": "Low - reallocation only",
                },
                {
                    "action": "Review and renegotiate supplier costs",
                    "expected_impact": "Reduce COGS by 2-5% within 30 days",
                    "risk": "Low - no customer-facing change",
                },
            ]
        else:
            actions = [
                {
                    "action": "Maintain current pricing to preserve margin upside",
                    "expected_impact": "Continue above-projection margin",
                    "risk": "Low - no change needed",
                },
                {
                    "action": "Consider slight price reduction to drive volume",
                    "expected_impact": "Increase revenue while maintaining acceptable margin",
                    "risk": "Low - margin still above target",
                },
            ]
    else:
        actions = [
            {
                "action": "Initiate abbreviated pricing cycle for reassessment",
                "expected_impact": "Updated scenario within 24 hours",
                "risk": "Low - data-driven adjustment",
            },
            {
                "action": "Increase monitoring frequency to 30-minute intervals",
                "expected_impact": "Earlier detection of further deviations",
                "risk": "Low - observability only",
            },
        ]

    return actions


def _assess_urgency(magnitude: float, metric: str) -> str:
    """Assess the urgency of the adjustment based on deviation magnitude."""
    if metric == "revenue":
        if magnitude > 0.20:
            return "high"
        elif magnitude > 0.10:
            return "medium"
        else:
            return "low"
    elif metric == "margin":
        if magnitude > 0.05:
            return "high"
        elif magnitude > 0.03:
            return "medium"
        else:
            return "low"
    return "medium"


def create_implementation_monitoring_agent() -> Agent:
    """Create and configure the Implementation Monitoring Agent.

    Returns an Agent instance configured with:
    - Model: us.anthropic.claude-sonnet-4-6
    - System prompt for implementation monitoring
    - Tools: execute_price_update, track_kpis, detect_performance_variance,
             generate_adjustment

    Returns:
        Configured Strands Agent for implementation monitoring.
    """
    agent = Agent(
        model=SPECIALIST_MODEL,
        system_prompt=IMPLEMENTATION_MONITORING_SYSTEM_PROMPT,
        tools=[
            execute_price_update,
            track_kpis,
            detect_performance_variance,
            generate_adjustment,
        ],
    )

    return agent
