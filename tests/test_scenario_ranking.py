"""Unit tests for the scenario ranking module.

Tests composite score calculation, scenario sorting by score descending,
and contiguous rank assignment from 1 to N.

Validates: Requirements 3.2
"""

import pytest

from shared.scenario_ranking import (
    DEFAULT_MARGIN_WEIGHT,
    DEFAULT_MARKET_SHARE_WEIGHT,
    DEFAULT_REVENUE_WEIGHT,
    calculate_composite_score,
    rank_scenarios,
)


class TestCalculateCompositeScore:
    """Tests for the calculate_composite_score function."""

    def test_default_weights(self):
        score = calculate_composite_score(
            projected_revenue=100.0,
            projected_margin=50.0,
            projected_market_share=20.0,
        )
        expected = 0.4 * 100.0 + 0.35 * 50.0 + 0.25 * 20.0
        assert score == pytest.approx(expected)

    def test_none_market_share_treated_as_zero(self):
        score = calculate_composite_score(
            projected_revenue=100.0,
            projected_margin=50.0,
            projected_market_share=None,
        )
        expected = 0.4 * 100.0 + 0.35 * 50.0 + 0.25 * 0.0
        assert score == pytest.approx(expected)

    def test_custom_weights(self):
        score = calculate_composite_score(
            projected_revenue=200.0,
            projected_margin=100.0,
            projected_market_share=50.0,
            revenue_weight=0.5,
            margin_weight=0.3,
            market_share_weight=0.2,
        )
        expected = 0.5 * 200.0 + 0.3 * 100.0 + 0.2 * 50.0
        assert score == pytest.approx(expected)

    def test_zero_values(self):
        score = calculate_composite_score(
            projected_revenue=0.0,
            projected_margin=0.0,
            projected_market_share=0.0,
        )
        assert score == 0.0

    def test_negative_values(self):
        score = calculate_composite_score(
            projected_revenue=-100.0,
            projected_margin=-50.0,
            projected_market_share=-10.0,
        )
        expected = 0.4 * (-100.0) + 0.35 * (-50.0) + 0.25 * (-10.0)
        assert score == pytest.approx(expected)


