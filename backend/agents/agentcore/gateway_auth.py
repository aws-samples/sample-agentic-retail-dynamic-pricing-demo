"""SigV4 (AWS_IAM) authentication for the AgentCore Gateway MCP endpoint.

The gateway uses AWS_IAM inbound authorization: every MCP request (the POSTs,
the GET event stream and the DELETE that ends a session) must carry a SigV4
signature for service "bedrock-agentcore" from a principal allowed to call
bedrock-agentcore:InvokeGateway on the gateway. Deployed runtimes sign with
their execution role (RetailPricingAgentCoreRole).

AGENTCORE_GATEWAY_AUTH selects how a runtime authenticates to the gateway:
    AWS_IAM (default)  sign every request with SigV4
    NONE               send unsigned requests; only works against a gateway whose
                       inbound authorizer is still NONE (an older deployment)

scripts/deploy_agentcore.py sets AWS_IAM on every runtime, and
scripts/secure_gateway.py only switches the gateway to AWS_IAM once every
runtime serves a version that signs.
"""

from __future__ import annotations

import os
import re
from collections.abc import Generator

import boto3
import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from strands.tools.mcp import MCPClient

GATEWAY_AUTH_ENV = "AGENTCORE_GATEWAY_AUTH"
AUTH_AWS_IAM = "AWS_IAM"
AUTH_NONE = "NONE"
SIGNING_SERVICE = "bedrock-agentcore"

# Headers SigV4Auth adds; copied onto the outgoing request.
_AUTH_HEADERS = ("Authorization", "X-Amz-Date", "X-Amz-Security-Token")
_GATEWAY_HOST = re.compile(r"\.gateway\.bedrock-agentcore\.([a-z0-9-]+)\.amazonaws\.com$")


def region_from_gateway_url(url: str) -> str:
    """AWS Region of a gateway URL (<id>.gateway.bedrock-agentcore.<region>.amazonaws.com)."""
    match = _GATEWAY_HOST.search(httpx.URL(url).host)
    if match:
        return match.group(1)
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if region:
        return region
    raise ValueError(f"Cannot tell the AWS Region of gateway URL {url!r}; set AWS_REGION.")


class GatewaySigV4Auth(httpx.Auth):
    """httpx auth that signs every request with SigV4 for the AgentCore Gateway.

    requires_request_body: the signature covers the SHA-256 of the body, so the
    body must be read before signing. strands' adapter for the mcp 2.x (httpx2)
    transport only forwards the body to an httpx.Auth when this is set; without
    it every POST would be signed over an empty body and rejected.

    Only host, x-amz-date and x-amz-security-token are signed, so headers the
    HTTP client adds or rewrites after signing cannot invalidate the signature.
    Credentials are read on every request, so rotated role credentials are used.
    """

    requires_request_body = True

    def __init__(self, region: str, session: boto3.Session | None = None, service: str = SIGNING_SERVICE):
        self.region = region
        self.service = service
        self._session = session or boto3.Session()

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        credentials = self._session.get_credentials()
        if credentials is None:
            raise RuntimeError("No AWS credentials available to sign AgentCore Gateway requests.")
        aws_request = AWSRequest(method=request.method, url=str(request.url), data=request.content or b"")
        SigV4Auth(credentials.get_frozen_credentials(), self.service, self.region).add_auth(aws_request)
        for name in _AUTH_HEADERS:
            value = aws_request.headers.get(name)
            if value:
                request.headers[name] = value
        yield request


def gateway_auth_mode() -> str:
    """AWS_IAM or NONE, from AGENTCORE_GATEWAY_AUTH (default AWS_IAM)."""
    mode = (os.environ.get(GATEWAY_AUTH_ENV) or AUTH_AWS_IAM).strip().upper()
    if mode not in (AUTH_AWS_IAM, AUTH_NONE):
        raise ValueError(f"{GATEWAY_AUTH_ENV} must be {AUTH_AWS_IAM} or {AUTH_NONE}, got {mode!r}.")
    return mode


def create_gateway_mcp_client(endpoint: str) -> MCPClient:
    """MCP client for the gateway's MCP URL (<gatewayUrl>/mcp), signing per AGENTCORE_GATEWAY_AUTH."""
    if gateway_auth_mode() == AUTH_NONE:
        return MCPClient(url=endpoint)
    return MCPClient(url=endpoint, auth_provider=GatewaySigV4Auth(region_from_gateway_url(endpoint)))
