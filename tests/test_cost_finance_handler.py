"""Tests for the Cost & Finance MCP Server handler."""

import json

from backend.mcp_servers.cost_finance.handler import (
    BASELINE_COSTS,
    BASELINE_FINANCIAL_CONSTRAINTS,
    BASELINE_MARGIN_TARGETS,
    COST_VARIANCE,
    handler,
    get_cost_structure,
    get_margin_targets,
    get_financial_constraints,
    _apply_variance,
)


class TestApplyVariance:
    """Tests for the _apply_variance helper function."""

    def test_variance_within_bounds(self):
        """Returned value stays within ±5% of baseline."""
        baseline = 100.0
        for _ in range(100):
            result = _apply_variance(baseline)
            assert baseline * (1 - COST_VARIANCE) <= result <= baseline * (1 + COST_VARIANCE)

    def test_variance_with_custom_bound(self):
        """Custom variance bound is respected."""
        baseline = 50.0
        custom_variance = 0.10
        for _ in range(100):
            result = _apply_variance(baseline, variance=custom_variance)
            assert baseline * 0.90 <= result <= baseline * 1.10

    def test_result_rounded_to_4_decimals(self):
        """Result is rounded to 4 decimal places."""
        result = _apply_variance(33.333333)
        decimal_str = str(result).split(".")[-1] if "." in str(result) else ""
        assert len(decimal_str) <= 4


class TestGetCostStructure:
    """Tests for the get_cost_structure tool."""

    def test_returns_all_cost_components(self):
        """Response includes materials, labor, overhead, shipping."""
        result = get_cost_structure({"category": "electronics"})
        breakdown = result["cost_breakdown"]
        assert "materials" in breakdown
        assert "labor" in breakdown
        assert "overhead" in breakdown
        assert "shipping" in breakdown

    def test_total_unit_cost_is_sum_of_components(self):
        """Total unit cost equals sum of all cost components."""
        result = get_cost_structure({"category": "apparel"})
        breakdown = result["cost_breakdown"]
        expected_total = round(
            breakdown["materials"] + breakdown["labor"]
            + breakdown["overhead"] + breakdown["shipping"],
            4,
        )
        assert result["total_unit_cost"] == expected_total

    def test_costs_within_variance_bounds(self):
        """Each cost component is within ±5% of baseline."""
        category = "electronics"
        baseline = BASELINE_COSTS[category]
        for _ in range(50):
            result = get_cost_structure({"category": category})
            breakdown = result["cost_breakdown"]
            for component in ["materials", "labor", "overhead", "shipping"]:
                base_val = baseline[component]
                assert base_val * (1 - COST_VARIANCE) <= breakdown[component] <= base_val * (1 + COST_VARIANCE)

    def test_default_category_is_electronics(self):
        """Default category is electronics when not specified."""
        result = get_cost_structure({})
        assert result["category"] == "electronics"

    def test_unknown_category_falls_back_to_electronics(self):
        """Unknown category falls back to electronics baseline."""
        result = get_cost_structure({"category": "unknown_category"})
        assert result["category"] == "unknown_category"
        # Should still return valid cost data (falls back to electronics baseline)
        assert result["total_unit_cost"] > 0

    def test_includes_product_id(self):
        """Response includes the product_id from params."""
        result = get_cost_structure({"product_id": "PROD-XYZ"})
        assert result["product_id"] == "PROD-XYZ"

    def test_includes_currency(self):
        """Response includes currency field."""
        result = get_cost_structure({})
        assert result["currency"] == "USD"


class TestGetMarginTargets:
    """Tests for the get_margin_targets tool."""

    def test_returns_all_channels(self):
        """Response includes margin targets for all channels."""
        result = get_margin_targets({"category": "electronics"})
        targets = result["margin_targets"]
        assert "online" in targets
        assert "retail_store" in targets
        assert "wholesale" in targets
        assert "marketplace" in targets

    def test_each_channel_has_target_min_stretch(self):
        """Each channel has target, min_acceptable, and stretch margins."""
        result = get_margin_targets({"category": "apparel"})
        for channel_data in result["margin_targets"].values():
            assert "target_margin" in channel_data
            assert "min_acceptable_margin" in channel_data
            assert "stretch_margin" in channel_data

    def test_margin_targets_within_variance(self):
        """Margin targets are within ±5% of baseline."""
        category = "electronics"
        baseline = BASELINE_MARGIN_TARGETS[category]
        for _ in range(50):
            result = get_margin_targets({"category": category})
            for channel, base_target in baseline.items():
                actual = result["margin_targets"][channel]["target_margin"]
                assert base_target * (1 - COST_VARIANCE) <= actual <= base_target * (1 + COST_VARIANCE)

    def test_includes_fiscal_quarter(self):
        """Response includes fiscal quarter."""
        result = get_margin_targets({})
        assert "fiscal_quarter" in result
        assert result["fiscal_quarter"].startswith("Q")

    def test_includes_strategy(self):
        """Response includes strategy field."""
        result = get_margin_targets({})
        assert result["strategy"] in [
            "margin_protection",
            "growth_focused",
            "competitive_response",
            "balanced",
        ]


