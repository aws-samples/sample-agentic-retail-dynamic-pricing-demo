"""Guardrails Demo API handler.

Provides a /guardrails/demo endpoint that runs guardrail checks with
intentionally violating inputs to demonstrate compliance enforcement.

This handler is SELF-CONTAINED — it does not import from shared/guardrails.py
because the Lambda deployment package only includes the api_handlers/ directory.
The guardrail logic is duplicated here intentionally for deployment simplicity.
"""

import json
import re

try:
    from log_config import configure_logging
except ImportError:
    from backend.api_handlers.log_config import configure_logging

logger = configure_logging(__name__)


# --- Inline guardrail functions (self-contained for Lambda deployment) ---

def _check_below_cost(price: float, total_unit_cost: float) -> dict:
    passed = price >= total_unit_cost
    reason = None if passed else (
        f"Price ${price:.2f} is below total unit cost ${total_unit_cost:.2f}"
    )
    return {"rule": "below-cost", "passed": passed, "reason": reason}


def _check_map_compliance(price: float, map_price: float | None) -> dict:
    if map_price is None:
        return {"rule": "MAP-enforcement", "passed": True, "reason": "No MAP constraint"}
    passed = price >= map_price
    reason = None if passed else (
        f"Price ${price:.2f} is below Minimum Advertised Price ${map_price:.2f}"
    )
    return {"rule": "MAP-enforcement", "passed": passed, "reason": reason}


def _check_geographic_bias(regional_prices: list[dict], threshold_pct: float = 15.0) -> dict:
    if len(regional_prices) <= 1:
        return {"rule": "geographic-bias", "passed": True, "reason": "Single region"}
    prices = [rp["price"] for rp in regional_prices]
    mean_price = sum(prices) / len(prices)
    if mean_price == 0:
        return {"rule": "geographic-bias", "passed": True, "reason": "Zero mean"}
    max_variance = max(prices) - min(prices)
    variance_pct = (max_variance / mean_price) * 100
    passed = variance_pct <= threshold_pct
    reason = None if passed else (
        f"Regional price variance {variance_pct:.1f}% exceeds "
        f"{threshold_pct:.1f}% threshold (range: ${min(prices):.2f} to ${max(prices):.2f}, mean: ${mean_price:.2f})"
    )
    return {"rule": "geographic-bias", "passed": passed, "reason": reason}


