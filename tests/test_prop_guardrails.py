"""Property-based tests for the guardrails engine.

Uses hypothesis to validate universal correctness properties of guardrail
functions across all valid inputs.

Feature: retail-dynamic-pricing
Validates: Requirements 8.1, 8.2, 8.3
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from shared.guardrails import (
    RegionalPrice,
    check_below_cost,
    check_geographic_bias,
    check_map_compliance,
)


# --- Strategies ---

# Positive finite floats for prices and costs
positive_price = st.floats(min_value=0.01, max_value=1_000_000.0, allow_nan=False, allow_infinity=False)
non_negative_price = st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False)
threshold_percent = st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False)


@st.composite
def price_below_cost(draw):
    """Generate a (price, cost) pair where price < cost."""
    cost = draw(st.floats(min_value=0.01, max_value=1_000_000.0, allow_nan=False, allow_infinity=False))
    # price must be strictly less than cost
    price = draw(st.floats(min_value=0.0, max_value=cost, allow_nan=False, allow_infinity=False, exclude_max=True))
    return price, cost


@st.composite
def price_at_or_above_cost(draw):
    """Generate a (price, cost) pair where price >= cost."""
    cost = draw(st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False))
    price = draw(st.floats(min_value=cost, max_value=2_000_000.0, allow_nan=False, allow_infinity=False))
    return price, cost


@st.composite
def price_below_map(draw):
    """Generate a (price, MAP) pair where price < MAP."""
    map_price = draw(st.floats(min_value=0.01, max_value=1_000_000.0, allow_nan=False, allow_infinity=False))
    price = draw(st.floats(min_value=0.0, max_value=map_price, allow_nan=False, allow_infinity=False, exclude_max=True))
    return price, map_price


@st.composite
def price_at_or_above_map(draw):
    """Generate a (price, MAP) pair where price >= MAP."""
    map_price = draw(st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False))
    price = draw(st.floats(min_value=map_price, max_value=2_000_000.0, allow_nan=False, allow_infinity=False))
    return price, map_price


@st.composite
def regional_prices_exceeding_threshold(draw):
    """Generate regional prices where (max-min)/mean > threshold/100."""
    threshold = draw(st.floats(min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False))
    # Generate a mean price
    mean_price = draw(st.floats(min_value=10.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    # The spread must exceed threshold% of mean
    # We need (max - min) / mean > threshold / 100
    # So spread > mean * threshold / 100
    min_spread = mean_price * threshold / 100.0
    # Add a buffer to ensure we're strictly above
    spread = draw(st.floats(
        min_value=min_spread * 1.01,
        max_value=min_spread * 3.0,
        allow_nan=False,
        allow_infinity=False,
    ))
    # Create min and max prices around the mean
    min_price = mean_price - spread / 2.0
    max_price = mean_price + spread / 2.0
    assume(min_price > 0)
    assume(max_price > 0)

    # Generate 2-5 regional prices between min and max
    num_regions = draw(st.integers(min_value=2, max_value=5))
    regions = [f"region-{i}" for i in range(num_regions)]
    prices = [min_price, max_price]  # Ensure min and max are present
    for _ in range(num_regions - 2):
        p = draw(st.floats(min_value=min_price, max_value=max_price, allow_nan=False, allow_infinity=False))
        prices.append(p)

    regional = [
        RegionalPrice(product_id="prod-1", region=regions[i], price=prices[i])
        for i in range(num_regions)
    ]
    # Verify actual variance strictly exceeds threshold with the real mean
    # Use a small epsilon to avoid floating-point boundary cases where
    # the implementation's <= check passes at exact equality
    actual_mean = sum(prices[:num_regions]) / num_regions
    actual_variance_pct = (max(prices[:num_regions]) - min(prices[:num_regions])) / actual_mean * 100
    assume(actual_variance_pct > threshold + 1e-9)
    return regional, threshold


# --- Property 11: Below-cost guardrail rejects correctly ---


class TestProperty11BelowCostGuardrail:
    """Property 11: Below-cost guardrail rejects correctly.

    For any price < total_unit_cost, check_below_cost must return passed=False.
    For any price >= total_unit_cost, must return passed=True.

    **Validates: Requirements 8.1**
    """

    @settings(max_examples=100)
    @given(data=price_below_cost())
    def test_price_below_cost_is_rejected(self, data):
        """For any price < total_unit_cost, the guardrail must reject (passed=False)."""
        price, cost = data
        result = check_below_cost(price, cost)
        assert result.passed is False, (
            f"Expected rejection for price={price} < cost={cost}, got passed=True"
        )
        assert result.rule == "below-cost"
        assert result.reason is not None

    @settings(max_examples=100)
    @given(data=price_at_or_above_cost())
    def test_price_at_or_above_cost_passes(self, data):
        """For any price >= total_unit_cost, the guardrail must pass (passed=True)."""
        price, cost = data
        result = check_below_cost(price, cost)
        assert result.passed is True, (
            f"Expected pass for price={price} >= cost={cost}, got passed=False"
        )
        assert result.rule == "below-cost"
        assert result.reason is None


# --- Property 12: MAP guardrail rejects correctly ---


class TestProperty12MAPGuardrail:
    """Property 12: MAP guardrail rejects correctly.

    For any price < MAP (when MAP is not None), check_map_compliance must return passed=False.
    For any price >= MAP, must return passed=True.

    **Validates: Requirements 8.2**
    """

    @settings(max_examples=100)
    @given(data=price_below_map())
    def test_price_below_map_is_rejected(self, data):
        """For any price < MAP, the guardrail must reject (passed=False)."""
        price, map_price = data
        result = check_map_compliance(price, map_price)
        assert result.passed is False, (
            f"Expected rejection for price={price} < MAP={map_price}, got passed=True"
        )
        assert result.rule == "MAP-enforcement"
        assert result.reason is not None

    @settings(max_examples=100)
    @given(data=price_at_or_above_map())
    def test_price_at_or_above_map_passes(self, data):
        """For any price >= MAP, the guardrail must pass (passed=True)."""
        price, map_price = data
        result = check_map_compliance(price, map_price)
        assert result.passed is True, (
            f"Expected pass for price={price} >= MAP={map_price}, got passed=False"
        )
        assert result.rule == "MAP-enforcement"
        assert result.reason is None

    @settings(max_examples=100)
    @given(price=non_negative_price)
    def test_none_map_always_passes(self, price):
        """When MAP is None, the guardrail must always pass."""
        result = check_map_compliance(price, None)
        assert result.passed is True
        assert result.rule == "MAP-enforcement"


# --- Property 13: Geographic bias guardrail flags correctly ---


class TestProperty13GeographicBiasGuardrail:
    """Property 13: Geographic bias guardrail flags correctly.

    For any set of regional prices where (max-min)/mean > threshold/100,
    check_geographic_bias must return passed=False.

    **Validates: Requirements 8.3**
    """

    @settings(max_examples=100)
    @given(data=regional_prices_exceeding_threshold())
    def test_variance_exceeding_threshold_is_flagged(self, data):
        """When regional price variance exceeds threshold, guardrail must flag (passed=False)."""
        regional_prices, threshold = data
        result = check_geographic_bias(regional_prices, threshold_percent=threshold)
        assert result.passed is False, (
            f"Expected flag for variance exceeding {threshold}% threshold, "
            f"prices={[rp.price for rp in regional_prices]}"
        )
        assert result.rule == "geographic-bias"
        assert result.reason is not None

    @settings(max_examples=100)
    @given(
        price=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        num_regions=st.integers(min_value=2, max_value=10),
    )
    def test_uniform_prices_always_pass(self, price, num_regions):
        """When all regional prices are identical, variance is 0 and guardrail must pass."""
        regional_prices = [
            RegionalPrice(product_id="prod-1", region=f"region-{i}", price=price)
            for i in range(num_regions)
        ]
        result = check_geographic_bias(regional_prices)
        assert result.passed is True, (
            f"Expected pass for uniform prices={price} across {num_regions} regions"
        )
        assert result.rule == "geographic-bias"

    @settings(max_examples=100)
    @given(
        price=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    )
    def test_single_region_always_passes(self, price):
        """A single region cannot have geographic bias."""
        regional_prices = [
            RegionalPrice(product_id="prod-1", region="region-0", price=price)
        ]
        result = check_geographic_bias(regional_prices)
        assert result.passed is True
