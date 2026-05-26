"""Guardrails engine for pricing scenario validation.

Implements pure functions for enforcing pricing compliance rules:
- Below-cost rejection (Requirement 8.1)
- MAP enforcement (Requirement 8.2)
- Geographic bias detection (Requirement 8.3)
- PII protection (Requirement 8.4)

All functions are pure (no side effects, no AWS calls) and return
structured GuardrailResult objects.
"""

import re
from dataclasses import dataclass

from shared.models.pricing_scenario import GuardrailResult


# Default threshold for geographic bias detection (15% of mean price)
DEFAULT_GEO_BIAS_THRESHOLD = 15.0

# PII patterns for detection
_EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)
_PHONE_PATTERN = re.compile(
    r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
)
_ACCOUNT_ID_PATTERN = re.compile(
    r"\b(?:account[_\-\s]?(?:id|number|#)?[:\s]*)\d{6,}\b",
    re.IGNORECASE,
)
# AWS account IDs (12 digits)
_AWS_ACCOUNT_PATTERN = re.compile(r"\b\d{12}\b")
# SSN pattern
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# Credit card pattern (basic)
_CREDIT_CARD_PATTERN = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")


@dataclass
class ProductCostInfo:
    """Product cost information for guardrail evaluation."""

    product_id: str
    total_unit_cost: float
    minimum_advertised_price: float | None = None


@dataclass
class RegionalPrice:
    """Price for a product in a specific region."""

    product_id: str
    region: str
    price: float


def check_below_cost(
    price: float,
    total_unit_cost: float,
) -> GuardrailResult:
    """Check if a price is at or above the total unit cost.

    Requirement 8.1: Reject any scenario where the recommended price
    is below the product's total unit cost.

    Args:
        price: The recommended price for the product.
        total_unit_cost: The total unit cost of the product.

    Returns:
        GuardrailResult with pass/fail and reason.
    """
    passed = price >= total_unit_cost
    reason = None if passed else (
        f"Price {price:.4f} is below total unit cost {total_unit_cost:.4f}"
    )
    return GuardrailResult(rule="below-cost", passed=passed, reason=reason)


def check_map_compliance(
    price: float,
    minimum_advertised_price: float | None,
) -> GuardrailResult:
    """Check if a price meets the Minimum Advertised Price constraint.

    Requirement 8.2: Reject any scenario that violates MAP agreements
    for products with MAP constraints.

    Args:
        price: The recommended price for the product.
        minimum_advertised_price: The MAP for the product, or None if no MAP applies.

    Returns:
        GuardrailResult with pass/fail and reason.
    """
    if minimum_advertised_price is None:
        return GuardrailResult(
            rule="MAP-enforcement",
            passed=True,
            reason="No MAP constraint applies",
        )

    passed = price >= minimum_advertised_price
    reason = None if passed else (
        f"Price {price:.4f} is below minimum advertised price "
        f"{minimum_advertised_price:.4f}"
    )
    return GuardrailResult(rule="MAP-enforcement", passed=passed, reason=reason)


def check_geographic_bias(
    regional_prices: list[RegionalPrice],
    threshold_percent: float = DEFAULT_GEO_BIAS_THRESHOLD,
) -> GuardrailResult:
    """Check if price variance across regions exceeds the threshold.

    Requirement 8.3: Flag any scenario where the price variance across
    geographic regions for the same product exceeds a configurable threshold
    expressed as a percentage of the mean price (default 15%).

    The variance is calculated as:
        max_variance = max(prices) - min(prices)
        flagged if max_variance > (threshold_percent / 100) * mean_price

    Args:
        regional_prices: List of prices across regions for the same product.
        threshold_percent: Maximum allowed variance as percentage of mean price.

    Returns:
        GuardrailResult with pass/fail and reason.
    """
    if len(regional_prices) <= 1:
        return GuardrailResult(
            rule="geographic-bias",
            passed=True,
            reason="Single region or no regional data; no bias possible",
        )

    prices = [rp.price for rp in regional_prices]
    mean_price = sum(prices) / len(prices)

    if mean_price == 0:
        return GuardrailResult(
            rule="geographic-bias",
            passed=True,
            reason="Mean price is zero; cannot calculate variance percentage",
        )

    max_price = max(prices)
    min_price = min(prices)
    max_variance = max_price - min_price
    variance_percent = (max_variance / mean_price) * 100

    passed = variance_percent <= threshold_percent
    reason = None if passed else (
        f"Regional price variance {variance_percent:.2f}% exceeds "
        f"threshold {threshold_percent:.2f}% of mean price {mean_price:.4f} "
        f"(range: {min_price:.4f} to {max_price:.4f})"
    )
    return GuardrailResult(rule="geographic-bias", passed=passed, reason=reason)


def check_pii_protection(text: str) -> GuardrailResult:
    """Check if text contains personally identifiable information (PII).

    Requirement 8.4: Prevent customer-identifiable data including customer
    names, account identifiers, and purchase history from being included
    in agent-to-agent communications or scenario outputs.

    Checks for:
    - Email addresses
    - Phone numbers
    - Account identifiers
    - SSNs
    - Credit card numbers

    Args:
        text: The text to check for PII patterns.

    Returns:
        GuardrailResult with pass/fail and reason.
    """
    pii_found: list[str] = []

    if _EMAIL_PATTERN.search(text):
        pii_found.append("email address")

    if _PHONE_PATTERN.search(text):
        pii_found.append("phone number")

    if _ACCOUNT_ID_PATTERN.search(text):
        pii_found.append("account identifier")

    if _SSN_PATTERN.search(text):
        pii_found.append("SSN")

    if _CREDIT_CARD_PATTERN.search(text):
        pii_found.append("credit card number")

    passed = len(pii_found) == 0
    reason = None if passed else (
        f"PII detected: {', '.join(pii_found)}"
    )
    return GuardrailResult(rule="PII-protection", passed=passed, reason=reason)


def run_all_guardrails(
    price: float,
    total_unit_cost: float,
    minimum_advertised_price: float | None = None,
    regional_prices: list[RegionalPrice] | None = None,
    agent_communication_text: str | None = None,
    geo_bias_threshold_percent: float = DEFAULT_GEO_BIAS_THRESHOLD,
) -> list[GuardrailResult]:
    """Run all guardrail checks on a pricing scenario.

    Executes all four guardrail rules and returns structured results
    for each rule evaluation.

    Args:
        price: The recommended price for the product.
        total_unit_cost: The total unit cost of the product.
        minimum_advertised_price: The MAP for the product, or None if no MAP.
        regional_prices: List of prices across regions for geographic bias check.
        agent_communication_text: Text from agent communications to check for PII.
        geo_bias_threshold_percent: Threshold for geographic bias (default 15%).

    Returns:
        List of GuardrailResult objects, one per rule evaluated.
    """
    results: list[GuardrailResult] = []

    # 1. Below-cost check
    results.append(check_below_cost(price, total_unit_cost))

    # 2. MAP enforcement
    results.append(check_map_compliance(price, minimum_advertised_price))

    # 3. Geographic bias detection
    if regional_prices is not None:
        results.append(
            check_geographic_bias(regional_prices, geo_bias_threshold_percent)
        )

    # 4. PII protection
    if agent_communication_text is not None:
        results.append(check_pii_protection(agent_communication_text))

    return results
