"""Integration tests for MCP Servers.

Tests each MCP Server with at least 2 known inputs (nominal + error case)
and validates response schema conformance.

Validates: Requirements 12.3
"""

import json
from datetime import datetime, timezone

import pytest

from backend.mcp_servers.competitor_api.handler import handler as competitor_handler
from backend.mcp_servers.erp_pos.handler import handler as erp_pos_handler
from backend.mcp_servers.market_signals.handler import handler as market_signals_handler
from backend.mcp_servers.cost_finance.handler import handler as cost_finance_handler


# --- Schema Validation Helpers ---


def validate_mcp_response_schema(body: dict) -> None:
    """Validate that a parsed response body conforms to the MCP Response Schema.

    Expected schema:
    {
        "status": str ("success" or "error"),
        "data": dict,
        "metadata": {
            "timestamp": str (ISO 8601),
            "source": str,
            "latencyMs": int (>= 0)
        }
    }
    """
    # Required top-level fields
    assert "status" in body, "Response missing 'status' field"
    assert "data" in body, "Response missing 'data' field"
    assert "metadata" in body, "Response missing 'metadata' field"

    # Status must be "success" or "error"
    assert body["status"] in ("success", "error"), (
        f"Invalid status: {body['status']}, expected 'success' or 'error'"
    )

    # Data must be a dict
    assert isinstance(body["data"], dict), (
        f"'data' must be a dict, got {type(body['data']).__name__}"
    )

    # Metadata validation
    metadata = body["metadata"]
    assert isinstance(metadata, dict), "'metadata' must be a dict"
    assert "timestamp" in metadata, "Metadata missing 'timestamp'"
    assert "source" in metadata, "Metadata missing 'source'"
    assert "latencyMs" in metadata, "Metadata missing 'latencyMs'"

    # Timestamp must be valid ISO 8601
    assert isinstance(metadata["timestamp"], str), "'timestamp' must be a string"
    parsed_ts = datetime.fromisoformat(metadata["timestamp"])
    assert parsed_ts.tzinfo is not None, "Timestamp must include timezone info"

    # Source must be a non-empty string
    assert isinstance(metadata["source"], str), "'source' must be a string"
    assert len(metadata["source"]) > 0, "'source' must not be empty"

    # LatencyMs must be a non-negative integer
    assert isinstance(metadata["latencyMs"], int), "'latencyMs' must be an integer"
    assert metadata["latencyMs"] >= 0, "'latencyMs' must be >= 0"


def parse_response(result: dict) -> dict:
    """Parse a Lambda handler response and return the body as a dict."""
    assert "body" in result or "statusCode" in result, "Invalid Lambda response format"
    if "body" in result:
        return json.loads(result["body"])
    return result


# --- Competitor API Server Integration Tests ---


class TestCompetitorAPIServerIntegration:
    """Integration tests for the Competitor API MCP Server."""

    def test_nominal_get_competitor_prices(self):
        """Nominal case: valid product_id returns competitor pricing data."""
        event = {"tool": "get_competitor_prices", "params": {"product_id": "ELEC-001"}}
        result = competitor_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "success"
        assert body["metadata"]["source"] == "competitor_api_server"

        # Validate data payload structure
        data = body["data"]
        assert data["productId"] == "ELEC-001"
        assert "competitors" in data
        assert len(data["competitors"]) >= 3
        assert "averageCompetitorPrice" in data
        assert "priceRange" in data

    def test_error_missing_product_id(self):
        """Error case: missing required product_id parameter."""
        event = {"tool": "get_competitor_prices", "params": {}}
        result = competitor_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "error"
        assert "error" in body
        assert body["error"]["code"] == "INVALID_PARAMS"
        assert "product_id" in body["error"]["message"].lower()

    def test_nominal_get_price_history(self):
        """Nominal case: valid product_id returns price history."""
        event = {"tool": "get_price_history", "params": {"product_id": "GROC-002", "days": 7}}
        result = competitor_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "success"
        assert body["data"]["productId"] == "GROC-002"
        assert body["data"]["periodDays"] == 7
        assert len(body["data"]["history"]) == 7
        assert "trend" in body["data"]

    def test_error_unknown_tool(self):
        """Error case: invoking a non-existent tool."""
        event = {"tool": "nonexistent_tool", "params": {"product_id": "ELEC-001"}}
        result = competitor_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "error"
        assert body["error"]["code"] == "UNKNOWN_TOOL"

    def test_nominal_get_market_position(self):
        """Nominal case: valid product_id returns market position data."""
        event = {"tool": "get_market_position", "params": {"product_id": "HOME-003"}}
        result = competitor_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "success"
        assert body["data"]["productId"] == "HOME-003"
        assert "priceIndex" in body["data"]
        assert "positioning" in body["data"]
        assert "ourMarketShare" in body["data"]

    def test_error_missing_tool_field(self):
        """Error case: request with no tool field."""
        event = {"params": {"product_id": "ELEC-001"}}
        result = competitor_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "error"
        assert body["error"]["code"] == "MISSING_TOOL"


