"""Property-based tests for confidence scores and scenario count.

Property 5: Confidence scores are valid integers
    For any valid PricingScenario, confidenceScore must be an integer in [0, 100].

Property 4: Scenario count within bounds
    For any list of scenarios passed through rank_scenarios(), the output count
    equals the input count (no scenarios lost or duplicated).

Feature: retail-dynamic-pricing

Validates: Requirements 3.3, 3.1, 3.6
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from shared.models.pricing_scenario import (
    PricingScenario,
    RiskLevel,
    StatusLabel,
)
from shared.scenario_ranking import rank_scenarios


# --- Strategies ---

status_labels = st.sampled_from([s.value for s in StatusLabel])
risk_levels = st.sampled_from([s.value for s in RiskLevel])


@st.composite
def valid_price_change(draw):
    """Generate a valid price change dictionary."""
    product_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N", "Pd"))))
    current_price = draw(st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False))
    new_price = draw(st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False))
    change_percent = ((new_price - current_price) / current_price) * 100.0
    return {
        "productId": product_id,
        "currentPrice": current_price,
        "newPrice": new_price,
        "changePercent": round(change_percent, 4),
    }


@st.composite
def valid_confidence_score(draw):
    """Generate a valid confidence score (integer 0-100)."""
    return draw(st.integers(min_value=0, max_value=100))


@st.composite
def valid_pricing_scenario_dict(draw):
    """Generate a valid PricingScenario dictionary."""
    scenario_id = draw(st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Pd"))))
    cycle_id = draw(st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Pd"))))
    rank = draw(st.integers(min_value=1, max_value=1000))
    confidence_score = draw(valid_confidence_score())
    status_label = draw(status_labels)
    risk_level = draw(risk_levels)
    price_changes = draw(st.lists(valid_price_change(), min_size=1, max_size=5))
    projected_revenue = draw(st.floats(min_value=-1000000.0, max_value=1000000.0, allow_nan=False, allow_infinity=False))
    projected_margin = draw(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    composite_score = draw(st.floats(min_value=-1000000.0, max_value=1000000.0, allow_nan=False, allow_infinity=False))

    return {
        "scenarioId": scenario_id,
        "cycleId": cycle_id,
        "rank": rank,
        "confidenceScore": confidence_score,
        "statusLabel": status_label,
        "riskLevel": risk_level,
        "priceChanges": price_changes,
        "projectedRevenue": projected_revenue,
        "projectedMargin": projected_margin,
        "compositeScore": composite_score,
        "competitiveFactors": {"avgCompetitorPrice": 30.50},
        "demandFactors": {"elasticity": -1.2},
        "marketFactors": {"trendScore": 0.75},
    }


@st.composite
def scenario_for_ranking(draw):
    """Generate a minimal scenario dict suitable for rank_scenarios()."""
    scenario_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))))
    projected_revenue = draw(st.floats(min_value=-100000.0, max_value=100000.0, allow_nan=False, allow_infinity=False))
    projected_margin = draw(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    projected_market_share = draw(st.one_of(
        st.none(),
        st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
    ))
    result = {
        "scenarioId": scenario_id,
        "projectedRevenue": projected_revenue,
        "projectedMargin": projected_margin,
    }
    if projected_market_share is not None:
        result["projectedMarketShare"] = projected_market_share
    return result


# --- Property 5: Confidence scores are valid integers ---


class TestProperty5ConfidenceScoresValid:
    """Property 5: Confidence scores are valid integers.

    For any valid PricingScenario, confidenceScore must be an integer in [0, 100].

    **Validates: Requirements 3.3**
    """

    @given(confidence_score=st.integers(min_value=0, max_value=100))
    @settings(max_examples=100)
    def test_valid_confidence_scores_accepted(self, confidence_score: int):
        """Any integer in [0, 100] is accepted as a valid confidence score.

        **Validates: Requirements 3.3**
        """
        data = {
            "scenarioId": "scen-001",
            "cycleId": "cycle-001",
            "rank": 1,
            "confidenceScore": confidence_score,
            "statusLabel": "Recommended",
            "riskLevel": "LOW",
            "priceChanges": [{"productId": "p1", "currentPrice": 10.0, "newPrice": 11.0, "changePercent": 10.0}],
            "projectedRevenue": 1000.0,
            "projectedMargin": 0.25,
            "compositeScore": 50.0,
            "competitiveFactors": {"data": True},
            "demandFactors": {"data": True},
            "marketFactors": {"data": True},
        }
        scenario = PricingScenario.from_dict(data)
        assert isinstance(scenario.confidence_score, int)
        assert 0 <= scenario.confidence_score <= 100

    @given(confidence_score=st.integers(min_value=101, max_value=1000))
    @settings(max_examples=100)
    def test_confidence_scores_above_100_rejected(self, confidence_score: int):
        """Any integer above 100 is rejected by Pydantic validation.

        **Validates: Requirements 3.3**
        """
        data = {
            "scenarioId": "scen-001",
            "cycleId": "cycle-001",
            "rank": 1,
            "confidenceScore": confidence_score,
            "statusLabel": "Recommended",
            "riskLevel": "LOW",
            "priceChanges": [{"productId": "p1", "currentPrice": 10.0, "newPrice": 11.0, "changePercent": 10.0}],
            "projectedRevenue": 1000.0,
            "projectedMargin": 0.25,
            "compositeScore": 50.0,
            "competitiveFactors": {"data": True},
            "demandFactors": {"data": True},
            "marketFactors": {"data": True},
        }
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    @given(confidence_score=st.integers(min_value=-1000, max_value=-1))
    @settings(max_examples=100)
    def test_confidence_scores_below_0_rejected(self, confidence_score: int):
        """Any integer below 0 is rejected by Pydantic validation.

        **Validates: Requirements 3.3**
        """
        data = {
            "scenarioId": "scen-001",
            "cycleId": "cycle-001",
            "rank": 1,
            "confidenceScore": confidence_score,
            "statusLabel": "Recommended",
            "riskLevel": "LOW",
            "priceChanges": [{"productId": "p1", "currentPrice": 10.0, "newPrice": 11.0, "changePercent": 10.0}],
            "projectedRevenue": 1000.0,
            "projectedMargin": 0.25,
            "compositeScore": 50.0,
            "competitiveFactors": {"data": True},
            "demandFactors": {"data": True},
            "marketFactors": {"data": True},
        }
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    @given(scenario_data=valid_pricing_scenario_dict())
    @settings(max_examples=100)
    def test_constructed_scenario_has_valid_confidence_score(self, scenario_data: dict):
        """For any valid PricingScenario, confidenceScore is an integer in [0, 100].

        **Validates: Requirements 3.3**
        """
        scenario = PricingScenario.from_dict(scenario_data)
        assert isinstance(scenario.confidence_score, int)
        assert 0 <= scenario.confidence_score <= 100


# --- Property 4: Scenario count within bounds ---


class TestProperty4ScenarioCountWithinBounds:
    """Property 4: Scenario count within bounds.

    For any list of scenarios passed through rank_scenarios(), the output count
    equals the input count (no scenarios lost or duplicated).

    **Validates: Requirements 3.1, 3.6**
    """

    @given(scenarios=st.lists(scenario_for_ranking(), min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_output_count_equals_input_count(self, scenarios: list):
        """rank_scenarios() preserves the count: output length equals input length.

        **Validates: Requirements 3.1, 3.6**
        """
        result = rank_scenarios(scenarios)
        assert len(result) == len(scenarios)

    @given(scenarios=st.lists(scenario_for_ranking(), min_size=50, max_size=200))
    @settings(max_examples=100)
    def test_valid_scenario_count_in_generation_range(self, scenarios: list):
        """When input count is in [50, 200], output count stays in [50, 200].

        The system generates 50-200 scenarios. After ranking, the count must
        remain within these bounds (no scenarios lost or duplicated).

        **Validates: Requirements 3.1, 3.6**
        """
        result = rank_scenarios(scenarios)
        assert 50 <= len(result) <= 200

    @given(scenarios=st.lists(scenario_for_ranking(), min_size=1, max_size=200))
    @settings(max_examples=100)
    def test_no_scenarios_lost_or_duplicated(self, scenarios: list):
        """All input scenario IDs appear exactly once in the output.

        **Validates: Requirements 3.1, 3.6**
        """
        result = rank_scenarios(scenarios)
        input_ids = [s["scenarioId"] for s in scenarios]
        output_ids = [s["scenarioId"] for s in result]
        assert sorted(output_ids) == sorted(input_ids)

    @given(count=st.integers(min_value=0, max_value=200))
    @settings(max_examples=100)
    def test_output_count_matches_any_input_count(self, count: int):
        """For any input count between 0 and 200, output count equals input count.

        **Validates: Requirements 3.1, 3.6**
        """
        scenarios = [
            {
                "scenarioId": f"s{i}",
                "projectedRevenue": float(i * 100),
                "projectedMargin": float(i) * 0.01,
            }
            for i in range(count)
        ]
        result = rank_scenarios(scenarios)
        assert len(result) == count
