"""SigV4 HTTP utility for Bedrock AgentCore Runtime API invocations.

Lambda's bundled boto3 does not include the bedrock-agentcore service client,
so we sign requests manually using botocore's SigV4Auth and make HTTP calls
with urllib3.

This module provides:
- SigV4 request signing for the "bedrock" service
- A helper function for InvokeAgentRuntime calls
- Streaming response handling
- Error handling for timeout, 4xx, and 5xx responses

Requirements: 11.7
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Generator
from urllib.parse import urlparse

import boto3
import urllib3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials

logger = logging.getLogger(__name__)

# Default timeout for HTTP requests (seconds)
DEFAULT_CONNECT_TIMEOUT = 10.0
DEFAULT_READ_TIMEOUT = 130.0  # > 120s agent timeout to allow full response


@dataclass
class AgentCoreConfig:
    """Configuration for AgentCore Runtime API calls.

    Attributes:
        region: AWS region for the AgentCore endpoint.
        endpoint_url: Optional custom endpoint URL. If None, uses the default
            Bedrock AgentCore Runtime endpoint for the region.
        connect_timeout: Connection timeout in seconds.
        read_timeout: Read timeout in seconds.
    """

    region: str = "us-east-1"
    endpoint_url: str | None = None
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT
    read_timeout: float = DEFAULT_READ_TIMEOUT

    @property
    def base_url(self) -> str:
        """Return the base URL for AgentCore Runtime API."""
        if self.endpoint_url:
            return self.endpoint_url.rstrip("/")
        return f"https://bedrock-agent-runtime.{self.region}.amazonaws.com"


@dataclass
class AgentCoreResponse:
    """Response from an AgentCore Runtime API call.

    Attributes:
        status_code: HTTP status code.
        headers: Response headers.
        body: Parsed response body (for non-streaming responses).
        stream: Raw response for streaming (caller must iterate).
        error: Error details if the request failed.
    """

    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] | None = None
    stream: urllib3.HTTPResponse | None = None
    error: dict[str, Any] | None = None

    @property
    def is_success(self) -> bool:
        """Return True if the response indicates success (2xx)."""
        return 200 <= self.status_code < 300

    @property
    def is_client_error(self) -> bool:
        """Return True if the response indicates a client error (4xx)."""
        return 400 <= self.status_code < 500

    @property
    def is_server_error(self) -> bool:
        """Return True if the response indicates a server error (5xx)."""
        return 500 <= self.status_code < 600


class SigV4Client:
    """HTTP client that signs requests with AWS SigV4 for Bedrock AgentCore.

    Uses botocore's SigV4Auth to sign requests and urllib3 for HTTP transport.
    """

    def __init__(
        self,
        config: AgentCoreConfig | None = None,
        credentials: Credentials | None = None,
        session: boto3.Session | None = None,
    ) -> None:
        """Initialize the SigV4 client.

        Args:
            config: AgentCore configuration. Uses defaults if None.
            credentials: AWS credentials for signing. If None, resolves from
                the boto3 session or environment.
            session: boto3 session for credential resolution. Creates a new
                session if None.
        """
        self._config = config or AgentCoreConfig()
        self._session = session or boto3.Session(region_name=self._config.region)
        self._credentials = credentials or self._resolve_credentials()
        self._http = urllib3.PoolManager(
            timeout=urllib3.Timeout(
                connect=self._config.connect_timeout,
                read=self._config.read_timeout,
            ),
            retries=urllib3.Retry(total=0),  # We handle retries at a higher level
        )

    def _resolve_credentials(self) -> Credentials:
        """Resolve AWS credentials from the boto3 session."""
        botocore_session = self._session._session
        credentials = botocore_session.get_credentials()
        if credentials is None:
            raise RuntimeError(
                "Unable to resolve AWS credentials. Ensure credentials are "
                "configured via environment variables, IAM role, or AWS config."
            )
        return credentials.get_frozen_credentials()

    def sign_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: bytes | str | None = None,
        service: str = "bedrock",
    ) -> dict[str, str]:
        """Sign an HTTP request with SigV4.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: Full request URL.
            headers: Request headers to include in signing.
            body: Request body (bytes or string).
            service: AWS service name for signing (default: "bedrock").

        Returns:
            Dictionary of signed headers to include in the request.
        """
        headers = dict(headers) if headers else {}
        body_bytes = body.encode("utf-8") if isinstance(body, str) else (body or b"")

        aws_request = AWSRequest(
            method=method,
            url=url,
            headers=headers,
            data=body_bytes,
        )

        SigV4Auth(self._credentials, service, self._config.region).add_auth(
            aws_request
        )

        return dict(aws_request.headers)

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: bytes | str | None = None,
        service: str = "bedrock",
        stream: bool = False,
    ) -> AgentCoreResponse:
        """Make a signed HTTP request to an AWS service.

        Args:
            method: HTTP method.
            url: Full request URL.
            headers: Additional request headers.
            body: Request body.
            service: AWS service name for signing.
            stream: If True, return the raw response for streaming.

        Returns:
            AgentCoreResponse with status, headers, and body or stream.
        """
        headers = dict(headers) if headers else {}
        body_bytes = body.encode("utf-8") if isinstance(body, str) else (body or b"")

        # Add content-type if not present and body is provided
        if body_bytes and "content-type" not in {k.lower() for k in headers}:
            headers["Content-Type"] = "application/json"

        signed_headers = self.sign_request(
            method=method,
            url=url,
            headers=headers,
            body=body_bytes,
            service=service,
        )

        try:
            response = self._http.request(
                method=method,
                url=url,
                headers=signed_headers,
                body=body_bytes if body_bytes else None,
                preload_content=not stream,
            )
        except urllib3.exceptions.ConnectTimeoutError as e:
            logger.error("Connection timeout to %s: %s", url, e)
            return AgentCoreResponse(
                status_code=0,
                error={
                    "code": "CONNECTION_TIMEOUT",
                    "message": f"Connection timeout to {url}",
                    "exception": str(e),
                },
            )
        except urllib3.exceptions.ReadTimeoutError as e:
            logger.error("Read timeout from %s: %s", url, e)
            return AgentCoreResponse(
                status_code=0,
                error={
                    "code": "READ_TIMEOUT",
                    "message": f"Read timeout from {url}",
                    "exception": str(e),
                },
            )
        except urllib3.exceptions.MaxRetryError as e:
            logger.error("Connection failed to %s: %s", url, e)
            return AgentCoreResponse(
                status_code=0,
                error={
                    "code": "CONNECTION_ERROR",
                    "message": f"Connection failed to {url}",
                    "exception": str(e),
                },
            )
        except urllib3.exceptions.HTTPError as e:
            logger.error("HTTP error for %s: %s", url, e)
            return AgentCoreResponse(
                status_code=0,
                error={
                    "code": "HTTP_ERROR",
                    "message": f"HTTP error for {url}",
                    "exception": str(e),
                },
            )

        response_headers = dict(response.headers)

        if stream and response.status >= 200 and response.status < 300:
            return AgentCoreResponse(
                status_code=response.status,
                headers=response_headers,
                stream=response,
            )

        # Parse response body
        body_data = None
        error_data = None

        try:
            raw_body = response.data if not stream else response.read()
            if raw_body:
                body_data = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            body_data = {"raw": raw_body.decode("utf-8", errors="replace")}

        if response.status >= 400:
            error_data = {
                "code": f"HTTP_{response.status}",
                "message": body_data.get("message", "Unknown error")
                if isinstance(body_data, dict)
                else "Unknown error",
                "status_code": response.status,
                "body": body_data,
            }
            logger.error(
                "Request to %s failed with status %d: %s",
                url,
                response.status,
                error_data["message"],
            )

        return AgentCoreResponse(
            status_code=response.status,
            headers=response_headers,
            body=body_data,
            error=error_data,
        )


def invoke_agent_runtime(
    agent_id: str,
    session_id: str,
    input_text: str,
    config: AgentCoreConfig | None = None,
    client: SigV4Client | None = None,
    enable_trace: bool = False,
    additional_params: dict[str, Any] | None = None,
) -> AgentCoreResponse:
    """Invoke an AgentCore Runtime agent with SigV4-signed request.

    This is the primary helper function for calling InvokeAgentRuntime.
    It constructs the proper URL, request body, and handles the streaming
    response from AgentCore.

    Args:
        agent_id: The AgentCore agent ID to invoke.
        session_id: Session ID for the agent invocation (scoped to Pricing Group).
        input_text: The input text/prompt to send to the agent.
        config: AgentCore configuration. Uses defaults if None.
        client: Pre-configured SigV4Client. Creates one if None.
        enable_trace: Whether to enable AgentCore tracing.
        additional_params: Additional parameters to include in the request body.

    Returns:
        AgentCoreResponse with streaming response or error details.
    """
    config = config or AgentCoreConfig()
    client = client or SigV4Client(config=config)

    url = (
        f"{config.base_url}/agents/{agent_id}"
        f"/agentAliases/TSTALIASID/sessions/{session_id}/text"
    )

    request_body: dict[str, Any] = {
        "inputText": input_text,
        "enableTrace": enable_trace,
    }

    if additional_params:
        request_body.update(additional_params)

    body_json = json.dumps(request_body)

    logger.info(
        "Invoking AgentCore agent %s in session %s",
        agent_id,
        session_id,
    )

    response = client.request(
        method="POST",
        url=url,
        headers={"Content-Type": "application/json"},
        body=body_json,
        service="bedrock",
        stream=True,
    )

    if not response.is_success and response.error:
        logger.error(
            "AgentCore invocation failed for agent %s: %s",
            agent_id,
            response.error,
        )

    return response


def read_streaming_response(
    response: AgentCoreResponse,
) -> Generator[dict[str, Any], None, None]:
    """Read and parse a streaming response from AgentCore Runtime.

    AgentCore returns responses as a stream of JSON events. This generator
    yields each parsed event as a dictionary.

    Args:
        response: The AgentCoreResponse with a stream attribute.

    Yields:
        Parsed JSON event dictionaries from the stream.

    Raises:
        ValueError: If the response has no stream or is an error response.
    """
    if response.error:
        raise ValueError(
            f"Cannot read stream from error response: {response.error}"
        )

    if response.stream is None:
        raise ValueError("Response has no stream to read")

    buffer = b""
    for chunk in response.stream.stream(amt=4096):
        buffer += chunk
        # AgentCore streams events separated by newlines
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line.decode("utf-8"))
                yield event
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning("Failed to parse stream event: %s", e)
                continue

    # Process any remaining data in buffer
    if buffer.strip():
        try:
            event = json.loads(buffer.decode("utf-8"))
            yield event
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Failed to parse final stream chunk: %s", e)


def collect_streaming_response(response: AgentCoreResponse) -> dict[str, Any]:
    """Collect all events from a streaming response into a single result.

    Convenience function that reads the entire stream and assembles the
    final agent output.

    Args:
        response: The AgentCoreResponse with a stream attribute.

    Returns:
        Dictionary with 'events' (list of all events) and 'output' (final
        assembled text output from the agent).
    """
    events: list[dict[str, Any]] = []
    output_parts: list[str] = []

    for event in read_streaming_response(response):
        events.append(event)
        # Extract text chunks from the event
        if "chunk" in event:
            chunk_data = event["chunk"]
            if "bytes" in chunk_data:
                import base64

                text = base64.b64decode(chunk_data["bytes"]).decode("utf-8")
                output_parts.append(text)
            elif "text" in chunk_data:
                output_parts.append(chunk_data["text"])
        elif "text" in event:
            output_parts.append(event["text"])

    return {
        "events": events,
        "output": "".join(output_parts),
    }
