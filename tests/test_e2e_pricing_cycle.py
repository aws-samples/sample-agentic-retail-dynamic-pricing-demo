"""End-to-end integration test for the full pricing cycle pipeline.

Tests the complete flow:
1. Create a pricing cycle via persistence.create_pricing_cycle
2. Run the orchestrator (run_pricing_cycle from backend/agents/orchestrator.py)
3. Verify scenarios were generated (check persistence.get_scenarios)
4. Approve a scenario via the approval handler logic
5. Verify product prices were updated in the Products table

Uses moto for DynamoDB mocking and patches agent invocations to avoid
real Bedrock calls while exercising the full pipeline logic.

Requirements: 1.1, 6.2
"""

import json
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import patch, MagicMock

import boto3
import pytest
from moto import mock_aws

from backend.orchestration.persistence import (
    create_pricing_cycle,
    update_cycle_status,
    store_scenarios,
    get_cycle,
    get_scenarios,
)
from backend.agents.orchestrator import (
    run_pricing_cycle,
    PricingCycleRequest,
    PricingCycleResult,
)
from backend.api_handlers.approvals import _update_product_prices


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def aws_environment():
    """Create a full mocked AWS environment with all required DynamoDB tables."""
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

        # Create Products table
        resource.create_table(
            TableName="Products",
            KeySchema=[
                {"AttributeName": "productId", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "productId", "AttributeType": "S"},
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

        # Create Approvals table
        resource.create_table(
            TableName="Approvals",
            KeySchema=[
                {"AttributeName": "scenarioId", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "scenarioId", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield resource


@pytest.fixture
def seed_products(aws_environment):
    """Seed the Products table with sample products for testing."""
    products_table = aws_environment.Table("Products")

    products = [
        {
            "productId": "prod-001",
            "name": "Premium Coffee Beans 1kg",
            "description": "Single-origin Arabica coffee beans",
            "category": "Beverages",
            "subCategory": "Coffee",
            "productFamily": "Premium Coffee",
            "currentPrice": Decimal("24.99"),
            "previousPrice": Decimal("22.99"),
            "totalUnitCost": Decimal("12.50"),
            "mapPrice": Decimal("19.99"),
            "channels": ["online", "retail"],
            "regions": ["us-east", "us-west"],
        },
        {
            "productId": "prod-002",
            "name": "Organic Green Tea 500g",
            "description": "Japanese organic green tea leaves",
            "category": "Beverages",
            "subCategory": "Tea",
            "productFamily": "Premium Tea",
            "currentPrice": Decimal("18.99"),
            "previousPrice": Decimal("17.49"),
            "totalUnitCost": Decimal("8.00"),
            "mapPrice": Decimal("14.99"),
            "channels": ["online"],
            "regions": ["us-east", "us-west", "eu-west"],
        },
        {
            "productId": "prod-003",
            "name": "Sparkling Water 12-Pack",
            "description": "Natural sparkling mineral water",
            "category": "Beverages",
            "subCategory": "Water",
            "productFamily": "Sparkling Water",
            "currentPrice": Decimal("8.99"),
            "previousPrice": Decimal("8.49"),
            "totalUnitCost": Decimal("4.00"),
            "channels": ["online", "retail", "wholesale"],
            "regions": ["us-east"],
        },
    ]

    for product in products:
        products_table.put_item(Item=product)

    return products


def _make_mock_scenarios(cycle_id: str, product_ids: list[str]) -> list[dict[str, Any]]:
    """Generate mock pricing scenarios for testing.

    Creates a set of realistic scenarios that would be produced by the
    Strategy Synthesis Agent, with proper structure for the full pipeline.
    """
    scenarios = []
    for i in range(1, 4):
        scenario_id = f"scen-{uuid.uuid4().hex[:8]}"
        price_changes = []
        for pid in product_ids:
            base_price = 24.99 if pid == "prod-001" else 18.99 if pid == "prod-002" else 8.99
            change_pct = 3.0 + i  # 4%, 5%, 6% changes
            new_price = round(base_price * (1 + change_pct / 100), 4)
            price_changes.append({
                "productId": pid,
                "currentPrice": base_price,
                "newPrice": new_price,
                "changePercent": change_pct,
            })

        scenarios.append({
            "scenarioId": scenario_id,
            "cycleId": cycle_id,
            "rank": i,
            "confidenceScore": 95 - (i * 5),
            "statusLabel": "Recommended" if i == 1 else "Review Required",
            "riskLevel": "LOW" if i == 1 else "MEDIUM",
            "compositeScore": 95.0 - (i * 3.5),
            "projectedRevenue": 150000.1234 - (i * 10000),
            "projectedMargin": 0.2345 - (i * 0.01),
            "projectedMarketShare": 0.15 + (i * 0.01),
            "priceChanges": price_changes,
            "competitiveFactors": {
                "avgCompetitorPrice": 26.50,
                "marketPosition": "premium",
            },
            "demandFactors": {
                "elasticity": -1.2,
                "forecastedDemand": 5000,
            },
            "marketFactors": {
                "trendDirection": "up",
                "sentimentScore": 0.72,
            },
            "guardrailResults": [
                {"rule": "below_cost", "passed": True, "reason": ""},
                {"rule": "map_enforcement", "passed": True, "reason": ""},
                {"rule": "geographic_bias", "passed": True, "reason": ""},
            ],
            "approvalStatus": "PENDING",
        })

    return scenarios


# ---------------------------------------------------------------------------
# End-to-End Integration Test
# ---------------------------------------------------------------------------


class TestEndToEndPricingCycle:
    """End-to-end integration test for the full pricing cycle pipeline.

    Validates: Requirements 1.1, 6.2
    """

    def test_full_pricing_cycle_flow(self, aws_environment, seed_products):
        """Test the complete pricing cycle: submit → execute → generate → approve → update.

        This test exercises the full pipeline:
        1. Create a pricing cycle record in DynamoDB
        2. Run the orchestrator with mocked agent invocations
        3. Verify scenarios are stored in DynamoDB
        4. Approve the top scenario
        5. Verify product prices are updated in the Products table
        """
        cycle_id = f"cycle-{uuid.uuid4().hex[:8]}"
        product_ids = ["prod-001", "prod-002", "prod-003"]

        # -----------------------------------------------------------------
        # Step 1: Create a pricing cycle via persistence
        # -----------------------------------------------------------------
        cycle_record = create_pricing_cycle(
            cycle_id=cycle_id,
            pricing_group="Beverages",
            objectives=["revenue_maximization", "margin_protection"],
            constraints={"minMargin": 10, "maxPriceChange": 15},
            requested_by="test-user-001",
            dynamodb_resource=aws_environment,
        )

        assert cycle_record["cycleId"] == cycle_id
        assert cycle_record["status"] == "INITIATED"
        assert cycle_record["pricingGroup"] == "Beverages"

        # Verify the cycle is persisted
        persisted_cycle = get_cycle(
            cycle_id=cycle_id,
            dynamodb_resource=aws_environment,
        )
        assert persisted_cycle is not None
        assert persisted_cycle["status"] == "INITIATED"

        # -----------------------------------------------------------------
        # Step 2: Run the orchestrator with mocked agents
        # -----------------------------------------------------------------
        # Mock the agent factories to return predictable results without
        # calling real Bedrock endpoints
        mock_scenarios = _make_mock_scenarios(cycle_id, product_ids)

        mock_competitive_result = {
            "avgCompetitorPrice": 26.50,
            "marketPosition": "premium",
            "priceGap": 1.51,
        }
        mock_demand_result = {
            "elasticity": -1.2,
            "forecastedDemand": 5000,
            "inventoryWeeks": 4.2,
        }
        mock_market_result = {
            "trendDirection": "up",
            "sentimentScore": 0.72,
            "macroOutlook": "stable",
        }

        # Patch the synthesize function to return our mock scenarios
        with patch(
            "backend.agents.orchestrator.synthesize_pricing_strategies"
        ) as mock_synthesize, patch(
            "backend.agents.orchestrator._run_parallel_intelligence_agents"
        ) as mock_parallel:
            # Mock parallel agents returning successful results
            from backend.agents.orchestrator import AgentResult

            mock_parallel.return_value = [
                AgentResult(
                    agent_name="Competitive Intelligence",
                    success=True,
                    data=mock_competitive_result,
                    duration_ms=1500,
                    retries_used=0,
                ),
                AgentResult(
                    agent_name="Demand Forecasting",
                    success=True,
                    data=mock_demand_result,
                    duration_ms=2000,
                    retries_used=0,
                ),
                AgentResult(
                    agent_name="Market Intelligence",
                    success=True,
                    data=mock_market_result,
                    duration_ms=1800,
                    retries_used=0,
                ),
            ]

            # Mock synthesis to return our prepared scenarios
            mock_synthesize.return_value = {
                "ranked_scenarios": mock_scenarios,
                "shortfall_notification": None,
                "synthesis_metadata": {
                    "cycle_id": cycle_id,
                    "total_generated": 60,
                    "total_valid": 3,
                    "total_rejected": 57,
                    "objectives": ["revenue_maximization", "margin_protection"],
                    "constraints": {"minMargin": 10, "maxPriceChange": 15},
                },
            }

            # Execute the orchestrator
            result = run_pricing_cycle(
                request=PricingCycleRequest(
                    pricing_group="Beverages",
                    pricing_group_type="CATEGORY",
                    objectives=["revenue_maximization", "margin_protection"],
                    constraints={"minMargin": 10, "maxPriceChange": 15},
                    product_costs=[
                        {"productId": "prod-001", "totalUnitCost": 12.50},
                        {"productId": "prod-002", "totalUnitCost": 8.00},
                        {"productId": "prod-003", "totalUnitCost": 4.00},
                    ],
                )
            )

        # Verify orchestrator returned successfully
        assert result.status in ("COMPLETE", "DEGRADED")
        assert len(result.ranked_scenarios) == 3
        assert result.degraded_agents == []

        # -----------------------------------------------------------------
        # Step 3: Store scenarios and verify in DynamoDB
        # -----------------------------------------------------------------
        # Store the generated scenarios (simulating what the API handler does)
        stored_count = store_scenarios(
            cycle_id=cycle_id,
            scenarios=result.ranked_scenarios,
            dynamodb_resource=aws_environment,
        )
        assert stored_count == 3

        # Update cycle status to COMPLETE
        update_cycle_status(
            cycle_id=cycle_id,
            status="COMPLETE",
            scenario_count=stored_count,
            dynamodb_resource=aws_environment,
        )

        # Verify scenarios are retrievable
        scenarios_result = get_scenarios(
            cycle_id=cycle_id,
            dynamodb_resource=aws_environment,
        )
        assert scenarios_result["totalCount"] == 3
        assert scenarios_result["scenarios"][0]["rank"] == 1
        assert scenarios_result["scenarios"][0]["statusLabel"] == "Recommended"
        assert scenarios_result["scenarios"][0]["riskLevel"] == "LOW"

        # Verify cycle is marked COMPLETE
        completed_cycle = get_cycle(
            cycle_id=cycle_id,
            dynamodb_resource=aws_environment,
        )
        assert completed_cycle is not None
        assert completed_cycle["status"] == "COMPLETE"
        assert completed_cycle["scenarioCount"] == 3

        # -----------------------------------------------------------------
        # Step 4: Approve the top scenario
        # -----------------------------------------------------------------
        top_scenario = scenarios_result["scenarios"][0]
        scenario_id = top_scenario["scenarioId"]

        # Update scenario approval status in DynamoDB
        scenarios_table = aws_environment.Table("PricingScenarios")
        now = datetime.now(timezone.utc).isoformat()
        scenarios_table.update_item(
            Key={"cycleId": cycle_id, "scenarioId": scenario_id},
            UpdateExpression=(
                "SET approvalStatus = :status, approvalComment = :comment, "
                "approvedBy = :actor, approvedAt = :ts"
            ),
            ExpressionAttributeValues={
                ":status": "APPROVED",
                ":comment": "Approved for implementation - good revenue projection",
                ":actor": "test-user-001",
                ":ts": now,
            },
        )

        # Write approval record to Approvals table
        approvals_table = aws_environment.Table("Approvals")
        approvals_table.put_item(Item={
            "scenarioId": scenario_id,
            "timestamp": now,
            "action": "APPROVED",
            "actorId": "test-user-001",
            "comment": "Approved for implementation - good revenue projection",
            "riskLevel": "LOW",
        })

        # Verify approval was recorded
        approval_response = approvals_table.get_item(
            Key={"scenarioId": scenario_id, "timestamp": now}
        )
        assert "Item" in approval_response
        assert approval_response["Item"]["action"] == "APPROVED"

        # -----------------------------------------------------------------
        # Step 5: Update product prices (simulating implementation)
        # -----------------------------------------------------------------
        price_changes = top_scenario["priceChanges"]

        # Use the approval handler's price update logic
        _update_product_prices(aws_environment, price_changes)

        # Verify product prices were updated in the Products table
        products_table = aws_environment.Table("Products")

        for change in price_changes:
            product_id = change["productId"]
            response = products_table.get_item(Key={"productId": product_id})
            product = response["Item"]

            expected_new_price = Decimal(str(change["newPrice"]))
            assert product["currentPrice"] == expected_new_price, (
                f"Product {product_id} price not updated: "
                f"expected {expected_new_price}, got {product['currentPrice']}"
            )
            assert "priceUpdatedAt" in product, (
                f"Product {product_id} missing priceUpdatedAt timestamp"
            )

    def test_storefront_price_update_timing(self, aws_environment, seed_products):
        """Verify that product prices are updated promptly after approval.

        Requirement 6.2: Storefront SHALL update displayed prices within 60 seconds.
        This test verifies the price update happens within the time constraint.
        """
        cycle_id = f"cycle-{uuid.uuid4().hex[:8]}"
        product_ids = ["prod-001"]

        # Create cycle
        create_pricing_cycle(
            cycle_id=cycle_id,
            pricing_group="Beverages",
            objectives=["revenue_maximization"],
            constraints={},
            requested_by="test-user-001",
            dynamodb_resource=aws_environment,
        )

        # Create and store a scenario
        scenario_id = f"scen-{uuid.uuid4().hex[:8]}"
        scenarios = [{
            "scenarioId": scenario_id,
            "cycleId": cycle_id,
            "rank": 1,
            "confidenceScore": 90,
            "statusLabel": "Recommended",
            "riskLevel": "LOW",
            "compositeScore": 92.0,
            "projectedRevenue": 150000.0,
            "projectedMargin": 0.25,
            "priceChanges": [{
                "productId": "prod-001",
                "currentPrice": 24.99,
                "newPrice": 26.24,
                "changePercent": 5.0,
            }],
            "competitiveFactors": {"avgCompetitorPrice": 27.00},
            "demandFactors": {"elasticity": -1.1},
            "marketFactors": {"trendDirection": "up"},
            "guardrailResults": [
                {"rule": "below_cost", "passed": True, "reason": ""},
            ],
            "approvalStatus": "PENDING",
        }]

        store_scenarios(
            cycle_id=cycle_id,
            scenarios=scenarios,
            dynamodb_resource=aws_environment,
        )

        # Record the time before approval
        approval_start = time.time()

        # Approve and update prices
        price_changes = scenarios[0]["priceChanges"]
        _update_product_prices(aws_environment, price_changes)

        # Record the time after price update
        update_duration = time.time() - approval_start

        # Verify the update happened within 60 seconds (Requirement 6.2)
        assert update_duration < 60, (
            f"Price update took {update_duration:.2f}s, exceeding 60s requirement"
        )

        # Verify the price was actually updated
        products_table = aws_environment.Table("Products")
        response = products_table.get_item(Key={"productId": "prod-001"})
        product = response["Item"]
        assert product["currentPrice"] == Decimal("26.24")

    def test_cycle_status_transitions(self, aws_environment, seed_products):
        """Verify DynamoDB records are correct at each stage of the cycle."""
        cycle_id = f"cycle-{uuid.uuid4().hex[:8]}"

        # Stage 1: INITIATED
        create_pricing_cycle(
            cycle_id=cycle_id,
            pricing_group="Beverages",
            objectives=["balanced"],
            constraints={},
            requested_by="test-user-001",
            dynamodb_resource=aws_environment,
        )

        cycle = get_cycle(cycle_id=cycle_id, dynamodb_resource=aws_environment)
        assert cycle["status"] == "INITIATED"

        # Stage 2: ANALYZING
        update_cycle_status(
            cycle_id=cycle_id,
            status="ANALYZING",
            agent_statuses={
                "competitive-intelligence": {"status": "running"},
                "demand-forecasting": {"status": "running"},
                "market-intelligence": {"status": "running"},
            },
            dynamodb_resource=aws_environment,
        )

        cycle = get_cycle(cycle_id=cycle_id, dynamodb_resource=aws_environment)
        assert cycle["status"] == "ANALYZING"
        assert "competitive-intelligence" in cycle["agentStatuses"]

        # Stage 3: SYNTHESIZING
        update_cycle_status(
            cycle_id=cycle_id,
            status="SYNTHESIZING",
            agent_statuses={
                "competitive-intelligence": {"status": "completed"},
                "demand-forecasting": {"status": "completed"},
                "market-intelligence": {"status": "completed"},
            },
            dynamodb_resource=aws_environment,
        )

        cycle = get_cycle(cycle_id=cycle_id, dynamodb_resource=aws_environment)
        assert cycle["status"] == "SYNTHESIZING"

        # Stage 4: COMPLETE
        update_cycle_status(
            cycle_id=cycle_id,
            status="COMPLETE",
            scenario_count=55,
            dynamodb_resource=aws_environment,
        )

        cycle = get_cycle(cycle_id=cycle_id, dynamodb_resource=aws_environment)
        assert cycle["status"] == "COMPLETE"
        assert cycle["scenarioCount"] == 55
        assert "completedAt" in cycle

    def test_multiple_product_price_updates(self, aws_environment, seed_products):
        """Verify all products in a scenario have their prices updated on approval."""
        price_changes = [
            {
                "productId": "prod-001",
                "currentPrice": 24.99,
                "newPrice": 26.49,
                "changePercent": 6.0,
            },
            {
                "productId": "prod-002",
                "currentPrice": 18.99,
                "newPrice": 19.94,
                "changePercent": 5.0,
            },
            {
                "productId": "prod-003",
                "currentPrice": 8.99,
                "newPrice": 9.35,
                "changePercent": 4.0,
            },
        ]

        _update_product_prices(aws_environment, price_changes)

        products_table = aws_environment.Table("Products")

        # Verify each product was updated
        for change in price_changes:
            response = products_table.get_item(
                Key={"productId": change["productId"]}
            )
            product = response["Item"]
            expected_price = Decimal(str(change["newPrice"]))
            assert product["currentPrice"] == expected_price
            assert product["previousPrice"] == Decimal(str(change["currentPrice"]))
            assert "priceUpdatedAt" in product

    def test_scenario_approval_status_persisted(self, aws_environment, seed_products):
        """Verify that scenario approval status is correctly persisted in DynamoDB."""
        cycle_id = f"cycle-{uuid.uuid4().hex[:8]}"
        scenario_id = f"scen-{uuid.uuid4().hex[:8]}"

        # Store a scenario
        scenarios = [{
            "scenarioId": scenario_id,
            "cycleId": cycle_id,
            "rank": 1,
            "confidenceScore": 88,
            "statusLabel": "Recommended",
            "riskLevel": "LOW",
            "compositeScore": 90.0,
            "projectedRevenue": 120000.0,
            "projectedMargin": 0.22,
            "priceChanges": [{
                "productId": "prod-001",
                "currentPrice": 24.99,
                "newPrice": 25.99,
                "changePercent": 4.0,
            }],
            "competitiveFactors": {"avgCompetitorPrice": 26.00},
            "demandFactors": {"elasticity": -1.0},
            "marketFactors": {"trendDirection": "stable"},
            "guardrailResults": [],
            "approvalStatus": "PENDING",
        }]

        store_scenarios(
            cycle_id=cycle_id,
            scenarios=scenarios,
            dynamodb_resource=aws_environment,
        )

        # Approve the scenario
        scenarios_table = aws_environment.Table("PricingScenarios")
        now = datetime.now(timezone.utc).isoformat()
        scenarios_table.update_item(
            Key={"cycleId": cycle_id, "scenarioId": scenario_id},
            UpdateExpression=(
                "SET approvalStatus = :status, approvedBy = :actor, approvedAt = :ts"
            ),
            ExpressionAttributeValues={
                ":status": "APPROVED",
                ":actor": "test-user-001",
                ":ts": now,
            },
        )

        # Verify the approval status is persisted
        response = scenarios_table.get_item(
            Key={"cycleId": cycle_id, "scenarioId": scenario_id}
        )
        item = response["Item"]
        assert item["approvalStatus"] == "APPROVED"
        assert item["approvedBy"] == "test-user-001"
        assert item["approvedAt"] == now
