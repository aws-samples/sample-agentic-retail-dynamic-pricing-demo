"""Property-based tests for variance detection.

Property 14: Variance detection triggers adjustment correctly.

For any pair of actual and projected values:
- variance_detected is True IF AND ONLY IF revenue_variance > threshold OR margin_variance > threshold
- When variance_detected is True, recommendation must not be None
- When variance_detected is False, recommendation must be None
- breached_thresholds must contain "revenue" iff revenue_variance > revenue_threshold
- breached_thresholds must contain "margin" iff margin_variance > margin_threshold

**Validates: Requirements 9.3**
"""

from hypothesis import given, settings, assume
from hypothesis.strategies import floats

from shared.variance_detection import detect_variance


# Strategies for realistic financial values
# Revenue values: positive, non-zero, finite
revenue_values = floats(min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False)
# Margin values: between -1 and 1 (percentage as decimal)
margin_values = floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)
# Threshold values: positive, non-zero, finite
threshold_values = floats(min_value=0.001, max_value=1.0, allow_nan=False, allow_infinity=False)


@settings(max_examples=100)
@given(
    actual_revenue=revenue_values,
    projected_revenue=revenue_values,
    actual_margin=margin_values,
    projected_margin=margin_values,
    revenue_threshold=threshold_values,
    margin_threshold=threshold_values,
)
def test_variance_detection_triggers_adjustment_correctly(
    actual_revenue: float,
    projected_revenue: float,
    actual_margin: float,
    projected_margin: float,
    revenue_threshold: float,
    margin_threshold: float,
) -> None:
    """Property 14: Variance detection triggers adjustment correctly.

    **Validates: Requirements 9.3**
    """
    # projected_revenue must be non-zero (function raises ValueError otherwise)
    assume(projected_revenue != 0.0)

    result = detect_variance(
        actual_revenue=actual_revenue,
        projected_revenue=projected_revenue,
        actual_margin=actual_margin,
        projected_margin=projected_margin,
        revenue_threshold=revenue_threshold,
        margin_threshold=margin_threshold,
    )

    # Compute expected variances
    expected_revenue_variance = abs(actual_revenue - projected_revenue) / abs(projected_revenue)
    expected_margin_variance = abs(actual_margin - projected_margin)

    # Check revenue_variance and margin_variance are computed correctly
    assert abs(result.revenue_variance - expected_revenue_variance) < 1e-9, (
        f"Revenue variance mismatch: got {result.revenue_variance}, expected {expected_revenue_variance}"
    )
    assert abs(result.margin_variance - expected_margin_variance) < 1e-9, (
        f"Margin variance mismatch: got {result.margin_variance}, expected {expected_margin_variance}"
    )

    # Property: breached_thresholds contains "revenue" iff revenue_variance > revenue_threshold
    revenue_breached = expected_revenue_variance > revenue_threshold
    assert ("revenue" in result.breached_thresholds) == revenue_breached, (
        f"revenue in breached_thresholds={result.breached_thresholds} but "
        f"revenue_variance={expected_revenue_variance}, threshold={revenue_threshold}"
    )

    # Property: breached_thresholds contains "margin" iff margin_variance > margin_threshold
    margin_breached = expected_margin_variance > margin_threshold
    assert ("margin" in result.breached_thresholds) == margin_breached, (
        f"margin in breached_thresholds={result.breached_thresholds} but "
        f"margin_variance={expected_margin_variance}, threshold={margin_threshold}"
    )

    # Property: variance_detected is True IFF revenue_variance > threshold OR margin_variance > threshold
    expected_detected = revenue_breached or margin_breached
    assert result.variance_detected == expected_detected, (
        f"variance_detected={result.variance_detected} but expected {expected_detected} "
        f"(revenue_breached={revenue_breached}, margin_breached={margin_breached})"
    )

    # Property: When variance_detected is True, recommendation must not be None
    if result.variance_detected:
        assert result.recommendation is not None, (
            "variance_detected is True but recommendation is None"
        )

    # Property: When variance_detected is False, recommendation must be None
    if not result.variance_detected:
        assert result.recommendation is None, (
            f"variance_detected is False but recommendation is not None: {result.recommendation}"
        )
