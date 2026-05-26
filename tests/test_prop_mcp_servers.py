"""Property-based tests for MCP Server responses.

Uses hypothesis to validate that MCP Server responses conform to the
expected schema and that randomized data stays within specified variance bounds.

Feature: retail-dynamic-pricing
Validates: Requirements 2.5, 2.6
"""

import json

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from backend.mcp_servers.competitor_api.handler import (
    handler as competitor_handler,
    PRODUCT_BASELINES as COMPETITOR_BASELINES,
    PRICE_VARIANCE,
)
from backend.mcp_servers.erp_pos.handler import (
    handler as erp_pos_handler,
    BASELINE_WEEKLY_UNITS,
    BASELINE_MONTHLY_UNITS,
    BASELINE_HOURLY_TRANSACTIONS,
    BASELINE_WAREHOUSE_STOCK,
    BASELINE_STORE_STOCK,
)
from backend.mcp_servers.cost_finance.handler import (
    handler as cost_finance_handler,
    COST_VARIANCE,
    BASELINE_COSTS,
)
from backend.mcp_servers.market_signals.handler import (
    handler as market_signals_handler,
)


# --- Strategies ---

# Product IDs known to the competitor API server
competitor_product_ids = st.sampled_from(list(COMPETITOR_BASELINES.keys()))

# Cost finance categories
cost_categories = st.sampled_from(list(BASELINE_COSTS.keys()))

# Competitor API tools
competitor_tools = st.sampled_from(["get_competitor_prices", "get_price_history", "get_market_position"])

# ERP/POS tools
erp_pos_tools = st.sampled_from(["get_sales_history", "get_pos_realtime", "get_inventory_levels", "get_elasticity_data"])

# Market signals tools
market_signals_tools = st.sampled_from(["get_market_trends", "get_consumer_sentiment", "get_macro_indicators"])

# Cost finance tools
cost_finance_tools = st.sampled_from(["get_cost_structure", "get_margin_targets", "get_financial_constraints"])


def _parse_response_body(response: dict) -> dict:
    """Parse the JSON body from a Lambda response."""
    body = response.get("body")
    if isinstance(body, str):
        return json.loads(body)
    return body


# --- Property 2: MCP Server responses conform to schema ---


