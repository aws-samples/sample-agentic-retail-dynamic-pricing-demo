"""Risk classification function for pricing scenarios.

Classifies pricing scenarios into risk levels based on price change magnitude,
margin impact, and deviation from historical pricing. Maps risk levels to
approval status labels.

Validates: Requirements 7.4, 3.7
"""

from shared.models.pricing_scenario import RiskLevel, StatusLabel


# Risk level to status label mapping
_RISK_TO_STATUS: dict[RiskLevel, StatusLabel] = {
    RiskLevel.LOW: StatusLabel.RECOMMENDED,
    RiskLevel.MEDIUM: StatusLabel.REVIEW_REQUIRED,
    RiskLevel.HIGH: StatusLabel.HUMAN_EXCEPTION_HANDLING,
}


def classify_risk(
    price_change_percent: float,
    margin_impact_pp: float,
    deviation_from_90day_avg: float = 0.0,
) -> tuple[RiskLevel, StatusLabel]:
    """Classify a pricing scenario's risk level and determine its status label.

    Risk classification rules:
    - HIGH: price change >15% OR margin impact >5pp OR >20% deviation from 90-day avg
    - MEDIUM: price change 5-15% OR margin impact 2-5pp
    - LOW: price change ≤5% AND margin impact ≤2pp

    Args:
        price_change_percent: Absolute percentage change in price (e.g., 10.0 for 10%).
        margin_impact_pp: Absolute margin impact in percentage points (e.g., 3.0 for 3pp).
        deviation_from_90day_avg: Absolute percentage deviation from 90-day historical
            average price (e.g., 25.0 for 25%). Defaults to 0.0.

    Returns:
        A tuple of (RiskLevel, StatusLabel) where:
        - LOW → "Recommended"
        - MEDIUM → "Review Required"
        - HIGH → "Human Exception Handling"
    """
    abs_price_change = abs(price_change_percent)
    abs_margin_impact = abs(margin_impact_pp)
    abs_deviation = abs(deviation_from_90day_avg)

    # Check HIGH risk first (most restrictive)
    if abs_price_change > 15.0 or abs_margin_impact > 5.0 or abs_deviation > 20.0:
        risk_level = RiskLevel.HIGH
    # Check MEDIUM risk
    elif abs_price_change > 5.0 or abs_margin_impact > 2.0:
        risk_level = RiskLevel.MEDIUM
    # Default to LOW risk
    else:
        risk_level = RiskLevel.LOW

    return risk_level, _RISK_TO_STATUS[risk_level]
