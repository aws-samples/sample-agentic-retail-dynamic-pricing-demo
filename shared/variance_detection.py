"""Variance detection for the Implementation Monitoring Agent.

Compares actual vs. projected performance metrics and generates adjustment
recommendations when configurable thresholds are breached.

Validates: Requirements 9.3
"""

from dataclasses import dataclass, field


# Default thresholds
REVENUE_VARIANCE_THRESHOLD = 0.10  # 10% variance on revenue
MARGIN_VARIANCE_THRESHOLD = 0.03  # 3 percentage points on margin


@dataclass(frozen=True)
class VarianceResult:
    """Result of a variance detection check.

    Attributes:
        variance_detected: Whether any threshold was breached.
        revenue_variance: The relative variance between actual and projected revenue.
        margin_variance: The absolute difference between actual and projected margin.
        breached_thresholds: List of threshold names that were breached.
        recommendation: Adjustment recommendation text, or None if no variance detected.
    """

    variance_detected: bool
    revenue_variance: float
    margin_variance: float
    breached_thresholds: list[str] = field(default_factory=list)
    recommendation: str | None = None


def detect_variance(
    actual_revenue: float,
    projected_revenue: float,
    actual_margin: float,
    projected_margin: float,
    revenue_threshold: float = REVENUE_VARIANCE_THRESHOLD,
    margin_threshold: float = MARGIN_VARIANCE_THRESHOLD,
) -> VarianceResult:
    """Detect performance variance between actual and projected metrics.

    Compares actual vs. projected revenue (relative variance) and actual vs.
    projected margin (absolute difference in percentage points). Returns an
    adjustment recommendation when thresholds are breached.

    Args:
        actual_revenue: Actual revenue observed.
        projected_revenue: Revenue that was projected by the pricing scenario.
        actual_margin: Actual margin observed (as a decimal, e.g. 0.25 for 25%).
        projected_margin: Projected margin (as a decimal, e.g. 0.25 for 25%).
        revenue_threshold: Relative threshold for revenue variance (default 0.10).
        margin_threshold: Absolute threshold for margin variance in percentage
            points (default 0.03).

    Returns:
        VarianceResult with detection outcome and recommendation.

    Raises:
        ValueError: If projected_revenue is zero (cannot compute relative variance).
    """
    if projected_revenue == 0:
        raise ValueError("projected_revenue cannot be zero")

    # Revenue variance: |actual - projected| / |projected|
    revenue_variance = abs(actual_revenue - projected_revenue) / abs(projected_revenue)

    # Margin variance: absolute difference in percentage points
    margin_variance = abs(actual_margin - projected_margin)

    breached: list[str] = []

    if revenue_variance > revenue_threshold:
        breached.append("revenue")

    if margin_variance > margin_threshold:
        breached.append("margin")

    variance_detected = len(breached) > 0

    recommendation: str | None = None
    if variance_detected:
        recommendation = _build_recommendation(
            actual_revenue=actual_revenue,
            projected_revenue=projected_revenue,
            actual_margin=actual_margin,
            projected_margin=projected_margin,
            revenue_variance=revenue_variance,
            margin_variance=margin_variance,
            breached_thresholds=breached,
        )

    return VarianceResult(
        variance_detected=variance_detected,
        revenue_variance=revenue_variance,
        margin_variance=margin_variance,
        breached_thresholds=breached,
        recommendation=recommendation,
    )


def _build_recommendation(
    actual_revenue: float,
    projected_revenue: float,
    actual_margin: float,
    projected_margin: float,
    revenue_variance: float,
    margin_variance: float,
    breached_thresholds: list[str],
) -> str:
    """Build a human-readable adjustment recommendation."""
    parts: list[str] = ["Performance variance detected."]

    if "revenue" in breached_thresholds:
        direction = "below" if actual_revenue < projected_revenue else "above"
        parts.append(
            f"Revenue is {revenue_variance:.1%} {direction} projection "
            f"(actual: {actual_revenue:.2f}, projected: {projected_revenue:.2f})."
        )

    if "margin" in breached_thresholds:
        direction = "below" if actual_margin < projected_margin else "above"
        parts.append(
            f"Margin deviates by {margin_variance:.4f} percentage points {direction} projection "
            f"(actual: {actual_margin:.4f}, projected: {projected_margin:.4f})."
        )

    parts.append("Recommend initiating corrective pricing adjustment.")

    return " ".join(parts)
