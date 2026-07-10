"""Property-based tests for the scenario ranking module.

Uses hypothesis to verify that scenario ranking produces contiguous ranks
ordered by composite score for arbitrary inputs.

Feature: retail-dynamic-pricing
"""

import pytest
from hypothesis import given, settings
from hypothesis.strategies import (
    composite,
    floats,
    integers,
    lists,
    text,
)

from shared.scenario_ranking import rank_scenarios


# Strategy to generate a single scenario dict with random projected metrics
@composite
def scenario_strategy(draw):
    """Generate a random pricing scenario dict with projected metrics."""
    scenario_id = draw(text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz0123456789"))
    projected_revenue = draw(floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))
    projected_margin = draw(floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))
    projected_market_share = draw(floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))

    return {
        "scenarioId": scenario_id,
        "projectedRevenue": projected_revenue,
        "projectedMargin": projected_margin,
        "projectedMarketShare": projected_market_share,
    }


# Strategy to generate a non-empty list of scenarios
scenario_list_strategy = lists(scenario_strategy(), min_size=1, max_size=50)


class TestPropertyScenarioRanking:
    """Property 1: Scenario ranking is contiguous and ordered by composite score.

    For any list of N scenarios (N >= 1):
    - Ranks form a contiguous sequence from 1 to N (no gaps, no duplicates)
    - For any two scenarios with ranks i and j where i < j,
      compositeScore[i] >= compositeScore[j]

    **Validates: Requirements 1.3, 3.2**
    """

    @settings(max_examples=100)
    @given(scenarios=scenario_list_strategy)
    def test_ranks_form_contiguous_sequence(self, scenarios):
        """Ranks form a contiguous sequence from 1 to N with no gaps or duplicates.

        **Validates: Requirements 1.3, 3.2**
        """
        ranked = rank_scenarios(scenarios)
        n = len(ranked)

        # Extract all ranks
        ranks = [s["rank"] for s in ranked]

        # Ranks should be exactly {1, 2, ..., N}
        assert sorted(ranks) == list(range(1, n + 1)), (
            f"Expected contiguous ranks 1..{n}, got {sorted(ranks)}"
        )

    @settings(max_examples=100)
    @given(scenarios=scenario_list_strategy)
    def test_ranks_ordered_by_composite_score_descending(self, scenarios):
        """For ranks i < j, compositeScore at rank i >= compositeScore at rank j.

        **Validates: Requirements 1.3, 3.2**
        """
        ranked = rank_scenarios(scenarios)

        # Verify ordering: each scenario's composite score is >= the next one's
        for i in range(len(ranked) - 1):
            assert ranked[i]["compositeScore"] >= ranked[i + 1]["compositeScore"], (
                f"Scenario at rank {ranked[i]['rank']} has compositeScore "
                f"{ranked[i]['compositeScore']} which is less than scenario at rank "
                f"{ranked[i + 1]['rank']} with compositeScore {ranked[i + 1]['compositeScore']}"
            )

    @settings(max_examples=100)
    @given(scenarios=scenario_list_strategy)
    def test_output_length_matches_input_length(self, scenarios):
        """The number of ranked scenarios equals the number of input scenarios.

        **Validates: Requirements 1.3, 3.2**
        """
        ranked = rank_scenarios(scenarios)
        assert len(ranked) == len(scenarios)

    @settings(max_examples=100)
    @given(scenarios=scenario_list_strategy)
    def test_each_scenario_has_rank_and_composite_score(self, scenarios):
        """Every ranked scenario has both 'rank' and 'compositeScore' fields set.

        **Validates: Requirements 1.3, 3.2**
        """
        ranked = rank_scenarios(scenarios)
        for s in ranked:
            assert "rank" in s, "Scenario missing 'rank' field"
            assert "compositeScore" in s, "Scenario missing 'compositeScore' field"
            assert isinstance(s["rank"], int), f"Rank should be int, got {type(s['rank'])}"
            assert isinstance(s["compositeScore"], (int, float)), (
                f"compositeScore should be numeric, got {type(s['compositeScore'])}"
            )
