"""Session management and data isolation for AgentCore Pricing Cycles.

This module manages AgentCore sessions scoped to the Pricing_Group level,
enforces data isolation between concurrent sessions, and configures both
short-term memory (24h TTL) and long-term memory (100 cycles) via
Amazon Bedrock AgentCore Memory service.

Session Scope: Pricing_Group (product family | sub-category | category)
├── Short-term Memory (24h TTL)
│   ├── Agent intermediate outputs
│   ├── Request parameters
│   └── Inter-agent messages
└── Long-term Memory (100 cycles)
    ├── Selected scenarios + outcomes
    ├── Revenue/margin results
    └── Approval decisions

Requirements: 1.9, 1.10, 10.1, 10.2, 10.4
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from shared.sigv4_client import AgentCoreConfig, AgentCoreResponse, SigV4Client

logger = logging.getLogger(__name__)

# Memory configuration constants
SHORT_TERM_TTL_HOURS = 24
LONG_TERM_MAX_CYCLES = 100

# AgentCore Memory API paths
MEMORY_BASE_PATH = "/memory"
SESSIONS_BASE_PATH = "/sessions"


@dataclass
class SessionConfig:
    """Configuration for an AgentCore session.

    Attributes:
        region: AWS region for AgentCore.
        memory_store_id: The AgentCore Memory store identifier.
        short_term_ttl_hours: TTL for short-term memory entries (default 24h).
        long_term_max_cycles: Maximum number of cycles retained in long-term memory.
    """

    region: str = "us-east-1"
    memory_store_id: str = "retail-dynamic-pricing-memory"
    short_term_ttl_hours: int = SHORT_TERM_TTL_HOURS
    long_term_max_cycles: int = LONG_TERM_MAX_CYCLES


@dataclass
class SessionContext:
    """Represents an active AgentCore session scoped to a Pricing Group.

    Each session provides an isolated namespace for a single pricing cycle,
    ensuring no data leakage between concurrent sessions.

    Attributes:
        session_id: Unique session identifier (UUID).
        pricing_group: The Pricing Group this session is scoped to.
        pricing_group_type: Type of grouping (PRODUCT_FAMILY, SUB_CATEGORY, CATEGORY).
        namespace: Derived namespace for data isolation (pricing_group_type/pricing_group).
        created_at: ISO 8601 timestamp of session creation.
        is_active: Whether the session is currently active.
        metadata: Additional session metadata.
    """

    session_id: str
    pricing_group: str
    pricing_group_type: str
    namespace: str
    created_at: str
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """Manages AgentCore sessions with data isolation and memory configuration.

    Provides session lifecycle management (create, get, close) and memory
    operations (short-term and long-term) scoped to Pricing Group level.

    Each session operates in an isolated namespace derived from the Pricing Group,
    ensuring that concurrent pricing cycles cannot access each other's data.
    """

    def __init__(
        self,
        config: SessionConfig | None = None,
        sigv4_client: SigV4Client | None = None,
    ) -> None:
        """Initialize the SessionManager.

        Args:
            config: Session configuration. Uses defaults if None.
            sigv4_client: Pre-configured SigV4 client for AgentCore API calls.
                Creates one if None.
        """
        self._config = config or SessionConfig()
        self._agentcore_config = AgentCoreConfig(region=self._config.region)
        self._client = sigv4_client or SigV4Client(config=self._agentcore_config)
        self._active_sessions: dict[str, SessionContext] = {}

    # -----------------------------------------------------------------------
    # Session Lifecycle
    # -----------------------------------------------------------------------

    def create_session(
        self,
        pricing_group: str,
        pricing_group_type: str = "CATEGORY",
        metadata: dict[str, Any] | None = None,
    ) -> SessionContext:
        """Create a new AgentCore session scoped to a Pricing Group.

        Each session gets a unique ID and an isolated namespace derived from
        the pricing group, ensuring data isolation between concurrent sessions.

        Args:
            pricing_group: The Pricing Group name (product family, sub-category,
                or category).
            pricing_group_type: Type of grouping. One of PRODUCT_FAMILY,
                SUB_CATEGORY, or CATEGORY.
            metadata: Optional additional metadata to attach to the session.

        Returns:
            SessionContext representing the newly created session.

        Raises:
            ValueError: If pricing_group is empty or pricing_group_type is invalid.
        """
        if not pricing_group or not pricing_group.strip():
            raise ValueError("pricing_group must be a non-empty string")

        valid_types = {"PRODUCT_FAMILY", "SUB_CATEGORY", "CATEGORY"}
        if pricing_group_type not in valid_types:
            raise ValueError(
                f"pricing_group_type must be one of {valid_types}, "
                f"got '{pricing_group_type}'"
            )

        session_id = str(uuid.uuid4())
        namespace = self._build_namespace(pricing_group, pricing_group_type)
        created_at = datetime.now(timezone.utc).isoformat()

        session = SessionContext(
            session_id=session_id,
            pricing_group=pricing_group,
            pricing_group_type=pricing_group_type,
            namespace=namespace,
            created_at=created_at,
            is_active=True,
            metadata=metadata or {},
        )

        # Register the session in AgentCore via API
        self._register_session_in_agentcore(session)

        # Track locally
        self._active_sessions[session_id] = session

        logger.info(
            "Created session %s for pricing group '%s' (type: %s, namespace: %s)",
            session_id,
            pricing_group,
            pricing_group_type,
            namespace,
        )

        return session

    def get_session(self, session_id: str) -> SessionContext | None:
        """Retrieve an active session by its ID.

        Args:
            session_id: The unique session identifier.

        Returns:
            SessionContext if the session exists and is active, None otherwise.
        """
        session = self._active_sessions.get(session_id)
        if session and session.is_active:
            return session
        return None

    def close_session(self, session_id: str) -> bool:
        """Close an active session and clean up resources.

        Marks the session as inactive and notifies AgentCore to release
        session resources. Short-term memory will be discarded based on TTL.

        Args:
            session_id: The unique session identifier to close.

        Returns:
            True if the session was successfully closed, False if not found.
        """
        session = self._active_sessions.get(session_id)
        if session is None:
            logger.warning("Attempted to close non-existent session %s", session_id)
            return False

        session.is_active = False

        # Notify AgentCore to release session resources
        self._deregister_session_in_agentcore(session)

        logger.info(
            "Closed session %s for pricing group '%s'",
            session_id,
            session.pricing_group,
        )

        return True

    # -----------------------------------------------------------------------
    # Short-Term Memory (24h TTL) — Requirements 10.1
    # -----------------------------------------------------------------------

    def store_short_term(
        self,
        session_id: str,
        key: str,
        data: dict[str, Any],
        data_type: str = "agent_output",
    ) -> bool:
        """Store data in short-term memory for the current session.

        Short-term memory is session-bound with a 24h TTL. It stores:
        - Agent intermediate outputs
        - Request parameters
        - Inter-agent messages

        Data is namespaced to the session to enforce isolation.

        Args:
            session_id: The session to store data in.
            key: A unique key for this data entry within the session.
            data: The data payload to store.
            data_type: Type of data (agent_output, request_params, inter_agent_message).

        Returns:
            True if stored successfully, False otherwise.

        Raises:
            ValueError: If the session is not active or not found.
        """
        session = self._get_active_session_or_raise(session_id)

        # Build the namespaced key for isolation
        namespaced_key = f"{session.namespace}/{session_id}/short_term/{key}"

        ttl_seconds = self._config.short_term_ttl_hours * 3600
        expiry_timestamp = int(time.time()) + ttl_seconds

        memory_entry = {
            "key": namespaced_key,
            "value": json.dumps(data),
            "metadata": {
                "session_id": session_id,
                "pricing_group": session.pricing_group,
                "data_type": data_type,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "ttl": expiry_timestamp,
                "integrity_hash": self._compute_integrity_hash(data),
            },
        }

        response = self._write_memory(memory_entry)

        if response.is_success:
            logger.debug(
                "Stored short-term data '%s' in session %s (TTL: %dh)",
                key,
                session_id,
                self._config.short_term_ttl_hours,
            )
            return True

        logger.error(
            "Failed to store short-term data '%s' in session %s: %s",
            key,
            session_id,
            response.error,
        )
        return False

    def retrieve_short_term(
        self,
        session_id: str,
        key: str,
    ) -> dict[str, Any] | None:
        """Retrieve data from short-term memory for the current session.

        Only retrieves data within the session's namespace, enforcing
        data isolation between concurrent sessions.

        Args:
            session_id: The session to retrieve data from.
            key: The key of the data entry to retrieve.

        Returns:
            The stored data payload, or None if not found or expired.

        Raises:
            ValueError: If the session is not active or not found.
        """
        session = self._get_active_session_or_raise(session_id)

        namespaced_key = f"{session.namespace}/{session_id}/short_term/{key}"

        response = self._read_memory(namespaced_key)

        if response.is_success and response.body:
            value = response.body.get("value")
            if value:
                try:
                    parsed_data = json.loads(value)

                    # [H5 FIX] Security: Validate memory integrity hash — FAIL CLOSED.
                    # If the stored hash does not match the computed hash, the data
                    # has been tampered with. Reject it entirely rather than using
                    # potentially poisoned data that could bias pricing recommendations.
                    metadata = response.body.get("metadata", {})
                    stored_hash = metadata.get("integrity_hash")
                    if stored_hash:
                        computed_hash = self._compute_integrity_hash(parsed_data)
                        if computed_hash != stored_hash:
                            logger.error(
                                "SECURITY: Memory integrity violation for key '%s' "
                                "in session %s. Stored hash does not match content. "
                                "Rejecting tampered data (fail-closed).",
                                key,
                                session_id,
                            )
                            return None

                    return parsed_data
                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to parse short-term data for key '%s' in session %s",
                        key,
                        session_id,
                    )
                    return None

        logger.debug(
            "Short-term data '%s' not found in session %s",
            key,
            session_id,
        )
        return None

    # -----------------------------------------------------------------------
    # Memory Integrity
    # -----------------------------------------------------------------------

    @staticmethod
    def _compute_integrity_hash(data: dict[str, Any]) -> str:
        """Compute SHA-256 hash of data payload for tamper detection.

        Uses canonical JSON serialization (sorted keys) to ensure
        consistent hashing regardless of dict ordering.

        Args:
            data: The data payload to hash.

        Returns:
            Hex-encoded SHA-256 hash string.
        """
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # -----------------------------------------------------------------------
    # Long-Term Memory (100 cycles) — Requirements 10.2, 10.4
    # -----------------------------------------------------------------------

    def store_long_term(
        self,
        session_id: str,
        cycle_id: str,
        data: dict[str, Any],
    ) -> bool:
        """Store historical pricing outcome in long-term memory.

        Long-term memory retains data from the most recent 100 completed
        pricing cycles. It stores:
        - Selected pricing scenarios and outcomes
        - Observed revenue and margin results
        - Approval decisions

        Long-term memory is queryable across sessions for historical learning.

        Args:
            session_id: The session that produced this outcome.
            cycle_id: The pricing cycle identifier.
            data: The outcome data to persist (scenario, metrics, approval).

        Returns:
            True if stored successfully, False otherwise.

        Raises:
            ValueError: If the session is not active or not found.
        """
        session = self._get_active_session_or_raise(session_id)

        # Long-term memory uses pricing_group namespace (not session-specific)
        # so it can be queried across sessions for the same product/category
        namespaced_key = (
            f"{session.namespace}/long_term/{cycle_id}"
        )

        memory_entry = {
            "key": namespaced_key,
            "value": json.dumps(data),
            "metadata": {
                "cycle_id": cycle_id,
                "session_id": session_id,
                "pricing_group": session.pricing_group,
                "pricing_group_type": session.pricing_group_type,
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "memory_type": "long_term",
            },
        }

        response = self._write_memory(memory_entry)

        if response.is_success:
            logger.info(
                "Stored long-term outcome for cycle %s in namespace '%s'",
                cycle_id,
                session.namespace,
            )
            # Enforce the 100-cycle retention limit
            self._enforce_long_term_retention(session.namespace)
            return True

        logger.error(
            "Failed to store long-term data for cycle %s: %s",
            cycle_id,
            response.error,
        )
        return False

    def retrieve_long_term(
        self,
        pricing_group: str,
        pricing_group_type: str = "CATEGORY",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve historical pricing outcomes from long-term memory.

        Queries long-term memory for past outcomes of the specified product
        or category. This is used by the Strategy Synthesis Agent to
        incorporate historical learning into new scenario generation.

        Args:
            pricing_group: The Pricing Group to query history for.
            pricing_group_type: Type of grouping.
            limit: Maximum number of historical entries to return.
                Defaults to LONG_TERM_MAX_CYCLES.

        Returns:
            List of historical outcome dictionaries, ordered by most recent first.
        """
        namespace = self._build_namespace(pricing_group, pricing_group_type)
        prefix = f"{namespace}/long_term/"
        effective_limit = limit or self._config.long_term_max_cycles

        response = self._query_memory(prefix=prefix, limit=effective_limit)

        if response.is_success and response.body:
            entries = response.body.get("entries", [])
            results = []
            for entry in entries:
                value = entry.get("value")
                if value:
                    try:
                        results.append(json.loads(value))
                    except json.JSONDecodeError:
                        logger.warning(
                            "Failed to parse long-term entry in namespace '%s'",
                            namespace,
                        )
            return results

        logger.debug(
            "No long-term history found for pricing group '%s'",
            pricing_group,
        )
        return []

    # -----------------------------------------------------------------------
    # Data Isolation Enforcement — Requirement 1.10
    # -----------------------------------------------------------------------

    def validate_isolation(self, session_id: str, key: str) -> bool:
        """Validate that a memory key belongs to the given session's namespace.

        Ensures that no cross-session data access is possible. Each session
        can only access data within its own namespace.

        Args:
            session_id: The session attempting the access.
            key: The memory key being accessed.

        Returns:
            True if the key belongs to the session's namespace, False otherwise.
        """
        session = self._active_sessions.get(session_id)
        if session is None:
            return False

        # Short-term keys must include the session_id
        if "/short_term/" in key:
            return f"{session.namespace}/{session_id}/short_term/" in key

        # Long-term keys must match the namespace
        if "/long_term/" in key:
            return key.startswith(f"{session.namespace}/long_term/")

        return False

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _build_namespace(self, pricing_group: str, pricing_group_type: str) -> str:
        """Build an isolated namespace from pricing group info.

        The namespace ensures data isolation by scoping all memory operations
        to a specific pricing group context.

        Args:
            pricing_group: The Pricing Group name.
            pricing_group_type: The type of grouping.

        Returns:
            Namespace string in format: pricing_group_type/pricing_group_sanitized
        """
        # Sanitize the pricing group name for use as a namespace component
        sanitized = pricing_group.strip().lower().replace(" ", "_").replace("/", "_")
        return f"{pricing_group_type.lower()}/{sanitized}"

    def _get_active_session_or_raise(self, session_id: str) -> SessionContext:
        """Get an active session or raise ValueError.

        Args:
            session_id: The session ID to look up.

        Returns:
            The active SessionContext.

        Raises:
            ValueError: If session not found or not active.
        """
        session = self._active_sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session '{session_id}' not found")
        if not session.is_active:
            raise ValueError(f"Session '{session_id}' is no longer active")
        return session

    def _register_session_in_agentcore(self, session: SessionContext) -> None:
        """Register a new session with AgentCore via API.

        Calls the AgentCore sessions API to create a session resource
        with the appropriate namespace and configuration.

        Args:
            session: The session context to register.
        """
        url = (
            f"{self._agentcore_config.base_url}"
            f"{SESSIONS_BASE_PATH}/{session.session_id}"
        )

        body = json.dumps({
            "sessionId": session.session_id,
            "namespace": session.namespace,
            "pricingGroup": session.pricing_group,
            "pricingGroupType": session.pricing_group_type,
            "createdAt": session.created_at,
            "memoryConfig": {
                "shortTermTtlHours": self._config.short_term_ttl_hours,
                "longTermMaxCycles": self._config.long_term_max_cycles,
                "memoryStoreId": self._config.memory_store_id,
            },
            "metadata": session.metadata,
        })

        response = self._client.request(
            method="PUT",
            url=url,
            headers={"Content-Type": "application/json"},
            body=body,
            service="bedrock",
        )

        if not response.is_success:
            logger.warning(
                "Failed to register session %s in AgentCore (status %d): %s. "
                "Session will operate with local tracking only.",
                session.session_id,
                response.status_code,
                response.error,
            )

    def _deregister_session_in_agentcore(self, session: SessionContext) -> None:
        """Deregister a session from AgentCore via API.

        Notifies AgentCore that the session is closed so resources can be
        released. Short-term memory will expire based on TTL.

        Args:
            session: The session context to deregister.
        """
        url = (
            f"{self._agentcore_config.base_url}"
            f"{SESSIONS_BASE_PATH}/{session.session_id}"
        )

        response = self._client.request(
            method="DELETE",
            url=url,
            service="bedrock",
        )

        if not response.is_success:
            logger.warning(
                "Failed to deregister session %s from AgentCore (status %d): %s",
                session.session_id,
                response.status_code,
                response.error,
            )

    def _write_memory(self, entry: dict[str, Any]) -> AgentCoreResponse:
        """Write a memory entry to AgentCore Memory service.

        Args:
            entry: The memory entry containing key, value, and metadata.

        Returns:
            AgentCoreResponse from the API call.
        """
        url = (
            f"{self._agentcore_config.base_url}"
            f"{MEMORY_BASE_PATH}/{self._config.memory_store_id}/entries"
        )

        body = json.dumps(entry)

        return self._client.request(
            method="POST",
            url=url,
            headers={"Content-Type": "application/json"},
            body=body,
            service="bedrock",
        )

    def _read_memory(self, key: str) -> AgentCoreResponse:
        """Read a memory entry from AgentCore Memory service.

        Args:
            key: The namespaced key to retrieve.

        Returns:
            AgentCoreResponse with the memory entry data.
        """
        url = (
            f"{self._agentcore_config.base_url}"
            f"{MEMORY_BASE_PATH}/{self._config.memory_store_id}/entries/{key}"
        )

        return self._client.request(
            method="GET",
            url=url,
            service="bedrock",
        )

    def _query_memory(
        self, prefix: str, limit: int = LONG_TERM_MAX_CYCLES
    ) -> AgentCoreResponse:
        """Query memory entries by prefix from AgentCore Memory service.

        Args:
            prefix: The key prefix to query (namespace-scoped).
            limit: Maximum number of entries to return.

        Returns:
            AgentCoreResponse with matching memory entries.
        """
        url = (
            f"{self._agentcore_config.base_url}"
            f"{MEMORY_BASE_PATH}/{self._config.memory_store_id}/query"
        )

        body = json.dumps({
            "prefix": prefix,
            "limit": limit,
            "sortOrder": "DESCENDING",
        })

        return self._client.request(
            method="POST",
            url=url,
            headers={"Content-Type": "application/json"},
            body=body,
            service="bedrock",
        )

    def _enforce_long_term_retention(self, namespace: str) -> None:
        """Enforce the 100-cycle retention limit for long-term memory.

        Queries all long-term entries for the namespace and removes the
        oldest entries if the count exceeds LONG_TERM_MAX_CYCLES.

        Args:
            namespace: The namespace to enforce retention on.
        """
        prefix = f"{namespace}/long_term/"
        # Query with a higher limit to check if we need to prune
        check_limit = self._config.long_term_max_cycles + 10

        response = self._query_memory(prefix=prefix, limit=check_limit)

        if not response.is_success or not response.body:
            return

        entries = response.body.get("entries", [])
        if len(entries) <= self._config.long_term_max_cycles:
            return

        # Remove oldest entries (entries are sorted descending, so tail is oldest)
        entries_to_remove = entries[self._config.long_term_max_cycles:]

        for entry in entries_to_remove:
            entry_key = entry.get("key")
            if entry_key:
                self._delete_memory(entry_key)

        logger.info(
            "Pruned %d old long-term entries from namespace '%s'",
            len(entries_to_remove),
            namespace,
        )

    def _delete_memory(self, key: str) -> AgentCoreResponse:
        """Delete a memory entry from AgentCore Memory service.

        Args:
            key: The namespaced key to delete.

        Returns:
            AgentCoreResponse from the API call.
        """
        url = (
            f"{self._agentcore_config.base_url}"
            f"{MEMORY_BASE_PATH}/{self._config.memory_store_id}/entries/{key}"
        )

        return self._client.request(
            method="DELETE",
            url=url,
            service="bedrock",
        )
