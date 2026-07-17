"""Property-based tests for approval routing function.

Property 10: Approval routing matches risk level.
For any RiskLevel:
  - LOW → action_type must be AUTO_APPROVE, requires_justification=False
  - MEDIUM → action_type must be HUMAN_REVIEW, requires_justification=False
  - HIGH → action_type must be EXCEPTION_HANDLING, requires_justification=True,
           min_justification_length=50

Also validates that validate_approval with HIGH risk returns False for
justification < 50 chars and True for justification >= 50 chars.

Feature: retail-dynamic-pricing, Property 10: Approval routing matches risk level
Validates: Requirements 7.1, 7.2, 7.3
"""

from hypothesis import given, settings
from hypothesis.strategies import sampled_from, text, integers

from shared.approval_routing import (
    ApprovalAction,
    ApprovalActionType,
    get_approval_action,
    validate_approval,
)
from shared.models.pricing_scenario import RiskLevel


# Strategy for generating all valid risk levels
risk_levels = sampled_from([RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH])


class TestProperty10ApprovalRoutingMatchesRiskLevel:
    """Property 10: Approval routing matches risk level.

    Validates: Requirements 7.1, 7.2, 7.3
    """

    @given(risk_level=sampled_from([RiskLevel.LOW]))
    @settings(max_examples=100)
    def test_low_risk_auto_approves(self, risk_level: RiskLevel):
        """LOW risk → AUTO_APPROVE, requires_justification=False.

        **Validates: Requirements 7.1**
        """
        action = get_approval_action(risk_level)
        assert action.action_type == ApprovalActionType.AUTO_APPROVE, (
            f"Expected AUTO_APPROVE for LOW risk, got {action.action_type}"
        )
        assert action.requires_justification is False, (
            "LOW risk should not require justification"
        )
        assert action.min_justification_length == 0, (
            f"LOW risk min_justification_length should be 0, got {action.min_justification_length}"
        )

    @given(risk_level=sampled_from([RiskLevel.MEDIUM]))
    @settings(max_examples=100)
    def test_medium_risk_routes_to_human_review(self, risk_level: RiskLevel):
        """MEDIUM risk → HUMAN_REVIEW, requires_justification=False.

        **Validates: Requirements 7.2**
        """
        action = get_approval_action(risk_level)
        assert action.action_type == ApprovalActionType.HUMAN_REVIEW, (
            f"Expected HUMAN_REVIEW for MEDIUM risk, got {action.action_type}"
        )
        assert action.requires_justification is False, (
            "MEDIUM risk should not require justification"
        )
        assert action.min_justification_length == 0, (
            f"MEDIUM risk min_justification_length should be 0, got {action.min_justification_length}"
        )

    @given(risk_level=sampled_from([RiskLevel.HIGH]))
    @settings(max_examples=100)
    def test_high_risk_routes_to_exception_handling(self, risk_level: RiskLevel):
        """HIGH risk → EXCEPTION_HANDLING, requires_justification=True, min_justification_length=50.

        **Validates: Requirements 7.3**
        """
        action = get_approval_action(risk_level)
        assert action.action_type == ApprovalActionType.EXCEPTION_HANDLING, (
            f"Expected EXCEPTION_HANDLING for HIGH risk, got {action.action_type}"
        )
        assert action.requires_justification is True, (
            "HIGH risk should require justification"
        )
        assert action.min_justification_length == 50, (
            f"HIGH risk min_justification_length should be 50, got {action.min_justification_length}"
        )

    @given(risk_level=risk_levels)
    @settings(max_examples=100)
    def test_routing_is_deterministic_and_exhaustive(self, risk_level: RiskLevel):
        """For any valid RiskLevel, get_approval_action returns a valid ApprovalAction
        with action_type in the expected set.

        **Validates: Requirements 7.1, 7.2, 7.3**
        """
        action = get_approval_action(risk_level)
        assert isinstance(action, ApprovalAction)
        assert action.action_type in (
            ApprovalActionType.AUTO_APPROVE,
            ApprovalActionType.HUMAN_REVIEW,
            ApprovalActionType.EXCEPTION_HANDLING,
        )

    @given(
        justification_length=integers(min_value=0, max_value=49),
    )
    @settings(max_examples=100)
    def test_high_risk_validate_approval_rejects_short_justification(
        self, justification_length: int
    ):
        """HIGH risk validate_approval returns False for justification < 50 chars.

        **Validates: Requirements 7.3**
        """
        justification = "x" * justification_length
        result = validate_approval(RiskLevel.HIGH, justification)
        assert result is False, (
            f"Expected False for HIGH risk with justification length {justification_length}, "
            f"got {result}"
        )

    @given(
        justification_length=integers(min_value=50, max_value=500),
    )
    @settings(max_examples=100)
    def test_high_risk_validate_approval_accepts_sufficient_justification(
        self, justification_length: int
    ):
        """HIGH risk validate_approval returns True for justification >= 50 chars.

        **Validates: Requirements 7.3**
        """
        justification = "a" * justification_length
        result = validate_approval(RiskLevel.HIGH, justification)
        assert result is True, (
            f"Expected True for HIGH risk with justification length {justification_length}, "
            f"got {result}"
        )

    @given(
        justification=text(min_size=0, max_size=200),
    )
    @settings(max_examples=100)
    def test_low_risk_validate_approval_always_valid(self, justification: str):
        """LOW risk validate_approval always returns True regardless of justification.

        **Validates: Requirements 7.1**
        """
        result = validate_approval(RiskLevel.LOW, justification)
        assert result is True, (
            f"Expected True for LOW risk regardless of justification, got {result}"
        )

    @given(
        justification=text(min_size=0, max_size=200),
    )
    @settings(max_examples=100)
    def test_medium_risk_validate_approval_always_valid(self, justification: str):
        """MEDIUM risk validate_approval always returns True regardless of justification.

        **Validates: Requirements 7.2**
        """
        result = validate_approval(RiskLevel.MEDIUM, justification)
        assert result is True, (
            f"Expected True for MEDIUM risk regardless of justification, got {result}"
        )

    @settings(max_examples=100)
    @given(risk_level=risk_levels)
    def test_high_risk_validate_approval_rejects_none_justification(self, risk_level: RiskLevel):
        """HIGH risk validate_approval returns False when justification is None.

        **Validates: Requirements 7.3**
        """
        if risk_level == RiskLevel.HIGH:
            result = validate_approval(risk_level, None)
            assert result is False, (
                "Expected False for HIGH risk with None justification"
            )
