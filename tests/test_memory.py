"""Unit tests for the historical memory module.

Tests the query, persistence, and context-building functions for long-term
memory used by the Strategy Synthesis Agent.

Validates: Requirements 10.3, 10.5
"""

import time
from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws
from boto3.dynamodb.conditions import Key

from backend.orchestration.memory import (
    DEFAULT_QUERY_LIMIT,
    MAX_CYCLES_PER_KEY,
    MEMORY_TABLE_NAME,
    _enforce_retention_limit,
    _extract_product_or_category,
    build_historical_context,
    persist_outcome,
    query_historical_outcomes,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dynamodb_table():
    """Create a mocked DynamoDB table for testing."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName=MEMORY_TABLE_NAME,
            KeySchema=[
                {"AttributeName": "product_or_category", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "product_or_category", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(
            TableName=MEMORY_TABLE_NAME
        )
        yield table


@pytest.fixture
def sample_scenario():
    """A sample approved scenario for testing."""
    return {
        "scenarioId": "scenario-001",
        "cycleId": "cycle-001",
        "rank": 1,
        "confidenceScore": 85,
        "statusLabel": "Recommended",
        "riskLevel": "LOW",
        "priceChanges": [
            {
                "productId": "product-abc",
                "currentPrice": 29.99,
                "newPrice": 31.49,
                "changePercent": 5.0,
            }
        ],
        "projectedRevenue": 150000.0,
        "projectedMargin": 0.28,
        "projectedMarketShare": 0.15,
        "compositeScore": 87.5,
        "competitiveFactors": {"avg_competitor_price": 32.0},
        "demandFactors": {"elasticity": -1.2},
        "marketFactors": {"trend": "growing"},
        "approvalStatus": "APPROVED",
    }


@pytest.fixture
def sample_actual_metrics():
    """Sample actual metrics observed after implementation."""
    return {
        "actual_revenue": 145000.0,
        "actual_margin": 0.27,
        "actual_market_share": 0.16,
    }


# ---------------------------------------------------------------------------
# Tests: query_historical_outcomes
# ---------------------------------------------------------------------------


class TestQueryHistoricalOutcomes:
    """Tests for querying historical outcomes from long-term memory."""

    def test_query_returns_empty_list_when_no_data(self, dynamodb_table):
        """Query returns empty list when no outcomes exist for the key."""
        results = query_historical_outcomes("product-xyz")
        assert results == []

    def test_query_returns_persisted_outcomes(
        self, dynamodb_table, sample_scenario, sample_actual_metrics
    ):
        """Query returns outcomes that were previously persisted."""
        persist_outcome("cycle-001", sample_scenario, sample_actual_metrics)

        results = query_historical_outcomes("product-abc")
        assert len(results) == 1
        assert results[0]["cycle_id"] == "cycle-001"
        assert results[0]["approval_decision"] == "APPROVED"

    def test_query_respects_limit(self, dynamodb_table, sample_scenario):
        """Query returns at most 'limit' results."""
        # Persist 5 outcomes
        for i in range(5):
            scenario = {**sample_scenario, "scenarioId": f"scenario-{i:03d}"}
            persist_outcome(f"cycle-{i:03d}", scenario)

        results = query_historical_outcomes("product-abc", limit=3)
        assert len(results) == 3

    def test_query_returns_most_recent_first(self, dynamodb_table, sample_scenario):
        """Query returns outcomes ordered by timestamp descending (most recent first)."""
        for i in range(3):
            scenario = {**sample_scenario, "scenarioId": f"scenario-{i:03d}"}
            persist_outcome(f"cycle-{i:03d}", scenario)
            time.sleep(0.01)  # Ensure distinct timestamps

        results = query_historical_outcomes("product-abc", limit=10)
        assert len(results) == 3
        # Most recent should be first (cycle-002)
        timestamps = [r["timestamp"] for r in results]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_query_caps_limit_at_max_cycles(self, dynamodb_table):
        """Query caps the effective limit at MAX_CYCLES_PER_KEY."""
        results = query_historical_outcomes("product-abc", limit=500)
        # Should not raise; just returns what's available (empty in this case)
        assert results == []

    def test_query_raises_on_empty_key(self, dynamodb_table):
        """Query raises ValueError when product_id_or_category is empty."""
        with pytest.raises(ValueError, match="must not be empty"):
            query_historical_outcomes("")

    def test_query_raises_on_invalid_limit(self, dynamodb_table):
        """Query raises ValueError when limit is less than 1."""
        with pytest.raises(ValueError, match="limit must be at least 1"):
            query_historical_outcomes("product-abc", limit=0)

    def test_query_isolates_by_product(self, dynamodb_table, sample_scenario):
        """Query only returns outcomes for the specified product/category."""
        # Persist for product-abc
        persist_outcome("cycle-001", sample_scenario)

        # Persist for a different product
        other_scenario = {
            **sample_scenario,
            "priceChanges": [
                {
                    "productId": "product-xyz",
                    "currentPrice": 10.0,
                    "newPrice": 11.0,
                    "changePercent": 10.0,
                }
            ],
        }
        persist_outcome("cycle-002", other_scenario)

        # Query for product-abc should only return 1 result
        results = query_historical_outcomes("product-abc")
        assert len(results) == 1
        assert results[0]["cycle_id"] == "cycle-001"

        # Query for product-xyz should only return 1 result
        results = query_historical_outcomes("product-xyz")
        assert len(results) == 1
        assert results[0]["cycle_id"] == "cycle-002"


# ---------------------------------------------------------------------------
# Tests: persist_outcome
# ---------------------------------------------------------------------------


class TestPersistOutcome:
    """Tests for persisting approved scenario outcomes to long-term memory."""

    def test_persist_stores_record_successfully(
        self, dynamodb_table, sample_scenario, sample_actual_metrics
    ):
        """Persist stores a complete record with all expected fields."""
        record = persist_outcome(
            "cycle-001", sample_scenario, sample_actual_metrics
        )

        assert record["cycle_id"] == "cycle-001"
        assert record["product_or_category"] == "product-abc"
        assert record["approval_decision"] == "APPROVED"
        assert record["projected_metrics"]["revenue"] == 150000.0
        assert record["projected_metrics"]["margin"] == 0.28
        assert record["actual_metrics"]["actual_revenue"] == 145000.0
        assert record["timestamp"] is not None

    def test_persist_without_actual_metrics(self, dynamodb_table, sample_scenario):
        """Persist works when actual_metrics is None."""
        record = persist_outcome("cycle-001", sample_scenario)

        assert record["actual_metrics"] is None
        assert record["projected_metrics"]["revenue"] == 150000.0

    def test_persist_extracts_scenario_details(
        self, dynamodb_table, sample_scenario
    ):
        """Persist correctly extracts scenario details into selected_scenario."""
        record = persist_outcome("cycle-001", sample_scenario)

        selected = record["selected_scenario"]
        assert selected["scenario_id"] == "scenario-001"
        assert selected["confidence_score"] == 85
        assert selected["risk_level"] == "LOW"
        assert selected["status_label"] == "Recommended"
        assert selected["composite_score"] == 87.5
        assert len(selected["price_changes"]) == 1

    def test_persist_raises_on_empty_cycle_id(self, dynamodb_table, sample_scenario):
        """Persist raises ValueError when cycle_id is empty."""
        with pytest.raises(ValueError, match="cycle_id must not be empty"):
            persist_outcome("", sample_scenario)

    def test_persist_raises_on_empty_scenario(self, dynamodb_table):
        """Persist raises ValueError when scenario is empty."""
        with pytest.raises(ValueError, match="scenario must not be empty"):
            persist_outcome("cycle-001", {})

    def test_persist_handles_python_field_names(self, dynamodb_table):
        """Persist works with Python-style field names (snake_case)."""
        scenario = {
            "scenario_id": "scenario-002",
            "cycle_id": "cycle-002",
            "confidence_score": 72,
            "risk_level": "MEDIUM",
            "status_label": "Review Required",
            "price_changes": [
                {
                    "product_id": "product-def",
                    "current_price": 50.0,
                    "new_price": 55.0,
                    "change_percent": 10.0,
                }
            ],
            "projected_revenue": 200000.0,
            "projected_margin": 0.32,
            "projected_market_share": 0.20,
            "composite_score": 75.0,
            "approval_status": "APPROVED",
        }
        record = persist_outcome("cycle-002", scenario)

        assert record["product_or_category"] == "product-def"
        assert record["selected_scenario"]["confidence_score"] == 72
        assert record["projected_metrics"]["revenue"] == 200000.0

    def test_persist_completes_within_60_seconds(
        self, dynamodb_table, sample_scenario
    ):
        """Persist completes well within the 60-second SLA."""
        start = time.time()
        persist_outcome("cycle-001", sample_scenario)
        elapsed = time.time() - start

        # Should complete in well under 60 seconds (mocked DynamoDB is instant)
        assert elapsed < 60.0

    def test_persist_uses_utc_timestamp(self, dynamodb_table, sample_scenario):
        """Persist records use UTC timestamps in ISO 8601 format."""
        record = persist_outcome("cycle-001", sample_scenario)

        timestamp = record["timestamp"]
        # Should be parseable as ISO 8601
        parsed = datetime.fromisoformat(timestamp)
        assert parsed.tzinfo is not None  # Has timezone info


# ---------------------------------------------------------------------------
# Tests: build_historical_context
# ---------------------------------------------------------------------------


class TestBuildHistoricalContext:
    """Tests for building historical context strings for agent prompts."""

    def test_empty_outcomes_returns_empty_string(self):
        """Empty outcomes list returns empty string."""
        result = build_historical_context([])
        assert result == ""

    def test_single_outcome_formats_correctly(self):
        """Single outcome is formatted with all expected sections."""
        outcomes = [
            {
                "cycle_id": "cycle-001",
                "timestamp": "2024-01-15T10:30:00+00:00",
                "selected_scenario": {
                    "scenario_id": "scenario-001",
                    "confidence_score": 85,
                    "risk_level": "LOW",
                    "composite_score": 87.5,
                    "price_changes": [
                        {"productId": "product-abc", "changePercent": 5.0}
                    ],
                },
                "projected_metrics": {
                    "revenue": 150000.0,
                    "margin": 0.28,
                    "market_share": 0.15,
                },
                "actual_metrics": {
                    "actual_revenue": 145000.0,
                    "actual_margin": 0.27,
                },
                "approval_decision": "APPROVED",
            }
        ]

        result = build_historical_context(outcomes)

        assert "Historical Pricing Outcomes (1 previous cycles)" in result
        assert "cycle-001" in result
        assert "2024-01-15T10:30:00+00:00" in result
        assert "APPROVED" in result
        assert "85" in result  # confidence score
        assert "LOW" in result  # risk level
        assert "150000.0" in result  # projected revenue
        assert "145000.0" in result  # actual revenue
        assert "product-abc" in result

    def test_multiple_outcomes_all_included(self):
        """Multiple outcomes are all included in the context."""
        outcomes = [
            {
                "cycle_id": f"cycle-{i:03d}",
                "timestamp": f"2024-01-{15+i}T10:30:00+00:00",
                "selected_scenario": {
                    "confidence_score": 80 + i,
                    "risk_level": "LOW",
                    "composite_score": 85.0,
                    "price_changes": [],
                },
                "projected_metrics": {"revenue": 100000 + i * 10000, "margin": 0.25},
                "actual_metrics": None,
                "approval_decision": "APPROVED",
            }
            for i in range(5)
        ]

        result = build_historical_context(outcomes)

        assert "5 previous cycles" in result
        for i in range(5):
            assert f"cycle-{i:03d}" in result

    def test_context_includes_summary_insights(self):
        """Context includes summary section with approval counts and averages."""
        outcomes = [
            {
                "cycle_id": "cycle-001",
                "timestamp": "2024-01-15T10:30:00+00:00",
                "selected_scenario": {"confidence_score": 80, "risk_level": "LOW",
                                      "composite_score": 85.0, "price_changes": []},
                "projected_metrics": {"revenue": 100000, "margin": 0.25},
                "actual_metrics": None,
                "approval_decision": "APPROVED",
            },
            {
                "cycle_id": "cycle-002",
                "timestamp": "2024-01-16T10:30:00+00:00",
                "selected_scenario": {"confidence_score": 60, "risk_level": "MEDIUM",
                                      "composite_score": 70.0, "price_changes": []},
                "projected_metrics": {"revenue": 90000, "margin": 0.22},
                "actual_metrics": None,
                "approval_decision": "REJECTED",
            },
        ]

        result = build_historical_context(outcomes)

        assert "Summary Insights" in result
        assert "Total cycles reviewed: 2" in result
        assert "Approved: 1" in result
        assert "Rejected: 1" in result
        assert "Average Confidence Score: 70" in result

    def test_context_shows_variance_when_actual_available(self):
        """Context calculates and shows revenue variance when actuals are available."""
        outcomes = [
            {
                "cycle_id": "cycle-001",
                "timestamp": "2024-01-15T10:30:00+00:00",
                "selected_scenario": {"confidence_score": 85, "risk_level": "LOW",
                                      "composite_score": 87.5, "price_changes": []},
                "projected_metrics": {"revenue": 100000.0, "margin": 0.25},
                "actual_metrics": {"actual_revenue": 85000.0, "actual_margin": 0.22},
                "approval_decision": "APPROVED",
            }
        ]

        result = build_historical_context(outcomes)

        assert "Revenue Variance" in result
        assert "15.0%" in result
        assert "below" in result

    def test_context_handles_missing_actual_metrics(self):
        """Context gracefully handles outcomes without actual metrics."""
        outcomes = [
            {
                "cycle_id": "cycle-001",
                "timestamp": "2024-01-15T10:30:00+00:00",
                "selected_scenario": {"confidence_score": 85, "risk_level": "LOW",
                                      "composite_score": 87.5, "price_changes": []},
                "projected_metrics": {"revenue": 100000.0, "margin": 0.25},
                "actual_metrics": None,
                "approval_decision": "APPROVED",
            }
        ]

        result = build_historical_context(outcomes)

        assert "Not yet available" in result

    def test_context_truncates_price_changes_at_three(self):
        """Context shows at most 3 price changes with a 'more' indicator."""
        outcomes = [
            {
                "cycle_id": "cycle-001",
                "timestamp": "2024-01-15T10:30:00+00:00",
                "selected_scenario": {
                    "confidence_score": 85,
                    "risk_level": "LOW",
                    "composite_score": 87.5,
                    "price_changes": [
                        {"productId": f"product-{i}", "changePercent": 5.0 + i}
                        for i in range(5)
                    ],
                },
                "projected_metrics": {"revenue": 100000.0, "margin": 0.25},
                "actual_metrics": None,
                "approval_decision": "APPROVED",
            }
        ]

        result = build_historical_context(outcomes)

        assert "product-0" in result
        assert "product-1" in result
        assert "product-2" in result
        assert "product-3" not in result
        assert "2 more" in result


# ---------------------------------------------------------------------------
# Tests: _extract_product_or_category
# ---------------------------------------------------------------------------


class TestExtractProductOrCategory:
    """Tests for extracting the product/category key from scenarios."""

    def test_extracts_from_camel_case_price_changes(self):
        """Extracts product ID from camelCase priceChanges."""
        scenario = {
            "priceChanges": [
                {"productId": "product-abc", "currentPrice": 10.0}
            ]
        }
        assert _extract_product_or_category(scenario) == "product-abc"

    def test_extracts_from_snake_case_price_changes(self):
        """Extracts product ID from snake_case price_changes."""
        scenario = {
            "price_changes": [
                {"product_id": "product-def", "current_price": 10.0}
            ]
        }
        assert _extract_product_or_category(scenario) == "product-def"

    def test_falls_back_to_category(self):
        """Falls back to category when no price_changes."""
        scenario = {"category": "electronics", "priceChanges": []}
        assert _extract_product_or_category(scenario) == "electronics"

    def test_falls_back_to_pricing_group(self):
        """Falls back to pricing_group when no price_changes or category."""
        scenario = {"pricing_group": "beverages"}
        assert _extract_product_or_category(scenario) == "beverages"

    def test_falls_back_to_cycle_id(self):
        """Falls back to cycleId when no other keys available."""
        scenario = {"cycleId": "cycle-999"}
        assert _extract_product_or_category(scenario) == "cycle-999"

    def test_returns_unknown_for_empty_scenario(self):
        """Returns 'unknown' for a scenario with no identifiable keys."""
        scenario = {"someOtherField": "value"}
        assert _extract_product_or_category(scenario) == "unknown"


# ---------------------------------------------------------------------------
# Tests: _enforce_retention_limit
# ---------------------------------------------------------------------------


class TestEnforceRetentionLimit:
    """Tests for the retention limit enforcement."""

    def test_no_pruning_when_under_limit(self, dynamodb_table, sample_scenario):
        """No records are deleted when count is under MAX_CYCLES_PER_KEY."""
        # Persist 5 outcomes (well under 100)
        for i in range(5):
            scenario = {**sample_scenario, "scenarioId": f"scenario-{i:03d}"}
            persist_outcome(f"cycle-{i:03d}", scenario)
            time.sleep(0.01)

        results = query_historical_outcomes("product-abc", limit=100)
        assert len(results) == 5

    def test_pruning_when_over_limit(self, dynamodb_table):
        """Oldest records are pruned when count exceeds MAX_CYCLES_PER_KEY."""
        # We'll use a smaller scenario to speed up the test
        # and directly insert items to avoid the overhead of persist_outcome
        table = dynamodb_table

        # Insert 103 items directly
        for i in range(103):
            table.put_item(
                Item={
                    "product_or_category": "product-test",
                    "timestamp": f"2024-01-01T{i:06d}",
                    "cycle_id": f"cycle-{i:03d}",
                    "selected_scenario": {},
                    "projected_metrics": {},
                    "actual_metrics": None,
                    "approval_decision": "APPROVED",
                }
            )

        # Enforce the limit
        _enforce_retention_limit("product-test")

        # Should now have exactly MAX_CYCLES_PER_KEY items
        response = table.query(
            KeyConditionExpression=Key("product_or_category").eq("product-test"),
        )
        assert len(response["Items"]) == MAX_CYCLES_PER_KEY

    def test_pruning_removes_oldest_records(self, dynamodb_table):
        """Pruning removes the oldest records, keeping the most recent."""
        table = dynamodb_table

        # Insert 102 items
        for i in range(102):
            table.put_item(
                Item={
                    "product_or_category": "product-test",
                    "timestamp": f"2024-01-01T{i:06d}",
                    "cycle_id": f"cycle-{i:03d}",
                    "selected_scenario": {},
                    "projected_metrics": {},
                    "actual_metrics": None,
                    "approval_decision": "APPROVED",
                }
            )

        _enforce_retention_limit("product-test")

        # Query remaining items (most recent first)
        response = table.query(
            KeyConditionExpression=Key("product_or_category").eq("product-test"),
            ScanIndexForward=True,
        )
        items = response["Items"]
        assert len(items) == MAX_CYCLES_PER_KEY

        # The oldest 2 should have been removed (cycle-000, cycle-001)
        cycle_ids = [item["cycle_id"] for item in items]
        assert "cycle-000" not in cycle_ids
        assert "cycle-001" not in cycle_ids
        # The most recent should still be there
        assert "cycle-101" in cycle_ids


# ---------------------------------------------------------------------------
# Tests: Integration (query + persist together)
# ---------------------------------------------------------------------------


class TestIntegration:
    """Integration tests combining persist and query operations."""

    def test_persist_then_query_round_trip(
        self, dynamodb_table, sample_scenario, sample_actual_metrics
    ):
        """Persisted outcomes can be queried back with all data intact."""
        persist_outcome("cycle-001", sample_scenario, sample_actual_metrics)

        results = query_historical_outcomes("product-abc")
        assert len(results) == 1

        record = results[0]
        assert record["cycle_id"] == "cycle-001"
        assert record["selected_scenario"]["scenario_id"] == "scenario-001"
        # DynamoDB stores numbers as Decimal
        assert float(record["projected_metrics"]["margin"]) == pytest.approx(0.28)
        assert record["approval_decision"] == "APPROVED"

    def test_persist_and_build_context(
        self, dynamodb_table, sample_scenario, sample_actual_metrics
    ):
        """Persisted outcomes can be queried and formatted into context."""
        persist_outcome("cycle-001", sample_scenario, sample_actual_metrics)

        outcomes = query_historical_outcomes("product-abc")
        context = build_historical_context(outcomes)

        assert "Historical Pricing Outcomes" in context
        assert "cycle-001" in context
        assert "APPROVED" in context

    def test_multiple_products_isolated(self, dynamodb_table):
        """Outcomes for different products are isolated in queries."""
        scenario_a = {
            "scenarioId": "s-a",
            "priceChanges": [
                {"productId": "prod-A", "currentPrice": 10, "newPrice": 11,
                 "changePercent": 10}
            ],
            "projectedRevenue": 100000,
            "projectedMargin": 0.25,
            "compositeScore": 80,
            "confidenceScore": 75,
            "riskLevel": "LOW",
            "statusLabel": "Recommended",
            "approvalStatus": "APPROVED",
        }
        scenario_b = {
            "scenarioId": "s-b",
            "priceChanges": [
                {"productId": "prod-B", "currentPrice": 20, "newPrice": 22,
                 "changePercent": 10}
            ],
            "projectedRevenue": 200000,
            "projectedMargin": 0.30,
            "compositeScore": 90,
            "confidenceScore": 88,
            "riskLevel": "LOW",
            "statusLabel": "Recommended",
            "approvalStatus": "APPROVED",
        }

        persist_outcome("cycle-a", scenario_a)
        persist_outcome("cycle-b", scenario_b)

        results_a = query_historical_outcomes("prod-A")
        results_b = query_historical_outcomes("prod-B")

        assert len(results_a) == 1
        assert results_a[0]["cycle_id"] == "cycle-a"
        assert len(results_b) == 1
        assert results_b[0]["cycle_id"] == "cycle-b"
