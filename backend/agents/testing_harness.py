"""Agent Testing Harness for individual agent invocation via InvokeAgentRuntime.

Provides a testing framework to invoke each agent individually using SigV4-signed
HTTP requests to the Bedrock AgentCore Runtime API. Validates that each agent
returns a response conforming to its defined output schema within 30 seconds.

Requirements: 12.1, 12.2, 12.4
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from shared.sigv4_client import (
    AgentCoreConfig,
    AgentCoreResponse,
    SigV4Client,
    collect_streaming_response,
    invoke_agent_runtime,
)

logger = logging.getLogger(__name__)

# Maximum allowed response time per agent (seconds)
AGENT_TIMEOUT_SECONDS = 30


# ---------------------------------------------------------------------------
# Expected response schemas per agent
# ---------------------------------------------------------------------------

COMPETITIVE_INTELLIGENCE_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "avgCompetitorPrice",
        "priceIndex",
        "positioning",
        "channelAnalysis",
        "sentimentIndicators",
    ],
    "properties": {
        "avgCompetitorPrice": {"type": "number"},
        "priceIndex": {"type": "number"},
        "positioning": {
            "type": "string",
            "enum": ["price_leader", "competitive", "premium"],
        },
        "channelAnalysis": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["channel", "avgPrice"],
            },
        },
        "sentimentIndicators": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["indicator", "value"],
            },
        },
        "competitorCount": {"type": "integer"},
        "dataSource": {"type": "string"},
        "marketGrowthRate": {"type": "number"},
        "priceVolatility": {"type": "number"},
    },
}


DEMAND_FORECASTING_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "forecastedDemand",
        "elasticity",
        "seasonalityFactor",
        "inventoryStatus",
        "trendDirection",
    ],
    "properties": {
        "forecastedDemand": {"type": "number", "minimum": 0},
        "elasticity": {"type": "number"},
        "seasonalityFactor": {"type": "number", "minimum": 0},
        "inventoryStatus": {
            "type": "string",
            "enum": ["healthy", "low", "critical"],
        },
        "trendDirection": {
            "type": "string",
            "enum": ["increasing", "stable", "decreasing"],
        },
    },
}

MARKET_INTELLIGENCE_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "trendScore",
        "sentimentScore",
        "macroOutlook",
        "opportunityIndicators",
        "marketMomentum",
    ],
    "properties": {
        "trendScore": {"type": "number", "minimum": -1.0, "maximum": 1.0},
        "sentimentScore": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "macroOutlook": {
            "type": "string",
            "enum": ["bullish", "neutral", "bearish"],
        },
        "opportunityIndicators": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "description", "confidence"],
            },
        },
        "marketMomentum": {
            "type": "string",
            "enum": ["accelerating", "stable", "decelerating"],
        },
    },
}


STRATEGY_SYNTHESIS_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["ranked_scenarios", "synthesis_metadata"],
    "properties": {
        "ranked_scenarios": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "scenarioId",
                    "cycleId",
                    "rank",
                    "confidenceScore",
                    "statusLabel",
                    "riskLevel",
                    "priceChanges",
                    "projectedRevenue",
                    "projectedMargin",
                    "compositeScore",
                    "competitiveFactors",
                    "demandFactors",
                    "marketFactors",
                ],
            },
            "minItems": 50,
            "maxItems": 200,
        },
        "synthesis_metadata": {
            "type": "object",
            "required": ["cycle_id", "total_generated", "total_valid"],
        },
        "shortfall_notification": {"type": "object"},
    },
}

IMPLEMENTATION_MONITORING_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["scenario_id", "timestamp"],
    "properties": {
        "scenario_id": {"type": "string"},
        "timestamp": {"type": "string"},
        "total_updates": {"type": "integer"},
        "successful": {"type": "integer"},
        "failed": {"type": "integer"},
        "details": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["productId", "status"],
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Sample request payloads per agent
# ---------------------------------------------------------------------------

COMPETITIVE_INTELLIGENCE_SAMPLE_PAYLOAD: dict[str, Any] = {
    "inputText": (
        "Analyze the competitive pricing landscape for product 'PROD-001' "
        "in the 'Electronics' category. Gather competitor prices, price "
        "history, and market position data. Return structured competitive "
        "factors in JSON format."
    ),
    "enableTrace": False,
}

DEMAND_FORECASTING_SAMPLE_PAYLOAD: dict[str, Any] = {
    "inputText": (
        "Forecast demand for product 'PROD-001' in the 'Electronics' "
        "category. Analyze sales history, POS real-time data, inventory "
        "levels, and price elasticity. Return structured demand factors "
        "in JSON format including forecastedDemand, elasticity, "
        "seasonalityFactor, inventoryStatus, and trendDirection."
    ),
    "enableTrace": False,
}

MARKET_INTELLIGENCE_SAMPLE_PAYLOAD: dict[str, Any] = {
    "inputText": (
        "Analyze market conditions for the 'Electronics' category. "
        "Examine market trends, consumer sentiment, and macroeconomic "
        "indicators. Return structured market factors in JSON format "
        "including trendScore, sentimentScore, macroOutlook, "
        "opportunityIndicators, and marketMomentum."
    ),
    "enableTrace": False,
}


STRATEGY_SYNTHESIS_SAMPLE_PAYLOAD: dict[str, Any] = {
    "inputText": (
        "Synthesize pricing strategies for pricing cycle 'CYCLE-001'. "
        "Combine the following intelligence inputs:\n"
        "Competitive: avg competitor price $99.99, price index 102, "
        "positioning competitive, 5 competitors analyzed.\n"
        "Demand: forecasted demand 1200 units, elasticity -1.5, "
        "seasonality factor 1.1, inventory healthy, trend increasing.\n"
        "Market: trend score 0.6, sentiment 0.72, macro outlook bullish, "
        "momentum accelerating.\n"
        "Generate 50-200 pricing scenarios, apply guardrails, rank by "
        "composite business impact, and classify risk levels."
    ),
    "enableTrace": False,
}

IMPLEMENTATION_MONITORING_SAMPLE_PAYLOAD: dict[str, Any] = {
    "inputText": (
        "Execute price update for approved scenario 'SCN-001'. "
        "Update product 'PROD-001' from $99.99 to $104.99 (5% increase). "
        "Track KPIs: projected revenue $125,000, projected margin 22%, "
        "projected conversion rate 3.5%. Monitor for variance against "
        "thresholds (10% revenue, 3pp margin)."
    ),
    "enableTrace": False,
}


# ---------------------------------------------------------------------------
# Agent test configuration
# ---------------------------------------------------------------------------


@dataclass
class AgentTestConfig:
    """Configuration for testing an individual agent.

    Attributes:
        agent_name: Human-readable name of the agent.
        agent_id: The AgentCore agent ID (set via environment or config).
        sample_payload: Sample request payload for the agent.
        response_schema: Expected JSON schema for the agent's response.
        timeout_seconds: Maximum allowed response time.
        description: Brief description of what the agent does.
    """

    agent_name: str
    agent_id: str
    sample_payload: dict[str, Any]
    response_schema: dict[str, Any]
    timeout_seconds: float = AGENT_TIMEOUT_SECONDS
    description: str = ""


AGENT_TEST_CONFIGS: list[AgentTestConfig] = [
    AgentTestConfig(
        agent_name="Competitive Intelligence",
        agent_id="competitive-intelligence-agent",
        sample_payload=COMPETITIVE_INTELLIGENCE_SAMPLE_PAYLOAD,
        response_schema=COMPETITIVE_INTELLIGENCE_RESPONSE_SCHEMA,
        description=(
            "Collects and analyzes real-time competitor pricing data, "
            "channel-level analysis, and sentiment detection."
        ),
    ),
    AgentTestConfig(
        agent_name="Demand Forecasting",
        agent_id="demand-forecasting-agent",
        sample_payload=DEMAND_FORECASTING_SAMPLE_PAYLOAD,
        response_schema=DEMAND_FORECASTING_RESPONSE_SCHEMA,
        description=(
            "Analyzes ERP sales history, POS real-time data, inventory "
            "levels, and price elasticity by customer segment."
        ),
    ),
    AgentTestConfig(
        agent_name="Market Intelligence",
        agent_id="market-intelligence-agent",
        sample_payload=MARKET_INTELLIGENCE_SAMPLE_PAYLOAD,
        response_schema=MARKET_INTELLIGENCE_RESPONSE_SCHEMA,
        description=(
            "Performs cross-product analysis, market structure insights, "
            "and opportunity detection using market signals."
        ),
    ),
    AgentTestConfig(
        agent_name="Strategy Synthesis",
        agent_id="strategy-synthesis-agent",
        sample_payload=STRATEGY_SYNTHESIS_SAMPLE_PAYLOAD,
        response_schema=STRATEGY_SYNTHESIS_RESPONSE_SCHEMA,
        description=(
            "Combines intelligence outputs, applies guardrails, generates "
            "50-200 ranked pricing scenarios with confidence scores."
        ),
    ),
    AgentTestConfig(
        agent_name="Implementation Monitoring",
        agent_id="implementation-monitoring-agent",
        sample_payload=IMPLEMENTATION_MONITORING_SAMPLE_PAYLOAD,
        response_schema=IMPLEMENTATION_MONITORING_RESPONSE_SCHEMA,
        description=(
            "Executes price updates, tracks post-implementation KPIs, "
            "detects variances, and triggers closed-loop feedback."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def validate_response_schema(
    response_data: dict[str, Any],
    schema: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Validate a response dictionary against an expected JSON schema.

    Performs lightweight schema validation checking:
    - Required fields are present
    - Field types match expected types
    - Enum values are valid
    - Array items have required fields
    - Numeric bounds are respected

    Args:
        response_data: The parsed response to validate.
        schema: The expected JSON schema definition.

    Returns:
        Tuple of (is_valid, list_of_errors). Empty error list means valid.
    """
    errors: list[str] = []

    if not isinstance(response_data, dict):
        errors.append(f"Expected object, got {type(response_data).__name__}")
        return False, errors

    # Check required fields
    required_fields = schema.get("required", [])
    for field_name in required_fields:
        if field_name not in response_data:
            errors.append(f"Missing required field: '{field_name}'")

    # Check property types and constraints
    properties = schema.get("properties", {})
    for field_name, field_schema in properties.items():
        if field_name not in response_data:
            continue

        value = response_data[field_name]
        field_type = field_schema.get("type")

        # Type checking
        if not _check_type(value, field_type):
            errors.append(
                f"Field '{field_name}': expected type '{field_type}', "
                f"got '{type(value).__name__}'"
            )
            continue

        # Enum validation
        if "enum" in field_schema and value not in field_schema["enum"]:
            errors.append(
                f"Field '{field_name}': value '{value}' not in "
                f"allowed values {field_schema['enum']}"
            )

        # Numeric bounds
        if field_type == "number" or field_type == "integer":
            if "minimum" in field_schema and value < field_schema["minimum"]:
                errors.append(
                    f"Field '{field_name}': value {value} below "
                    f"minimum {field_schema['minimum']}"
                )
            if "maximum" in field_schema and value > field_schema["maximum"]:
                errors.append(
                    f"Field '{field_name}': value {value} above "
                    f"maximum {field_schema['maximum']}"
                )

        # Array item validation
        if field_type == "array" and isinstance(value, list):
            items_schema = field_schema.get("items", {})
            item_required = items_schema.get("required", [])
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    for req_field in item_required:
                        if req_field not in item:
                            errors.append(
                                f"Field '{field_name}[{i}]': missing "
                                f"required field '{req_field}'"
                            )

    return len(errors) == 0, errors


