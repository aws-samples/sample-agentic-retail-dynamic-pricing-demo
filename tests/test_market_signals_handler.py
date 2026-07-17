"""Tests for Market Signals MCP Server handler."""

import json

from backend.mcp_servers.market_signals.handler import handler, TOOL_DEFINITIONS


class TestMarketSignalsHandler:
    """Tests for the Market Signals MCP Server Lambda handler."""

    def test_get_market_trends_returns_success(self):
        """Test get_market_trends returns a valid success response."""
        event = {"tool": "get_market_trends", "params": {"category": "electronics"}}
        result = handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "success"
        assert body["data"]["category"] == "electronics"
        assert "growthRate" in body["data"]
        assert "seasonalityIndex" in body["data"]
        assert "categoryMomentum" in body["data"]

    def test_get_market_trends_with_timeframe(self):
        """Test get_market_trends respects timeframe parameter."""
        event = {
            "tool": "get_market_trends",
            "params": {"category": "apparel", "timeframe": "30d"},
        }
        result = handler(event, None)

        body = json.loads(result["body"])
        assert body["status"] == "success"
        assert body["data"]["timeframe"] == "30d"
        assert body["data"]["category"] == "apparel"

    def test_get_consumer_sentiment_returns_success(self):
        """Test get_consumer_sentiment returns valid sentiment scores."""
        event = {"tool": "get_consumer_sentiment", "params": {"category": "food"}}
        result = handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "success"
        data = body["data"]
        assert data["category"] == "food"
        assert 0.0 <= data["overallSentiment"] <= 1.0
        assert 0.0 <= data["purchaseIntent"] <= 1.0
        assert 0.0 <= data["brandPerception"] <= 1.0
        assert 0.0 <= data["priceSensitivity"] <= 1.0
        assert 0.0 <= data["satisfactionScore"] <= 1.0

    def test_get_consumer_sentiment_with_channel(self):
        """Test get_consumer_sentiment respects channel parameter."""
        event = {
            "tool": "get_consumer_sentiment",
            "params": {"category": "electronics", "channel": "retail"},
        }
        result = handler(event, None)

        body = json.loads(result["body"])
        assert body["status"] == "success"
        assert body["data"]["channel"] == "retail"

    def test_get_consumer_sentiment_varies_between_invocations(self):
        """Test that sentiment scores vary between invocations."""
        event = {"tool": "get_consumer_sentiment", "params": {"category": "food"}}

        results = set()
        for _ in range(10):
            result = handler(event, None)
            body = json.loads(result["body"])
            results.add(body["data"]["overallSentiment"])

        # With 10 invocations, we should get multiple distinct values
        assert len(results) > 1

    def test_get_macro_indicators_returns_success(self):
        """Test get_macro_indicators returns valid economic indicators."""
        event = {"tool": "get_macro_indicators", "params": {"region": "US"}}
        result = handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "success"
        data = body["data"]
        assert data["region"] == "US"
        assert "cpi" in data
        assert "consumerConfidence" in data
        assert "unemploymentRate" in data
        assert "gdpGrowth" in data
        assert "interestRate" in data

    def test_get_macro_indicators_default_region(self):
        """Test get_macro_indicators uses US as default region."""
        event = {"tool": "get_macro_indicators", "params": {}}
        result = handler(event, None)

        body = json.loads(result["body"])
        assert body["status"] == "success"
        assert body["data"]["region"] == "US"

    def test_missing_tool_returns_error(self):
        """Test that missing tool field returns a 400 error."""
        event = {"params": {"category": "electronics"}}
        result = handler(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["status"] == "error"
        assert body["error"]["code"] == "MISSING_TOOL"

    def test_unknown_tool_returns_error(self):
        """Test that an unknown tool name returns a 400 error."""
        event = {"tool": "nonexistent_tool", "params": {}}
        result = handler(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["status"] == "error"
        assert body["error"]["code"] == "UNKNOWN_TOOL"

    def test_invalid_json_body_returns_error(self):
        """Test that an invalid JSON body returns a 400 error."""
        event = {"body": "not valid json{{{"}
        result = handler(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["status"] == "error"
        assert body["error"]["code"] == "INVALID_JSON"

    def test_response_conforms_to_mcp_schema(self):
        """Test that all responses conform to the MCP Response Schema."""
        event = {"tool": "get_market_trends", "params": {"category": "electronics"}}
        result = handler(event, None)

        body = json.loads(result["body"])
        # Required fields
        assert "status" in body
        assert body["status"] in ("success", "error")
        assert "data" in body
        assert isinstance(body["data"], dict)
        # Metadata
        assert "metadata" in body
        assert "timestamp" in body["metadata"]
        assert "source" in body["metadata"]
        assert "latencyMs" in body["metadata"]
        assert isinstance(body["metadata"]["latencyMs"], int)
        assert body["metadata"]["source"] == "market_signals_server"

    def test_error_response_conforms_to_mcp_schema(self):
        """Test that error responses also conform to the MCP Response Schema."""
        event = {"tool": "bad_tool", "params": {}}
        result = handler(event, None)

        body = json.loads(result["body"])
        assert "status" in body
        assert body["status"] == "error"
        assert "data" in body
        assert isinstance(body["data"], dict)
        assert "metadata" in body
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    def test_event_with_string_body(self):
        """Test handler correctly parses event with string body (API Gateway format)."""
        event = {
            "body": json.dumps(
                {"tool": "get_market_trends", "params": {"category": "toys"}}
            )
        }
        result = handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "success"
        assert body["data"]["category"] == "toys"

    def test_tool_definitions_exist(self):
        """Test that tool definitions are properly defined."""
        assert "get_market_trends" in TOOL_DEFINITIONS
        assert "get_consumer_sentiment" in TOOL_DEFINITIONS
        assert "get_macro_indicators" in TOOL_DEFINITIONS

        for tool_name, tool_def in TOOL_DEFINITIONS.items():
            assert "name" in tool_def
            assert "description" in tool_def
            assert "parameters" in tool_def
            assert tool_def["name"] == tool_name

    def test_market_trends_values_within_bounds(self):
        """Test that market trend values are within expected bounds."""
        event = {"tool": "get_market_trends", "params": {"category": "electronics"}}

        for _ in range(20):
            result = handler(event, None)
            body = json.loads(result["body"])
            data = body["data"]

            assert -0.05 <= data["growthRate"] <= 0.15
            assert 0.5 <= data["seasonalityIndex"] <= 1.5
            assert -1.0 <= data["categoryMomentum"] <= 1.0
            assert 0.0 <= data["volatilityIndex"] <= 1.0
            assert data["trendDirection"] in [
                "accelerating",
                "stable",
                "decelerating",
                "reversing",
            ]
            assert -0.20 <= data["demandShift"] <= 0.20

    def test_macro_indicators_values_within_bounds(self):
        """Test that macro indicator values are within expected bounds."""
        event = {"tool": "get_macro_indicators", "params": {"region": "EU"}}

        for _ in range(20):
            result = handler(event, None)
            body = json.loads(result["body"])
            data = body["data"]

            assert 1.5 <= data["cpi"] <= 4.5
            assert 70.0 <= data["consumerConfidence"] <= 130.0
            assert 3.0 <= data["unemploymentRate"] <= 7.0
            assert -1.0 <= data["gdpGrowth"] <= 5.0
            assert 2.0 <= data["interestRate"] <= 7.0
            assert -3.0 <= data["retailSalesGrowth"] <= 8.0
            assert -2.0 <= data["disposableIncomeChange"] <= 5.0
            assert data["economicOutlook"] in ["bullish", "neutral", "bearish"]

    def test_sentiment_scores_all_within_zero_to_one(self):
        """Test that all sentiment scores are within 0-1 range."""
        event = {"tool": "get_consumer_sentiment", "params": {"category": "beauty"}}

        for _ in range(20):
            result = handler(event, None)
            body = json.loads(result["body"])
            data = body["data"]

            assert 0.0 <= data["overallSentiment"] <= 1.0
            assert 0.0 <= data["purchaseIntent"] <= 1.0
            assert 0.0 <= data["brandPerception"] <= 1.0
            assert 0.0 <= data["priceSensitivity"] <= 1.0
            assert 0.0 <= data["satisfactionScore"] <= 1.0
            assert 0.0 <= data["socialBuzz"] <= 1.0

    def test_latency_ms_is_non_negative(self):
        """Test that latencyMs in metadata is a non-negative integer."""
        event = {"tool": "get_market_trends", "params": {"category": "electronics"}}
        result = handler(event, None)

        body = json.loads(result["body"])
        assert body["metadata"]["latencyMs"] >= 0
