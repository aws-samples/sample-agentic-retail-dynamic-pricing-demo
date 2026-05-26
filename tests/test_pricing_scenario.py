"""Unit tests for the PricingScenario data model.

Tests JSON serialization (4 decimal places), deserialization with schema validation,
and rejection of invalid payloads.
"""

import json

import pytest
from pydantic import ValidationError

from shared.models.pricing_scenario import (
    GuardrailResult,
    PriceChange,
    PricingScenario,
    RiskLevel,
    StatusLabel,
    PRICING_SCENARIO_JSON_SCHEMA,
)


def make_valid_scenario_dict(**overrides) -> dict:
    """Create a valid PricingScenario dictionary for testing."""
    base = {
        "scenarioId": "scen-001",
        "cycleId": "cycle-001",
        "rank": 1,
        "confidenceScore": 85,
        "statusLabel": "Recommended",
        "riskLevel": "LOW",
        "priceChanges": [
            {
                "productId": "prod-001",
                "currentPrice": 29.9999,
                "newPrice": 31.4567,
                "changePercent": 4.8557,
            }
        ],
        "projectedRevenue": 150000.1234,
        "projectedMargin": 0.2345,
        "compositeScore": 87.6543,
        "competitiveFactors": {"avgCompetitorPrice": 30.50},
        "demandFactors": {"elasticity": -1.2},
        "marketFactors": {"trendScore": 0.75},
    }
    base.update(overrides)
    return base


class TestPriceChange:
    """Tests for the PriceChange model."""

    def test_create_price_change(self):
        pc = PriceChange(
            productId="prod-001",
            currentPrice=29.99,
            newPrice=31.49,
            changePercent=5.0,
        )
        assert pc.product_id == "prod-001"
        assert pc.current_price == 29.99
        assert pc.new_price == 31.49
        assert pc.change_percent == 5.0

    def test_serialization_preserves_4_decimals(self):
        pc = PriceChange(
            productId="prod-001",
            currentPrice=29.99876543,
            newPrice=31.12345678,
            changePercent=3.76543210,
        )
        data = pc.model_dump(by_alias=True)
        assert data["currentPrice"] == 29.9988
        assert data["newPrice"] == 31.1235
        assert data["changePercent"] == 3.7654


class TestGuardrailResult:
    """Tests for the GuardrailResult model."""

    def test_create_passed_result(self):
        gr = GuardrailResult(rule="below-cost", passed=True)
        assert gr.rule == "below-cost"
        assert gr.passed is True
        assert gr.reason is None

    def test_create_failed_result_with_reason(self):
        gr = GuardrailResult(
            rule="MAP-enforcement", passed=False, reason="Price below MAP"
        )
        assert gr.passed is False
        assert gr.reason == "Price below MAP"


class TestPricingScenario:
    """Tests for the PricingScenario model."""

    def test_create_valid_scenario(self):
        data = make_valid_scenario_dict()
        scenario = PricingScenario.from_dict(data)
        assert scenario.scenario_id == "scen-001"
        assert scenario.cycle_id == "cycle-001"
        assert scenario.rank == 1
        assert scenario.confidence_score == 85
        assert scenario.status_label == StatusLabel.RECOMMENDED
        assert scenario.risk_level == RiskLevel.LOW
        assert len(scenario.price_changes) == 1
        assert scenario.competitive_factors == {"avgCompetitorPrice": 30.50}

    def test_serialization_uses_camel_case(self):
        data = make_valid_scenario_dict()
        scenario = PricingScenario.from_dict(data)
        output = scenario.to_dict()
        assert "scenarioId" in output
        assert "cycleId" in output
        assert "confidenceScore" in output
        assert "statusLabel" in output
        assert "riskLevel" in output
        assert "priceChanges" in output
        assert "projectedRevenue" in output
        assert "projectedMargin" in output
        assert "compositeScore" in output
        assert "competitiveFactors" in output
        assert "demandFactors" in output
        assert "marketFactors" in output

    def test_serialization_preserves_4_decimal_places(self):
        data = make_valid_scenario_dict(
            projectedRevenue=150000.123456789,
            projectedMargin=0.234567890,
            compositeScore=87.654321,
        )
        scenario = PricingScenario.from_dict(data)
        output = scenario.to_dict()
        assert output["projectedRevenue"] == 150000.1235
        assert output["projectedMargin"] == 0.2346
        assert output["compositeScore"] == 87.6543

    def test_json_serialization_round_trip(self):
        data = make_valid_scenario_dict()
        scenario = PricingScenario.from_dict(data)
        json_str = scenario.to_json()
        restored = PricingScenario.from_json(json_str)
        assert restored.scenario_id == scenario.scenario_id
        assert restored.cycle_id == scenario.cycle_id
        assert restored.rank == scenario.rank
        assert restored.confidence_score == scenario.confidence_score
        assert restored.status_label == scenario.status_label
        assert restored.risk_level == scenario.risk_level
        assert restored.projected_revenue == scenario.projected_revenue
        assert restored.projected_margin == scenario.projected_margin
        assert restored.composite_score == scenario.composite_score

    def test_json_output_is_valid_json(self):
        data = make_valid_scenario_dict()
        scenario = PricingScenario.from_dict(data)
        json_str = scenario.to_json()
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert parsed["scenarioId"] == "scen-001"

    def test_optional_fields_can_be_omitted(self):
        data = make_valid_scenario_dict()
        # projectedMarketShare and guardrailResults are optional
        assert "projectedMarketShare" not in data
        assert "guardrailResults" not in data
        scenario = PricingScenario.from_dict(data)
        assert scenario.projected_market_share is None
        assert scenario.guardrail_results is None

    def test_optional_fields_included_when_provided(self):
        data = make_valid_scenario_dict(
            projectedMarketShare=0.1234,
            guardrailResults=[
                {"rule": "below-cost", "passed": True},
                {"rule": "MAP-enforcement", "passed": False, "reason": "Below MAP"},
            ],
        )
        scenario = PricingScenario.from_dict(data)
        assert scenario.projected_market_share == 0.1234
        assert len(scenario.guardrail_results) == 2
        assert scenario.guardrail_results[0].passed is True
        assert scenario.guardrail_results[1].reason == "Below MAP"

    def test_all_status_labels_valid(self):
        for label in StatusLabel:
            data = make_valid_scenario_dict(statusLabel=label.value)
            scenario = PricingScenario.from_dict(data)
            assert scenario.status_label == label

    def test_all_risk_levels_valid(self):
        for level in RiskLevel:
            data = make_valid_scenario_dict(riskLevel=level.value)
            scenario = PricingScenario.from_dict(data)
            assert scenario.risk_level == level


