"""Unit tests for the guardrails engine.

Tests below-cost rejection, MAP enforcement, geographic bias detection,
PII protection, and the combined guardrails runner.

Validates: Requirements 8.1, 8.2, 8.3, 8.4
"""

import pytest

from shared.guardrails import (
    DEFAULT_GEO_BIAS_THRESHOLD,
    ProductCostInfo,
    RegionalPrice,
    check_below_cost,
    check_geographic_bias,
    check_map_compliance,
    check_pii_protection,
    run_all_guardrails,
)
from shared.models.pricing_scenario import GuardrailResult


class TestBelowCostGuardrail:
    """Tests for below-cost rejection (Requirement 8.1)."""

    def test_price_above_cost_passes(self):
        result = check_below_cost(price=30.00, total_unit_cost=20.00)
        assert result.passed is True
        assert result.rule == "below-cost"
        assert result.reason is None

    def test_price_equal_to_cost_passes(self):
        result = check_below_cost(price=20.00, total_unit_cost=20.00)
        assert result.passed is True
        assert result.rule == "below-cost"

    def test_price_below_cost_fails(self):
        result = check_below_cost(price=15.00, total_unit_cost=20.00)
        assert result.passed is False
        assert result.rule == "below-cost"
        assert "below total unit cost" in result.reason

    def test_price_slightly_below_cost_fails(self):
        result = check_below_cost(price=19.9999, total_unit_cost=20.0000)
        assert result.passed is False

    def test_zero_price_below_positive_cost_fails(self):
        result = check_below_cost(price=0.0, total_unit_cost=5.00)
        assert result.passed is False

    def test_zero_cost_with_zero_price_passes(self):
        result = check_below_cost(price=0.0, total_unit_cost=0.0)
        assert result.passed is True


class TestMAPEnforcement:
    """Tests for MAP enforcement (Requirement 8.2)."""

    def test_price_above_map_passes(self):
        result = check_map_compliance(price=50.00, minimum_advertised_price=40.00)
        assert result.passed is True
        assert result.rule == "MAP-enforcement"
        assert result.reason is None

    def test_price_equal_to_map_passes(self):
        result = check_map_compliance(price=40.00, minimum_advertised_price=40.00)
        assert result.passed is True

    def test_price_below_map_fails(self):
        result = check_map_compliance(price=35.00, minimum_advertised_price=40.00)
        assert result.passed is False
        assert result.rule == "MAP-enforcement"
        assert "below minimum advertised price" in result.reason

    def test_no_map_constraint_passes(self):
        result = check_map_compliance(price=10.00, minimum_advertised_price=None)
        assert result.passed is True
        assert "No MAP constraint" in result.reason

    def test_price_slightly_below_map_fails(self):
        result = check_map_compliance(price=39.9999, minimum_advertised_price=40.0000)
        assert result.passed is False


class TestGeographicBiasDetection:
    """Tests for geographic bias detection (Requirement 8.3)."""

    def test_uniform_prices_pass(self):
        regional_prices = [
            RegionalPrice(product_id="p1", region="US-East", price=30.00),
            RegionalPrice(product_id="p1", region="US-West", price=30.00),
            RegionalPrice(product_id="p1", region="EU", price=30.00),
        ]
        result = check_geographic_bias(regional_prices)
        assert result.passed is True
        assert result.rule == "geographic-bias"

    def test_variance_within_threshold_passes(self):
        # Mean = 30, range = 3 (10% of mean), threshold = 15%
        regional_prices = [
            RegionalPrice(product_id="p1", region="US-East", price=28.50),
            RegionalPrice(product_id="p1", region="US-West", price=31.50),
            RegionalPrice(product_id="p1", region="EU", price=30.00),
        ]
        result = check_geographic_bias(regional_prices)
        assert result.passed is True

    def test_variance_exceeds_threshold_fails(self):
        # Mean = 30, range = 10 (33% of mean), threshold = 15%
        regional_prices = [
            RegionalPrice(product_id="p1", region="US-East", price=25.00),
            RegionalPrice(product_id="p1", region="US-West", price=35.00),
            RegionalPrice(product_id="p1", region="EU", price=30.00),
        ]
        result = check_geographic_bias(regional_prices)
        assert result.passed is False
        assert "exceeds threshold" in result.reason

    def test_single_region_passes(self):
        regional_prices = [
            RegionalPrice(product_id="p1", region="US-East", price=30.00),
        ]
        result = check_geographic_bias(regional_prices)
        assert result.passed is True

    def test_empty_list_passes(self):
        result = check_geographic_bias([])
        assert result.passed is True

    def test_custom_threshold(self):
        # Mean = 100, range = 12 (12% of mean)
        regional_prices = [
            RegionalPrice(product_id="p1", region="US-East", price=94.00),
            RegionalPrice(product_id="p1", region="US-West", price=106.00),
        ]
        # With 10% threshold, should fail
        result = check_geographic_bias(regional_prices, threshold_percent=10.0)
        assert result.passed is False

        # With 15% threshold, should pass
        result = check_geographic_bias(regional_prices, threshold_percent=15.0)
        assert result.passed is True

    def test_variance_exactly_at_threshold_passes(self):
        # Mean = 100, range = 15 (15% of mean), threshold = 15%
        regional_prices = [
            RegionalPrice(product_id="p1", region="US-East", price=92.50),
            RegionalPrice(product_id="p1", region="US-West", price=107.50),
        ]
        result = check_geographic_bias(regional_prices, threshold_percent=15.0)
        assert result.passed is True


