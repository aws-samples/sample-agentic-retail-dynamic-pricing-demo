"""Scenario ranking module for calculating composite business impact scores.

Implements ranking of pricing scenarios by a weighted composite score derived
from projected revenue, margin, and market share metrics. Scenarios are sorted
descending by composite score and assigned contiguous ranks from 1 to N.

Validates: Requirements 3.2
"""

from typing import Any


# Default weights for composite score calculation
DEFAULT_REVENUE_WEIGHT = 0.4
DEFAULT_MARGIN_WEIGHT = 0.35
DEFAULT_MARKET_SHARE_WEIGHT = 0.25


def calculate_composite_score(
    projected_revenue: float,
    projected_margin: float,
    projected_market_share: float | None = None,
    revenue_weight: float = DEFAULT_REVENUE_WEIGHT,
    margin_weight: float = DEFAULT_MARGIN_WEIGHT,
    market_share_weight: float = DEFAULT_MARKET_SHARE_WEIGHT,
) -> float:
    """Calculate the composite business impact score for a scenario.

    The composite score is a weighted combination of projected revenue,
    margin, and market share. If market share is None, it is treated as 0.

    Args:
        projected_revenue: Projected revenue impact.
        projected_margin: Projected margin.
        projected_market_share: Projected market share change (optional).
        revenue_weight: Weight for revenue component (default 0.4).
        margin_weight: Weight for margin component (default 0.35).
        market_share_weight: Weight for market share component (default 0.25).

    Returns:
        The weighted composite score.
    """
    market_share_value = projected_market_share if projected_market_share is not None else 0.0

    return (
        revenue_weight * projected_revenue
        + margin_weight * projected_margin
        + market_share_weight * market_share_value
    )


def rank_scenarios(
    scenarios: list[dict[str, Any]],
    revenue_weight: float = DEFAULT_REVENUE_WEIGHT,
    margin_weight: float = DEFAULT_MARGIN_WEIGHT,
    market_share_weight: float = DEFAULT_MARKET_SHARE_WEIGHT,
) -> list[dict[str, Any]]:
    """Rank pricing scenarios by composite business impact score.

    Calculates a composite score for each scenario, sorts them in descending
    order (highest score first), and assigns contiguous ranks from 1 to N.

    Accepts scenario dicts using either camelCase or snake_case field names.

    Args:
        scenarios: List of scenario dictionaries with projected revenue,
            margin, and optionally market share fields.
        revenue_weight: Weight for revenue component (default 0.4).
        margin_weight: Weight for margin component (default 0.35).
        market_share_weight: Weight for market share component (default 0.25).

    Returns:
        A new list of scenario dictionaries sorted by composite score
        descending, with 'compositeScore' and 'rank' fields set.
        Rank 1 is the best (highest composite score).
    """
    scored_scenarios = []
    for scenario in scenarios:
        # Support both camelCase and snake_case field names
        revenue = scenario.get("projectedRevenue", scenario.get("projected_revenue", 0.0))
        margin = scenario.get("projectedMargin", scenario.get("projected_margin", 0.0))
        market_share = scenario.get(
            "projectedMarketShare", scenario.get("projected_market_share")
        )

        composite = calculate_composite_score(
            projected_revenue=revenue,
            projected_margin=margin,
            projected_market_share=market_share,
            revenue_weight=revenue_weight,
            margin_weight=margin_weight,
            market_share_weight=market_share_weight,
        )

        # Create a copy with the composite score set
        ranked = dict(scenario)
        ranked["compositeScore"] = composite
        scored_scenarios.append(ranked)

    # Sort by composite score descending (highest first)
    scored_scenarios.sort(key=lambda s: s["compositeScore"], reverse=True)

    # Assign contiguous ranks from 1 to N
    for i, scenario in enumerate(scored_scenarios, start=1):
        scenario["rank"] = i

    return scored_scenarios
