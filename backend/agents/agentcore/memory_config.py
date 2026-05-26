"""Shared AgentCore Memory configuration for all agent runtimes.

Provides a factory function to create AgentCore Memory session managers
that enable persistent memory across agent invocations.

Environment Variables:
    AGENTCORE_MEMORY_ID: The memory resource ID created via setup_memory.py
    AWS_REGION: AWS region for the memory client (default: us-east-1)
"""

from __future__ import annotations

import logging
import os
import uuid

logger = logging.getLogger(__name__)

MEMORY_ID = os.environ.get("AGENTCORE_MEMORY_ID", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def create_session_manager(
    session_id: str | None = None,
    actor_id: str = "pricing-system",
):
    """Create an AgentCore Memory session manager for an agent.

    Args:
        session_id: Optional session ID for conversation continuity.
            If not provided, a new unique session ID is generated.
        actor_id: Identifier for the actor using memory (default: pricing-system).

    Returns:
        An AgentCoreMemorySessionManager instance, or None if memory is not configured.
    """
    if not MEMORY_ID:
        logger.debug("AGENTCORE_MEMORY_ID not set; memory disabled for this agent.")
        return None

    try:
        from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
        from bedrock_agentcore.memory.integrations.strands.session_manager import (
            AgentCoreMemorySessionManager,
        )
    except ImportError:
        logger.warning(
            "bedrock_agentcore.memory package not available; memory disabled."
        )
        return None

    config = AgentCoreMemoryConfig(
        memory_id=MEMORY_ID,
        session_id=session_id or f"session-{uuid.uuid4().hex}",
        actor_id=actor_id,
    )

    return AgentCoreMemorySessionManager(
        agentcore_memory_config=config,
        region_name=AWS_REGION,
    )
