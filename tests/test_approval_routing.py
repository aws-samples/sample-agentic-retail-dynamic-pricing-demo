"""Unit tests for the approval routing module.

Tests risk-based approval routing logic:
- LOW risk → auto-approve
- MEDIUM risk → human review
- HIGH risk → exception handling with ≥50 char justification

Validates: Requirements 7.1, 7.2, 7.3
"""

import pytest

from shared.approval_routing import (
    ApprovalAction,
    ApprovalActionType,
    get_approval_action,
    validate_approval,
)
from shared.models.pricing_scenario import RiskLevel


class TestGetApprovalAction:
    """Tests for the get_approval_action function."""

    def test_low_risk_returns_auto_approve(self):
        action = get_approval_action(RiskLevel.LOW)
        assert action.action_type == ApprovalActionType.AUTO_APPROVE

    def test_low_risk_does_not_require_justification(self):
        action = get_approval_action(RiskLevel.LOW)
        assert action.requires_justification is False
        assert action.min_justification_length == 0

    def test_medium_risk_returns_human_review(self):
        action = get_approval_action(RiskLevel.MEDIUM)
        assert action.action_type == ApprovalActionType.HUMAN_REVIEW

    def test_medium_risk_does_not_require_justification(self):
        action = get_approval_action(RiskLevel.MEDIUM)
        assert action.requires_justification is False
        assert action.min_justification_length == 0

    def test_high_risk_returns_exception_handling(self):
        action = get_approval_action(RiskLevel.HIGH)
        assert action.action_type == ApprovalActionType.EXCEPTION_HANDLING

    def test_high_risk_requires_justification(self):
        action = get_approval_action(RiskLevel.HIGH)
        assert action.requires_justification is True
        assert action.min_justification_length == 50

    def test_all_risk_levels_return_approval_action(self):
        for level in RiskLevel:
            action = get_approval_action(level)
            assert isinstance(action, ApprovalAction)
            assert isinstance(action.action_type, ApprovalActionType)
            assert isinstance(action.requires_justification, bool)
            assert isinstance(action.min_justification_length, int)
            assert action.min_justification_length >= 0


class TestValidateApproval:
    """Tests for the validate_approval function."""

    def test_low_risk_valid_without_justification(self):
        assert validate_approval(RiskLevel.LOW) is True

    def test_low_risk_valid_with_none_justification(self):
        assert validate_approval(RiskLevel.LOW, justification=None) is True

    def test_low_risk_valid_with_empty_justification(self):
        assert validate_approval(RiskLevel.LOW, justification="") is True

    def test_medium_risk_valid_without_justification(self):
        assert validate_approval(RiskLevel.MEDIUM) is True

    def test_medium_risk_valid_with_none_justification(self):
        assert validate_approval(RiskLevel.MEDIUM, justification=None) is True

    def test_medium_risk_valid_with_empty_justification(self):
        assert validate_approval(RiskLevel.MEDIUM, justification="") is True

    def test_high_risk_invalid_without_justification(self):
        assert validate_approval(RiskLevel.HIGH) is False

    def test_high_risk_invalid_with_none_justification(self):
        assert validate_approval(RiskLevel.HIGH, justification=None) is False

    def test_high_risk_invalid_with_empty_justification(self):
        assert validate_approval(RiskLevel.HIGH, justification="") is False

    def test_high_risk_invalid_with_short_justification(self):
        # 49 characters - just under the threshold
        justification = "a" * 49
        assert validate_approval(RiskLevel.HIGH, justification=justification) is False

    def test_high_risk_valid_with_exact_50_char_justification(self):
        justification = "a" * 50
        assert validate_approval(RiskLevel.HIGH, justification=justification) is True

    def test_high_risk_valid_with_long_justification(self):
        justification = "This is a detailed justification explaining why this high-risk pricing change is necessary for the business."
        assert len(justification) >= 50
        assert validate_approval(RiskLevel.HIGH, justification=justification) is True

    def test_high_risk_boundary_49_chars_invalid(self):
        justification = "x" * 49
        assert validate_approval(RiskLevel.HIGH, justification=justification) is False

    def test_high_risk_boundary_50_chars_valid(self):
        justification = "x" * 50
        assert validate_approval(RiskLevel.HIGH, justification=justification) is True

    def test_high_risk_boundary_51_chars_valid(self):
        justification = "x" * 51
        assert validate_approval(RiskLevel.HIGH, justification=justification) is True


class TestApprovalActionDataclass:
    """Tests for the ApprovalAction dataclass."""

    def test_approval_action_is_frozen(self):
        action = ApprovalAction(
            action_type=ApprovalActionType.AUTO_APPROVE,
            requires_justification=False,
            min_justification_length=0,
        )
        with pytest.raises(Exception):
            action.action_type = ApprovalActionType.HUMAN_REVIEW

    def test_approval_action_equality(self):
        action1 = ApprovalAction(
            action_type=ApprovalActionType.AUTO_APPROVE,
            requires_justification=False,
            min_justification_length=0,
        )
        action2 = ApprovalAction(
            action_type=ApprovalActionType.AUTO_APPROVE,
            requires_justification=False,
            min_justification_length=0,
        )
        assert action1 == action2

    def test_different_actions_not_equal(self):
        action1 = get_approval_action(RiskLevel.LOW)
        action2 = get_approval_action(RiskLevel.HIGH)
        assert action1 != action2


class TestApprovalActionTypeEnum:
    """Tests for the ApprovalActionType enum."""

    def test_auto_approve_value(self):
        assert ApprovalActionType.AUTO_APPROVE == "AUTO_APPROVE"

    def test_human_review_value(self):
        assert ApprovalActionType.HUMAN_REVIEW == "HUMAN_REVIEW"

    def test_exception_handling_value(self):
        assert ApprovalActionType.EXCEPTION_HANDLING == "EXCEPTION_HANDLING"

    def test_enum_has_three_members(self):
        assert len(ApprovalActionType) == 3
