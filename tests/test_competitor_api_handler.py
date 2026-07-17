"""Tests for the Competitor API MCP Server handler."""

import json

import pytest

from backend.mcp_servers.competitor_api.handler import (
    PRICE_VARIANCE,
    PRODUCT_BASELINES,
    handler,
    get_competitor_prices,
    get_price_history,
    get_market_position,
)


class TestHandlerDispatch:
    """Tests for the Lambda handler dispatch logic."""

    def test_handler_dispatches_get_competitor_prices(self):
        event = {"tool": "get_competitor_prices", "params": {"product_id": "ELEC-001"}}
        result = handler(event, None)
        body = json.loads(result["body"])
        assert body["status"] == "success"
        assert body["data"]["productId"] == "ELEC-001"

    def test_handler_dispatches_get_price_history(self):
        event = {"tool": "get_price_history", "params": {"product_id": "ELEC-001"}}
        result = handler(event, None)
        body = json.loads(result["body"])
        assert body["status"] == "success"
        assert "history" in body["data"]

    def test_handler_dispatches_get_market_position(self):
        event = {"tool": "get_market_position", "params": {"product_id": "ELEC-001"}}
        result = handler(event, None)
        body = json.loads(result["body"])
        assert body["status"] == "success"
        assert "priceIndex" in body["data"]

    def test_handler_returns_error_for_missing_tool(self):
        event = {"params": {"product_id": "ELEC-001"}}
        result = handler(event, None)
        body = json.loads(result["body"])
        assert body["status"] == "error"
        assert body["error"]["code"] == "MISSING_TOOL"

    def test_handler_returns_error_for_unknown_tool(self):
        event = {"tool": "nonexistent_tool", "params": {}}
        result = handler(event, None)
        body = json.loads(result["body"])
        assert body["status"] == "error"
        assert body["error"]["code"] == "UNKNOWN_TOOL"

    def test_handler_parses_body_from_api_gateway_event(self):
        event = {
            "body": json.dumps({"tool": "get_competitor_prices", "params": {"product_id": "ELEC-001"}})
        }
        result = handler(event, None)
        body = json.loads(result["body"])
        assert body["status"] == "success"

    def test_handler_handles_invalid_json_body(self):
        event = {"body": "not valid json{{{"}
        result = handler(event, None)
        body = json.loads(result["body"])
        assert body["status"] == "error"
        assert body["error"]["code"] == "INVALID_REQUEST"


class TestMCPResponseSchema:
    """Tests that responses conform to the MCP Response Schema."""

    def test_success_response_has_required_fields(self):
        event = {"tool": "get_competitor_prices", "params": {"product_id": "ELEC-001"}}
        result = handler(event, None)
        body = json.loads(result["body"])

        assert "status" in body
        assert "data" in body
        assert "metadata" in body
        assert body["status"] in ("success", "error")

    def test_metadata_has_required_fields(self):
        event = {"tool": "get_competitor_prices", "params": {"product_id": "ELEC-001"}}
        result = handler(event, None)
        body = json.loads(result["body"])

        metadata = body["metadata"]
        assert "timestamp" in metadata
        assert "source" in metadata
        assert "latencyMs" in metadata
        assert metadata["source"] == "competitor_api_server"
        assert isinstance(metadata["latencyMs"], int)
        assert metadata["latencyMs"] >= 0

    def test_error_response_has_error_fields(self):
        event = {"tool": "get_competitor_prices", "params": {}}
        result = handler(event, None)
        body = json.loads(result["body"])

        assert body["status"] == "error"
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    def test_timestamp_is_iso8601_format(self):
        event = {"tool": "get_competitor_prices", "params": {"product_id": "ELEC-001"}}
        result = handler(event, None)
        body = json.loads(result["body"])

        from datetime import datetime, timezone
        # Should parse without error
        ts = body["metadata"]["timestamp"]
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None