class TestProperty2MCPResponseSchema:
    """Property 2: MCP Server responses conform to schema.

    For any valid tool invocation to any MCP Server, the returned JSON response
    SHALL contain a `status` field (either "success" or "error") and a `data`
    field (object), and a `metadata` field (dict with timestamp, source, latencyMs).

    **Validates: Requirements 2.5**
    """

    @settings(max_examples=100)
    @given(
        product_id=competitor_product_ids,
        tool=competitor_tools,
    )
    def test_competitor_api_response_conforms_to_schema(self, product_id, tool):
        """Competitor API Server responses must have status, data, and metadata fields."""
        event = {"tool": tool, "params": {"product_id": product_id}}
        response = competitor_handler(event, None)

        body = _parse_response_body(response)

        # status must be present and valid
        assert "status" in body, "Response missing 'status' field"
        assert body["status"] in ("success", "error"), (
            f"status must be 'success' or 'error', got '{body['status']}'"
        )

        # data must be present and a dict
        assert "data" in body, "Response missing 'data' field"
        assert isinstance(body["data"], dict), (
            f"'data' must be a dict, got {type(body['data']).__name__}"
        )

        # metadata must be present with required fields
        assert "metadata" in body, "Response missing 'metadata' field"
        metadata = body["metadata"]
        assert isinstance(metadata, dict), "'metadata' must be a dict"
        assert "timestamp" in metadata, "metadata missing 'timestamp'"
        assert "source" in metadata, "metadata missing 'source'"
        assert "latencyMs" in metadata, "metadata missing 'latencyMs'"
        assert isinstance(metadata["latencyMs"], int), "latencyMs must be an integer"

    @settings(max_examples=100)
    @given(tool=erp_pos_tools)
    def test_erp_pos_response_conforms_to_schema(self, tool):
        """ERP/POS Server responses must have status, data, and metadata fields."""
        event = {"tool": tool, "params": {"product_id": "PROD-001"}}
        response = erp_pos_handler(event, None)

        body = _parse_response_body(response)

        assert "status" in body, "Response missing 'status' field"
        assert body["status"] in ("success", "error"), (
            f"status must be 'success' or 'error', got '{body['status']}'"
        )

        assert "data" in body, "Response missing 'data' field"
        assert isinstance(body["data"], dict), (
            f"'data' must be a dict, got {type(body['data']).__name__}"
        )

        assert "metadata" in body, "Response missing 'metadata' field"
        metadata = body["metadata"]
        assert isinstance(metadata, dict), "'metadata' must be a dict"
        assert "timestamp" in metadata, "metadata missing 'timestamp'"
        assert "source" in metadata, "metadata missing 'source'"
        assert "latencyMs" in metadata, "metadata missing 'latencyMs'"
        assert isinstance(metadata["latencyMs"], int), "latencyMs must be an integer"

    @settings(max_examples=100)
    @given(tool=market_signals_tools)
    def test_market_signals_response_conforms_to_schema(self, tool):
        """Market Signals Server responses must have status, data, and metadata fields."""
        params = {"category": "electronics", "region": "US", "channel": "online"}
        event = {"tool": tool, "params": params}
        response = market_signals_handler(event, None)

        body = _parse_response_body(response)

        assert "status" in body, "Response missing 'status' field"
        assert body["status"] in ("success", "error"), (
            f"status must be 'success' or 'error', got '{body['status']}'"
        )

        assert "data" in body, "Response missing 'data' field"
        assert isinstance(body["data"], dict), (
            f"'data' must be a dict, got {type(body['data']).__name__}"
        )

        assert "metadata" in body, "Response missing 'metadata' field"
        metadata = body["metadata"]
        assert isinstance(metadata, dict), "'metadata' must be a dict"
        assert "timestamp" in metadata, "metadata missing 'timestamp'"
        assert "source" in metadata, "metadata missing 'source'"
        assert "latencyMs" in metadata, "metadata missing 'latencyMs'"
        assert isinstance(metadata["latencyMs"], int), "latencyMs must be an integer"

    @settings(max_examples=100)
    @given(tool=cost_finance_tools)
    def test_cost_finance_response_conforms_to_schema(self, tool):
        """Cost & Finance Server responses must have status, data, and metadata fields."""
        event = {"tool": tool, "params": {"category": "electronics"}}
        response = cost_finance_handler(event, None)

        body = _parse_response_body(response)

        assert "status" in body, "Response missing 'status' field"
        assert body["status"] in ("success", "error"), (
            f"status must be 'success' or 'error', got '{body['status']}'"
        )

        assert "data" in body, "Response missing 'data' field"
        assert isinstance(body["data"], dict), (
            f"'data' must be a dict, got {type(body['data']).__name__}"
        )

        assert "metadata" in body, "Response missing 'metadata' field"
        metadata = body["metadata"]
        assert isinstance(metadata, dict), "'metadata' must be a dict"
        assert "timestamp" in metadata, "metadata missing 'timestamp'"
        assert "source" in metadata, "metadata missing 'source'"
        assert "latencyMs" in metadata, "metadata missing 'latencyMs'"
        assert isinstance(metadata["latencyMs"], int), "latencyMs must be an integer"

    @settings(max_examples=100)
    @given(tool=competitor_tools)
    def test_error_response_conforms_to_schema(self, tool):
        """Error responses must also conform to schema with status='error'."""
        # Invoke without required product_id to trigger error
        event = {"tool": tool, "params": {}}
        response = competitor_handler(event, None)

        body = _parse_response_body(response)

        assert "status" in body, "Error response missing 'status' field"
        assert body["status"] in ("success", "error"), (
            f"status must be 'success' or 'error', got '{body['status']}'"
        )

        assert "data" in body, "Error response missing 'data' field"
        assert isinstance(body["data"], dict), "'data' must be a dict in error responses"

        assert "metadata" in body, "Error response missing 'metadata' field"
        metadata = body["metadata"]
        assert isinstance(metadata, dict), "'metadata' must be a dict"
        assert "timestamp" in metadata, "metadata missing 'timestamp'"
        assert "source" in metadata, "metadata missing 'source'"
        assert "latencyMs" in metadata, "metadata missing 'latencyMs'"