def _check_pii(text: str) -> dict:
    pii_found = []
    if re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text):
        pii_found.append("email address")
    if re.search(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text):
        pii_found.append("phone number")
    if re.search(r"\baccount[_\-\s]?(?:id|number|#)?[:\s]*\d{6,}\b", text, re.IGNORECASE):
        pii_found.append("account identifier")
    if re.search(r"\b\d{3}-\d{2}-\d{4}\b", text):
        pii_found.append("SSN")
    if re.search(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", text):
        pii_found.append("credit card number")
    passed = len(pii_found) == 0
    reason = None if passed else f"PII detected: {', '.join(pii_found)}"
    return {"rule": "PII-protection", "passed": passed, "reason": reason}


# --- Demo scenarios ---

DEMO_SCENARIOS = {
    "below_cost": {
        "description": "Pricing Wireless Earbuds below manufacturing cost",
        "product_id": "ELEC-001",
        "product_name": "ProSound Wireless Earbuds",
        "attempted_price": 55.00,
        "total_unit_cost": 71.50,
        "map_price": None,
    },
    "map_violation": {
        "description": "Advertising Smart Watch below manufacturer's MAP",
        "product_id": "ELEC-003",
        "product_name": "FitTrack Pro Smartwatch",
        "attempted_price": 249.99,
        "total_unit_cost": 180.00,
        "map_price": 279.99,
    },
    "geographic_bias": {
        "description": "Setting 35% price variance across US regions for same product",
        "product_id": "HOME-002",
        "product_name": "CleanForce Stick Vacuum",
        "attempted_price": 199.99,
        "total_unit_cost": 45.50,
        "regional_prices": [
            {"region": "US-East", "price": 169.99},
            {"region": "US-West", "price": 229.99},
            {"region": "US-Central", "price": 199.99},
        ],
    },
    "predatory_pricing": {
        "description": "Attempting predatory pricing to eliminate competitor",
        "product_id": "GROC-002",
        "product_name": "Mountain Roast Coffee",
        "attempted_price": 3.99,
        "total_unit_cost": 12.00,
        "agent_text": "Set price at $3.99 to undercut CompetitorX at $8.99 and drive them out of the coffee market entirely.",
    },
    "pii_protection": {
        "description": "Customer PII detected in agent communication",
        "product_id": "ELEC-005",
        "product_name": "Noise Cancelling Headphones",
        "attempted_price": 249.99,
        "total_unit_cost": 95.00,
        "agent_text": "Based on purchase history of customer john.doe@example.com (account ID: 123456789, phone: 555-123-4567), recommend premium pricing.",
    },
    "price_fixing": {
        "description": "Attempting to coordinate prices with competitors",
        "product_id": "ELEC-002",
        "product_name": "Bluetooth Speaker",
        "attempted_price": 149.99,
        "total_unit_cost": 71.50,
        "agent_text": "Per our agreement with MegaMart and ValueStore, all retailers will maintain the $149.99 price point. No discounting below this coordinated floor.",
    },
}


# --- Handler functions per guardrail type ---

def _run_below_cost(s):
    r = _check_below_cost(s["attempted_price"], s["total_unit_cost"])
    return {**r, "scenario": {"productId": s["product_id"], "productName": s["product_name"],
            "attemptedPrice": s["attempted_price"], "costOrThreshold": s["total_unit_cost"]}}

def _run_map_violation(s):
    r = _check_map_compliance(s["attempted_price"], s["map_price"])
    return {**r, "scenario": {"productId": s["product_id"], "productName": s["product_name"],
            "attemptedPrice": s["attempted_price"], "costOrThreshold": s["map_price"]}}

def _run_geographic_bias(s):
    r = _check_geographic_bias(s["regional_prices"])
    prices = [rp["price"] for rp in s["regional_prices"]]
    mean_p = sum(prices) / len(prices)
    return {**r, "scenario": {"productId": s["product_id"], "productName": s["product_name"],
            "attemptedPrice": mean_p, "costOrThreshold": mean_p * 0.15}}

def _run_predatory_pricing(s):
    cost_r = _check_below_cost(s["attempted_price"], s["total_unit_cost"])
    return {
        "rule": "below-cost + predatory-intent",
        "passed": False,
        "reason": (
            f"{cost_r['reason']}. Additionally, the strategy describes predatory intent "
            f"to eliminate competitors — blocked by Bedrock Guardrails (Sherman Act Section 2)."
        ),
        "scenario": {"productId": s["product_id"], "productName": s["product_name"],
                     "attemptedPrice": s["attempted_price"], "costOrThreshold": s["total_unit_cost"]},
    }

def _run_pii_protection(s):
    r = _check_pii(s.get("agent_text", ""))
    return {**r, "scenario": {"productId": s["product_id"], "productName": s["product_name"],
            "attemptedPrice": s["attempted_price"], "costOrThreshold": 0}}

def _run_price_fixing(s):
    return {
        "rule": "price-coordination-blocked",
        "passed": False,
        "reason": (
            "BLOCKED: Communication contains price coordination language "
            "('agreement', 'coordinated floor', 'all retailers will maintain'). "
            "This constitutes price fixing — per se illegal under Sherman Act Section 1."
        ),
        "scenario": {"productId": s["product_id"], "productName": s["product_name"],
                     "attemptedPrice": s["attempted_price"], "costOrThreshold": s["attempted_price"]},
    }


HANDLERS = {
    "below_cost": _run_below_cost,
    "map_violation": _run_map_violation,
    "geographic_bias": _run_geographic_bias,
    "predatory_pricing": _run_predatory_pricing,
    "pii_protection": _run_pii_protection,
    "price_fixing": _run_price_fixing,
}


def handler(event, context):
    """Lambda handler for POST /guardrails/demo."""
    logger.info("Guardrails Demo invoked")

    # Parse body
    try:
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        elif isinstance(event.get("body"), dict):
            body = event["body"]
        else:
            body = event
    except (json.JSONDecodeError, TypeError, AttributeError):
        return _response(400, {"error": "Invalid request body"})

    guardrail_type = body.get("guardrailType")

    if not guardrail_type or guardrail_type not in HANDLERS:
        return _response(400, {
            "error": f"Invalid guardrailType. Available: {list(HANDLERS.keys())}"
        })

    scenario = DEMO_SCENARIOS[guardrail_type]
    result = HANDLERS[guardrail_type](scenario)

    return _response(200, result)


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(body),
    }
