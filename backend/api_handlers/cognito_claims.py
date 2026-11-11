"""Read the caller's identity from the API Gateway Cognito authorizer claims.

Shared by the API handler Lambdas (every handler is packaged from this
directory, so a plain ``import cognito_claims`` works in Lambda).
"""

from __future__ import annotations

import re
from typing import Any

# cognito:groups arrives as a list, "Operations", "Operations,PricingAnalysts"
# or "[Operations, PricingAnalysts]", depending on the authorizer type.
_GROUP_SEPARATORS = re.compile(r"[\s,]+")


def get_claims(event: dict[str, Any]) -> dict[str, Any]:
    """Return the Cognito claims of the request, or {} if there are none."""
    authorizer = (event.get("requestContext") or {}).get("authorizer") or {}
    claims = authorizer.get("claims") or {}
    return claims if isinstance(claims, dict) else {}


def get_caller_sub(event: dict[str, Any]) -> str:
    """Return the Cognito-verified user ID (``sub``) of the caller, or ''."""
    sub = get_claims(event).get("sub", "")
    return sub if isinstance(sub, str) else ""


def get_groups(event: dict[str, Any]) -> set[str]:
    """Return the caller's Cognito group names as a set of exact names."""
    raw = get_claims(event).get("cognito:groups", "")
    if isinstance(raw, (list, tuple, set)):
        return {str(g).strip() for g in raw if str(g).strip()}
    if not isinstance(raw, str):
        return set()
    return {g for g in _GROUP_SEPARATORS.split(raw.strip().strip("[]")) if g}


def is_in_group(event: dict[str, Any], group: str) -> bool:
    """True only if the caller is in exactly this group (no substring matches)."""
    return group in get_groups(event)
