"""Seed script to populate DynamoDB with historical pricing cycles for demo purposes.

Creates 5 completed pricing cycles with scenarios, approvals, and varied data
so the Analytics tab and Audit Trail have content from the start.

Usage:
    python scripts/seed_demo_cycles.py
"""

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3

PRICING_CYCLES_TABLE = "PricingCycles"
PRICING_SCENARIOS_TABLE = "PricingScenarios"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _decimal(val: float) -> Decimal:
    return Decimal(str(round(val, 4)))


def seed_demo_cycles():
    dynamodb = boto3.resource("dynamodb")
    cycles_table = dynamodb.Table(PRICING_CYCLES_TABLE)
    scenarios_table = dynamodb.Table(PRICING_SCENARIOS_TABLE)

    now = datetime.now(timezone.utc)

    demo_cycles = [
        {
            "pricingGroup": "Electronics-Audio",
            "objectives": ["revenue_maximization", "competitive_positioning"],
            "constraints": {"minMargin": 15, "maxPriceChange": 10},
            "offset_hours": 48,
        },
        {
            "pricingGroup": "Grocery-Dairy",
            "objectives": ["margin_protection"],
            "constraints": {"minMargin": 20, "maxPriceChange": 8},
            "offset_hours": 36,
        },
        {
            "pricingGroup": "Home & Garden-Lighting",
            "objectives": ["revenue_maximization"],
            "constraints": {"minMargin": 25, "maxPriceChange": 5},
            "offset_hours": 24,
        },
        {
            "pricingGroup": "Electronics-Wearables",
            "objectives": ["market_share_growth", "revenue_maximization"],
            "constraints": {"minMargin": 12, "maxPriceChange": 15},
            "offset_hours": 12,
        },
        {
            "pricingGroup": "Grocery-Beverages",
            "objectives": ["competitive_positioning", "margin_protection"],
            "constraints": {"minMargin": 10, "maxPriceChange": 12},
            "offset_hours": 6,
        },
    ]

    print(f"Seeding {len(demo_cycles)} historical pricing cycles...")

    for i, cycle_config in enumerate(demo_cycles, 1):
        cycle_id = str(uuid.uuid4())
        created_at = now - timedelta(hours=cycle_config["offset_hours"])
        completed_at = created_at + timedelta(seconds=random.randint(45, 65))

        # Write cycle
        cycle_item = {
            "cycleId": cycle_id,
            "status": "COMPLETE",
            "pricingGroup": cycle_config["pricingGroup"],
            "objectives": cycle_config["objectives"],
            "constraints": {k: _decimal(v) for k, v in cycle_config["constraints"].items()},
            "scenarioCount": 3,
            "requestedBy": "demo-user",
            "createdAt": _iso(created_at),
            "completedAt": _iso(completed_at),
            "agentStatuses": {
                "orchestrator": {"status": "completed"},
                "competitive_intelligence": {"status": "completed"},
                "demand_forecasting": {"status": "completed"},
                "market_intelligence": {"status": "completed"},
                "strategy_synthesis": {"status": "completed"},
                "implementation_monitoring": {"status": "completed"},
            },
        }
        cycles_table.put_item(Item=cycle_item)

        # Generate 3 scenarios
        strategies = [
            {"name": "Aggressive Growth", "risk": "HIGH", "confidence": random.randint(65, 78), "bias": 0.7},
            {"name": "Balanced Optimization", "risk": "MEDIUM", "confidence": random.randint(80, 90), "bias": 0.0},
            {"name": "Conservative Protection", "risk": "LOW", "confidence": random.randint(88, 95), "bias": -0.5},
        ]

        for rank, strategy in enumerate(strategies, 1):
            scenario_id = str(uuid.uuid4())
            projected_revenue = round(random.uniform(20000, 80000), 2)
            projected_margin = round(random.uniform(0.12, 0.28), 4)

            # Auto-approve LOW risk, manually approve one MEDIUM
            if strategy["risk"] == "LOW":
                approval_status = "APPROVED"
                approved_by = "system-auto-approval"
                approval_comment = "Auto-approved: LOW risk scenario meets all business rules (straight-through processing)"
            elif strategy["risk"] == "MEDIUM" and random.random() > 0.5:
                approval_status = "APPROVED"
                approved_by = "demo-user"
                approval_comment = "Approved: balanced approach aligns with Q2 strategy"
            else:
                approval_status = None
                approved_by = None
                approval_comment = None

            status_label = (
                "Recommended" if strategy["risk"] == "LOW"
                else "Review Required" if strategy["risk"] == "MEDIUM"
                else "Human Exception Handling"
            )

            scenario_item = {
                "cycleId": cycle_id,
                "scenarioId": scenario_id,
                "rank": rank,
                "confidenceScore": strategy["confidence"],
                "statusLabel": status_label,
                "riskLevel": strategy["risk"],
                "projectedRevenue": _decimal(projected_revenue),
                "projectedMargin": _decimal(projected_margin),
                "projectedMarketShare": _decimal(round(random.uniform(-2, 5), 2)),
                "compositeScore": _decimal(round(strategy["confidence"] * 0.8 + random.uniform(0, 20), 2)),
                "priceChanges": [
                    {
                        "productId": f"prod-demo-{random.randint(1,19):03d}",
                        "productName": f"Demo Product {random.randint(1,19)}",
                        "currentPrice": _decimal(round(random.uniform(10, 200), 2)),
                        "newPrice": _decimal(round(random.uniform(10, 200), 2)),
                        "changePercent": _decimal(round(random.uniform(-10, 10), 2)),
                    }
                ],
                "competitiveFactors": {
                    "competitorPriceIndex": _decimal(round(random.uniform(0.85, 1.15), 3)),
                    "marketPosition": "competitive",
                    "dataSource": "simulated",
                },
                "demandFactors": {
                    "elasticity": _decimal(round(random.uniform(-2.5, -0.5), 2)),
                    "seasonalIndex": _decimal(round(random.uniform(0.8, 1.3), 2)),
                    "dataSource": "simulated",
                },
                "marketFactors": {
                    "inflationRate": "3.2%",
                    "consumerSentiment": _decimal(round(random.uniform(60, 85), 1)),
                    "dataSource": "simulated",
                },
                "guardrailResults": [
                    {"rule": "Minimum Margin", "passed": True},
                    {"rule": "Maximum Price Change", "passed": True},
                    {"rule": "Bedrock Guardrail Policy", "passed": True},
                ],
                "aiRationale": f"Strategy: {strategy['name']}. Optimized for {', '.join(cycle_config['objectives']).replace('_', ' ')} in {cycle_config['pricingGroup'].replace('-', ' > ')}.",
                "dataSource": "simulated",
                "createdAt": _iso(completed_at),
            }

            if approval_status:
                scenario_item["approvalStatus"] = approval_status
                scenario_item["approvedBy"] = approved_by
                scenario_item["approvalComment"] = approval_comment
                scenario_item["approvedAt"] = _iso(completed_at + timedelta(minutes=random.randint(1, 30)))

            scenarios_table.put_item(Item=scenario_item)

        print(f"  [{i}/{len(demo_cycles)}] {cycle_config['pricingGroup']} — 3 scenarios")

    print(f"\nDone! {len(demo_cycles)} historical cycles seeded.")
    print("The Analytics tab and Audit Trail will now show data.")


if __name__ == "__main__":
    seed_demo_cycles()
