"""Unit tests for the variance detection function.

Tests the detect_variance function which compares actual vs. projected
performance metrics and triggers adjustment recommendations when thresholds
are breached.

Validates: Requirements 9.3
"""

import pytest

from shared.variance_detection import (
    MARGIN_VARIANCE_THRESHOLD,
    REVENUE_VARIANCE_THRESHOLD,
    VarianceResult,
    detect_variance,
)


class TestNoVarianceDetected:
    """Tests where actual metrics are within acceptable thresholds."""

    def test_exact_match_no_variance(self):
        result = detect_variance(
            actual_revenue=100000.0,
            projected_revenue=100000.0,
            actual_margin=0.25,
            projected_margin=0.25,
        )
        assert result.variance_detected is False
        assert result.revenue_variance == 0.0
        assert result.margin_variance == 0.0
        assert result.breached_thresholds == []
        assert result.recommendation is None

    def test_within_revenue_threshold(self):
        # 5% variance is below the 10% threshold
        result = detect_variance(
            actual_revenue=95000.0,
            projected_revenue=100000.0,
            actual_margin=0.25,
            projected_margin=0.25,
        )
        assert result.variance_detected is False
        assert result.revenue_variance == pytest.approx(0.05)
        assert result.breached_thresholds == []
        assert result.recommendation is None

    def test_within_margin_threshold(self):
        # 2pp variance is below the 3pp threshold
        result = detect_variance(
            actual_revenue=100000.0,
            projected_revenue=100000.0,
            actual_margin=0.23,
            projected_margin=0.25,
        )
        assert result.variance_detected is False
        assert result.margin_variance == pytest.approx(0.02)
        assert result.breached_thresholds == []
        assert result.recommendation is None

    def test_at_exact_revenue_threshold_no_breach(self):
        # Exactly at 10% is NOT a breach (threshold is >10%)
        result = detect_variance(
            actual_revenue=90000.0,
            projected_revenue=100000.0,
            actual_margin=0.25,
            projected_margin=0.25,
        )
        assert result.variance_detected is False
        assert result.revenue_variance == pytest.approx(0.10)
        assert result.breached_thresholds == []

    def test_at_exact_margin_threshold_no_breach(self):
        # Exactly at 3pp is NOT a breach (threshold is >3pp)
        result = detect_variance(
            actual_revenue=100000.0,
            projected_revenue=100000.0,
            actual_margin=0.22,
            projected_margin=0.25,
        )
        assert result.variance_detected is False
        assert result.margin_variance == pytest.approx(0.03)
        assert result.breached_thresholds == []


class TestRevenueVarianceDetected:
    """Tests where revenue variance exceeds the threshold."""

    def test_revenue_below_projection(self):
        # 15% below projection exceeds 10% threshold
        result = detect_variance(
            actual_revenue=85000.0,
            projected_revenue=100000.0,
            actual_margin=0.25,
            projected_margin=0.25,
        )
        assert result.variance_detected is True
        assert result.revenue_variance == pytest.approx(0.15)
        assert result.breached_thresholds == ["revenue"]
        assert result.recommendation is not None
        assert "Revenue" in result.recommendation
        assert "below" in result.recommendation

    def test_revenue_above_projection(self):
        # 20% above projection exceeds 10% threshold
        result = detect_variance(
            actual_revenue=120000.0,
            projected_revenue=100000.0,
            actual_margin=0.25,
            projected_margin=0.25,
        )
        assert result.variance_detected is True
        assert result.revenue_variance == pytest.approx(0.20)
        assert result.breached_thresholds == ["revenue"]
        assert "above" in result.recommendation

    def test_just_over_revenue_threshold(self):
        # Just barely over 10%
        result = detect_variance(
            actual_revenue=89999.0,
            projected_revenue=100000.0,
            actual_margin=0.25,
            projected_margin=0.25,
        )
        assert result.variance_detected is True
        assert result.revenue_variance > 0.10
        assert "revenue" in result.breached_thresholds


class TestMarginVarianceDetected:
    """Tests where margin variance exceeds the threshold."""

    def test_margin_below_projection(self):
        # 5pp below projection exceeds 3pp threshold
        result = detect_variance(
            actual_revenue=100000.0,
            projected_revenue=100000.0,
            actual_margin=0.20,
            projected_margin=0.25,
        )
        assert result.variance_detected is True
        assert result.margin_variance == pytest.approx(0.05)
        assert result.breached_thresholds == ["margin"]
        assert result.recommendation is not None
        assert "Margin" in result.recommendation
        assert "below" in result.recommendation

    def test_margin_above_projection(self):
        # 4pp above projection exceeds 3pp threshold
        result = detect_variance(
            actual_revenue=100000.0,
            projected_revenue=100000.0,
            actual_margin=0.29,
            projected_margin=0.25,
        )
        assert result.variance_detected is True
        assert result.margin_variance == pytest.approx(0.04)
        assert result.breached_thresholds == ["margin"]
        assert "above" in result.recommendation

    def test_just_over_margin_threshold(self):
        # Just barely over 3pp
        result = detect_variance(
            actual_revenue=100000.0,
            projected_revenue=100000.0,
            actual_margin=0.2199,
            projected_margin=0.25,
        )
        assert result.variance_detected is True
        assert result.margin_variance > 0.03
        assert "margin" in result.breached_thresholds


