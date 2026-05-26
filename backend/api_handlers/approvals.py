"""Lambda handler for approval workflow endpoints.

Handles:
- POST /approvals: Approve, reject, or request modifications to a scenario
"""

import json
import logging
import os
from typing import Any

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

logger = logging.getLogger()
logger.setLevel(logging.INFO)

APPROVALS_TABLE = os.environ.get("APPROVALS_TABLE", "Approvals")
PRICING_SCENARIOS_TABLE = os.environ.get("PRICING_SCENARIOS_TABLE", "PricingScenarios")
PRODUCTS_TABLE = os.environ.get("PRODUCTS_TABLE", "Products")
AGENTCORE_ENDPOINT = os.environ.get("AGENTCORE_ENDPOINT", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def _sign_request(method: str, url: str, body: str = "") -> dict[str, str]:
    """Sign an HTTP request with SigV4 for AgentCore invocations.

    Returns headers dict containing the Authorization and other SigV4 headers.
    """
    session = boto3.Session()
    credentials = session.get_credentials().get_frozen_credentials()

    request = AWSRequest(method=method, url=url, data=body)
    request.headers["Content-Type"] = "application/json"

    SigV4Auth(credentials, "bedrock", AWS_REGION).add_auth(request)
    return dict(request.headers)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for approval workflow endpoints."""
    http_method = event.get("httpMethod", "")
    path = event.get("path", "")

    logger.info("Approvals handler: %s %s", http_method, path)

    try:
        if http_method == "POST" and path == "/approvals":
            return _process_approval(event)
        else:
            return _response(404, {"error": "Not found"})
    except Exception as e:
        logger.exception("Error handling request")
        return _response(500, {"error": str(e)})


def _process_approval(event: dict[str, Any]) -> dict[str, Any]:
    """Handle POST /approvals - process approval/rejection of a scenario."""
    body = json.loads(event.get("body", "{}"))

    scenario_id = body.get("scenarioId", "")
    action = body.get("action", "")  # APPROVED, REJECTED
    comment = body.get("comment", "")
    risk_level = body.get("riskLevel", "")

    # Validate HIGH risk requires >= 50 character justification
    if risk_level == "HIGH" and action == "APPROVED" and len(comment) < 50:
        return _response(400, {
            "error": "High risk approvals require a justification of at least 50 characters",
        })

    # TODO: Write approval record to Approvals table
    # TODO: Update scenario approvalStatus in PricingScenarios table
    # TODO: On approval, trigger Implementation Monitoring Agent via SigV4
    # TODO: On approval, update product prices in Products table

    return _response(200, {
        "message": f"Scenario {scenario_id} {action.lower()}",
        "scenarioId": scenario_id,
        "action": action,
    })


def _response(status_code: int, body: dict) -> dict[str, Any]:
    """Build API Gateway proxy response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