class TestGetCompetitorPrices:
    """Tests for the get_competitor_prices tool."""

    def test_returns_competitor_prices_for_known_product(self):
        event = {"tool": "get_competitor_prices", "params": {"product_id": "ELEC-001"}}
        result = handler(event, None)
        body = json.loads(result["body"])

        data = body["data"]
        assert data["productId"] == "ELEC-001"
        assert data["productName"] == "Wireless Earbuds"
        assert data["category"] == "electronics"
        assert "competitors" in data
        assert len(data["competitors"]) >= 3
        assert len(data["competitors"]) <= 5

    def test_competitor_prices_within_10_percent_variance(self):
        """Verify all competitor prices are within ±10% of baseline."""
        event = {"tool": "get_competitor_prices", "params": {"product_id": "ELEC-001"}}
        baseline = PRODUCT_BASELINES["ELEC-001"]["baseline_price"]

        # Run multiple times to increase confidence
        for _ in range(20):
            result = handler(event, None)
            body = json.loads(result["body"])
            for competitor in body["data"]["competitors"]:
                price = competitor["price"]
                lower_bound = baseline * (1 - PRICE_VARIANCE)
                upper_bound = baseline * (1 + PRICE_VARIANCE)
                assert lower_bound <= price <= upper_bound, (
                    f"Price {price} outside ±10% of baseline {baseline}"
                )

    def test_returns_average_and_range(self):
        event = {"tool": "get_competitor_prices", "params": {"product_id": "GROC-002"}}
        result = handler(event, None)
        body = json.loads(result["body"])

        data = body["data"]
        assert "averageCompetitorPrice" in data
        assert "priceRange" in data
        assert "min" in data["priceRange"]
        assert "max" in data["priceRange"]
        assert data["priceRange"]["min"] <= data["priceRange"]["max"]

    def test_error_when_product_id_missing(self):
        event = {"tool": "get_competitor_prices", "params": {}}
        result = handler(event, None)
        body = json.loads(result["body"])
        assert body["status"] == "error"
        assert body["error"]["code"] == "INVALID_PARAMS"

    def test_handles_unknown_product_with_category(self):
        event = {"tool": "get_competitor_prices", "params": {"product_id": "UNKNOWN-001", "category": "groceries"}}
        result = handler(event, None)
        body = json.loads(result["body"])
        assert body["status"] == "success"
        assert body["data"]["productId"] == "UNKNOWN-001"
        assert len(body["data"]["competitors"]) >= 3

    def test_competitor_entry_has_required_fields(self):
        event = {"tool": "get_competitor_prices", "params": {"product_id": "ELEC-003"}}
        result = handler(event, None)
        body = json.loads(result["body"])

        for competitor in body["data"]["competitors"]:
            assert "competitorId" in competitor
            assert "competitorName" in competitor
            assert "channel" in competitor
            assert "price" in competitor
            assert "currency" in competitor
            assert "inStock" in competitor
            assert "lastUpdated" in competitor
            assert competitor["currency"] == "USD"


class TestGetPriceHistory:
    """Tests for the get_price_history tool."""

    def test_returns_history_for_known_product(self):
        event = {"tool": "get_price_history", "params": {"product_id": "ELEC-002"}}
        result = handler(event, None)
        body = json.loads(result["body"])

        data = body["data"]
        assert data["productId"] == "ELEC-002"
        assert data["periodDays"] == 30
        assert len(data["history"]) == 30

    def test_respects_days_parameter(self):
        event = {"tool": "get_price_history", "params": {"product_id": "ELEC-002", "days": 7}}
        result = handler(event, None)
        body = json.loads(result["body"])
        assert body["data"]["periodDays"] == 7
        assert len(body["data"]["history"]) == 7

    def test_caps_days_at_90(self):
        event = {"tool": "get_price_history", "params": {"product_id": "ELEC-002", "days": 365}}
        result = handler(event, None)
        body = json.loads(result["body"])
        assert body["data"]["periodDays"] == 90
        assert len(body["data"]["history"]) == 90

    def test_history_prices_within_10_percent_variance(self):
        event = {"tool": "get_price_history", "params": {"product_id": "GROC-001", "days": 7}}
        baseline = PRODUCT_BASELINES["GROC-001"]["baseline_price"]

        result = handler(event, None)
        body = json.loads(result["body"])

        for entry in body["data"]["history"]:
            for price_entry in entry["prices"]:
                price = price_entry["price"]
                lower_bound = baseline * (1 - PRICE_VARIANCE)
                upper_bound = baseline * (1 + PRICE_VARIANCE)
                assert lower_bound <= price <= upper_bound

    def test_includes_trend_data(self):
        event = {"tool": "get_price_history", "params": {"product_id": "ELEC-001"}}
        result = handler(event, None)
        body = json.loads(result["body"])

        trend = body["data"]["trend"]
        assert "direction" in trend
        assert trend["direction"] in ("increasing", "decreasing", "stable")
        assert "percentageChange" in trend
        assert "recentAverage" in trend
        assert "olderAverage" in trend

    def test_error_when_product_id_missing(self):
        event = {"tool": "get_price_history", "params": {}}
        result = handler(event, None)
        body = json.loads(result["body"])
        assert body["status"] == "error"