class TestBothThresholdsBreached:
    """Tests where both revenue and margin thresholds are breached."""

    def test_both_below_projection(self):
        result = detect_variance(
            actual_revenue=80000.0,
            projected_revenue=100000.0,
            actual_margin=0.18,
            projected_margin=0.25,
        )
        assert result.variance_detected is True
        assert result.revenue_variance == pytest.approx(0.20)
        assert result.margin_variance == pytest.approx(0.07)
        assert "revenue" in result.breached_thresholds
        assert "margin" in result.breached_thresholds
        assert result.recommendation is not None
        assert "Revenue" in result.recommendation
        assert "Margin" in result.recommendation

    def test_revenue_above_margin_below(self):
        result = detect_variance(
            actual_revenue=115000.0,
            projected_revenue=100000.0,
            actual_margin=0.20,
            projected_margin=0.25,
        )
        assert result.variance_detected is True
        assert "revenue" in result.breached_thresholds
        assert "margin" in result.breached_thresholds


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_zero_projected_revenue_raises_error(self):
        with pytest.raises(ValueError, match="projected_revenue cannot be zero"):
            detect_variance(
                actual_revenue=100000.0,
                projected_revenue=0.0,
                actual_margin=0.25,
                projected_margin=0.25,
            )

    def test_negative_revenue_values(self):
        # Negative revenue (loss) should still compute variance correctly
        result = detect_variance(
            actual_revenue=-5000.0,
            projected_revenue=100000.0,
            actual_margin=0.25,
            projected_margin=0.25,
        )
        assert result.variance_detected is True
        assert result.revenue_variance == pytest.approx(1.05)

    def test_very_small_projected_revenue(self):
        # Small projected revenue with proportionally small actual
        result = detect_variance(
            actual_revenue=1.0,
            projected_revenue=1.0,
            actual_margin=0.25,
            projected_margin=0.25,
        )
        assert result.variance_detected is False

    def test_zero_margin_values(self):
        result = detect_variance(
            actual_revenue=100000.0,
            projected_revenue=100000.0,
            actual_margin=0.0,
            projected_margin=0.0,
        )
        assert result.variance_detected is False
        assert result.margin_variance == 0.0

    def test_negative_margin_values(self):
        # Negative margins (losses) should still detect variance
        result = detect_variance(
            actual_revenue=100000.0,
            projected_revenue=100000.0,
            actual_margin=-0.05,
            projected_margin=0.25,
        )
        assert result.variance_detected is True
        assert result.margin_variance == pytest.approx(0.30)
        assert "margin" in result.breached_thresholds


class TestCustomThresholds:
    """Tests with custom threshold values."""

    def test_stricter_revenue_threshold(self):
        # 5% threshold instead of default 10%
        result = detect_variance(
            actual_revenue=93000.0,
            projected_revenue=100000.0,
            actual_margin=0.25,
            projected_margin=0.25,
            revenue_threshold=0.05,
        )
        assert result.variance_detected is True
        assert "revenue" in result.breached_thresholds

    def test_stricter_margin_threshold(self):
        # 1pp threshold instead of default 3pp
        result = detect_variance(
            actual_revenue=100000.0,
            projected_revenue=100000.0,
            actual_margin=0.235,
            projected_margin=0.25,
            margin_threshold=0.01,
        )
        assert result.variance_detected is True
        assert "margin" in result.breached_thresholds

    def test_relaxed_thresholds_no_breach(self):
        # Very relaxed thresholds
        result = detect_variance(
            actual_revenue=80000.0,
            projected_revenue=100000.0,
            actual_margin=0.20,
            projected_margin=0.25,
            revenue_threshold=0.25,
            margin_threshold=0.10,
        )
        assert result.variance_detected is False
        assert result.breached_thresholds == []


class TestVarianceResultDataclass:
    """Tests for the VarianceResult dataclass."""

    def test_result_is_immutable(self):
        result = detect_variance(
            actual_revenue=100000.0,
            projected_revenue=100000.0,
            actual_margin=0.25,
            projected_margin=0.25,
        )
        with pytest.raises(AttributeError):
            result.variance_detected = True  # type: ignore

    def test_result_fields_accessible(self):
        result = detect_variance(
            actual_revenue=85000.0,
            projected_revenue=100000.0,
            actual_margin=0.20,
            projected_margin=0.25,
        )
        assert isinstance(result.variance_detected, bool)
        assert isinstance(result.revenue_variance, float)
        assert isinstance(result.margin_variance, float)
        assert isinstance(result.breached_thresholds, list)
        assert isinstance(result.recommendation, str)


class TestDefaultThresholdConstants:
    """Tests that default threshold constants are correctly defined."""

    def test_revenue_threshold_is_ten_percent(self):
        assert REVENUE_VARIANCE_THRESHOLD == 0.10

    def test_margin_threshold_is_three_percentage_points(self):
        assert MARGIN_VARIANCE_THRESHOLD == 0.03
