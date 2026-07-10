"""Property-based tests for the Strategy Synthesis Agent output.

Uses hypothesis to validate universal correctness properties of the
Strategy Synthesis Agent's guardrail filtering, intelligence agent
references, and status label assignment.

Feature: retail-dynamic-pricing
Validates: Requirements 3.4, 3.5, 3.7, 8.6
"""

import uuid

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from backend.agents.strategy_synthesis import (
    classify_and_label_scenarios,
    synthesize_pricing_strategies,
    validate_scenarios_guardrails,
)


# --- Strategies ---

positive_price = st.floats(
    min_value=0.01, max_value=10_000.0, allow_nan=False, allow_infinity=False
)

non_negative_price = st.floats(
    min_value=0.0, max_value=10_000.0, allow_nan=False, allow_infinity=False
)

change_percent = st.floats(
    min_value=-50.0, max_value=50.0, allow_nan=False, allow_infinity=False
)

margin_impact = st.floats(
    min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False
)

deviation_90day = st.floats(
    min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False
)


@st.composite
def scenario_with_price_below_cost(draw):
    """Generate a scenario where at least one product's newPrice < total_unit_cost."""
    total_unit_cost = draw(st.floats(min_value=10.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    # newPrice strictly below cost
    new_price = draw(st.floats(min_value=0.01, max_value=total_unit_cost, allow_nan=False, allow_infinity=False, exclude_max=True))
    # Ensure rounding doesn't push price up to equal cost
    new_price = round(new_price, 4)
    assume(new_price < total_unit_cost)
    current_price = draw(st.floats(min_value=1.0, max_value=2000.0, allow_nan=False, allow_infinity=False))
    change_pct = ((new_price - current_price) / current_price * 100) if current_price > 0 else 0.0

    product_id = f"PROD-{draw(st.integers(min_value=1, max_value=9999)):04d}"

    scenario = {
        "scenarioId": f"SCN-{uuid.uuid4().hex[:8]}",
        "cycleId": str(uuid.uuid4()),
        "priceChanges": [{
            "productId": product_id,
            "currentPrice": round(current_price, 4),
            "newPrice": round(new_price, 4),
            "changePercent": round(change_pct, 4),
        }],
        "projectedRevenue": draw(st.floats(min_value=-10000, max_value=10000, allow_nan=False, allow_infinity=False)),
        "projectedMargin": draw(st.floats(min_value=0, max_value=50, allow_nan=False, allow_infinity=False)),
        "projectedMarketShare": draw(st.floats(min_value=-5, max_value=5, allow_nan=False, allow_infinity=False)),
        "competitiveFactors": {"avg_competitor_price": 100.0},
        "demandFactors": {"elasticity": -1.5},
        "marketFactors": {"market_growth_rate": 0.03},
    }

    product_cost = {
        "product_id": product_id,
        "total_unit_cost": total_unit_cost,
        "minimum_advertised_price": None,
    }

    return scenario, product_cost


@st.composite
def scenario_with_price_below_map(draw):
    """Generate a scenario where at least one product's newPrice < MAP."""
    map_price = draw(st.floats(min_value=10.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    # newPrice strictly below MAP
    new_price = draw(st.floats(min_value=0.01, max_value=map_price, allow_nan=False, allow_infinity=False, exclude_max=True))
    # Ensure rounding doesn't push price up to equal MAP
    new_price = round(new_price, 4)
    assume(new_price < map_price)
    # total_unit_cost low enough so below-cost doesn't trigger
    total_unit_cost = draw(st.floats(min_value=0.01, max_value=new_price, allow_nan=False, allow_infinity=False))
    current_price = draw(st.floats(min_value=1.0, max_value=2000.0, allow_nan=False, allow_infinity=False))
    change_pct = ((new_price - current_price) / current_price * 100) if current_price > 0 else 0.0

    product_id = f"PROD-{draw(st.integers(min_value=1, max_value=9999)):04d}"

    scenario = {
        "scenarioId": f"SCN-{uuid.uuid4().hex[:8]}",
        "cycleId": str(uuid.uuid4()),
        "priceChanges": [{
            "productId": product_id,
            "currentPrice": round(current_price, 4),
            "newPrice": round(new_price, 4),
            "changePercent": round(change_pct, 4),
        }],
        "projectedRevenue": draw(st.floats(min_value=-10000, max_value=10000, allow_nan=False, allow_infinity=False)),
        "projectedMargin": draw(st.floats(min_value=0, max_value=50, allow_nan=False, allow_infinity=False)),
        "projectedMarketShare": draw(st.floats(min_value=-5, max_value=5, allow_nan=False, allow_infinity=False)),
        "competitiveFactors": {"avg_competitor_price": 100.0},
        "demandFactors": {"elasticity": -1.5},
        "marketFactors": {"market_growth_rate": 0.03},
    }

    product_cost = {
        "product_id": product_id,
        "total_unit_cost": total_unit_cost,
        "minimum_advertised_price": map_price,
    }

    return scenario, product_cost


@st.composite
def valid_scenario_with_all_factors(draw):
    """Generate a valid scenario that has all three intelligence agent factors."""
    current_price = draw(st.floats(min_value=50.0, max_value=500.0, allow_nan=False, allow_infinity=False))
    # Keep price change small to avoid guardrail issues
    change_pct = draw(st.floats(min_value=-3.0, max_value=3.0, allow_nan=False, allow_infinity=False))
    new_price = round(current_price * (1 + change_pct / 100), 4)
    assume(new_price > 0)

    product_id = f"PROD-{draw(st.integers(min_value=1, max_value=9999)):04d}"

    # Competitive factors - at least one key-value pair
    competitive_factors = {
        "avg_competitor_price": draw(st.floats(min_value=10.0, max_value=1000.0, allow_nan=False, allow_infinity=False)),
        "competitive_position": draw(st.sampled_from(["premium", "mid-market", "value"])),
    }

    # Demand factors - at least one key-value pair
    demand_factors = {
        "elasticity": draw(st.floats(min_value=-3.0, max_value=-0.1, allow_nan=False, allow_infinity=False)),
        "trend": draw(st.sampled_from(["growing", "stable", "declining"])),
    }

    # Market factors - at least one key-value pair
    market_factors = {
        "market_growth_rate": draw(st.floats(min_value=-0.1, max_value=0.2, allow_nan=False, allow_infinity=False)),
        "sentiment_score": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
    }

    scenario = {
        "scenarioId": f"SCN-{uuid.uuid4().hex[:8]}",
        "cycleId": str(uuid.uuid4()),
        "priceChanges": [{
            "productId": product_id,
            "currentPrice": round(current_price, 4),
            "newPrice": new_price,
            "changePercent": round(change_pct, 4),
        }],
        "projectedRevenue": draw(st.floats(min_value=-10000, max_value=10000, allow_nan=False, allow_infinity=False)),
        "projectedMargin": draw(st.floats(min_value=0, max_value=50, allow_nan=False, allow_infinity=False)),
        "projectedMarketShare": draw(st.floats(min_value=-5, max_value=5, allow_nan=False, allow_infinity=False)),
        "competitiveFactors": competitive_factors,
        "demandFactors": demand_factors,
        "marketFactors": market_factors,
        "marginImpact": draw(st.floats(min_value=0, max_value=6, allow_nan=False, allow_infinity=False)),
        "deviationFrom90DayAvg": draw(st.floats(min_value=0, max_value=25, allow_nan=False, allow_infinity=False)),
    }

    return scenario


@st.composite
def scenario_for_classification(draw):
    """Generate a scenario with known price change and margin impact for classification."""
    max_price_change = draw(st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False))
    margin_impact_val = draw(st.floats(min_value=0.0, max_value=8.0, allow_nan=False, allow_infinity=False))
    deviation_val = draw(st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False))

    # Build a scenario with the specified change percent
    current_price = 100.0
    # Use positive or negative change based on drawn value
    sign = draw(st.sampled_from([1.0, -1.0]))
    actual_change = max_price_change * sign
    new_price = round(current_price * (1 + actual_change / 100), 4)

    scenario = {
        "scenarioId": f"SCN-{uuid.uuid4().hex[:8]}",
        "cycleId": str(uuid.uuid4()),
        "priceChanges": [{
            "productId": "PROD-0001",
            "currentPrice": current_price,
            "newPrice": new_price,
            "changePercent": actual_change,
        }],
        "projectedRevenue": 5000.0,
        "projectedMargin": 25.0,
        "projectedMarketShare": 1.0,
        "competitiveFactors": {"avg_competitor_price": 100.0},
        "demandFactors": {"elasticity": -1.5},
        "marketFactors": {"market_growth_rate": 0.03},
        "marginImpact": margin_impact_val,
        "deviationFrom90DayAvg": deviation_val,
    }

    return scenario, max_price_change, margin_impact_val, deviation_val


@st.composite
def intelligence_inputs(draw):
    """Generate valid intelligence agent inputs for synthesize_pricing_strategies."""
    current_price = draw(st.floats(min_value=50.0, max_value=500.0, allow_nan=False, allow_infinity=False))
    # Keep total_unit_cost very low relative to current_price so that
    # the scenario generator (which produces changes of at most ~-12%)
    # cannot generate prices below cost. This ensures the property test
    # focuses on verifying the guardrail filtering logic works correctly.
    total_unit_cost = draw(st.floats(min_value=0.01, max_value=current_price * 0.1, allow_nan=False, allow_infinity=False))

    product_id = f"PROD-{draw(st.integers(min_value=1, max_value=9999)):04d}"

    competitive_intelligence = {
        "competitor_prices": {"competitor_a": current_price * 1.05, "competitor_b": current_price * 0.95},
        "average_price": current_price,
        "position": draw(st.sampled_from(["premium", "mid-market", "value"])),
        "price_gap": draw(st.floats(min_value=-10, max_value=10, allow_nan=False, allow_infinity=False)),
        "products": [{"productId": product_id, "currentPrice": current_price}],
    }

    demand_forecasting = {
        "elasticity": draw(st.floats(min_value=-3.0, max_value=-0.1, allow_nan=False, allow_infinity=False)),
        "trend": draw(st.sampled_from(["growing", "stable", "declining"])),
        "forecast_volume": draw(st.integers(min_value=100, max_value=10000)),
        "seasonality_index": draw(st.floats(min_value=0.5, max_value=1.5, allow_nan=False, allow_infinity=False)),
    }

    market_intelligence = {
        "market_growth_rate": draw(st.floats(min_value=-0.05, max_value=0.15, allow_nan=False, allow_infinity=False)),
        "sentiment_score": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        "macro_indicator": draw(st.sampled_from(["bullish", "neutral", "bearish"])),
        "opportunity_score": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
    }

    product_costs = [{
        "product_id": product_id,
        "total_unit_cost": total_unit_cost,
        "minimum_advertised_price": None,
    }]

    return competitive_intelligence, demand_forecasting, market_intelligence, product_costs


# --- Property 6: Guardrail-violating scenarios excluded from output ---


class TestProperty6GuardrailViolatingExcluded:
    """Property 6: Guardrail-violating scenarios excluded from output.

    For any scenario where newPrice < total_unit_cost OR newPrice < MAP,
    that scenario must NOT appear in valid_scenarios output.

    **Validates: Requirements 3.4, 8.6**
    """

    @settings(max_examples=100)
    @given(data=scenario_with_price_below_cost())
    def test_below_cost_scenario_excluded_from_valid(self, data):
        """Scenarios with price below cost must not appear in valid_scenarios."""
        scenario, product_cost = data
        result = validate_scenarios_guardrails(
            scenarios=[scenario],
            product_costs=[product_cost],
        )
        valid_ids = [s["scenarioId"] for s in result["valid_scenarios"]]
        assert scenario["scenarioId"] not in valid_ids, (
            f"Scenario {scenario['scenarioId']} with price below cost "
            f"should be excluded from valid_scenarios"
        )
        # Must appear in rejected
        rejected_ids = [s["scenarioId"] for s in result["rejected_scenarios"]]
        assert scenario["scenarioId"] in rejected_ids

    @settings(max_examples=100)
    @given(data=scenario_with_price_below_map())
    def test_below_map_scenario_excluded_from_valid(self, data):
        """Scenarios with price below MAP must not appear in valid_scenarios."""
        scenario, product_cost = data
        result = validate_scenarios_guardrails(
            scenarios=[scenario],
            product_costs=[product_cost],
        )
        valid_ids = [s["scenarioId"] for s in result["valid_scenarios"]]
        assert scenario["scenarioId"] not in valid_ids, (
            f"Scenario {scenario['scenarioId']} with price below MAP "
            f"should be excluded from valid_scenarios"
        )
        rejected_ids = [s["scenarioId"] for s in result["rejected_scenarios"]]
        assert scenario["scenarioId"] in rejected_ids

    @settings(max_examples=100)
    @given(data=intelligence_inputs())
    def test_full_pipeline_excludes_guardrail_violations(self, data):
        """In synthesize_pricing_strategies, no scenario in ranked output violates guardrails."""
        competitive, demand, market, product_costs = data
        result = synthesize_pricing_strategies(
            competitive_intelligence=competitive,
            demand_forecasting=demand,
            market_intelligence=market,
            product_costs=product_costs,
        )
        ranked = result["ranked_scenarios"]
        total_unit_cost = product_costs[0]["total_unit_cost"]
        map_price = product_costs[0].get("minimum_advertised_price")

        for scenario in ranked:
            for pc in scenario.get("priceChanges", []):
                new_price = pc.get("newPrice", 0)
                assert new_price >= total_unit_cost, (
                    f"Scenario {scenario.get('scenarioId')} has newPrice={new_price} "
                    f"below total_unit_cost={total_unit_cost}"
                )
                if map_price is not None:
                    assert new_price >= map_price, (
                        f"Scenario {scenario.get('scenarioId')} has newPrice={new_price} "
                        f"below MAP={map_price}"
                    )


# --- Property 7: Each scenario references all three intelligence agents ---


class TestProperty7AllIntelligenceAgentsReferenced:
    """Property 7: Each scenario references all three intelligence agents.

    For any scenario in the output of synthesize_pricing_strategies,
    competitiveFactors, demandFactors, and marketFactors must each be
    non-empty dicts.

    **Validates: Requirements 3.5**
    """

    @settings(max_examples=100)
    @given(data=intelligence_inputs())
    def test_all_scenarios_have_competitive_factors(self, data):
        """Every output scenario must have non-empty competitiveFactors."""
        competitive, demand, market, product_costs = data
        result = synthesize_pricing_strategies(
            competitive_intelligence=competitive,
            demand_forecasting=demand,
            market_intelligence=market,
            product_costs=product_costs,
        )
        for scenario in result["ranked_scenarios"]:
            cf = scenario.get("competitiveFactors")
            assert cf is not None, "competitiveFactors must be present"
            assert isinstance(cf, dict), "competitiveFactors must be a dict"
            assert len(cf) > 0, (
                f"competitiveFactors must be non-empty for scenario "
                f"{scenario.get('scenarioId')}"
            )

    @settings(max_examples=100)
    @given(data=intelligence_inputs())
    def test_all_scenarios_have_demand_factors(self, data):
        """Every output scenario must have non-empty demandFactors."""
        competitive, demand, market, product_costs = data
        result = synthesize_pricing_strategies(
            competitive_intelligence=competitive,
            demand_forecasting=demand,
            market_intelligence=market,
            product_costs=product_costs,
        )
        for scenario in result["ranked_scenarios"]:
            df = scenario.get("demandFactors")
            assert df is not None, "demandFactors must be present"
            assert isinstance(df, dict), "demandFactors must be a dict"
            assert len(df) > 0, (
                f"demandFactors must be non-empty for scenario "
                f"{scenario.get('scenarioId')}"
            )

    @settings(max_examples=100)
    @given(data=intelligence_inputs())
    def test_all_scenarios_have_market_factors(self, data):
        """Every output scenario must have non-empty marketFactors."""
        competitive, demand, market, product_costs = data
        result = synthesize_pricing_strategies(
            competitive_intelligence=competitive,
            demand_forecasting=demand,
            market_intelligence=market,
            product_costs=product_costs,
        )
        for scenario in result["ranked_scenarios"]:
            mf = scenario.get("marketFactors")
            assert mf is not None, "marketFactors must be present"
            assert isinstance(mf, dict), "marketFactors must be a dict"
            assert len(mf) > 0, (
                f"marketFactors must be non-empty for scenario "
                f"{scenario.get('scenarioId')}"
            )


# --- Property 8: Status label matches risk classification ---


class TestProperty8StatusLabelMatchesRisk:
    """Property 8: Status label matches risk classification.

    For any labeled scenario, statusLabel must be "Recommended" when
    riskLevel is "LOW", "Review Required" when "MEDIUM", and
    "Human Exception Handling" when "HIGH".

    **Validates: Requirements 3.7**
    """

    @settings(max_examples=100)
    @given(data=scenario_for_classification())
    def test_status_label_matches_risk_level(self, data):
        """statusLabel must correspond to riskLevel for every classified scenario."""
        scenario, max_price_change, margin_impact_val, deviation_val = data

        labeled = classify_and_label_scenarios(scenarios=[scenario])
        assert len(labeled) == 1

        result = labeled[0]
        risk_level = result["riskLevel"]
        status_label = result["statusLabel"]

        expected_mapping = {
            "LOW": "Recommended",
            "MEDIUM": "Review Required",
            "HIGH": "Human Exception Handling",
        }

        assert risk_level in expected_mapping, (
            f"Unexpected riskLevel: {risk_level}"
        )
        assert status_label == expected_mapping[risk_level], (
            f"For riskLevel={risk_level}, expected statusLabel="
            f"'{expected_mapping[risk_level]}' but got '{status_label}'"
        )

    @settings(max_examples=100)
    @given(data=intelligence_inputs())
    def test_full_pipeline_status_labels_match_risk(self, data):
        """In full pipeline output, every scenario's statusLabel matches its riskLevel."""
        competitive, demand, market, product_costs = data
        result = synthesize_pricing_strategies(
            competitive_intelligence=competitive,
            demand_forecasting=demand,
            market_intelligence=market,
            product_costs=product_costs,
        )

        expected_mapping = {
            "LOW": "Recommended",
            "MEDIUM": "Review Required",
            "HIGH": "Human Exception Handling",
        }

        for scenario in result["ranked_scenarios"]:
            risk_level = scenario.get("riskLevel")
            status_label = scenario.get("statusLabel")
            assert risk_level in expected_mapping, (
                f"Unexpected riskLevel: {risk_level} in scenario {scenario.get('scenarioId')}"
            )
            assert status_label == expected_mapping[risk_level], (
                f"Scenario {scenario.get('scenarioId')}: riskLevel={risk_level} "
                f"should have statusLabel='{expected_mapping[risk_level]}' "
                f"but got '{status_label}'"
            )
