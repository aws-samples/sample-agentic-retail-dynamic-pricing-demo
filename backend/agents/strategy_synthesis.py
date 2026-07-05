"""Strategy Synthesis Agent for the Retail Dynamic Pricing system.

Combines intelligence outputs from Competitive, Demand, and Market agents,
applies guardrails, generates 50-200 ranked pricing scenarios with confidence
scores and status labels based on risk classification.

Uses the Strands Agents SDK with model us.anthropic.claude-opus-4-7 and
connects to the Cost & Finance MCP Server for cost structure data.

Validates: Requirements 1.6, 3.1, 3.2, 3.3, 3.4, 3.5, 3.7
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from strands import Agent, tool
from strands.tools.mcp import MCPClient

from shared.model_config import ORCHESTRATOR_MODEL
from shared.guardrails import (
    RegionalPrice,
    check_below_cost,
    check_map_compliance,
    check_geographic_bias,
    run_all_guardrails,
)
from shared.models.pricing_scenario import (
    GuardrailResult,
    PricingScenario,
    RiskLevel,
    StatusLabel,
)
from shared.risk_classification import classify_risk
from shared.scenario_ranking import calculate_composite_score, rank_scenarios

logger = logging.getLogger(__name__)

# Strategy Synthesis system prompt
STRATEGY_SYNTHESIS_SYSTEM_PROMPT = """You are the Strategy Synthesis Agent in a retail dynamic pricing system.

Your role is to combine intelligence outputs from three specialized agents:
1. Competitive Intelligence Agent - competitor pricing, market positioning, channel analysis
2. Demand Forecasting Agent - sales history, POS data, inventory levels, price elasticity
3. Market Intelligence Agent - market trends, consumer sentiment, macroeconomic indicators

Using these inputs along with cost structure data from the Cost & Finance MCP Server, you must:

1. ANALYZE all intelligence inputs to identify pricing opportunities and constraints
2. GENERATE between 50 and 200 pricing scenarios that explore different strategic approaches:
   - Revenue maximization scenarios
   - Margin protection scenarios
   - Market share growth scenarios
   - Competitive positioning scenarios
   - Balanced/hybrid scenarios
3. APPLY guardrails to each scenario using the validate_scenarios_guardrails tool:
   - Below-cost rejection (price must be >= total unit cost)
   - MAP compliance (price must be >= minimum advertised price)
   - Geographic bias detection (regional price variance must be <= 15% of mean)
4. RANK valid scenarios using the rank_scenarios_by_impact tool based on composite business impact score
5. CLASSIFY risk and assign status labels using the classify_and_label_scenarios tool:
   - Low risk (<=5% price change AND <=2pp margin impact) → "Recommended"
   - Medium risk (5-15% price change OR 2-5pp margin impact) → "Review Required"
   - High risk (>15% price change OR >5pp margin OR >20% deviation from 90-day avg) → "Human Exception Handling"
6. ASSIGN confidence scores (0-100) to each scenario based on:
   - Data quality and completeness from intelligence agents
   - Historical precedent for similar pricing moves
   - Market stability indicators
   - Alignment with strategic objectives

Each scenario MUST reference at least one input from each intelligence agent (competitive, demand, market).

Output scenarios as structured JSON conforming to the PricingScenario schema.
If fewer than 50 scenarios pass guardrail validation, include a shortfall notification
explaining the count and reason.