class TestGetMarketPosition:
    """Tests for the get_market_position tool."""

    def test_returns_market_position_for_known_product(self):
        event = {"tool": "get_market_position", "params": {"product_id": "HOME-001"}}
        result = handler(event, None)
        body = json.loads(result["body"])

        data = body["data"]
        assert data["productId"] == "HOME-001"
        assert "ourPrice" in data
        assert "ourMarketShare" in data
        assert "priceIndex" in data
        assert "positioning" in data
        assert "competitors" in data

    def test_market_share_is_reasonable(self):
        event = {"tool": "get_market_position", "params": {"product_id": "ELEC-005"}}
        result = handler(event, None)
        body = json.loads(result["body"])

        data = body["data"]
        assert 0 < data["ourMarketShare"] <= 100

    def test_positioning_values_are_valid(self):
        event = {"tool": "get_market_position", "params": {"product_id": "ELEC-001"}}

        # Run multiple times to potentially hit different positioning values
        positions_seen = set()
        for _ in range(50):
            result = handler(event, None)
            body = json.loads(result["body"])
            positions_seen.add(body["data"]["positioning"])

        for pos in positions_seen:
            assert pos in ("price_leader", "premium", "competitive")

    def test_our_price_within_10_percent_variance(self):
        baseline = PRODUCT_BASELINES["ELEC-003"]["baseline_price"]
        event = {"tool": "get_market_position", "params": {"product_id": "ELEC-003"}}

        for _ in range(20):
            result = handler(event, None)
            body = json.loads(result["body"])
            our_price = body["data"]["ourPrice"]
            lower_bound = baseline * (1 - PRICE_VARIANCE)
            upper_bound = baseline * (1 + PRICE_VARIANCE)
            assert lower_bound <= our_price <= upper_bound

    def test_competitor_price_points_within_variance(self):
        baseline = PRODUCT_BASELINES["HOME-002"]["baseline_price"]
        event = {"tool": "get_market_position", "params": {"product_id": "HOME-002"}}

        for _ in range(20):
            result = handler(event, None)
            body = json.loads(result["body"])
            for comp in body["data"]["competitors"]:
                price = comp["pricePoint"]
                lower_bound = baseline * (1 - PRICE_VARIANCE)
                upper_bound = baseline * (1 + PRICE_VARIANCE)
                assert lower_bound <= price <= upper_bound

    def test_includes_market_metrics(self):
        event = {"tool": "get_market_position", "params": {"product_id": "ELEC-001"}}
        result = handler(event, None)
        body = json.loads(result["body"])

        data = body["data"]
        assert "marketAverage" in data
        assert "marketSize" in data
        assert "marketGrowthRate" in data
        assert data["marketSize"] > 0

    def test_error_when_product_id_missing(self):
        event = {"tool": "get_market_position", "params": {}}
        result = handler(event, None)
        body = json.loads(result["body"])
        assert body["status"] == "error"
