"""Unit tests for the risk classification function.

Tests the classify_risk function against the threshold rules defined in
Requirements 7.4 and 3.7.
"""

import pytest

from shared.models.pricing_scenario import RiskLevel, StatusLabel
from shared.risk_classification import classify_risk


class TestLowRisk:
    """Tests for LOW risk classification: price change ≤5% AND margin impact ≤2pp."""

    def test_zero_change(self):
        risk, status = classify_risk(0.0, 0.0)
        assert risk == RiskLevel.LOW
        assert status == StatusLabel.RECOMMENDED

    def test_at_boundary(self):
        """Exactly 5% price change and 2pp margin impact should be LOW."""
        risk, status = classify_risk(5.0, 2.0)
        assert risk == RiskLevel.LOW
        assert status == StatusLabel.RECOMMENDED

    def test_small_changes(self):
        risk, status = classify_risk(2.5, 1.0)
        assert risk == RiskLevel.LOW
        assert status == StatusLabel.RECOMMENDED

    def test_negative_values_within_bounds(self):
        """Negative price change (price decrease) within bounds is LOW."""
        risk, status = classify_risk(-3.0, -1.5)
        assert risk == RiskLevel.LOW
        assert status == StatusLabel.RECOMMENDED

    def test_with_small_deviation(self):
        """Small deviation from 90-day avg doesn't affect LOW classification."""
        risk, status = classify_risk(3.0, 1.0, 10.0)
        assert risk == RiskLevel.LOW
        assert status == StatusLabel.RECOMMENDED


class TestMediumRisk:
    """Tests for MEDIUM risk: price change 5-15% OR margin impact 2-5pp."""

    def test_price_change_just_above_5(self):
        risk, status = classify_risk(5.1, 1.0)
        assert risk == RiskLevel.MEDIUM
        assert status == StatusLabel.REVIEW_REQUIRED

    def test_margin_impact_just_above_2(self):
        risk, status = classify_risk(3.0, 2.1)
        assert risk == RiskLevel.MEDIUM
        assert status == StatusLabel.REVIEW_REQUIRED

    def test_price_change_at_15(self):
        """15% price change is within MEDIUM range (not exceeding 15%)."""
        risk, status = classify_risk(15.0, 1.0)
        assert risk == RiskLevel.MEDIUM
        assert status == StatusLabel.REVIEW_REQUIRED

    def test_margin_impact_at_5(self):
        """5pp margin impact is within MEDIUM range (not exceeding 5pp)."""
        risk, status = classify_risk(3.0, 5.0)
        assert risk == RiskLevel.MEDIUM
        assert status == StatusLabel.REVIEW_REQUIRED

    def test_both_in_medium_range(self):
        risk, status = classify_risk(10.0, 3.5)
        assert risk == RiskLevel.MEDIUM
        assert status == StatusLabel.REVIEW_REQUIRED

    def test_negative_price_change_medium(self):
        """Negative price change exceeding 5% triggers MEDIUM."""
        risk, status = classify_risk(-8.0, 1.0)
        assert risk == RiskLevel.MEDIUM
        assert status == StatusLabel.REVIEW_REQUIRED

    def test_deviation_at_20_with_low_others(self):
        """20% deviation from 90-day avg is at boundary, not exceeding."""
        risk, status = classify_risk(3.0, 1.0, 20.0)
        assert risk == RiskLevel.LOW
        assert status == StatusLabel.RECOMMENDED


class TestHighRisk:
    """Tests for HIGH risk: price change >15% OR margin impact >5pp OR >20% deviation."""

    def test_price_change_above_15(self):
        risk, status = classify_risk(15.1, 1.0)
        assert risk == RiskLevel.HIGH
        assert status == StatusLabel.HUMAN_EXCEPTION_HANDLING

    def test_margin_impact_above_5(self):
        risk, status = classify_risk(3.0, 5.1)
        assert risk == RiskLevel.HIGH
        assert status == StatusLabel.HUMAN_EXCEPTION_HANDLING

    def test_deviation_above_20(self):
        risk, status = classify_risk(3.0, 1.0, 20.1)
        assert risk == RiskLevel.HIGH
        assert status == StatusLabel.HUMAN_EXCEPTION_HANDLING

    def test_large_price_change(self):
        risk, status = classify_risk(50.0, 1.0)
        assert risk == RiskLevel.HIGH
        assert status == StatusLabel.HUMAN_EXCEPTION_HANDLING

    def test_large_margin_impact(self):
        risk, status = classify_risk(3.0, 10.0)
        assert risk == RiskLevel.HIGH
        assert status == StatusLabel.HUMAN_EXCEPTION_HANDLING

    def test_large_deviation(self):
        risk, status = classify_risk(3.0, 1.0, 50.0)
        assert risk == RiskLevel.HIGH
        assert status == StatusLabel.HUMAN_EXCEPTION_HANDLING

    def test_all_high_triggers(self):
        """All three criteria exceed HIGH thresholds."""
        risk, status = classify_risk(20.0, 8.0, 30.0)
        assert risk == RiskLevel.HIGH
        assert status == StatusLabel.HUMAN_EXCEPTION_HANDLING

    def test_negative_large_price_change(self):
        """Large negative price change triggers HIGH."""
        risk, status = classify_risk(-20.0, 1.0)
        assert risk == RiskLevel.HIGH
        assert status == StatusLabel.HUMAN_EXCEPTION_HANDLING

    def test_negative_large_deviation(self):
        """Large negative deviation triggers HIGH."""
        risk, status = classify_risk(3.0, 1.0, -25.0)
        assert risk == RiskLevel.HIGH
        assert status == StatusLabel.HUMAN_EXCEPTION_HANDLING


class TestStatusLabelMapping:
    """Tests that risk levels correctly map to status labels."""

    def test_low_maps_to_recommended(self):
        _, status = classify_risk(0.0, 0.0)
        assert status == StatusLabel.RECOMMENDED
        assert status.value == "Recommended"

    def test_medium_maps_to_review_required(self):
        _, status = classify_risk(10.0, 0.0)
        assert status == StatusLabel.REVIEW_REQUIRED
        assert status.value == "Review Required"

    def test_high_maps_to_human_exception_handling(self):
        _, status = classify_risk(20.0, 0.0)
        assert status == StatusLabel.HUMAN_EXCEPTION_HANDLING
        assert status.value == "Human Exception Handling"


class TestDefaultDeviation:
    """Tests that deviation_from_90day_avg defaults to 0."""

    def test_default_deviation_does_not_affect_low(self):
        risk, _ = classify_risk(3.0, 1.0)
        assert risk == RiskLevel.LOW

    def test_default_deviation_does_not_affect_medium(self):
        risk, _ = classify_risk(10.0, 1.0)
        assert risk == RiskLevel.MEDIUM

    def test_explicit_zero_deviation_same_as_default(self):
        result_default = classify_risk(10.0, 3.0)
        result_explicit = classify_risk(10.0, 3.0, 0.0)
        assert result_default == result_explicit