# --- Property 3: MCP Server data within variance bounds ---


class TestProperty3MCPDataVarianceBounds:
    """Property 3: MCP Server data within variance bounds.

    For any sequence of invocations to an MCP Server, all returned numeric
    values SHALL fall within the specified variance bounds from the baseline:
    - Competitor prices within ±10%
    - Demand volumes within ±20%
    - Cost inputs within ±5%

    **Validates: Requirements 2.6**
    """

    @settings(max_examples=100)
    @given(product_id=competitor_product_ids)
    def test_competitor_prices_within_10_percent_variance(self, product_id):
        """All competitor prices must be within ±10% of the product baseline price."""
        event = {"tool": "get_competitor_prices", "params": {"product_id": product_id}}
        response = competitor_handler(event, None)

        body = _parse_response_body(response)
        assert body["status"] == "success"

        data = body["data"]
        baseline_price = COMPETITOR_BASELINES[product_id]["baseline_price"]

        min_allowed = baseline_price * (1.0 - PRICE_VARIANCE)
        max_allowed = baseline_price * (1.0 + PRICE_VARIANCE)

        for competitor in data["competitors"]:
            price = competitor["price"]
            assert min_allowed <= price <= max_allowed, (
                f"Competitor price {price} outside ±10% bounds "
                f"[{min_allowed:.2f}, {max_allowed:.2f}] for baseline {baseline_price}"
            )

    @settings(max_examples=100)
    @given(product_id=competitor_product_ids)
    def test_competitor_price_history_within_10_percent_variance(self, product_id):
        """Historical competitor prices must be within ±10% of baseline."""
        event = {
            "tool": "get_price_history",
            "params": {"product_id": product_id, "days": 7},
        }
        response = competitor_handler(event, None)

        body = _parse_response_body(response)
        assert body["status"] == "success"

        data = body["data"]
        baseline_price = COMPETITOR_BASELINES[product_id]["baseline_price"]

        min_allowed = baseline_price * (1.0 - PRICE_VARIANCE)
        max_allowed = baseline_price * (1.0 + PRICE_VARIANCE)

        for entry in data["history"]:
            for price_entry in entry["prices"]:
                price = price_entry["price"]
                assert min_allowed <= price <= max_allowed, (
                    f"Historical price {price} outside ±10% bounds "
                    f"[{min_allowed:.2f}, {max_allowed:.2f}] for baseline {baseline_price}"
                )

    @settings(max_examples=100)
    @given(product_id=competitor_product_ids)
    def test_competitor_market_position_prices_within_10_percent(self, product_id):
        """Market position prices must be within ±10% of baseline."""
        event = {"tool": "get_market_position", "params": {"product_id": product_id}}
        response = competitor_handler(event, None)

        body = _parse_response_body(response)
        assert body["status"] == "success"

        data = body["data"]
        baseline_price = COMPETITOR_BASELINES[product_id]["baseline_price"]

        min_allowed = baseline_price * (1.0 - PRICE_VARIANCE)
        max_allowed = baseline_price * (1.0 + PRICE_VARIANCE)

        # Check our price
        our_price = data["ourPrice"]
        assert min_allowed <= our_price <= max_allowed, (
            f"Our price {our_price} outside ±10% bounds "
            f"[{min_allowed:.2f}, {max_allowed:.2f}] for baseline {baseline_price}"
        )

        # Check competitor price points
        for competitor in data["competitors"]:
            price = competitor["pricePoint"]
            assert min_allowed <= price <= max_allowed, (
                f"Competitor pricePoint {price} outside ±10% bounds "
                f"[{min_allowed:.2f}, {max_allowed:.2f}] for baseline {baseline_price}"
            )

    @settings(max_examples=100)
    @given(data=st.data())
    def test_erp_pos_demand_volumes_within_20_percent_variance(self, data):
        """ERP/POS demand volumes (units sold) must be within ±20% of baseline."""
        event = {
            "tool": "get_sales_history",
            "params": {"product_id": "PROD-001", "period": "weekly", "weeks": 4},
        }
        response = erp_pos_handler(event, None)

        body = _parse_response_body(response)
        assert body["status"] == "success"

        response_data = body["data"]
        baseline = BASELINE_WEEKLY_UNITS

        min_allowed = baseline * (1.0 - 0.20)
        max_allowed = baseline * (1.0 + 0.20)

        for period_entry in response_data["salesHistory"]:
            units_sold = period_entry["unitsSold"]
            # Allow for rounding (int conversion) by adding a small tolerance
            assert min_allowed - 1 <= units_sold <= max_allowed + 1, (
                f"Units sold {units_sold} outside ±20% bounds "
                f"[{min_allowed:.0f}, {max_allowed:.0f}] for baseline {baseline}"
            )

    @settings(max_examples=100)
    @given(data=st.data())
    def test_erp_pos_hourly_transactions_within_20_percent(self, data):
        """POS hourly transaction counts must be within ±20% of baseline."""
        event = {
            "tool": "get_pos_realtime",
            "params": {"product_id": "PROD-001", "hours": 4},
        }
        response = erp_pos_handler(event, None)

        body = _parse_response_body(response)
        assert body["status"] == "success"

        response_data = body["data"]
        baseline = BASELINE_HOURLY_TRANSACTIONS

        min_allowed = baseline * (1.0 - 0.20)
        max_allowed = baseline * (1.0 + 0.20)

        for tx in response_data["transactions"]:
            tx_count = tx["transactionCount"]
            assert min_allowed - 1 <= tx_count <= max_allowed + 1, (
                f"Transaction count {tx_count} outside ±20% bounds "
                f"[{min_allowed:.0f}, {max_allowed:.0f}] for baseline {baseline}"
            )

    @settings(max_examples=100)
    @given(category=cost_categories)
    def test_cost_finance_costs_within_5_percent_variance(self, category):
        """Cost structure values must be within ±5% of baseline for each component."""
        event = {
            "tool": "get_cost_structure",
            "params": {"category": category, "product_id": "PROD-001"},
        }
        response = cost_finance_handler(event, None)

        body = _parse_response_body(response)
        assert body["status"] == "success"

        data = body["data"]
        baseline = BASELINE_COSTS[category]

        for component in ["materials", "labor", "overhead", "shipping"]:
            actual = data["cost_breakdown"][component]
            base_val = baseline[component]
            min_allowed = base_val * (1.0 - COST_VARIANCE)
            max_allowed = base_val * (1.0 + COST_VARIANCE)

            assert min_allowed <= actual <= max_allowed, (
                f"Cost component '{component}' = {actual} outside ±5% bounds "
                f"[{min_allowed:.4f}, {max_allowed:.4f}] for baseline {base_val}"
            )

    @settings(max_examples=100)
    @given(data=st.data())
    def test_market_signals_sentiment_between_0_and_1(self, data):
        """Market signals sentiment scores must be between 0 and 1."""
        event = {
            "tool": "get_consumer_sentiment",
            "params": {"category": "electronics", "channel": "online"},
        }
        response = market_signals_handler(event, None)

        body = _parse_response_body(response)
        assert body["status"] == "success"

        response_data = body["data"]

        # Check all sentiment scores are in [0, 1]
        sentiment_fields = [
            "overallSentiment",
            "purchaseIntent",
            "brandPerception",
            "priceSensitivity",
            "satisfactionScore",
            "socialBuzz",
        ]

        for field in sentiment_fields:
            value = response_data[field]
            assert 0.0 <= value <= 1.0, (
                f"Sentiment field '{field}' = {value} outside [0, 1] bounds"
            )
