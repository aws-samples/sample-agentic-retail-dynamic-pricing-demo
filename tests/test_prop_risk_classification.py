"""Property-based tests for risk classification function.

Property 9: Risk classification follows threshold rules.
For any inputs:
  - If abs(price_change) <= 5 AND abs(margin_impact) <= 2 AND abs(deviation) <= 20 → LOW
  - If abs(price_change) > 15 OR abs(margin_impact) > 5 OR abs(deviation) > 20 → HIGH
  - Otherwise → MEDIUM
Also verifies status label mapping: LOW→Recommended, MEDIUM→Review Required,
HIGH→Human Exception Handling.

Feature: retail-dynamic-pricing
Validates: Requirements 7.4
"""

import pytest
from hypothesis import given, settings
from hypothesis.strategies import floats

from shared.models.pricing_scenario import RiskLevel, StatusLabel
from shared.risk_classification import classify_risk

# Strategies for generating realistic price change, margin impact, and deviation values
# Using finite floats to avoid NaN/inf edge cases
reasonable_float = floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False)


class TestProperty9RiskClassificationThresholdRules:
    """Property 9: Risk classification follows threshold rules.

    Validates: Requirements 7.4
    """

    @given(
        price_change=floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        margin_impact=floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False),
        deviation=floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_low_risk_when_all_within_low_thresholds(
        self, price_change: float, margin_impact: float, deviation: float
    ):
        """If abs(price_change) <= 5 AND abs(margin_impact) <= 2 AND abs(deviation) <= 20,
        risk must be LOW with status Recommended."""
        risk, status = classify_risk(price_change, margin_impact, deviation)
        assert risk == RiskLevel.LOW, (
            f"Expected LOW for price_change={price_change}, "
            f"margin_impact={margin_impact}, deviation={deviation}, got {risk}"
        )
        assert status == StatusLabel.RECOMMENDED

    @given(
        price_change=floats(min_value=15.01, max_value=100.0, allow_nan=False, allow_infinity=False),
        margin_impact=reasonable_float,
        deviation=reasonable_float,
    )
    @settings(max_examples=100)
    def test_high_risk_when_price_change_exceeds_15(
        self, price_change: float, margin_impact: float, deviation: float
    ):
        """If abs(price_change) > 15, risk must be HIGH."""
        risk, status = classify_risk(price_change, margin_impact, deviation)
        assert risk == RiskLevel.HIGH, (
            f"Expected HIGH for price_change={price_change}, got {risk}"
        )
        assert status == StatusLabel.HUMAN_EXCEPTION_HANDLING

    @given(
        price_change=floats(min_value=-100.0, max_value=-15.01, allow_nan=False, allow_infinity=False),
        margin_impact=reasonable_float,
        deviation=reasonable_float,
    )
    @settings(max_examples=100)
    def test_high_risk_when_negative_price_change_exceeds_15(
        self, price_change: float, margin_impact: float, deviation: float
    ):
        """If abs(price_change) > 15 (negative direction), risk must be HIGH."""
        risk, status = classify_risk(price_change, margin_impact, deviation)
        assert risk == RiskLevel.HIGH, (
            f"Expected HIGH for price_change={price_change}, got {risk}"
        )
        assert status == StatusLabel.HUMAN_EXCEPTION_HANDLING

    @given(
        price_change=floats(min_value=-15.0, max_value=15.0, allow_nan=False, allow_infinity=False),
        margin_impact=floats(min_value=5.01, max_value=100.0, allow_nan=False, allow_infinity=False),
        deviation=reasonable_float,
    )
    @settings(max_examples=100)
    def test_high_risk_when_margin_impact_exceeds_5(
        self, price_change: float, margin_impact: float, deviation: float
    ):
        """If abs(margin_impact) > 5, risk must be HIGH."""
        risk, status = classify_risk(price_change, margin_impact, deviation)
        assert risk == RiskLevel.HIGH, (
            f"Expected HIGH for margin_impact={margin_impact}, got {risk}"
        )
        assert status == StatusLabel.HUMAN_EXCEPTION_HANDLING

    @given(
        price_change=floats(min_value=-15.0, max_value=15.0, allow_nan=False, allow_infinity=False),
        margin_impact=floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        deviation=floats(min_value=20.01, max_value=100.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_high_risk_when_deviation_exceeds_20(
        self, price_change: float, margin_impact: float, deviation: float
    ):
        """If abs(deviation) > 20, risk must be HIGH."""
        risk, status = classify_risk(price_change, margin_impact, deviation)
        assert risk == RiskLevel.HIGH, (
            f"Expected HIGH for deviation={deviation}, got {risk}"
        )
        assert status == StatusLabel.HUMAN_EXCEPTION_HANDLING

    @given(
        price_change=floats(min_value=5.01, max_value=15.0, allow_nan=False, allow_infinity=False),
        margin_impact=floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False),
        deviation=floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_medium_risk_when_price_change_between_5_and_15(
        self, price_change: float, margin_impact: float, deviation: float
    ):
        """If price_change is between 5 and 15 (exclusive) with other inputs in LOW range,
        risk must be MEDIUM."""
        risk, status = classify_risk(price_change, margin_impact, deviation)
        assert risk == RiskLevel.MEDIUM, (
            f"Expected MEDIUM for price_change={price_change}, "
            f"margin_impact={margin_impact}, deviation={deviation}, got {risk}"
        )
        assert status == StatusLabel.REVIEW_REQUIRED

    @given(
        price_change=floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        margin_impact=floats(min_value=2.01, max_value=5.0, allow_nan=False, allow_infinity=False),
        deviation=floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_medium_risk_when_margin_impact_between_2_and_5(
        self, price_change: float, margin_impact: float, deviation: float
    ):
        """If margin_impact is between 2 and 5 (exclusive) with price_change in LOW range,
        risk must be MEDIUM."""
        risk, status = classify_risk(price_change, margin_impact, deviation)
        assert risk == RiskLevel.MEDIUM, (
            f"Expected MEDIUM for price_change={price_change}, "
            f"margin_impact={margin_impact}, deviation={deviation}, got {risk}"
        )
        assert status == StatusLabel.REVIEW_REQUIRED

    @given(
        price_change=reasonable_float,
        margin_impact=reasonable_float,
        deviation=reasonable_float,
    )
    @settings(max_examples=100)
    def test_status_label_always_matches_risk_level(
        self, price_change: float, margin_impact: float, deviation: float
    ):
        """For any inputs, the status label must match the risk level:
        LOW→Recommended, MEDIUM→Review Required, HIGH→Human Exception Handling."""
        risk, status = classify_risk(price_change, margin_impact, deviation)

        expected_mapping = {
            RiskLevel.LOW: StatusLabel.RECOMMENDED,
            RiskLevel.MEDIUM: StatusLabel.REVIEW_REQUIRED,
            RiskLevel.HIGH: StatusLabel.HUMAN_EXCEPTION_HANDLING,
        }
        assert status == expected_mapping[risk], (
            f"Status {status} does not match risk level {risk}. "
            f"Expected {expected_mapping[risk]}"
        )

    @given(
        price_change=reasonable_float,
        margin_impact=reasonable_float,
        deviation=reasonable_float,
    )
    @settings(max_examples=100)
    def test_classification_is_exhaustive_and_deterministic(
        self, price_change: float, margin_impact: float, deviation: float
    ):
        """For any valid inputs, the function must return exactly one of
        LOW, MEDIUM, or HIGH — never anything else."""
        risk, status = classify_risk(price_change, margin_impact, deviation)
        assert risk in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH)
        assert status in (
            StatusLabel.RECOMMENDED,
            StatusLabel.REVIEW_REQUIRED,
            StatusLabel.HUMAN_EXCEPTION_HANDLING,
        )
