"""Tests for the ERP/POS MCP Server Lambda handler."""

import json

from backend.mcp_servers.erp_pos.handler import handler, TOOL_HANDLERS


class TestHandlerDispatch:
    """Test the handler dispatches correctly to tool handlers."""

    def test_handler_dispatches_get_sales_history(self):
        event = {"tool": "get_sales_history", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert "salesHistory" in body["data"]

    def test_handler_dispatches_get_pos_realtime(self):
        event = {"tool": "get_pos_realtime", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert "transactions" in body["data"]

    def test_handler_dispatches_get_inventory_levels(self):
        event = {"tool": "get_inventory_levels", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert "locations" in body["data"]

    def test_handler_dispatches_get_elasticity_data(self):
        event = {"tool": "get_elasticity_data", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert "segments" in body["data"]

    def test_handler_returns_error_for_missing_tool(self):
        event = {"params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["status"] == "error"
        assert body["error"]["code"] == "MISSING_TOOL"

    def test_handler_returns_error_for_unknown_tool(self):
        event = {"tool": "nonexistent_tool", "params": {}}
        response = handler(event, None)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["status"] == "error"
        assert body["error"]["code"] == "UNKNOWN_TOOL"

    def test_handler_parses_string_body(self):
        event = {"body": json.dumps({"tool": "get_sales_history", "params": {"product_id": "PROD-001"}})}
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"

    def test_handler_parses_dict_body(self):
        event = {"body": {"tool": "get_inventory_levels", "params": {"product_id": "PROD-002"}}}
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"

    def test_handler_returns_error_for_invalid_json_body(self):
        event = {"body": "not valid json {{{"}
        response = handler(event, None)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["status"] == "error"
        assert body["error"]["code"] == "INVALID_REQUEST"


class TestMCPResponseSchema:
    """Test that all responses conform to the MCP Response Schema."""

    def test_success_response_has_required_fields(self):
        event = {"tool": "get_sales_history", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        body = json.loads(response["body"])

        assert "status" in body
        assert "data" in body
        assert "metadata" in body
        assert body["status"] == "success"
        assert isinstance(body["data"], dict)

    def test_metadata_has_required_fields(self):
        event = {"tool": "get_sales_history", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        body = json.loads(response["body"])

        metadata = body["metadata"]
        assert "timestamp" in metadata
        assert "source" in metadata
        assert "latencyMs" in metadata
        assert metadata["source"] == "erp_pos_server"
        assert isinstance(metadata["latencyMs"], int)
        assert metadata["latencyMs"] >= 0

    def test_error_response_has_required_fields(self):
        event = {"tool": "unknown_tool", "params": {}}
        response = handler(event, None)
        body = json.loads(response["body"])

        assert body["status"] == "error"
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
        assert "metadata" in body


class TestGetSalesHistory:
    """Test the get_sales_history tool."""

    def test_returns_correct_number_of_periods(self):
        event = {"tool": "get_sales_history", "params": {"product_id": "PROD-001", "weeks": 8}}
        response = handler(event, None)
        body = json.loads(response["body"])
        assert len(body["data"]["salesHistory"]) == 8

    def test_returns_weekly_data_by_default(self):
        event = {"tool": "get_sales_history", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        body = json.loads(response["body"])
        assert body["data"]["period"] == "weekly"
        assert body["data"]["totalPeriods"] == 12

    def test_returns_monthly_data(self):
        event = {"tool": "get_sales_history", "params": {"product_id": "PROD-001", "period": "monthly"}}
        response = handler(event, None)
        body = json.loads(response["body"])
        assert body["data"]["period"] == "monthly"

    def test_sales_data_has_expected_fields(self):
        event = {"tool": "get_sales_history", "params": {"product_id": "PROD-001", "weeks": 1}}
        response = handler(event, None)
        body = json.loads(response["body"])
        record = body["data"]["salesHistory"][0]

        assert "periodStart" in record
        assert "periodEnd" in record
        assert "unitsSold" in record
        assert "revenue" in record
        assert "averageSellingPrice" in record
        assert "returnRate" in record
        assert "promotionActive" in record

    def test_units_sold_within_variance_bounds(self):
        """Demand volumes should be within ±20% of baseline (1500 weekly)."""
        event = {"tool": "get_sales_history", "params": {"product_id": "PROD-001", "weeks": 50}}
        response = handler(event, None)
        body = json.loads(response["body"])

        baseline = 1500
        min_val = baseline * 0.80
        max_val = baseline * 1.20

        for record in body["data"]["salesHistory"]:
            assert min_val <= record["unitsSold"] <= max_val, (
                f"unitsSold {record['unitsSold']} outside ±20% of {baseline}"
            )

    def test_summary_fields_present(self):
        event = {"tool": "get_sales_history", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        body = json.loads(response["body"])
        summary = body["data"]["summary"]

        assert "totalUnitsSold" in summary
        assert "totalRevenue" in summary
        assert "averageUnitsPerPeriod" in summary
        assert "trendDirection" in summary


class TestGetPosRealtime:
    """Test the get_pos_realtime tool."""

    def test_returns_correct_number_of_hours(self):
        event = {"tool": "get_pos_realtime", "params": {"product_id": "PROD-001", "hours": 6}}
        response = handler(event, None)
        body = json.loads(response["body"])
        assert len(body["data"]["transactions"]) == 6

    def test_default_24_hours(self):
        event = {"tool": "get_pos_realtime", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        body = json.loads(response["body"])
        assert body["data"]["periodHours"] == 24
        assert len(body["data"]["transactions"]) == 24

    def test_transaction_data_has_expected_fields(self):
        event = {"tool": "get_pos_realtime", "params": {"product_id": "PROD-001", "hours": 1}}
        response = handler(event, None)
        body = json.loads(response["body"])
        record = body["data"]["transactions"][0]

        assert "hour" in record
        assert "transactionCount" in record
        assert "totalUnits" in record
        assert "revenue" in record
        assert "averageBasketSize" in record

    def test_transaction_count_within_variance_bounds(self):
        """Transaction counts should be within ±20% of baseline (45/hour)."""
        event = {"tool": "get_pos_realtime", "params": {"product_id": "PROD-001", "hours": 50}}
        response = handler(event, None)
        body = json.loads(response["body"])

        baseline = 45
        min_val = baseline * 0.80
        max_val = baseline * 1.20

        for record in body["data"]["transactions"]:
            assert min_val <= record["transactionCount"] <= max_val, (
                f"transactionCount {record['transactionCount']} outside ±20% of {baseline}"
            )

    def test_store_filter_applied(self):
        event = {"tool": "get_pos_realtime", "params": {"product_id": "PROD-001", "store_id": "STR-001"}}
        response = handler(event, None)
        body = json.loads(response["body"])
        assert body["data"]["storeId"] == "STR-001"


class TestGetInventoryLevels:
    """Test the get_inventory_levels tool."""

    def test_returns_all_locations_by_default(self):
        event = {"tool": "get_inventory_levels", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        body = json.loads(response["body"])
        # 3 warehouses + 5 stores = 8 locations
        assert len(body["data"]["locations"]) == 8

    def test_filter_warehouse_only(self):
        event = {"tool": "get_inventory_levels", "params": {"product_id": "PROD-001", "location_type": "warehouse"}}
        response = handler(event, None)
        body = json.loads(response["body"])
        assert len(body["data"]["locations"]) == 3
        for loc in body["data"]["locations"]:
            assert loc["locationType"] == "warehouse"

    def test_filter_store_only(self):
        event = {"tool": "get_inventory_levels", "params": {"product_id": "PROD-001", "location_type": "store"}}
        response = handler(event, None)
        body = json.loads(response["body"])
        assert len(body["data"]["locations"]) == 5
        for loc in body["data"]["locations"]:
            assert loc["locationType"] == "store"

    def test_inventory_data_has_expected_fields(self):
        event = {"tool": "get_inventory_levels", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        body = json.loads(response["body"])
        loc = body["data"]["locations"][0]

        assert "locationId" in loc
        assert "locationName" in loc
        assert "locationType" in loc
        assert "region" in loc
        assert "quantityOnHand" in loc
        assert "quantityReserved" in loc
        assert "quantityAvailable" in loc
        assert "daysOfSupply" in loc

    def test_warehouse_stock_within_variance_bounds(self):
        """Warehouse stock should be within ±20% of baseline (5000)."""
        event = {"tool": "get_inventory_levels", "params": {"product_id": "PROD-001", "location_type": "warehouse"}}
        response = handler(event, None)
        body = json.loads(response["body"])

        baseline = 5000
        min_val = baseline * 0.80
        max_val = baseline * 1.20

        for loc in body["data"]["locations"]:
            assert min_val <= loc["quantityOnHand"] <= max_val, (
                f"quantityOnHand {loc['quantityOnHand']} outside ±20% of {baseline}"
            )

    def test_summary_fields_present(self):
        event = {"tool": "get_inventory_levels", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        body = json.loads(response["body"])
        summary = body["data"]["summary"]

        assert "totalLocations" in summary
        assert "totalOnHand" in summary
        assert "totalAvailable" in summary
        assert "stockHealthStatus" in summary


class TestGetElasticityData:
    """Test the get_elasticity_data tool."""

    def test_returns_segments(self):
        event = {"tool": "get_elasticity_data", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        body = json.loads(response["body"])
        assert len(body["data"]["segments"]) == 5

    def test_segment_data_has_expected_fields(self):
        event = {"tool": "get_elasticity_data", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        body = json.loads(response["body"])
        seg = body["data"]["segments"][0]

        assert "segmentId" in seg
        assert "segmentName" in seg
        assert "priceElasticity" in seg
        assert "crossPriceElasticity" in seg
        assert "incomeElasticity" in seg
        assert "segmentShare" in seg
        assert "sampleSize" in seg
        assert "confidenceInterval" in seg

    def test_elasticity_values_are_negative(self):
        """Price elasticity should be negative (demand decreases as price increases)."""
        event = {"tool": "get_elasticity_data", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        body = json.loads(response["body"])

        for seg in body["data"]["segments"]:
            assert seg["priceElasticity"] < 0

    def test_segment_shares_sum_to_one(self):
        """Segment shares should be normalized to sum to approximately 1.0."""
        event = {"tool": "get_elasticity_data", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        body = json.loads(response["body"])

        total_share = sum(seg["segmentShare"] for seg in body["data"]["segments"])
        assert abs(total_share - 1.0) < 0.01

    def test_category_parameter_passed_through(self):
        event = {"tool": "get_elasticity_data", "params": {"product_id": "PROD-001", "category": "electronics"}}
        response = handler(event, None)
        body = json.loads(response["body"])
        assert body["data"]["category"] == "electronics"

    def test_summary_fields_present(self):
        event = {"tool": "get_elasticity_data", "params": {"product_id": "PROD-001"}}
        response = handler(event, None)
        body = json.loads(response["body"])
        summary = body["data"]["summary"]

        assert "weightedElasticity" in summary
        assert "mostElasticSegment" in summary
        assert "leastElasticSegment" in summary
        assert "totalSegments" in summary