class TestPIIProtection:
    """Tests for PII protection (Requirement 8.4)."""

    def test_clean_text_passes(self):
        text = "Product pricing analysis shows 15% margin improvement."
        result = check_pii_protection(text)
        assert result.passed is True
        assert result.rule == "PII-protection"
        assert result.reason is None

    def test_email_detected(self):
        text = "Customer john.doe@example.com placed an order."
        result = check_pii_protection(text)
        assert result.passed is False
        assert "email address" in result.reason

    def test_phone_number_detected(self):
        text = "Contact customer at 555-123-4567 for feedback."
        result = check_pii_protection(text)
        assert result.passed is False
        assert "phone number" in result.reason

    def test_phone_with_country_code_detected(self):
        text = "Call +1-555-123-4567 for details."
        result = check_pii_protection(text)
        assert result.passed is False
        assert "phone number" in result.reason

    def test_account_id_detected(self):
        text = "Account ID: 123456789 has high purchase frequency."
        result = check_pii_protection(text)
        assert result.passed is False
        assert "account identifier" in result.reason

    def test_ssn_detected(self):
        text = "SSN 123-45-6789 found in records."
        result = check_pii_protection(text)
        assert result.passed is False
        assert "SSN" in result.reason

    def test_credit_card_detected(self):
        text = "Card number 4111-1111-1111-1111 on file."
        result = check_pii_protection(text)
        assert result.passed is False
        assert "credit card number" in result.reason

    def test_multiple_pii_types_detected(self):
        text = "Customer john@example.com called from 555-123-4567."
        result = check_pii_protection(text)
        assert result.passed is False
        assert "email address" in result.reason
        assert "phone number" in result.reason

    def test_empty_text_passes(self):
        result = check_pii_protection("")
        assert result.passed is True

    def test_numeric_data_without_pii_passes(self):
        text = "Revenue increased by $150,000 with 23.5% margin."
        result = check_pii_protection(text)
        assert result.passed is True


class TestRunAllGuardrails:
    """Tests for the combined guardrails runner."""

    def test_all_pass_scenario(self):
        results = run_all_guardrails(
            price=50.00,
            total_unit_cost=30.00,
            minimum_advertised_price=40.00,
            regional_prices=[
                RegionalPrice(product_id="p1", region="US-East", price=50.00),
                RegionalPrice(product_id="p1", region="US-West", price=51.00),
            ],
            agent_communication_text="Clean pricing analysis text.",
        )
        assert len(results) == 4
        assert all(r.passed for r in results)

    def test_below_cost_fails_in_combined(self):
        results = run_all_guardrails(
            price=25.00,
            total_unit_cost=30.00,
        )
        below_cost = next(r for r in results if r.rule == "below-cost")
        assert below_cost.passed is False

    def test_map_fails_in_combined(self):
        results = run_all_guardrails(
            price=35.00,
            total_unit_cost=30.00,
            minimum_advertised_price=40.00,
        )
        map_result = next(r for r in results if r.rule == "MAP-enforcement")
        assert map_result.passed is False

    def test_geo_bias_fails_in_combined(self):
        results = run_all_guardrails(
            price=50.00,
            total_unit_cost=30.00,
            regional_prices=[
                RegionalPrice(product_id="p1", region="US-East", price=40.00),
                RegionalPrice(product_id="p1", region="US-West", price=60.00),
            ],
        )
        geo_result = next(r for r in results if r.rule == "geographic-bias")
        assert geo_result.passed is False

    def test_pii_fails_in_combined(self):
        results = run_all_guardrails(
            price=50.00,
            total_unit_cost=30.00,
            agent_communication_text="Customer email: test@example.com",
        )
        pii_result = next(r for r in results if r.rule == "PII-protection")
        assert pii_result.passed is False

    def test_optional_checks_skipped_when_none(self):
        results = run_all_guardrails(
            price=50.00,
            total_unit_cost=30.00,
        )
        # Only below-cost and MAP (with None MAP) should be present
        assert len(results) == 2
        rules = [r.rule for r in results]
        assert "below-cost" in rules
        assert "MAP-enforcement" in rules

    def test_custom_geo_threshold(self):
        results = run_all_guardrails(
            price=50.00,
            total_unit_cost=30.00,
            regional_prices=[
                RegionalPrice(product_id="p1", region="US-East", price=45.00),
                RegionalPrice(product_id="p1", region="US-West", price=55.00),
            ],
            geo_bias_threshold_percent=25.0,
        )
        geo_result = next(r for r in results if r.rule == "geographic-bias")
        # Mean = 50, range = 10, variance = 20% < 25% threshold
        assert geo_result.passed is True

    def test_results_are_guardrail_result_instances(self):
        results = run_all_guardrails(
            price=50.00,
            total_unit_cost=30.00,
        )
        for result in results:
            assert isinstance(result, GuardrailResult)

    def test_multiple_failures(self):
        results = run_all_guardrails(
            price=15.00,
            total_unit_cost=30.00,
            minimum_advertised_price=40.00,
            regional_prices=[
                RegionalPrice(product_id="p1", region="US-East", price=10.00),
                RegionalPrice(product_id="p1", region="US-West", price=50.00),
            ],
            agent_communication_text="Contact john@example.com",
        )
        failed = [r for r in results if not r.passed]
        assert len(failed) == 4  # All four should fail