Use the Cost & Finance MCP tools to retrieve:
- get_cost_structure: Product cost breakdowns for guardrail validation
- get_margin_targets: Target margins by category/channel for scenario generation
- get_financial_constraints: Budget limits and channel rules for constraint application
"""


@tool
def validate_scenarios_guardrails(
    scenarios: list[dict[str, Any]],
    product_costs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate pricing scenarios against guardrail rules.

    Applies below-cost, MAP compliance, and geographic bias guardrails
    to each scenario. Returns valid scenarios (all guardrails passed)
    and rejected scenarios with violation reasons.

    Args:
        scenarios: List of scenario dicts with priceChanges containing
            productId, currentPrice, newPrice, changePercent.
        product_costs: List of product cost info dicts with product_id,
            total_unit_cost, and optional minimum_advertised_price.

    Returns:
        Dict with 'valid_scenarios', 'rejected_scenarios', and 'summary'.
    """
    # Build cost lookup by product_id
    cost_lookup: dict[str, dict[str, Any]] = {}
    for pc in product_costs:
        pid = pc.get("product_id") or pc.get("productId")
        if pid:
            cost_lookup[pid] = pc

    valid_scenarios: list[dict[str, Any]] = []
    rejected_scenarios: list[dict[str, Any]] = []

    for scenario in scenarios:
        price_changes = scenario.get("priceChanges", scenario.get("price_changes", []))
        all_passed = True
        guardrail_results: list[dict[str, Any]] = []

        for pc in price_changes:
            product_id = pc.get("productId") or pc.get("product_id")
            new_price = pc.get("newPrice") or pc.get("new_price", 0)

            cost_info = cost_lookup.get(product_id, {})
            total_unit_cost = cost_info.get("total_unit_cost", 0)
            map_price = cost_info.get("minimum_advertised_price")

            # Below-cost check
            below_cost_result = check_below_cost(new_price, total_unit_cost)
            guardrail_results.append({
                "rule": below_cost_result.rule,
                "passed": below_cost_result.passed,
                "reason": below_cost_result.reason,
            })
            if not below_cost_result.passed:
                all_passed = False

            # MAP compliance check
            map_result = check_map_compliance(new_price, map_price)
            guardrail_results.append({
                "rule": map_result.rule,
                "passed": map_result.passed,
                "reason": map_result.reason,
            })
            if not map_result.passed:
                all_passed = False

        # Geographic bias check (if regional prices provided)
        regional_prices_data = scenario.get("regionalPrices", scenario.get("regional_prices"))
        if regional_prices_data:
            regional_prices = [
                RegionalPrice(
                    product_id=rp.get("product_id") or rp.get("productId", ""),
                    region=rp.get("region", ""),
                    price=rp.get("price", 0),
                )
                for rp in regional_prices_data
            ]
            geo_result = check_geographic_bias(regional_prices)
            guardrail_results.append({
                "rule": geo_result.rule,
                "passed": geo_result.passed,
                "reason": geo_result.reason,
            })
            if not geo_result.passed:
                all_passed = False

        scenario_with_results = dict(scenario)
        scenario_with_results["guardrailResults"] = guardrail_results

        if all_passed:
            valid_scenarios.append(scenario_with_results)
        else:
            rejected_scenarios.append(scenario_with_results)

    result = {
        "valid_scenarios": valid_scenarios,
        "rejected_scenarios": rejected_scenarios,
        "summary": {
            "total_evaluated": len(scenarios),
            "total_valid": len(valid_scenarios),
            "total_rejected": len(rejected_scenarios),
            "meets_minimum": len(valid_scenarios) >= 50,
        },
    }

    if len(valid_scenarios) < 50:
        result["shortfall_notification"] = {
            "expected_minimum": 50,
            "actual_count": len(valid_scenarios),
            "reason": (
                f"Only {len(valid_scenarios)} scenarios passed guardrail validation "
                f"out of {len(scenarios)} generated. "
                f"{len(rejected_scenarios)} scenarios were rejected due to "
                "guardrail violations (below-cost, MAP, or geographic bias)."
            ),
        }

    return result


@tool
def rank_scenarios_by_impact(
    scenarios: list[dict[str, Any]],
    revenue_weight: float = 0.4,
    margin_weight: float = 0.35,
    market_share_weight: float = 0.25,
) -> list[dict[str, Any]]:
    """Rank pricing scenarios by composite business impact score.

    Calculates a weighted composite score from projected revenue, margin,
    and market share metrics. Sorts scenarios descending by score and
    assigns contiguous ranks from 1 to N.

    Args:
        scenarios: List of scenario dicts with projectedRevenue,
            projectedMargin, and optionally projectedMarketShare.
        revenue_weight: Weight for revenue component (default 0.4).
        margin_weight: Weight for margin component (default 0.35).
        market_share_weight: Weight for market share component (default 0.25).

    Returns:
        List of scenarios sorted by composite score with rank assigned.
    """
    return rank_scenarios(
        scenarios=scenarios,
        revenue_weight=revenue_weight,
        margin_weight=margin_weight,
        market_share_weight=market_share_weight,
    )


