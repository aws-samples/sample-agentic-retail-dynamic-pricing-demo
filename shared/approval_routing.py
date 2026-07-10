"""Approval routing logic for risk-based pricing scenario workflow.

Routes pricing scenarios to the appropriate approval path based on risk level:
- LOW risk: Auto-approved within 30 seconds
- MEDIUM risk: Routed to Product Manager for human review
- HIGH risk: Routed as exception requiring ≥50 character justification

These are pure functions with no side effects.

Validates: Requirements 7.1, 7.2, 7.3
"""

from dataclasses import dataclass
from enum import Enum

from shared.models.pricing_scenario import RiskLevel


class ApprovalActionType(str, Enum):
    """The type of approval action to take for a pricing scenario."""

    AUTO_APPROVE = "AUTO_APPROVE"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    EXCEPTION_HANDLING = "EXCEPTION_HANDLING"


@dataclass(frozen=True)
class ApprovalAction:
    """Describes the approval routing action for a pricing scenario.

    Attributes:
        action_type: The type of approval action (auto-approve, human review, or exception).
        requires_justification: Whether a written justification is required before approval.
        min_justification_length: Minimum character length for the justification (0 if not required).
    """

    action_type: ApprovalActionType
    requires_justification: bool
    min_justification_length: int


def get_approval_action(risk_level: RiskLevel) -> ApprovalAction:
    """Determine the approval routing action based on risk level.

    Args:
        risk_level: The risk classification of the pricing scenario.

    Returns:
        An ApprovalAction describing how the scenario should be routed.

    Routing rules:
        - LOW risk: Auto-approve (no justification needed)
        - MEDIUM risk: Route to Product Manager for human review (no justification needed)
        - HIGH risk: Route as exception (requires justification of ≥50 characters)
    """
    if risk_level == RiskLevel.LOW:
        return ApprovalAction(
            action_type=ApprovalActionType.AUTO_APPROVE,
            requires_justification=False,
            min_justification_length=0,
        )
    elif risk_level == RiskLevel.MEDIUM:
        return ApprovalAction(
            action_type=ApprovalActionType.HUMAN_REVIEW,
            requires_justification=False,
            min_justification_length=0,
        )
    else:  # HIGH
        return ApprovalAction(
            action_type=ApprovalActionType.EXCEPTION_HANDLING,
            requires_justification=True,
            min_justification_length=50,
        )


def validate_approval(risk_level: RiskLevel, justification: str | None = None) -> bool:
    """Validate whether an approval submission meets the requirements for the given risk level.

    Args:
        risk_level: The risk classification of the pricing scenario.
        justification: The written justification provided by the approver (if any).

    Returns:
        True if the approval meets all requirements, False otherwise.

    Validation rules:
        - LOW risk: Always valid (auto-approved, no justification needed)
        - MEDIUM risk: Always valid (human review, no justification needed)
        - HIGH risk: Valid only if justification is provided and is ≥50 characters
    """
    action = get_approval_action(risk_level)

    if not action.requires_justification:
        return True

    if justification is None:
        return False

    return len(justification) >= action.min_justification_length