class TestGetFinancialConstraints:
    """Tests for the get_financial_constraints tool."""

    def test_returns_all_constraint_fields(self):
        """Response includes all expected constraint fields."""
        result = get_financial_constraints({})
        assert "max_discount_percent" in result
        assert "min_margin_percent" in result
        assert "quarterly_budget_limit" in result
        assert "monthly_promotion_budget" in result
        assert "max_loss_leader_items" in result
        assert "channel_rules" in result

    def test_channel_rules_for_all_channels(self):
        """Returns rules for all channels when no channel filter specified."""
        result = get_financial_constraints({})
        rules = result["channel_rules"]
        assert "online" in rules
        assert "retail_store" in rules
        assert "wholesale" in rules
        assert "marketplace" in rules

    def test_channel_filter_returns_single_channel(self):
        """Returns rules for only the specified channel."""
        result = get_financial_constraints({"channel": "online"})
        rules = result["channel_rules"]
        assert "online" in rules
        assert len(rules) == 1

    def test_constraints_within_variance(self):
        """Numeric constraints are within ±5% of baseline."""
        baseline = BASELINE_FINANCIAL_CONSTRAINTS
        for _ in range(50):
            result = get_financial_constraints({})
            for field in ["max_discount_percent", "min_margin_percent",
                          "quarterly_budget_limit", "monthly_promotion_budget"]:
                base_val = baseline[field]
                assert base_val * (1 - COST_VARIANCE) <= result[field] <= base_val * (1 + COST_VARIANCE)

    def test_max_loss_leader_items_not_randomized(self):
        """Integer constraint max_loss_leader_items is not randomized."""
        result = get_financial_constraints({})
        assert result["max_loss_leader_items"] == 5


class TestHandler:
    """Tests for the Lambda handler function."""

    def test_successful_get_cost_structure(self):
        """Handler dispatches get_cost_structure correctly."""
        event = {"tool": "get_cost_structure", "params": {"category": "electronics"}}
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert "cost_breakdown" in body["data"]
        assert "total_unit_cost" in body["data"]

    def test_successful_get_margin_targets(self):
        """Handler dispatches get_margin_targets correctly."""
        event = {"tool": "get_margin_targets", "params": {"category": "apparel"}}
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert "margin_targets" in body["data"]

    def test_successful_get_financial_constraints(self):
        """Handler dispatches get_financial_constraints correctly."""
        event = {"tool": "get_financial_constraints", "params": {}}
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert "max_discount_percent" in body["data"]
        assert "channel_rules" in body["data"]

    def test_missing_tool_returns_error(self):
        """Handler returns error when tool field is missing."""
        event = {"params": {}}
        response = handler(event, None)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["status"] == "error"
        assert body["error"]["code"] == "MISSING_TOOL"

    def test_unknown_tool_returns_error(self):
        """Handler returns error for unknown tool name."""
        event = {"tool": "nonexistent_tool", "params": {}}
        response = handler(event, None)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["status"] == "error"
        assert body["error"]["code"] == "UNKNOWN_TOOL"

    def test_response_includes_metadata(self):
        """Response includes metadata with timestamp, source, and latencyMs."""
        event = {"tool": "get_cost_structure", "params": {}}
        response = handler(event, None)
        body = json.loads(response["body"])
        metadata = body["metadata"]
        assert "timestamp" in metadata
        assert metadata["source"] == "cost_finance_server"
        assert "latencyMs" in metadata
        assert isinstance(metadata["latencyMs"], int)

    def test_handles_api_gateway_event_format(self):
        """Handler handles API Gateway event format with string body."""
        event = {
            "body": json.dumps({
                "tool": "get_cost_structure",
                "params": {"category": "grocery"},
            })
        }
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert body["data"]["category"] == "grocery"

    def test_mcp_response_schema_conformance(self):
        """Response conforms to MCP Response Schema."""
        event = {"tool": "get_margin_targets", "params": {"category": "home_garden"}}
        response = handler(event, None)
        body = json.loads(response["body"])

        # Required fields
        assert "status" in body
        assert body["status"] in ("success", "error")
        assert "data" in body
        assert isinstance(body["data"], dict)

        # Metadata fields
        assert "metadata" in body
        assert "timestamp" in body["metadata"]
        assert "source" in body["metadata"]
        assert "latencyMs" in body["metadata"]

    def test_error_response_schema_conformance(self):
        """Error response conforms to MCP Response Schema."""
        event = {"tool": "bad_tool", "params": {}}
        response = handler(event, None)
        body = json.loads(response["body"])

        assert body["status"] == "error"
        assert "data" in body
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
        assert "metadata" in body