class TestRankScenarios:
    """Tests for the rank_scenarios function."""

    def test_empty_list_returns_empty(self):
        result = rank_scenarios([])
        assert result == []

    def test_single_scenario_gets_rank_1(self):
        scenarios = [
            {
                "scenarioId": "s1",
                "projectedRevenue": 1000.0,
                "projectedMargin": 0.25,
                "projectedMarketShare": 0.05,
            }
        ]
        result = rank_scenarios(scenarios)
        assert len(result) == 1
        assert result[0]["rank"] == 1
        assert "compositeScore" in result[0]

    def test_scenarios_sorted_descending_by_composite_score(self):
        scenarios = [
            {"scenarioId": "low", "projectedRevenue": 100.0, "projectedMargin": 10.0},
            {"scenarioId": "high", "projectedRevenue": 1000.0, "projectedMargin": 100.0},
            {"scenarioId": "mid", "projectedRevenue": 500.0, "projectedMargin": 50.0},
        ]
        result = rank_scenarios(scenarios)
        assert result[0]["scenarioId"] == "high"
        assert result[1]["scenarioId"] == "mid"
        assert result[2]["scenarioId"] == "low"

    def test_contiguous_ranks_1_to_n(self):
        scenarios = [
            {"scenarioId": f"s{i}", "projectedRevenue": float(i * 100), "projectedMargin": float(i * 10)}
            for i in range(5)
        ]
        result = rank_scenarios(scenarios)
        ranks = [s["rank"] for s in result]
        assert ranks == [1, 2, 3, 4, 5]

    def test_no_duplicate_ranks(self):
        scenarios = [
            {"scenarioId": f"s{i}", "projectedRevenue": float(i * 50), "projectedMargin": float(i * 5)}
            for i in range(10)
        ]
        result = rank_scenarios(scenarios)
        ranks = [s["rank"] for s in result]
        assert len(ranks) == len(set(ranks))

    def test_higher_score_gets_lower_rank_number(self):
        scenarios = [
            {"scenarioId": "best", "projectedRevenue": 10000.0, "projectedMargin": 500.0},
            {"scenarioId": "worst", "projectedRevenue": 100.0, "projectedMargin": 5.0},
        ]
        result = rank_scenarios(scenarios)
        best = next(s for s in result if s["scenarioId"] == "best")
        worst = next(s for s in result if s["scenarioId"] == "worst")
        assert best["rank"] < worst["rank"]
        assert best["rank"] == 1

    def test_composite_score_is_set_on_each_scenario(self):
        scenarios = [
            {"scenarioId": "s1", "projectedRevenue": 200.0, "projectedMargin": 30.0, "projectedMarketShare": 5.0},
            {"scenarioId": "s2", "projectedRevenue": 300.0, "projectedMargin": 40.0, "projectedMarketShare": 8.0},
        ]
        result = rank_scenarios(scenarios)
        for s in result:
            assert "compositeScore" in s
            assert isinstance(s["compositeScore"], float)

    def test_composite_score_calculation_matches_formula(self):
        scenarios = [
            {"scenarioId": "s1", "projectedRevenue": 500.0, "projectedMargin": 100.0, "projectedMarketShare": 10.0},
        ]
        result = rank_scenarios(scenarios)
        expected = 0.4 * 500.0 + 0.35 * 100.0 + 0.25 * 10.0
        assert result[0]["compositeScore"] == pytest.approx(expected)

    def test_supports_camel_case_fields(self):
        scenarios = [
            {"scenarioId": "s1", "projectedRevenue": 100.0, "projectedMargin": 20.0, "projectedMarketShare": 5.0},
        ]
        result = rank_scenarios(scenarios)
        assert result[0]["rank"] == 1
        expected = 0.4 * 100.0 + 0.35 * 20.0 + 0.25 * 5.0
        assert result[0]["compositeScore"] == pytest.approx(expected)

    def test_supports_snake_case_fields(self):
        scenarios = [
            {"scenarioId": "s1", "projected_revenue": 100.0, "projected_margin": 20.0, "projected_market_share": 5.0},
        ]
        result = rank_scenarios(scenarios)
        assert result[0]["rank"] == 1
        expected = 0.4 * 100.0 + 0.35 * 20.0 + 0.25 * 5.0
        assert result[0]["compositeScore"] == pytest.approx(expected)

    def test_missing_market_share_treated_as_zero(self):
        scenarios = [
            {"scenarioId": "s1", "projectedRevenue": 100.0, "projectedMargin": 20.0},
        ]
        result = rank_scenarios(scenarios)
        expected = 0.4 * 100.0 + 0.35 * 20.0 + 0.25 * 0.0
        assert result[0]["compositeScore"] == pytest.approx(expected)

    def test_custom_weights_applied(self):
        scenarios = [
            {"scenarioId": "s1", "projectedRevenue": 100.0, "projectedMargin": 50.0, "projectedMarketShare": 25.0},
        ]
        result = rank_scenarios(scenarios, revenue_weight=0.5, margin_weight=0.3, market_share_weight=0.2)
        expected = 0.5 * 100.0 + 0.3 * 50.0 + 0.2 * 25.0
        assert result[0]["compositeScore"] == pytest.approx(expected)

    def test_does_not_mutate_input(self):
        scenarios = [
            {"scenarioId": "s1", "projectedRevenue": 100.0, "projectedMargin": 20.0},
            {"scenarioId": "s2", "projectedRevenue": 200.0, "projectedMargin": 40.0},
        ]
        original_ids = [s["scenarioId"] for s in scenarios]
        rank_scenarios(scenarios)
        # Original list should be unchanged
        assert [s["scenarioId"] for s in scenarios] == original_ids
        assert "rank" not in scenarios[0]
        assert "compositeScore" not in scenarios[0]

    def test_preserves_existing_fields(self):
        scenarios = [
            {
                "scenarioId": "s1",
                "cycleId": "c1",
                "projectedRevenue": 100.0,
                "projectedMargin": 20.0,
                "confidenceScore": 85,
                "statusLabel": "Recommended",
            },
        ]
        result = rank_scenarios(scenarios)
        assert result[0]["scenarioId"] == "s1"
        assert result[0]["cycleId"] == "c1"
        assert result[0]["confidenceScore"] == 85
        assert result[0]["statusLabel"] == "Recommended"

    def test_equal_scores_get_distinct_ranks(self):
        scenarios = [
            {"scenarioId": "s1", "projectedRevenue": 100.0, "projectedMargin": 20.0},
            {"scenarioId": "s2", "projectedRevenue": 100.0, "projectedMargin": 20.0},
            {"scenarioId": "s3", "projectedRevenue": 100.0, "projectedMargin": 20.0},
        ]
        result = rank_scenarios(scenarios)
        ranks = [s["rank"] for s in result]
        assert sorted(ranks) == [1, 2, 3]
