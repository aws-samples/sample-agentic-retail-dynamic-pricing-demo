"""Input sanitization for agent inputs and MCP server responses.

Scans text content for prompt injection patterns before passing data
to AI agents. Detects common adversarial prompt injection techniques
that attempt to override agent instructions.

This module provides defense-in-depth alongside Bedrock Guardrails
by catching injection attempts at the application layer before they
reach the model.

Set environment variable SKIP_INPUT_SANITIZATION=true to bypass
(for testing only).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# Environment variable to bypass sanitization (testing only)
_SKIP_SANITIZATION = os.environ.get("SKIP_INPUT_SANITIZATION", "").lower() == "true"

# Patterns indicating attempted prompt injection
_INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "instruction_override",
        re.compile(
            r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|context)",
            re.IGNORECASE,
        ),
    ),
    (
        "role_reassignment",
        re.compile(
            r"you\s+are\s+now\s+(a|an|the)\s+",
            re.IGNORECASE,
        ),
    ),
    (
        "system_prompt_injection",
        re.compile(
            r"<\s*system\s*>|<<\s*SYS\s*>>|\[INST\]|\[/INST\]",
            re.IGNORECASE,
        ),
    ),
    (
        "role_marker_injection",
        re.compile(
            r"^(system|human|assistant|user)\s*:\s*",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "instruction_injection",
        re.compile(
            r"(forget|disregard|override)\s+(everything|all|your)\s+(above|previous|instructions|rules)",
            re.IGNORECASE,
        ),
    ),
    (
        "jailbreak_attempt",
        re.compile(
            r"(DAN|do\s+anything\s+now|jailbreak|bypass\s+(safety|guardrail|filter))",
            re.IGNORECASE,
        ),
    ),
    (
        "prompt_leakage_attempt",
        re.compile(
            r"(repeat|print|show|reveal|output)\s+(your|the|system)\s+(prompt|instructions|rules)",
            re.IGNORECASE,
        ),
    ),
]


class PromptInjectionDetectedError(Exception):
    """Raised when a prompt injection pattern is detected in input data."""

    def __init__(self, pattern_name: str, context: str = "") -> None:
        self.pattern_name = pattern_name
        self.context = context
        super().__init__(
            f"Prompt injection detected (pattern: {pattern_name})"
            + (f" in context: {context}" if context else "")
        )


def sanitize_text(text: str, context: str = "") -> str:
    """Scan text for prompt injection patterns.

    Args:
        text: The text content to scan.
        context: Optional context identifier for logging (e.g., agent name).

    Returns:
        The original text if no injection detected.

    Raises:
        PromptInjectionDetectedError: If an injection pattern is found.
    """
    if _SKIP_SANITIZATION:
        return text

    for pattern_name, pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning(
                "Prompt injection detected (pattern: %s) in context: %s",
                pattern_name,
                context,
            )
            raise PromptInjectionDetectedError(
                pattern_name=pattern_name,
                context=context,
            )

    return text


def sanitize_dict(data: dict[str, Any], context: str = "") -> dict[str, Any]:
    """Recursively scan a dictionary for prompt injection patterns.

    Scans all string values in the dictionary (including nested dicts
    and lists) for injection patterns.

    Args:
        data: The dictionary to scan.
        context: Optional context identifier for logging.

    Returns:
        The original dictionary if no injection detected.

    Raises:
        PromptInjectionDetectedError: If an injection pattern is found.
    """
    if _SKIP_SANITIZATION:
        return data

    _scan_value(data, context)
    return data


def _scan_value(value: Any, context: str) -> None:
    """Recursively scan a value for injection patterns."""
    if isinstance(value, str):
        sanitize_text(value, context)
    elif isinstance(value, dict):
        for k, v in value.items():
            _scan_value(v, context)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _scan_value(item, context)


def sanitize_agent_output(data: dict[str, Any], agent_name: str) -> dict[str, Any]:
    """Sanitize an agent's output before passing to downstream agents.

    This is the primary entry point for the orchestrator to validate
    agent responses before feeding them into Strategy Synthesis or
    other downstream processing.

    Args:
        data: Parsed agent response data.
        agent_name: Name of the agent that produced this output.

    Returns:
        The original data if no injection detected.

    Raises:
        PromptInjectionDetectedError: If injection patterns are found.
    """
    return sanitize_dict(data, context=f"agent_output:{agent_name}")


def sanitize_mcp_response(data: dict[str, Any], server_name: str) -> dict[str, Any]:
    """Sanitize an MCP server response before agent consumption.

    Args:
        data: Parsed MCP server response data.
        server_name: Name of the MCP server that produced this response.

    Returns:
        The original data if no injection detected.

    Raises:
        PromptInjectionDetectedError: If injection patterns are found.
    """
    return sanitize_dict(data, context=f"mcp_response:{server_name}")