def _check_type(value: Any, expected_type: str | None) -> bool:
    """Check if a value matches the expected JSON schema type.

    Args:
        value: The value to check.
        expected_type: The expected JSON schema type string.

    Returns:
        True if the value matches the expected type.
    """
    if expected_type is None:
        return True

    type_map = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    expected_python_type = type_map.get(expected_type)
    if expected_python_type is None:
        return True

    return isinstance(value, expected_python_type)


# ---------------------------------------------------------------------------
# Test result data model
# ---------------------------------------------------------------------------


@dataclass
class AgentTestResult:
    """Result of testing an individual agent invocation.

    Attributes:
        agent_name: Name of the agent tested.
        agent_id: AgentCore agent ID.
        passed: Whether the test passed.
        response_time_seconds: Time taken to receive the response.
        timeout_exceeded: Whether the 30-second timeout was exceeded.
        schema_valid: Whether the response conformed to the expected schema.
        schema_errors: List of schema validation errors (if any).
        error_message: Error message if the invocation failed.
        raw_response: The raw response data (for debugging).
    """

    agent_name: str
    agent_id: str
    passed: bool = False
    response_time_seconds: float = 0.0
    timeout_exceeded: bool = False
    schema_valid: bool = False
    schema_errors: list[str] = field(default_factory=list)
    error_message: str | None = None
    raw_response: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for reporting."""
        return {
            "agent_name": self.agent_name,
            "agent_id": self.agent_id,
            "passed": self.passed,
            "response_time_seconds": round(self.response_time_seconds, 3),
            "timeout_exceeded": self.timeout_exceeded,
            "schema_valid": self.schema_valid,
            "schema_errors": self.schema_errors,
            "error_message": self.error_message,
        }


# ---------------------------------------------------------------------------
# Core testing functions
# ---------------------------------------------------------------------------


def invoke_agent_and_validate(
    config: AgentTestConfig,
    session_id: str = "test-session-001",
    agentcore_config: AgentCoreConfig | None = None,
    client: SigV4Client | None = None,
) -> AgentTestResult:
    """Invoke a single agent and validate its response.

    Sends the sample payload to the agent via InvokeAgentRuntime (SigV4),
    measures response time, and validates the response against the expected
    schema. Reports pass/fail with details on any failures.

    Args:
        config: The agent test configuration with payload and schema.
        session_id: Session ID for the agent invocation.
        agentcore_config: Optional AgentCore configuration override.
        client: Optional pre-configured SigV4Client.

    Returns:
        AgentTestResult with pass/fail status and details.
    """
    result = AgentTestResult(
        agent_name=config.agent_name,
        agent_id=config.agent_id,
    )

    # Configure timeout for 30 seconds
    if agentcore_config is None:
        agentcore_config = AgentCoreConfig(
            read_timeout=config.timeout_seconds + 5,
        )

    start_time = time.time()

    try:
        # Invoke the agent via SigV4-signed request
        response = invoke_agent_runtime(
            agent_id=config.agent_id,
            session_id=session_id,
            input_text=config.sample_payload["inputText"],
            config=agentcore_config,
            client=client,
            enable_trace=config.sample_payload.get("enableTrace", False),
        )

        elapsed = time.time() - start_time
        result.response_time_seconds = elapsed

        # Check timeout
        if elapsed > config.timeout_seconds:
            result.timeout_exceeded = True
            result.error_message = (
                f"Agent '{config.agent_name}' exceeded {config.timeout_seconds}s "
                f"timeout (took {elapsed:.2f}s)"
            )
            return result

        # Check for invocation errors
        if not response.is_success:
            result.error_message = (
                f"Agent '{config.agent_name}' invocation failed: "
                f"{response.error or f'HTTP {response.status_code}'}"
            )
            return result

        # Collect streaming response
        collected = collect_streaming_response(response)
        result.raw_response = collected

        # Parse the agent output as JSON
        output_text = collected.get("output", "")
        response_data = _extract_json_from_response(output_text)

        if response_data is None:
            result.error_message = (
                f"Agent '{config.agent_name}' did not return valid JSON. "
                f"Raw output: {output_text[:200]}"
            )
            return result

        # Validate against expected schema
        is_valid, errors = validate_response_schema(
            response_data, config.response_schema
        )
        result.schema_valid = is_valid
        result.schema_errors = errors

        if not is_valid:
            result.error_message = (
                f"Agent '{config.agent_name}' response failed schema "
                f"validation: {'; '.join(errors[:5])}"
            )
            return result

        # All checks passed
        result.passed = True
        return result

    except Exception as e:
        elapsed = time.time() - start_time
        result.response_time_seconds = elapsed
        result.error_message = (
            f"Agent '{config.agent_name}' invocation raised exception: {e}"
        )
        return result


def _extract_json_from_response(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from agent response text.

    Agents may return JSON embedded in natural language text. This function
    attempts to find and parse the JSON object from the response.

    Args:
        text: The raw text output from the agent.

    Returns:
        Parsed JSON dictionary, or None if no valid JSON found.
    """
    # Try parsing the entire text as JSON first
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to find JSON object within the text
    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start >= 0 and json_end > json_start:
        try:
            return json.loads(text[json_start:json_end])
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def run_all_agent_tests(
    session_id: str = "test-session-001",
    agentcore_config: AgentCoreConfig | None = None,
    client: SigV4Client | None = None,
    agent_ids: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run tests for all configured agents and produce a summary report.

    Invokes each agent individually, validates responses, and produces
    a consolidated pass/fail report.

    Args:
        session_id: Session ID for agent invocations.
        agentcore_config: Optional AgentCore configuration override.
        client: Optional pre-configured SigV4Client.
        agent_ids: Optional mapping of agent_name -> agent_id to override
            the default agent IDs in AGENT_TEST_CONFIGS.

    Returns:
        Dictionary with 'results' (list of AgentTestResult dicts),
        'summary' with pass/fail counts, and 'all_passed' boolean.
    """
    results: list[AgentTestResult] = []

    for config in AGENT_TEST_CONFIGS:
        # Override agent_id if provided
        if agent_ids and config.agent_name in agent_ids:
            config = AgentTestConfig(
                agent_name=config.agent_name,
                agent_id=agent_ids[config.agent_name],
                sample_payload=config.sample_payload,
                response_schema=config.response_schema,
                timeout_seconds=config.timeout_seconds,
                description=config.description,
            )

        logger.info("Testing agent: %s (%s)", config.agent_name, config.agent_id)
        result = invoke_agent_and_validate(
            config=config,
            session_id=session_id,
            agentcore_config=agentcore_config,
            client=client,
        )
        results.append(result)

        status = "PASS" if result.passed else "FAIL"
        logger.info(
            "  %s - %s (%.2fs)%s",
            status,
            config.agent_name,
            result.response_time_seconds,
            f" - {result.error_message}" if result.error_message else "",
        )

    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count

    return {
        "results": [r.to_dict() for r in results],
        "summary": {
            "total": len(results),
            "passed": passed_count,
            "failed": failed_count,
        },
        "all_passed": failed_count == 0,
    }


def run_single_agent_test(
    agent_name: str,
    session_id: str = "test-session-001",
    agent_id: str | None = None,
    agentcore_config: AgentCoreConfig | None = None,
    client: SigV4Client | None = None,
) -> AgentTestResult:
    """Run a test for a single agent by name.

    Convenience function to test one specific agent without running
    the full test suite.

    Args:
        agent_name: Name of the agent to test (must match a config name).
        session_id: Session ID for the agent invocation.
        agent_id: Optional override for the agent ID.
        agentcore_config: Optional AgentCore configuration override.
        client: Optional pre-configured SigV4Client.

    Returns:
        AgentTestResult for the specified agent.

    Raises:
        ValueError: If agent_name does not match any configured agent.
    """
    config = None
    for cfg in AGENT_TEST_CONFIGS:
        if cfg.agent_name == agent_name:
            config = cfg
            break

    if config is None:
        available = [c.agent_name for c in AGENT_TEST_CONFIGS]
        raise ValueError(
            f"Unknown agent '{agent_name}'. "
            f"Available agents: {available}"
        )

    if agent_id:
        config = AgentTestConfig(
            agent_name=config.agent_name,
            agent_id=agent_id,
            sample_payload=config.sample_payload,
            response_schema=config.response_schema,
            timeout_seconds=config.timeout_seconds,
            description=config.description,
        )

    return invoke_agent_and_validate(
        config=config,
        session_id=session_id,
        agentcore_config=agentcore_config,
        client=client,
    )


def print_test_report(report: dict[str, Any]) -> None:
    """Print a formatted test report to stdout.

    Args:
        report: The report dictionary from run_all_agent_tests().
    """
    print("\n" + "=" * 70)
    print("AGENT TESTING HARNESS - INDIVIDUAL INVOCATION RESULTS")
    print("=" * 70)

    for result in report["results"]:
        status = "✓ PASS" if result["passed"] else "✗ FAIL"
        print(f"\n  {status}  {result['agent_name']}")
        print(f"         Agent ID: {result['agent_id']}")
        print(f"         Response Time: {result['response_time_seconds']:.3f}s")

        if result["timeout_exceeded"]:
            print("         ⚠ TIMEOUT EXCEEDED (30s limit)")

        if result["schema_errors"]:
            print("         Schema Errors:")
            for err in result["schema_errors"][:5]:
                print(f"           - {err}")

        if result["error_message"]:
            print(f"         Error: {result['error_message']}")

    summary = report["summary"]
    print("\n" + "-" * 70)
    print(
        f"  SUMMARY: {summary['passed']}/{summary['total']} passed, "
        f"{summary['failed']} failed"
    )
    all_passed = "ALL TESTS PASSED" if report["all_passed"] else "SOME TESTS FAILED"
    print(f"  STATUS: {all_passed}")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Parse optional arguments
    agent_name = None
    if len(sys.argv) > 1:
        agent_name = sys.argv[1]

    if agent_name:
        print(f"Testing single agent: {agent_name}")
        result = run_single_agent_test(agent_name=agent_name)
        report = {
            "results": [result.to_dict()],
            "summary": {"total": 1, "passed": 1 if result.passed else 0, "failed": 0 if result.passed else 1},
            "all_passed": result.passed,
        }
    else:
        print("Testing all agents...")
        report = run_all_agent_tests()

    print_test_report(report)
    sys.exit(0 if report["all_passed"] else 1)
