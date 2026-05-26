"""Property-based tests for PricingScenario serialization round trip.

Property 15: Pricing Scenario serialization round trip
Property 16: Schema validation rejects invalid payloads

Validates: Requirements 14.5, 14.2, 14.3

Feature: retail-dynamic-pricing
"""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from shared.models.pricing_scenario import (
    PricingScenario,
    RiskLevel,
    StatusLabel,
)


# --- Strategies ---

status_labels = st.sampled_from([s.value for s in StatusLabel])
risk_levels = st.sampled_from([r.value for r in RiskLevel])

# Finite floats that avoid inf/nan and stay within reasonable monetary bounds
monetary_floats = st.floats(
    min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False
)

simple_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=50,
)

# Strategy for a single PriceChange dict
price_change_strategy = st.fixed_dictionaries({
    "productId": simple_text,
    "currentPrice": monetary_floats,
    "newPrice": monetary_floats,
    "changePercent": monetary_floats,
})

# Strategy for simple JSON-serializable dicts (used for factors)
simple_dict = st.fixed_dictionaries({"key": simple_text})

# Strategy for GuardrailResult dicts
guardrail_result_strategy = st.fixed_dictionaries({
    "rule": simple_text,
    "passed": st.booleans(),
}).flatmap(
    lambda d: st.fixed_dictionaries({
        "rule": st.just(d["rule"]),
        "passed": st.just(d["passed"]),
        "reason": st.none() if d["passed"] else simple_text,
    })
)

# Strategy for a valid PricingScenario dict
pricing_scenario_strategy = st.fixed_dictionaries({
    "scenarioId": simple_text,
    "cycleId": simple_text,
    "rank": st.integers(min_value=1, max_value=10000),
    "confidenceScore": st.integers(min_value=0, max_value=100),
    "statusLabel": status_labels,
    "riskLevel": risk_levels,
    "priceChanges": st.lists(price_change_strategy, min_size=1, max_size=5),
    "projectedRevenue": monetary_floats,
    "projectedMargin": monetary_floats,
    "compositeScore": monetary_floats,
    "competitiveFactors": simple_dict,
    "demandFactors": simple_dict,
    "marketFactors": simple_dict,
    "projectedMarketShare": st.one_of(st.none(), monetary_floats),
    "guardrailResults": st.one_of(
        st.none(),
        st.lists(guardrail_result_strategy, min_size=0, max_size=3),
    ),
})


