"""Unit tests for DynamoDB persistence layer.

Tests all persistence functions using moto to mock DynamoDB.
Covers: create_pricing_cycle, update_cycle_status, store_scenarios,
write_audit_trail, get_cycle, get_scenarios.

Requirements: 8.5, 11.2
"""

import boto3
import pytest
from moto import mock_aws

from backend.orchestration.persistence import (
    create_pricing_cycle,
    update_cycle_status,
    store_scenarios,
    write_audit_trail,
    get_cycle,
    get_scenarios,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dynamodb_resource():
    """Create a mocked DynamoDB resource with all required tables."""
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="us-east-1")

        # Create PricingCycles table
        resource.create_table(
            TableName="PricingCycles",
            KeySchema=[
                {"AttributeName": "cycleId", "KeyType": "HASH"},
                {"AttributeName": "status", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "cycleId", "AttributeType": "S"},
                {"AttributeName": "status", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create PricingScenarios table
        resource.create_table(
            TableName="PricingScenarios",
            KeySchema=[
                {"AttributeName": "cycleId", "KeyType": "HASH"},
                {"AttributeName": "scenarioId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "cycleId", "AttributeType": "S"},
                {"AttributeName": "scenarioId", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create AuditTrail table
        resource.create_table(
            TableName="AuditTrail",
            KeySchema=[
                {"AttributeName": "scenarioId", "KeyType": "HASH"},
                {"AttributeName": "timestamp#ruleId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "scenarioId", "AttributeType": "S"},
                {"AttributeName": "timestamp#ruleId", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield resource


# ---------------------------------------------------------------------------
# Tests: create_pricing_cycle
# ---------------------------------------------------------------------------


class TestCreatePricingCycle:
    """Tests for create_pricing_cycle function."""

    def test_creates_cycle_with_initiated_status(self, dynamodb_resource):
        """A new pricing cycle should be created with INITIATED status."""
        result = create_pricing_cycle(
            cycle_id="cycle-001",
            pricing_group="Electronics",
            objectives=["revenue_maximization", "margin_protection"],
            constraints={"minMargin": 10, "maxPriceChange": 15},
            requested_by="user-123",
            dynamodb_resource=dynamodb_resource,
        )

        assert result["cycleId"] == "cycle-001"
        assert result["status"] == "INITIATED"
        assert result["pricingGroup"] == "Electronics"
        assert result["objectives"] == ["revenue_maximization", "margin_protection"]
        assert result["constraints"] == {"minMargin": 10, "maxPriceChange": 15}
        assert result["requestedBy"] == "user-123"
        assert result["scenarioCount"] == 0
        assert result["agentStatuses"] == {}
        assert "createdAt" in result

    def test_cycle_persisted_to_dynamodb(self, dynamodb_resource):
        """The created cycle should be retrievable from DynamoDB."""
        create_pricing_cycle(
            cycle_id="cycle-002",
            pricing_group="Beverages",
            objectives=["competitive_positioning"],
            constraints={},
            requested_by="user-456",
            dynamodb_resource=dynamodb_resource,
        )

        # Verify it's in the table
        table = dynamodb_resource.Table("PricingCycles")
        response = table.get_item(
            Key={"cycleId": "cycle-002", "status": "INITIATED"}
        )
        item = response["Item"]
        assert item["pricingGroup"] == "Beverages"
        assert item["requestedBy"] == "user-456"

    def test_empty_constraints(self, dynamodb_resource):
        """A cycle with empty constraints should be created successfully."""
        result = create_pricing_cycle(
            cycle_id="cycle-003",
            pricing_group="Snacks",
            objectives=["market_share_growth"],
            constraints={},
            requested_by="user-789",
            dynamodb_resource=dynamodb_resource,
        )

        assert result["constraints"] == {}


# ---------------------------------------------------------------------------
# Tests: update_cycle_status
# ---------------------------------------------------------------------------


class TestUpdateCycleStatus:
    """Tests for update_cycle_status function."""

    def test_updates_status(self, dynamodb_resource):
        """Updating status should change the status field in the item."""
        create_pricing_cycle(
            cycle_id="cycle-010",
            pricing_group="Electronics",
            objectives=["balanced"],
            constraints={},
            requested_by="user-100",
            dynamodb_resource=dynamodb_resource,
        )

        result = update_cycle_status(
            cycle_id="cycle-010",
            status="ANALYZING",
            dynamodb_resource=dynamodb_resource,
        )

        assert result["status"] == "ANALYZING"

    def test_updates_agent_statuses(self, dynamodb_resource):
        """Agent statuses should be updated when provided."""
        create_pricing_cycle(
            cycle_id="cycle-011",
            pricing_group="Electronics",
            objectives=["balanced"],
            constraints={},
            requested_by="user-100",
            dynamodb_resource=dynamodb_resource,
        )

        agent_statuses = {
            "competitive-intelligence": {
                "status": "running",
                "startTime": "2024-01-15T10:00:00Z",
            },
            "demand-forecasting": {
                "status": "completed",
                "startTime": "2024-01-15T10:00:00Z",
                "endTime": "2024-01-15T10:01:30Z",
            },
        }

        result = update_cycle_status(
            cycle_id="cycle-011",
            status="ANALYZING",
            agent_statuses=agent_statuses,
            dynamodb_resource=dynamodb_resource,
        )

        assert result["agentStatuses"] == agent_statuses

    def test_complete_status_sets_completed_at(self, dynamodb_resource):
        """Setting status to COMPLETE should add a completedAt timestamp."""
        create_pricing_cycle(
            cycle_id="cycle-012",
            pricing_group="Electronics",
            objectives=["balanced"],
            constraints={},
            requested_by="user-100",
            dynamodb_resource=dynamodb_resource,
        )

        result = update_cycle_status(
            cycle_id="cycle-012",
            status="COMPLETE",
            scenario_count=75,
            dynamodb_resource=dynamodb_resource,
        )

        assert result["status"] == "COMPLETE"
        assert "completedAt" in result
        assert result["scenarioCount"] == 75

    def test_updates_scenario_count(self, dynamodb_resource):
        """Scenario count should be updated when provided."""
        create_pricing_cycle(
            cycle_id="cycle-013",
            pricing_group="Electronics",
            objectives=["balanced"],
            constraints={},
            requested_by="user-100",
            dynamodb_resource=dynamodb_resource,
        )

        result = update_cycle_status(
            cycle_id="cycle-013",
            status="SYNTHESIZING",
            scenario_count=50,
            dynamodb_resource=dynamodb_resource,
        )

        assert result["scenarioCount"] == 50


# ---------------------------------------------------------------------------
# Tests: get_cycle
# ---------------------------------------------------------------------------


class TestGetCycle:
    """Tests for get_cycle function."""

    def test_returns_existing_cycle(self, dynamodb_resource):
        """Should return the cycle item when it exists."""
        create_pricing_cycle(
            cycle_id="cycle-020",
            pricing_group="Dairy",
            objectives=["margin_protection"],
            constraints={"minMargin": 5},
            requested_by="user-200",
            dynamodb_resource=dynamodb_resource,
        )

        result = get_cycle(
            cycle_id="cycle-020",
            dynamodb_resource=dynamodb_resource,
        )

        assert result is not None
        assert result["cycleId"] == "cycle-020"
        assert result["pricingGroup"] == "Dairy"

    def test_returns_none_for_nonexistent_cycle(self, dynamodb_resource):
        """Should return None when the cycle does not exist."""
        result = get_cycle(
            cycle_id="nonexistent-cycle",
            dynamodb_resource=dynamodb_resource,
        )

        assert result is None


# ---------------------------------------------------------------------------
# Tests: store_scenarios
# ---------------------------------------------------------------------------


class TestStoreScenarios:
    """Tests for store_scenarios function."""

    def test_stores_single_scenario(self, dynamodb_resource):
        """A single scenario should be stored correctly."""
        scenarios = [
            {
                "scenarioId": "scen-001",
                "rank": 1,
                "confidenceScore": 85,
                "statusLabel": "Recommended",
                "riskLevel": "LOW",
                "compositeScore": 92.5,
                "projectedRevenue": 150000.1234,
                "projectedMargin": 0.2345,
            }
        ]

        count = store_scenarios(
            cycle_id="cycle-030",
            scenarios=scenarios,
            dynamodb_resource=dynamodb_resource,
        )

        assert count == 1

        # Verify via get_scenarios (handles Decimal->float conversion)
        result = get_scenarios(
            cycle_id="cycle-030",
            dynamodb_resource=dynamodb_resource,
        )
        item = result["scenarios"][0]
        assert item["rank"] == 1
        assert item["confidenceScore"] == 85
        assert item["statusLabel"] == "Recommended"

    def test_stores_multiple_scenarios(self, dynamodb_resource):
        """Multiple scenarios should be batch written correctly."""
        scenarios = [
            {"scenarioId": f"scen-{i:03d}", "rank": i, "confidenceScore": 90 - i}
            for i in range(1, 6)
        ]

        count = store_scenarios(
            cycle_id="cycle-031",
            scenarios=scenarios,
            dynamodb_resource=dynamodb_resource,
        )

        assert count == 5

    def test_stores_scenario_with_all_fields(self, dynamodb_resource):
        """All scenario fields should be preserved in DynamoDB."""
        scenarios = [
            {
                "scenarioId": "scen-full",
                "rank": 1,
                "confidenceScore": 95,
                "statusLabel": "Recommended",
                "riskLevel": "LOW",
                "compositeScore": 98.7654,
                "projectedRevenue": 200000.5678,
                "projectedMargin": 0.3456,
                "projectedMarketShare": 0.15,
                "priceChanges": [
                    {
                        "productId": "prod-001",
                        "currentPrice": 9.99,
                        "newPrice": 10.49,
                        "changePercent": 5.0,
                    }
                ],
                "competitiveFactors": {"avgCompetitorPrice": 10.25},
                "demandFactors": {"elasticity": -1.2},
                "marketFactors": {"trendDirection": "up"},
                "guardrailResults": [
                    {"rule": "below_cost", "passed": True, "reason": ""}
                ],
            }
        ]

        store_scenarios(
            cycle_id="cycle-032",
            scenarios=scenarios,
            dynamodb_resource=dynamodb_resource,
        )

        # Use get_scenarios which handles Decimal->float conversion
        result = get_scenarios(
            cycle_id="cycle-032",
            dynamodb_resource=dynamodb_resource,
        )
        item = result["scenarios"][0]
        assert item["priceChanges"][0]["productId"] == "prod-001"
        assert item["competitiveFactors"]["avgCompetitorPrice"] == pytest.approx(10.25)
        assert item["demandFactors"]["elasticity"] == pytest.approx(-1.2)

    def test_stores_empty_scenarios_list(self, dynamodb_resource):
        """An empty scenarios list should write zero items."""
        count = store_scenarios(
            cycle_id="cycle-033",
            scenarios=[],
            dynamodb_resource=dynamodb_resource,
        )

        assert count == 0


# ---------------------------------------------------------------------------
# Tests: get_scenarios
# ---------------------------------------------------------------------------


class TestGetScenarios:
    """Tests for get_scenarios function."""

    def test_returns_paginated_scenarios(self, dynamodb_resource):
        """Should return scenarios with pagination metadata."""
        scenarios = [
            {"scenarioId": f"scen-{i:03d}", "rank": i, "confidenceScore": 100 - i}
            for i in range(1, 26)
        ]
        store_scenarios(
            cycle_id="cycle-040",
            scenarios=scenarios,
            dynamodb_resource=dynamodb_resource,
        )

        result = get_scenarios(
            cycle_id="cycle-040",
            page=1,
            page_size=10,
            dynamodb_resource=dynamodb_resource,
        )

        assert len(result["scenarios"]) == 10
        assert result["page"] == 1
        assert result["pageSize"] == 10
        assert result["totalCount"] == 25
        assert result["totalPages"] == 3

    def test_second_page(self, dynamodb_resource):
        """Should return the correct items for page 2."""
        scenarios = [
            {"scenarioId": f"scen-{i:03d}", "rank": i, "confidenceScore": 100 - i}
            for i in range(1, 26)
        ]
        store_scenarios(
            cycle_id="cycle-041",
            scenarios=scenarios,
            dynamodb_resource=dynamodb_resource,
        )

        result = get_scenarios(
            cycle_id="cycle-041",
            page=2,
            page_size=10,
            dynamodb_resource=dynamodb_resource,
        )

        assert len(result["scenarios"]) == 10
        assert result["page"] == 2
        # Scenarios should be sorted by rank
        assert result["scenarios"][0]["rank"] == 11

    def test_last_page_partial(self, dynamodb_resource):
        """The last page may have fewer items than page_size."""
        scenarios = [
            {"scenarioId": f"scen-{i:03d}", "rank": i, "confidenceScore": 100 - i}
            for i in range(1, 26)
        ]
        store_scenarios(
            cycle_id="cycle-042",
            scenarios=scenarios,
            dynamodb_resource=dynamodb_resource,
        )

        result = get_scenarios(
            cycle_id="cycle-042",
            page=3,
            page_size=10,
            dynamodb_resource=dynamodb_resource,
        )

        assert len(result["scenarios"]) == 5
        assert result["page"] == 3

    def test_empty_result(self, dynamodb_resource):
        """Should return empty list when no scenarios exist for the cycle."""
        result = get_scenarios(
            cycle_id="nonexistent-cycle",
            dynamodb_resource=dynamodb_resource,
        )

        assert result["scenarios"] == []
        assert result["totalCount"] == 0
        assert result["totalPages"] == 1

    def test_scenarios_sorted_by_rank(self, dynamodb_resource):
        """Scenarios should be returned sorted by rank ascending."""
        # Insert in reverse order to test sorting
        scenarios = [
            {"scenarioId": f"scen-{i:03d}", "rank": i, "confidenceScore": 100 - i}
            for i in range(5, 0, -1)
        ]
        store_scenarios(
            cycle_id="cycle-043",
            scenarios=scenarios,
            dynamodb_resource=dynamodb_resource,
        )

        result = get_scenarios(
            cycle_id="cycle-043",
            page=1,
            page_size=20,
            dynamodb_resource=dynamodb_resource,
        )

        ranks = [s["rank"] for s in result["scenarios"]]
        assert ranks == [1, 2, 3, 4, 5]

    def test_default_page_size(self, dynamodb_resource):
        """Default page size should be 20."""
        scenarios = [
            {"scenarioId": f"scen-{i:03d}", "rank": i}
            for i in range(1, 31)
        ]
        store_scenarios(
            cycle_id="cycle-044",
            scenarios=scenarios,
            dynamodb_resource=dynamodb_resource,
        )

        result = get_scenarios(
            cycle_id="cycle-044",
            dynamodb_resource=dynamodb_resource,
        )

        assert len(result["scenarios"]) == 20
        assert result["pageSize"] == 20


# ---------------------------------------------------------------------------
# Tests: write_audit_trail
# ---------------------------------------------------------------------------


class TestWriteAuditTrail:
    """Tests for write_audit_trail function."""

    def test_writes_single_guardrail_result(self, dynamodb_resource):
        """A single guardrail result should be written to the audit trail."""
        guardrail_results = [
            {"rule": "below_cost", "passed": True, "reason": ""}
        ]

        count = write_audit_trail(
            scenario_id="scen-050",
            guardrail_results=guardrail_results,
            agent_id="strategy-synthesis",
            cycle_id="cycle-050",
            dynamodb_resource=dynamodb_resource,
        )

        assert count == 1

    def test_writes_multiple_guardrail_results(self, dynamodb_resource):
        """Multiple guardrail results should each be written as separate items."""
        guardrail_results = [
            {"rule": "below_cost", "passed": True, "reason": ""},
            {"rule": "map_enforcement", "passed": False, "reason": "Price below MAP"},
            {"rule": "geographic_bias", "passed": True, "reason": ""},
        ]

        count = write_audit_trail(
            scenario_id="scen-051",
            guardrail_results=guardrail_results,
            agent_id="strategy-synthesis",
            cycle_id="cycle-051",
            dynamodb_resource=dynamodb_resource,
        )

        assert count == 3

    def test_audit_trail_item_structure(self, dynamodb_resource):
        """Each audit trail item should have the correct structure."""
        guardrail_results = [
            {"rule": "below_cost", "passed": False, "reason": "Price is below unit cost"}
        ]

        write_audit_trail(
            scenario_id="scen-052",
            guardrail_results=guardrail_results,
            agent_id="strategy-synthesis",
            cycle_id="cycle-052",
            dynamodb_resource=dynamodb_resource,
        )

        # Query the table
        table = dynamodb_resource.Table("AuditTrail")
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("scenarioId").eq(
                "scen-052"
            ),
        )

        items = response["Items"]
        assert len(items) == 1

        item = items[0]
        assert item["scenarioId"] == "scen-052"
        assert item["guardrailRule"] == "below_cost"
        assert item["result"] == "REJECTED"
        assert item["violationReason"] == "Price is below unit cost"
        assert item["agentId"] == "strategy-synthesis"
        assert item["cycleId"] == "cycle-052"
        assert "timestamp#ruleId" in item
        assert "#below_cost" in item["timestamp#ruleId"]

    def test_passed_result_status(self, dynamodb_resource):
        """A passed guardrail should have result status PASSED."""
        guardrail_results = [
            {"rule": "map_enforcement", "passed": True, "reason": ""}
        ]

        write_audit_trail(
            scenario_id="scen-053",
            guardrail_results=guardrail_results,
            agent_id="strategy-synthesis",
            cycle_id="cycle-053",
            dynamodb_resource=dynamodb_resource,
        )

        table = dynamodb_resource.Table("AuditTrail")
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("scenarioId").eq(
                "scen-053"
            ),
        )

        item = response["Items"][0]
        assert item["result"] == "PASSED"

    def test_empty_guardrail_results(self, dynamodb_resource):
        """An empty guardrail results list should write zero items."""
        count = write_audit_trail(
            scenario_id="scen-054",
            guardrail_results=[],
            agent_id="strategy-synthesis",
            cycle_id="cycle-054",
            dynamodb_resource=dynamodb_resource,
        )

        assert count == 0