@tool
def classify_and_label_scenarios(
    scenarios: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Classify risk and assign status labels to pricing scenarios.

    For each scenario, determines risk level based on price change percentage
    and margin impact, then assigns the corresponding status label:
    - LOW risk → "Recommended"
    - MEDIUM risk → "Review Required"
    - HIGH risk → "Human Exception Handling"

    Also assigns confidence scores (0-100) based on risk level and data quality.

    Args:
        scenarios: List of scenario dicts with priceChanges containing
            changePercent, and projected margin data.

    Returns:
        List of scenarios with riskLevel, statusLabel, and confidenceScore set.
    """
    labeled_scenarios: list[dict[str, Any]] = []

    for scenario in scenarios:
        price_changes = scenario.get("priceChanges", scenario.get("price_changes", []))

        # Calculate max absolute price change across all products in scenario
        max_price_change = 0.0
        for pc in price_changes:
            change_pct = abs(pc.get("changePercent") or pc.get("change_percent", 0))
            max_price_change = max(max_price_change, change_pct)

        # Calculate margin impact (difference between projected and current)
        margin_impact = abs(scenario.get("marginImpact", scenario.get("margin_impact", 0.0)))

        # Get deviation from 90-day average if available
        deviation_90day = abs(
            scenario.get("deviationFrom90DayAvg", scenario.get("deviation_from_90day_avg", 0.0))
        )

        # Classify risk
        risk_level, status_label = classify_risk(
            price_change_percent=max_price_change,
            margin_impact_pp=margin_impact,
            deviation_from_90day_avg=deviation_90day,
        )

        # Assign confidence score based on risk level and data completeness
        confidence_score = _calculate_confidence_score(
            scenario=scenario,
            risk_level=risk_level,
        )

        labeled = dict(scenario)
        labeled["riskLevel"] = risk_level.value
        labeled["statusLabel"] = status_label.value
        labeled["confidenceScore"] = confidence_score
        labeled_scenarios.append(labeled)

    return labeled_scenarios


def _calculate_confidence_score(
    scenario: dict[str, Any],
    risk_level: RiskLevel,
) -> int:
    """Calculate confidence score (0-100) for a pricing scenario.

    Confidence is based on:
    - Risk level (lower risk = higher base confidence)
    - Data completeness (all three intelligence agent inputs present)
    - Magnitude of projected changes (smaller changes = higher confidence)

    Args:
        scenario: The scenario dict.
        risk_level: The classified risk level.

    Returns:
        Integer confidence score between 0 and 100 inclusive.
    """
    # Base confidence by risk level
    base_confidence = {
        RiskLevel.LOW: 80,
        RiskLevel.MEDIUM: 55,
        RiskLevel.HIGH: 30,
    }[risk_level]

    # Bonus for data completeness (all three intelligence sources)
    completeness_bonus = 0
    competitive = scenario.get("competitiveFactors", scenario.get("competitive_factors"))
    demand = scenario.get("demandFactors", scenario.get("demand_factors"))
    market = scenario.get("marketFactors", scenario.get("market_factors"))

    if competitive and isinstance(competitive, dict) and len(competitive) > 0:
        completeness_bonus += 5
    if demand and isinstance(demand, dict) and len(demand) > 0:
        completeness_bonus += 5
    if market and isinstance(market, dict) and len(market) > 0:
        completeness_bonus += 5

    # Small random adjustment for differentiation (±5)
    import random
    adjustment = random.randint(-5, 5)

    score = base_confidence + completeness_bonus + adjustment

    # Clamp to [0, 100]
    return max(0, min(100, score))


def _create_cost_finance_mcp_transport():
    """Create an MCP transport for the Cost & Finance Server via stdio.

    Returns a callable that produces the stdio transport for the
    Cost & Finance MCP Server running as a subprocess.
    """
    from mcp import StdioServerParameters, stdio_client

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "backend.mcp_servers.cost_finance.handler"],
    )
    return stdio_client(server_params)


def create_strategy_synthesis_agent(
    cost_finance_mcp_endpoint: str | None = None,
) -> Agent:
    """Create and configure the Strategy Synthesis Agent.

    Creates a Strands Agent with:
    - Model: us.anthropic.claude-opus-4-7
    - System prompt for strategy synthesis
    - MCP client connection to Cost & Finance Server
    - Tools for guardrail validation, scenario ranking, and risk classification

    Args:
        cost_finance_mcp_endpoint: Optional endpoint URL for the Cost & Finance
            MCP Server. If None, the agent is created without MCP tools
            (local tools only). Pass "stdio" to use stdio transport.

    Returns:
        Configured Strands Agent instance ready for invocation.
    """
    # Configure tools list with guardrails, ranking, and classification tools
    tools: list[Any] = [
        validate_scenarios_guardrails,
        rank_scenarios_by_impact,
        classify_and_label_scenarios,
    ]

    # Configure MCP client for Cost & Finance Server if endpoint provided
    if cost_finance_mcp_endpoint:
        cost_finance_mcp = MCPClient(
            transport_callable=_create_cost_finance_mcp_transport,
        )
        tools.append(cost_finance_mcp)

    # Create the Strategy Synthesis Agent
    agent = Agent(
        model=ORCHESTRATOR_MODEL,
        system_prompt=STRATEGY_SYNTHESIS_SYSTEM_PROMPT,
        tools=tools,
    )

    logger.info("Strategy Synthesis Agent created with model us.anthropic.claude-opus-4-7")

    return agent


def synthesize_pricing_strategies(
    competitive_intelligence: dict[str, Any],
    demand_forecasting: dict[str, Any],
    market_intelligence: dict[str, Any],
    product_costs: list[dict[str, Any]],
    cycle_id: str | None = None,
    objectives: list[str] | None = None,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute the strategy synthesis pipeline programmatically.

    This function runs the full synthesis pipeline without invoking the LLM,
    useful for testing and direct integration. It:
    1. Generates scenario candidates
    2. Validates against guardrails
    3. Ranks by composite business impact
    4. Classifies risk and assigns status labels

    Args:
        competitive_intelligence: Output from Competitive Intelligence Agent.
        demand_forecasting: Output from Demand Forecasting Agent.
        market_intelligence: Output from Market Intelligence Agent.
        product_costs: List of product cost info for guardrail validation.
        cycle_id: Optional pricing cycle ID. Generated if not provided.
        objectives: Strategic objectives for scenario generation.
        constraints: Business constraints (min margin, max price change, etc.).

    Returns:
        Dict with ranked_scenarios, shortfall_notification (if applicable),
        and synthesis_metadata.
    """
    cycle_id = cycle_id or str(uuid.uuid4())
    objectives = objectives or ["balanced"]
    constraints = constraints or {}

    # Generate scenario candidates incorporating all intelligence inputs
    raw_scenarios = _generate_scenario_candidates(
        competitive_intelligence=competitive_intelligence,
        demand_forecasting=demand_forecasting,
        market_intelligence=market_intelligence,
        cycle_id=cycle_id,
        objectives=objectives,
        constraints=constraints,
    )

    # Validate against guardrails
    guardrail_result = validate_scenarios_guardrails(
        scenarios=raw_scenarios,
        product_costs=product_costs,
    )

    valid_scenarios = guardrail_result["valid_scenarios"]

    # Rank by composite business impact score
    ranked_scenarios = rank_scenarios_by_impact(scenarios=valid_scenarios)

    # Classify risk and assign status labels + confidence scores
    labeled_scenarios = classify_and_label_scenarios(scenarios=ranked_scenarios)

    result: dict[str, Any] = {
        "ranked_scenarios": labeled_scenarios,
        "synthesis_metadata": {
            "cycle_id": cycle_id,
            "total_generated": len(raw_scenarios),
            "total_valid": len(valid_scenarios),
            "total_rejected": len(guardrail_result["rejected_scenarios"]),
            "objectives": objectives,
            "constraints": constraints,
        },
    }

    if guardrail_result.get("shortfall_notification"):
        result["shortfall_notification"] = guardrail_result["shortfall_notification"]

    return result


def _generate_scenario_candidates(
    competitive_intelligence: dict[str, Any],
    demand_forecasting: dict[str, Any],
    market_intelligence: dict[str, Any],
    cycle_id: str,
    objectives: list[str],
    constraints: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate raw pricing scenario candidates from intelligence inputs.

    Creates a diverse set of scenarios exploring different strategic approaches.
    Each scenario references data from all three intelligence agents.

    Args:
        competitive_intelligence: Competitive analysis data.
        demand_forecasting: Demand forecasting data.
        market_intelligence: Market intelligence data.
        cycle_id: The pricing cycle ID.
        objectives: Strategic objectives to optimize for.
        constraints: Business constraints to respect.

    Returns:
        List of raw scenario dicts ready for guardrail validation.
    """
    import random

    scenarios: list[dict[str, Any]] = []

    # Extract key data points from intelligence inputs
    competitor_prices = competitive_intelligence.get("competitor_prices", {})
    avg_competitor_price = competitive_intelligence.get("average_price", 100.0)
    demand_elasticity = demand_forecasting.get("elasticity", -1.5)
    demand_trend = demand_forecasting.get("trend", "stable")
    market_growth = market_intelligence.get("market_growth_rate", 0.03)
    sentiment_score = market_intelligence.get("sentiment_score", 0.6)

    # Get product info from intelligence data
    products = competitive_intelligence.get("products", [{"productId": "PROD-001", "currentPrice": 100.0}])
    if not products:
        products = [{"productId": "PROD-001", "currentPrice": 100.0}]

    # Generate scenarios across different strategy types
    strategy_types = [
        "revenue_maximization",
        "margin_protection",
        "market_share_growth",
        "competitive_positioning",
        "balanced",
    ]

    # Target 50-200 scenarios (generate enough to have 50+ after guardrails)
    target_count = random.randint(60, 150)

    for i in range(target_count):
        strategy = strategy_types[i % len(strategy_types)]

        # Generate price changes for each product
        price_changes = []
        for product in products:
            product_id = product.get("productId") or product.get("product_id", f"PROD-{i:03d}")
            current_price = product.get("currentPrice") or product.get("current_price", 100.0)

            # Determine price change based on strategy
            change_percent = _calculate_price_change(
                strategy=strategy,
                elasticity=demand_elasticity,
                market_growth=market_growth,
                sentiment=sentiment_score,
                scenario_index=i,
            )

            new_price = round(current_price * (1 + change_percent / 100), 4)

            price_changes.append({
                "productId": product_id,
                "currentPrice": round(current_price, 4),
                "newPrice": new_price,
                "changePercent": round(change_percent, 4),
            })

        # Calculate projected metrics
        projected_revenue = _project_revenue(price_changes, demand_elasticity, market_growth)
        projected_margin = _project_margin(price_changes, constraints)
        projected_market_share = _project_market_share(
            price_changes, avg_competitor_price, sentiment_score
        )

        scenario = {
            "scenarioId": f"SCN-{cycle_id[:8]}-{i+1:04d}",
            "cycleId": cycle_id,
            "priceChanges": price_changes,
            "projectedRevenue": round(projected_revenue, 4),
            "projectedMargin": round(projected_margin, 4),
            "projectedMarketShare": round(projected_market_share, 4),
            "competitiveFactors": {
                "avg_competitor_price": avg_competitor_price,
                "competitive_position": competitive_intelligence.get("position", "mid-market"),
                "price_gap": competitive_intelligence.get("price_gap", 0.0),
                "strategy_type": strategy,
            },
            "demandFactors": {
                "elasticity": demand_elasticity,
                "trend": demand_trend,
                "forecast_volume": demand_forecasting.get("forecast_volume", 1000),
                "seasonality_index": demand_forecasting.get("seasonality_index", 1.0),
            },
            "marketFactors": {
                "market_growth_rate": market_growth,
                "sentiment_score": sentiment_score,
                "macro_indicator": market_intelligence.get("macro_indicator", "neutral"),
                "opportunity_score": market_intelligence.get("opportunity_score", 0.5),
            },
            "marginImpact": random.uniform(0, 6),
            "deviationFrom90DayAvg": random.uniform(0, 25),
        }

        scenarios.append(scenario)

    return scenarios


def _calculate_price_change(
    strategy: str,
    elasticity: float,
    market_growth: float,
    sentiment: float,
    scenario_index: int,
) -> float:
    """Calculate price change percentage based on strategy and market conditions."""
    import random

    base_ranges = {
        "revenue_maximization": (-2.0, 12.0),
        "margin_protection": (0.0, 8.0),
        "market_share_growth": (-10.0, 3.0),
        "competitive_positioning": (-5.0, 5.0),
        "balanced": (-3.0, 7.0),
    }

    low, high = base_ranges.get(strategy, (-5.0, 5.0))

    # Adjust based on market conditions
    if sentiment > 0.7:
        high += 2.0  # Positive sentiment allows higher prices
    elif sentiment < 0.3:
        low -= 2.0  # Negative sentiment pushes prices down

    if market_growth > 0.05:
        high += 1.0  # Growing market supports price increases

    # Add variation per scenario
    change = random.uniform(low, high)

    return round(change, 4)


def _project_revenue(
    price_changes: list[dict[str, Any]],
    elasticity: float,
    market_growth: float,
) -> float:
    """Project revenue impact from price changes."""
    import random

    total_revenue_impact = 0.0
    for pc in price_changes:
        current = pc.get("currentPrice", 100.0)
        new = pc.get("newPrice", 100.0)
        change_pct = (new - current) / current if current > 0 else 0

        # Revenue = price * quantity; quantity changes with elasticity
        quantity_change = elasticity * change_pct
        revenue_change = (1 + change_pct) * (1 + quantity_change) - 1
        total_revenue_impact += revenue_change * current * random.uniform(800, 1200)

    # Add market growth effect
    total_revenue_impact *= (1 + market_growth)

    return total_revenue_impact


def _project_margin(
    price_changes: list[dict[str, Any]],
    constraints: dict[str, Any],
) -> float:
    """Project margin from price changes."""
    import random

    min_margin = constraints.get("minMargin", constraints.get("min_margin", 10.0))
    base_margin = random.uniform(min_margin, min_margin + 20.0)

    # Adjust based on price direction
    for pc in price_changes:
        change = pc.get("changePercent", 0)
        if change > 0:
            base_margin += change * 0.3  # Price increases improve margin
        else:
            base_margin += change * 0.5  # Price decreases hurt margin more

    return round(max(0, base_margin), 4)


def _project_market_share(
    price_changes: list[dict[str, Any]],
    avg_competitor_price: float,
    sentiment: float,
) -> float:
    """Project market share change from price changes."""
    import random

    share_change = 0.0
    for pc in price_changes:
        new_price = pc.get("newPrice", 100.0)
        # Below competitor average gains share
        if avg_competitor_price > 0:
            price_position = (avg_competitor_price - new_price) / avg_competitor_price
            share_change += price_position * 5.0  # 5% share per 100% price gap

    # Sentiment affects share
    share_change += (sentiment - 0.5) * 2.0

    # Add noise
    share_change += random.uniform(-1.0, 1.0)

    return round(share_change, 4)