# --- ERP/POS Server Integration Tests ---


class TestERPPOSServerIntegration:
    """Integration tests for the ERP/POS MCP Server."""

    def test_nominal_get_sales_history(self):
        """Nominal case: valid product_id returns sales history."""
        event = {"tool": "get_sales_history", "params": {"product_id": "PROD-001", "period": "weekly", "weeks": 4}}
        result = erp_pos_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "success"
        assert body["metadata"]["source"] == "erp_pos_server"

        data = body["data"]
        assert data["productId"] == "PROD-001"
        assert data["period"] == "weekly"
        assert data["totalPeriods"] == 4
        assert len(data["salesHistory"]) == 4
        assert "summary" in data

    def test_error_unknown_tool(self):
        """Error case: invoking a non-existent tool."""
        event = {"tool": "invalid_tool_name", "params": {"product_id": "PROD-001"}}
        result = erp_pos_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "error"
        assert body["error"]["code"] == "UNKNOWN_TOOL"

    def test_nominal_get_pos_realtime(self):
        """Nominal case: valid product_id returns real-time POS data."""
        event = {"tool": "get_pos_realtime", "params": {"product_id": "PROD-002", "hours": 6}}
        result = erp_pos_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "success"

        data = body["data"]
        assert data["productId"] == "PROD-002"
        assert data["periodHours"] == 6
        assert len(data["transactions"]) == 6
        assert "summary" in data
        assert data["summary"]["totalTransactions"] > 0

    def test_nominal_get_inventory_levels(self):
        """Nominal case: valid product_id returns inventory levels."""
        event = {"tool": "get_inventory_levels", "params": {"product_id": "PROD-003", "location_type": "warehouse"}}
        result = erp_pos_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "success"

        data = body["data"]
        assert data["productId"] == "PROD-003"
        assert data["locationType"] == "warehouse"
        assert len(data["locations"]) > 0
        assert all(loc["locationType"] == "warehouse" for loc in data["locations"])

    def test_nominal_get_elasticity_data(self):
        """Nominal case: valid product_id returns elasticity data."""
        event = {"tool": "get_elasticity_data", "params": {"product_id": "PROD-004", "category": "electronics"}}
        result = erp_pos_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "success"

        data = body["data"]
        assert data["productId"] == "PROD-004"
        assert data["category"] == "electronics"
        assert "segments" in data
        assert len(data["segments"]) > 0
        assert "summary" in data

    def test_error_missing_tool_field(self):
        """Error case: request with no tool field."""
        event = {"params": {"product_id": "PROD-001"}}
        result = erp_pos_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "error"
        assert body["error"]["code"] == "MISSING_TOOL"


# --- Market Signals Server Integration Tests ---


class TestMarketSignalsServerIntegration:
    """Integration tests for the Market Signals MCP Server."""

    def test_nominal_get_market_trends(self):
        """Nominal case: valid category returns market trend data."""
        event = {"tool": "get_market_trends", "params": {"category": "electronics", "timeframe": "30d"}}
        result = market_signals_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "success"
        assert body["metadata"]["source"] == "market_signals_server"

        data = body["data"]
        assert data["category"] == "electronics"
        assert data["timeframe"] == "30d"
        assert "growthRate" in data
        assert "seasonalityIndex" in data
        assert "categoryMomentum" in data
        assert "trendDirection" in data

    def test_error_unknown_tool(self):
        """Error case: invoking a non-existent tool."""
        event = {"tool": "fake_tool", "params": {"category": "electronics"}}
        result = market_signals_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "error"
        assert body["error"]["code"] == "UNKNOWN_TOOL"

    def test_nominal_get_consumer_sentiment(self):
        """Nominal case: valid category returns consumer sentiment scores."""
        event = {"tool": "get_consumer_sentiment", "params": {"category": "apparel", "channel": "retail"}}
        result = market_signals_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "success"

        data = body["data"]
        assert data["category"] == "apparel"
        assert data["channel"] == "retail"
        assert 0.0 <= data["overallSentiment"] <= 1.0
        assert "purchaseIntent" in data
        assert "brandPerception" in data
        assert "reviewSentiment" in data

    def test_nominal_get_macro_indicators(self):
        """Nominal case: valid region returns macroeconomic indicators."""
        event = {"tool": "get_macro_indicators", "params": {"region": "EU"}}
        result = market_signals_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "success"

        data = body["data"]
        assert data["region"] == "EU"
        assert "cpi" in data
        assert "consumerConfidence" in data
        assert "unemploymentRate" in data
        assert "gdpGrowth" in data
        assert "economicOutlook" in data

    def test_error_missing_tool_field(self):
        """Error case: request with no tool field."""
        event = {"params": {"category": "electronics"}}
        result = market_signals_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "error"
        assert body["error"]["code"] == "MISSING_TOOL"


# --- Cost & Finance Server Integration Tests ---