def floats_match_4dp(a: float | None, b: float | None) -> bool:
    """Check that two floats match to 4 decimal places."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return math.isclose(round(a, 4), round(b, 4), abs_tol=1e-9)


# --- Property 15: Serialization round trip ---


class TestProperty15SerializationRoundTrip:
    """Property 15: Pricing Scenario serialization round trip.

    For any valid PricingScenario object, serializing it to JSON and then
    deserializing the JSON back to a PricingScenario object SHALL produce
    an object with identical field names, data types, and values, where
    numeric fields match to at least 4 decimal places.

    **Validates: Requirements 14.5**
    """

    @given(scenario_data=pricing_scenario_strategy)
    @settings(max_examples=100)
    def test_json_round_trip_preserves_all_fields(self, scenario_data: dict):
        """Serialize to JSON then deserialize back — all fields match to 4dp."""
        original = PricingScenario.from_dict(scenario_data)

        # Round trip: to_json -> from_json
        json_str = original.to_json()
        restored = PricingScenario.from_json(json_str)

        # String fields must be identical
        assert restored.scenario_id == original.scenario_id
        assert restored.cycle_id == original.cycle_id

        # Integer fields must be identical
        assert restored.rank == original.rank
        assert restored.confidence_score == original.confidence_score

        # Enum fields must be identical
        assert restored.status_label == original.status_label
        assert restored.risk_level == original.risk_level

        # Numeric fields match to 4 decimal places
        assert floats_match_4dp(restored.projected_revenue, original.projected_revenue)
        assert floats_match_4dp(restored.projected_margin, original.projected_margin)
        assert floats_match_4dp(restored.composite_score, original.composite_score)
        assert floats_match_4dp(
            restored.projected_market_share, original.projected_market_share
        )

        # Price changes match
        assert len(restored.price_changes) == len(original.price_changes)
        for r_pc, o_pc in zip(restored.price_changes, original.price_changes):
            assert r_pc.product_id == o_pc.product_id
            assert floats_match_4dp(r_pc.current_price, o_pc.current_price)
            assert floats_match_4dp(r_pc.new_price, o_pc.new_price)
            assert floats_match_4dp(r_pc.change_percent, o_pc.change_percent)

        # Dict fields must be equal
        assert restored.competitive_factors == original.competitive_factors
        assert restored.demand_factors == original.demand_factors
        assert restored.market_factors == original.market_factors

        # Guardrail results
        if original.guardrail_results is None:
            assert restored.guardrail_results is None
        else:
            assert restored.guardrail_results is not None
            assert len(restored.guardrail_results) == len(original.guardrail_results)
            for r_gr, o_gr in zip(
                restored.guardrail_results, original.guardrail_results
            ):
                assert r_gr.rule == o_gr.rule
                assert r_gr.passed == o_gr.passed
                assert r_gr.reason == o_gr.reason

    @given(scenario_data=pricing_scenario_strategy)
    @settings(max_examples=100)
    def test_dict_round_trip_preserves_all_fields(self, scenario_data: dict):
        """Serialize to dict then deserialize back — all fields match to 4dp."""
        original = PricingScenario.from_dict(scenario_data)

        # Round trip: to_dict -> from_dict
        dict_repr = original.to_dict()
        restored = PricingScenario.from_dict(dict_repr)

        # String fields
        assert restored.scenario_id == original.scenario_id
        assert restored.cycle_id == original.cycle_id

        # Integer fields
        assert restored.rank == original.rank
        assert restored.confidence_score == original.confidence_score

        # Enum fields
        assert restored.status_label == original.status_label
        assert restored.risk_level == original.risk_level

        # Numeric fields match to 4 decimal places
        assert floats_match_4dp(restored.projected_revenue, original.projected_revenue)
        assert floats_match_4dp(restored.projected_margin, original.projected_margin)
        assert floats_match_4dp(restored.composite_score, original.composite_score)
        assert floats_match_4dp(
            restored.projected_market_share, original.projected_market_share
        )

        # Price changes
        assert len(restored.price_changes) == len(original.price_changes)
        for r_pc, o_pc in zip(restored.price_changes, original.price_changes):
            assert r_pc.product_id == o_pc.product_id
            assert floats_match_4dp(r_pc.current_price, o_pc.current_price)
            assert floats_match_4dp(r_pc.new_price, o_pc.new_price)
            assert floats_match_4dp(r_pc.change_percent, o_pc.change_percent)


# --- Property 16: Schema validation rejects invalid payloads ---


# Required fields that must be present
REQUIRED_FIELDS = [
    "scenarioId", "cycleId", "rank", "confidenceScore", "statusLabel",
    "riskLevel", "priceChanges", "projectedRevenue", "projectedMargin",
    "compositeScore", "competitiveFactors", "demandFactors", "marketFactors",
]


class TestProperty16SchemaValidationRejectsInvalid:
    """Property 16: Schema validation rejects invalid payloads.

    For any JSON payload that is missing a required field or contains a field
    with an incorrect data type, deserialization SHALL reject the payload and
    return an error indication without processing the invalid data.

    **Validates: Requirements 14.2, 14.3**
    """

    @given(
        scenario_data=pricing_scenario_strategy,
        field_to_remove=st.sampled_from(REQUIRED_FIELDS),
    )
    @settings(max_examples=100)
    def test_missing_required_field_raises_validation_error(
        self, scenario_data: dict, field_to_remove: str
    ):
        """Removing any required field from a valid payload must raise ValidationError."""
        # Remove the required field
        scenario_data.pop(field_to_remove, None)

        with pytest.raises(ValidationError):
            PricingScenario.from_dict(scenario_data)

    @given(
        scenario_data=pricing_scenario_strategy,
        wrong_value=st.sampled_from([
            ("rank", "not_an_int"),
            ("confidenceScore", "not_an_int"),
            ("statusLabel", "InvalidStatus"),
            ("riskLevel", "EXTREME"),
            ("priceChanges", "not_a_list"),
            ("projectedRevenue", "not_a_number"),
            ("projectedMargin", "not_a_number"),
            ("compositeScore", "not_a_number"),
            ("competitiveFactors", "not_a_dict"),
            ("demandFactors", 12345),
            ("marketFactors", [1, 2, 3]),
        ]),
    )
    @settings(max_examples=100)
    def test_wrong_type_raises_validation_error(
        self, scenario_data: dict, wrong_value: tuple
    ):
        """Setting a field to an incorrect type must raise ValidationError."""
        field_name, bad_value = wrong_value
        scenario_data[field_name] = bad_value

        with pytest.raises(ValidationError):
            PricingScenario.from_dict(scenario_data)