class TestSchemaValidationRejectsInvalid:
    """Tests that invalid payloads are rejected with appropriate errors."""

    def test_missing_scenario_id(self):
        data = make_valid_scenario_dict()
        del data["scenarioId"]
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_missing_cycle_id(self):
        data = make_valid_scenario_dict()
        del data["cycleId"]
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_missing_rank(self):
        data = make_valid_scenario_dict()
        del data["rank"]
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_missing_confidence_score(self):
        data = make_valid_scenario_dict()
        del data["confidenceScore"]
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_missing_price_changes(self):
        data = make_valid_scenario_dict()
        del data["priceChanges"]
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_missing_competitive_factors(self):
        data = make_valid_scenario_dict()
        del data["competitiveFactors"]
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_missing_demand_factors(self):
        data = make_valid_scenario_dict()
        del data["demandFactors"]
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_missing_market_factors(self):
        data = make_valid_scenario_dict()
        del data["marketFactors"]
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_rank_below_minimum(self):
        data = make_valid_scenario_dict(rank=0)
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_confidence_score_below_minimum(self):
        data = make_valid_scenario_dict(confidenceScore=-1)
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_confidence_score_above_maximum(self):
        data = make_valid_scenario_dict(confidenceScore=101)
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_invalid_status_label(self):
        data = make_valid_scenario_dict(statusLabel="Invalid")
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_invalid_risk_level(self):
        data = make_valid_scenario_dict(riskLevel="EXTREME")
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_rank_wrong_type(self):
        data = make_valid_scenario_dict(rank="first")
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_confidence_score_wrong_type(self):
        data = make_valid_scenario_dict(confidenceScore="high")
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_price_changes_wrong_type(self):
        data = make_valid_scenario_dict(priceChanges="not-a-list")
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_price_change_missing_product_id(self):
        data = make_valid_scenario_dict(
            priceChanges=[{"currentPrice": 10.0, "newPrice": 11.0, "changePercent": 10.0}]
        )
        with pytest.raises(ValidationError):
            PricingScenario.from_dict(data)

    def test_invalid_json_string_rejected(self):
        with pytest.raises(ValidationError):
            PricingScenario.from_json("not valid json")

    def test_empty_json_object_rejected(self):
        with pytest.raises(ValidationError):
            PricingScenario.from_json("{}")


class TestJsonSchemaDefinition:
    """Tests for the shared JSON Schema constant."""

    def test_schema_has_required_fields(self):
        required = PRICING_SCENARIO_JSON_SCHEMA["required"]
        expected = [
            "scenarioId", "cycleId", "rank", "confidenceScore", "statusLabel",
            "riskLevel", "priceChanges", "projectedRevenue", "projectedMargin",
            "compositeScore", "competitiveFactors", "demandFactors", "marketFactors",
        ]
        assert required == expected

    def test_schema_has_all_properties(self):
        props = PRICING_SCENARIO_JSON_SCHEMA["properties"]
        assert "scenarioId" in props
        assert "cycleId" in props
        assert "rank" in props
        assert "confidenceScore" in props
        assert "statusLabel" in props
        assert "riskLevel" in props
        assert "priceChanges" in props
        assert "projectedRevenue" in props
        assert "projectedMargin" in props
        assert "projectedMarketShare" in props
        assert "compositeScore" in props
        assert "competitiveFactors" in props
        assert "demandFactors" in props
        assert "marketFactors" in props
        assert "guardrailResults" in props

    def test_schema_rank_constraints(self):
        rank_schema = PRICING_SCENARIO_JSON_SCHEMA["properties"]["rank"]
        assert rank_schema["type"] == "integer"
        assert rank_schema["minimum"] == 1

    def test_schema_confidence_score_constraints(self):
        cs_schema = PRICING_SCENARIO_JSON_SCHEMA["properties"]["confidenceScore"]
        assert cs_schema["type"] == "integer"
        assert cs_schema["minimum"] == 0
        assert cs_schema["maximum"] == 100

    def test_schema_status_label_enum(self):
        sl_schema = PRICING_SCENARIO_JSON_SCHEMA["properties"]["statusLabel"]
        assert sl_schema["enum"] == [
            "Recommended", "Review Required", "Human Exception Handling"
        ]

    def test_schema_risk_level_enum(self):
        rl_schema = PRICING_SCENARIO_JSON_SCHEMA["properties"]["riskLevel"]
        assert rl_schema["enum"] == ["LOW", "MEDIUM", "HIGH"]