class TestCostFinanceServerIntegration:
    """Integration tests for the Cost & Finance MCP Server."""

    def test_nominal_get_cost_structure(self):
        """Nominal case: valid category returns cost breakdown."""
        event = {"tool": "get_cost_structure", "params": {"category": "electronics", "product_id": "ELEC-001"}}
        result = cost_finance_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "success"
        assert body["metadata"]["source"] == "cost_finance_server"

        data = body["data"]
        assert data["product_id"] == "ELEC-001"
        assert data["category"] == "electronics"
        assert "cost_breakdown" in data
        assert "total_unit_cost" in data
        assert data["total_unit_cost"] > 0

        breakdown = data["cost_breakdown"]
        assert "materials" in breakdown
        assert "labor" in breakdown
        assert "overhead" in breakdown
        assert "shipping" in breakdown

    def test_error_unknown_tool(self):
        """Error case: invoking a non-existent tool."""
        event = {"tool": "get_nonexistent_data", "params": {"category": "electronics"}}
        result = cost_finance_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "error"
        assert body["error"]["code"] == "UNKNOWN_TOOL"

    def test_nominal_get_margin_targets(self):
        """Nominal case: valid category returns margin targets."""
        event = {"tool": "get_margin_targets", "params": {"category": "apparel"}}
        result = cost_finance_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "success"

        data = body["data"]
        assert data["category"] == "apparel"
        assert "margin_targets" in data
        assert "strategy" in data
        # Should have targets for multiple channels
        assert len(data["margin_targets"]) > 0

    def test_nominal_get_financial_constraints(self):
        """Nominal case: returns financial constraints and channel rules."""
        event = {"tool": "get_financial_constraints", "params": {"channel": "online"}}
        result = cost_finance_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "success"

        data = body["data"]
        assert "max_discount_percent" in data
        assert "min_margin_percent" in data
        assert "quarterly_budget_limit" in data
        assert "channel_rules" in data
        assert "online" in data["channel_rules"]

    def test_error_missing_tool_field(self):
        """Error case: request with no tool field."""
        event = {"params": {"category": "electronics"}}
        result = cost_finance_handler(event, None)
        body = parse_response(result)

        validate_mcp_response_schema(body)
        assert body["status"] == "error"
        assert body["error"]["code"] == "MISSING_TOOL"


# --- Cross-Server Schema Conformance Tests ---


class TestCrossServerSchemaConformance:
    """Tests that all MCP servers produce responses conforming to the same schema."""

    @pytest.mark.parametrize("handler,event", [
        (competitor_handler, {"tool": "get_competitor_prices", "params": {"product_id": "ELEC-001"}}),
        (erp_pos_handler, {"tool": "get_sales_history", "params": {"product_id": "PROD-001"}}),
        (market_signals_handler, {"tool": "get_market_trends", "params": {"category": "electronics"}}),
        (cost_finance_handler, {"tool": "get_cost_structure", "params": {"category": "electronics"}}),
    ], ids=["competitor_api", "erp_pos", "market_signals", "cost_finance"])
    def test_all_servers_success_response_conforms_to_schema(self, handler, event):
        """All servers produce success responses conforming to MCP Response Schema."""
        result = handler(event, None)
        body = parse_response(result)
        validate_mcp_response_schema(body)
        assert body["status"] == "success"

    @pytest.mark.parametrize("handler,event", [
        (competitor_handler, {"tool": "bad_tool", "params": {}}),
        (erp_pos_handler, {"tool": "bad_tool", "params": {}}),
        (market_signals_handler, {"tool": "bad_tool", "params": {}}),
        (cost_finance_handler, {"tool": "bad_tool", "params": {}}),
    ], ids=["competitor_api", "erp_pos", "market_signals", "cost_finance"])
    def test_all_servers_error_response_conforms_to_schema(self, handler, event):
        """All servers produce error responses conforming to MCP Response Schema."""
        result = handler(event, None)
        body = parse_response(result)
        validate_mcp_response_schema(body)
        assert body["status"] == "error"
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    @pytest.mark.parametrize("handler,event,expected_source", [
        (competitor_handler, {"tool": "get_competitor_prices", "params": {"product_id": "ELEC-001"}}, "competitor_api_server"),
        (erp_pos_handler, {"tool": "get_sales_history", "params": {"product_id": "PROD-001"}}, "erp_pos_server"),
        (market_signals_handler, {"tool": "get_market_trends", "params": {"category": "electronics"}}, "market_signals_server"),
        (cost_finance_handler, {"tool": "get_cost_structure", "params": {"category": "electronics"}}, "cost_finance_server"),
    ], ids=["competitor_api", "erp_pos", "market_signals", "cost_finance"])
    def test_all_servers_report_correct_source(self, handler, event, expected_source):
        """Each server identifies itself correctly in metadata.source."""
        result = handler(event, None)
        body = parse_response(result)
        assert body["metadata"]["source"] == expected_source
