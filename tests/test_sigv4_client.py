"""Unit tests for the SigV4 HTTP utility for AgentCore invocations.

Tests SigV4 request signing, InvokeAgentRuntime helper, streaming response
handling, and error cases.

Validates: Requirements 11.7
"""

import json
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import urllib3

from shared.sigv4_client import (
    AgentCoreConfig,
    AgentCoreResponse,
    SigV4Client,
    collect_streaming_response,
    invoke_agent_runtime,
    read_streaming_response,
)


class TestAgentCoreConfig:
    """Tests for AgentCoreConfig dataclass."""

    def test_default_config(self):
        config = AgentCoreConfig()
        assert config.region == "us-east-1"
        assert config.endpoint_url is None
        assert config.connect_timeout == 10.0
        assert config.read_timeout == 130.0

    def test_custom_config(self):
        config = AgentCoreConfig(
            region="us-west-2",
            endpoint_url="https://custom.endpoint.com",
            connect_timeout=5.0,
            read_timeout=60.0,
        )
        assert config.region == "us-west-2"
        assert config.endpoint_url == "https://custom.endpoint.com"

    def test_base_url_default(self):
        config = AgentCoreConfig(region="us-west-2")
        assert config.base_url == "https://bedrock-agent-runtime.us-west-2.amazonaws.com"

    def test_base_url_custom_endpoint(self):
        config = AgentCoreConfig(endpoint_url="https://custom.endpoint.com/")
        assert config.base_url == "https://custom.endpoint.com"

    def test_base_url_strips_trailing_slash(self):
        config = AgentCoreConfig(endpoint_url="https://example.com///")
        assert config.base_url == "https://example.com"


class TestAgentCoreResponse:
    """Tests for AgentCoreResponse dataclass."""

    def test_success_response(self):
        response = AgentCoreResponse(status_code=200, body={"result": "ok"})
        assert response.is_success is True
        assert response.is_client_error is False
        assert response.is_server_error is False

    def test_client_error_response(self):
        response = AgentCoreResponse(status_code=400, error={"code": "BadRequest"})
        assert response.is_success is False
        assert response.is_client_error is True
        assert response.is_server_error is False

    def test_server_error_response(self):
        response = AgentCoreResponse(status_code=500, error={"code": "InternalError"})
        assert response.is_success is False
        assert response.is_client_error is False
        assert response.is_server_error is True

    def test_timeout_response(self):
        response = AgentCoreResponse(
            status_code=0,
            error={"code": "CONNECTION_TIMEOUT", "message": "timed out"},
        )
        assert response.is_success is False
        assert response.is_client_error is False
        assert response.is_server_error is False


class TestSigV4Client:
    """Tests for SigV4Client signing and request logic."""

    @pytest.fixture
    def mock_credentials(self):
        """Create mock AWS credentials."""
        creds = MagicMock()
        creds.access_key = "AKIAIOSFODNN7EXAMPLE"
        creds.secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        creds.token = "FwoGZXIvYXdzEBYaDHqa0AP"
        return creds

    @pytest.fixture
    def mock_session(self, mock_credentials):
        """Create a mock boto3 session that returns mock credentials."""
        session = MagicMock()
        botocore_session = MagicMock()
        frozen_creds = MagicMock()
        frozen_creds.access_key = mock_credentials.access_key
        frozen_creds.secret_key = mock_credentials.secret_key
        frozen_creds.token = mock_credentials.token
        creds_obj = MagicMock()
        creds_obj.get_frozen_credentials.return_value = frozen_creds
        botocore_session.get_credentials.return_value = creds_obj
        session._session = botocore_session
        return session

    @pytest.fixture
    def client(self, mock_session, mock_credentials):
        """Create a SigV4Client with mocked credentials."""
        config = AgentCoreConfig(region="us-east-1")
        return SigV4Client(
            config=config,
            credentials=mock_credentials,
            session=mock_session,
        )

    def test_sign_request_adds_authorization_header(self, client):
        """SigV4 signing should add Authorization header."""
        signed_headers = client.sign_request(
            method="POST",
            url="https://bedrock-agent-runtime.us-east-1.amazonaws.com/agents/test/text",
            headers={"Content-Type": "application/json"},
            body='{"inputText": "hello"}',
        )
        assert "Authorization" in signed_headers
        assert "AWS4-HMAC-SHA256" in signed_headers["Authorization"]

    def test_sign_request_adds_date_header(self, client):
        """SigV4 signing should add X-Amz-Date header."""
        signed_headers = client.sign_request(
            method="POST",
            url="https://bedrock-agent-runtime.us-east-1.amazonaws.com/test",
            body="{}",
        )
        assert "X-Amz-Date" in signed_headers

    def test_sign_request_adds_security_token(self, client):
        """SigV4 signing should add X-Amz-Security-Token for session credentials."""
        signed_headers = client.sign_request(
            method="POST",
            url="https://bedrock-agent-runtime.us-east-1.amazonaws.com/test",
            body="{}",
        )
        assert "X-Amz-Security-Token" in signed_headers

    def test_sign_request_includes_service_in_credential_scope(self, client):
        """Authorization header should reference the bedrock service."""
        signed_headers = client.sign_request(
            method="POST",
            url="https://bedrock-agent-runtime.us-east-1.amazonaws.com/test",
            body="{}",
            service="bedrock",
        )
        assert "bedrock" in signed_headers["Authorization"]

    def test_sign_request_includes_region_in_credential_scope(self, client):
        """Authorization header should reference the configured region."""
        signed_headers = client.sign_request(
            method="POST",
            url="https://bedrock-agent-runtime.us-east-1.amazonaws.com/test",
            body="{}",
        )
        assert "us-east-1" in signed_headers["Authorization"]

    def test_sign_request_empty_body(self, client):
        """Signing should work with no body (GET requests)."""
        signed_headers = client.sign_request(
            method="GET",
            url="https://bedrock-agent-runtime.us-east-1.amazonaws.com/test",
        )
        assert "Authorization" in signed_headers

    @patch.object(urllib3.PoolManager, "request")
    def test_request_success(self, mock_http_request, client):
        """Successful request should return parsed JSON body."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.data = json.dumps({"result": "success"}).encode("utf-8")
        mock_http_request.return_value = mock_response

        response = client.request(
            method="POST",
            url="https://bedrock-agent-runtime.us-east-1.amazonaws.com/test",
            body='{"inputText": "hello"}',
        )

        assert response.status_code == 200
        assert response.is_success is True
        assert response.body == {"result": "success"}
        assert response.error is None

    @patch.object(urllib3.PoolManager, "request")
    def test_request_client_error(self, mock_http_request, client):
        """4xx response should populate error field."""
        mock_response = MagicMock()
        mock_response.status = 403
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.data = json.dumps(
            {"message": "Access denied"}
        ).encode("utf-8")
        mock_http_request.return_value = mock_response

        response = client.request(
            method="POST",
            url="https://bedrock-agent-runtime.us-east-1.amazonaws.com/test",
            body="{}",
        )

        assert response.status_code == 403
        assert response.is_client_error is True
        assert response.error is not None
        assert response.error["code"] == "HTTP_403"
        assert "Access denied" in response.error["message"]

    @patch.object(urllib3.PoolManager, "request")
    def test_request_server_error(self, mock_http_request, client):
        """5xx response should populate error field."""
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.headers = {}
        mock_response.data = json.dumps(
            {"message": "Internal server error"}
        ).encode("utf-8")
        mock_http_request.return_value = mock_response

        response = client.request(
            method="POST",
            url="https://bedrock-agent-runtime.us-east-1.amazonaws.com/test",
            body="{}",
        )

        assert response.status_code == 500
        assert response.is_server_error is True
        assert response.error is not None
        assert response.error["code"] == "HTTP_500"

    @patch.object(urllib3.PoolManager, "request")
    def test_request_connection_timeout(self, mock_http_request, client):
        """Connection timeout should return error with code CONNECTION_TIMEOUT."""
        mock_http_request.side_effect = urllib3.exceptions.ConnectTimeoutError(
            None, None, "Connection timed out"
        )

        response = client.request(
            method="POST",
            url="https://bedrock-agent-runtime.us-east-1.amazonaws.com/test",
            body="{}",
        )

        assert response.status_code == 0
        assert response.error is not None
        assert response.error["code"] == "CONNECTION_TIMEOUT"

    @patch.object(urllib3.PoolManager, "request")
    def test_request_read_timeout(self, mock_http_request, client):
        """Read timeout should return error with code READ_TIMEOUT."""
        mock_http_request.side_effect = urllib3.exceptions.ReadTimeoutError(
            None, None, "Read timed out"
        )

        response = client.request(
            method="POST",
            url="https://bedrock-agent-runtime.us-east-1.amazonaws.com/test",
            body="{}",
        )

        assert response.status_code == 0
        assert response.error is not None
        assert response.error["code"] == "READ_TIMEOUT"

    @patch.object(urllib3.PoolManager, "request")
    def test_request_connection_error(self, mock_http_request, client):
        """Connection failure should return error with code CONNECTION_ERROR."""
        mock_http_request.side_effect = urllib3.exceptions.MaxRetryError(
            None, "https://example.com", "Connection refused"
        )

        response = client.request(
            method="POST",
            url="https://bedrock-agent-runtime.us-east-1.amazonaws.com/test",
            body="{}",
        )

        assert response.status_code == 0
        assert response.error is not None
        assert response.error["code"] == "CONNECTION_ERROR"

    @patch.object(urllib3.PoolManager, "request")
    def test_request_generic_http_error(self, mock_http_request, client):
        """Generic HTTP error should return error with code HTTP_ERROR."""
        mock_http_request.side_effect = urllib3.exceptions.HTTPError(
            "Something went wrong"
        )

        response = client.request(
            method="POST",
            url="https://bedrock-agent-runtime.us-east-1.amazonaws.com/test",
            body="{}",
        )

        assert response.status_code == 0
        assert response.error is not None
        assert response.error["code"] == "HTTP_ERROR"

    @patch.object(urllib3.PoolManager, "request")
    def test_request_streaming(self, mock_http_request, client):
        """Streaming request should return response with stream attribute."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_http_request.return_value = mock_response

        response = client.request(
            method="POST",
            url="https://bedrock-agent-runtime.us-east-1.amazonaws.com/test",
            body="{}",
            stream=True,
        )

        assert response.status_code == 200
        assert response.stream is mock_response
        assert response.body is None

    @patch.object(urllib3.PoolManager, "request")
    def test_request_adds_content_type(self, mock_http_request, client):
        """Request with body should add Content-Type header if not present."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.data = b"{}"
        mock_http_request.return_value = mock_response

        client.request(
            method="POST",
            url="https://bedrock-agent-runtime.us-east-1.amazonaws.com/test",
            body='{"key": "value"}',
        )

        # Verify the request was made with Content-Type in headers
        call_kwargs = mock_http_request.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
        assert "Content-Type" in headers

    def test_resolve_credentials_failure(self):
        """Should raise RuntimeError when credentials cannot be resolved."""
        session = MagicMock()
        botocore_session = MagicMock()
        botocore_session.get_credentials.return_value = None
        session._session = botocore_session

        with pytest.raises(RuntimeError, match="Unable to resolve AWS credentials"):
            SigV4Client(session=session)


class TestInvokeAgentRuntime:
    """Tests for the invoke_agent_runtime helper function."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock SigV4Client."""
        client = MagicMock(spec=SigV4Client)
        return client

    def test_invoke_constructs_correct_url(self, mock_client):
        """invoke_agent_runtime should construct the correct AgentCore URL."""
        mock_client.request.return_value = AgentCoreResponse(
            status_code=200,
            stream=MagicMock(),
        )
        config = AgentCoreConfig(region="us-east-1")

        invoke_agent_runtime(
            agent_id="agent-123",
            session_id="session-456",
            input_text="Analyze pricing",
            config=config,
            client=mock_client,
        )

        call_args = mock_client.request.call_args
        url = call_args.kwargs.get("url") or call_args[1].get("url")
        assert "agents/agent-123" in url
        assert "sessions/session-456" in url
        assert "agentAliases/TSTALIASID" in url
        assert url.endswith("/text")

    def test_invoke_sends_input_text(self, mock_client):
        """invoke_agent_runtime should include inputText in request body."""
        mock_client.request.return_value = AgentCoreResponse(
            status_code=200,
            stream=MagicMock(),
        )
        config = AgentCoreConfig(region="us-east-1")

        invoke_agent_runtime(
            agent_id="agent-123",
            session_id="session-456",
            input_text="Analyze pricing for electronics",
            config=config,
            client=mock_client,
        )

        call_args = mock_client.request.call_args
        body = call_args.kwargs.get("body") or call_args[1].get("body")
        body_dict = json.loads(body)
        assert body_dict["inputText"] == "Analyze pricing for electronics"

    def test_invoke_enables_trace(self, mock_client):
        """invoke_agent_runtime should set enableTrace when requested."""
        mock_client.request.return_value = AgentCoreResponse(
            status_code=200,
            stream=MagicMock(),
        )
        config = AgentCoreConfig(region="us-east-1")

        invoke_agent_runtime(
            agent_id="agent-123",
            session_id="session-456",
            input_text="test",
            config=config,
            client=mock_client,
            enable_trace=True,
        )

        call_args = mock_client.request.call_args
        body = call_args.kwargs.get("body") or call_args[1].get("body")
        body_dict = json.loads(body)
        assert body_dict["enableTrace"] is True

    def test_invoke_includes_additional_params(self, mock_client):
        """invoke_agent_runtime should merge additional_params into body."""
        mock_client.request.return_value = AgentCoreResponse(
            status_code=200,
            stream=MagicMock(),
        )
        config = AgentCoreConfig(region="us-east-1")

        invoke_agent_runtime(
            agent_id="agent-123",
            session_id="session-456",
            input_text="test",
            config=config,
            client=mock_client,
            additional_params={"memoryId": "mem-789"},
        )

        call_args = mock_client.request.call_args
        body = call_args.kwargs.get("body") or call_args[1].get("body")
        body_dict = json.loads(body)
        assert body_dict["memoryId"] == "mem-789"

    def test_invoke_uses_streaming(self, mock_client):
        """invoke_agent_runtime should request streaming response."""
        mock_client.request.return_value = AgentCoreResponse(
            status_code=200,
            stream=MagicMock(),
        )
        config = AgentCoreConfig(region="us-east-1")

        invoke_agent_runtime(
            agent_id="agent-123",
            session_id="session-456",
            input_text="test",
            config=config,
            client=mock_client,
        )

        call_args = mock_client.request.call_args
        stream = call_args.kwargs.get("stream") or call_args[1].get("stream")
        assert stream is True

    def test_invoke_returns_error_response(self, mock_client):
        """invoke_agent_runtime should return error response on failure."""
        mock_client.request.return_value = AgentCoreResponse(
            status_code=0,
            error={"code": "READ_TIMEOUT", "message": "Read timed out"},
        )
        config = AgentCoreConfig(region="us-east-1")

        response = invoke_agent_runtime(
            agent_id="agent-123",
            session_id="session-456",
            input_text="test",
            config=config,
            client=mock_client,
        )

        assert response.is_success is False
        assert response.error["code"] == "READ_TIMEOUT"

    def test_invoke_uses_custom_endpoint(self, mock_client):
        """invoke_agent_runtime should use custom endpoint from config."""
        mock_client.request.return_value = AgentCoreResponse(
            status_code=200,
            stream=MagicMock(),
        )
        config = AgentCoreConfig(
            region="us-west-2",
            endpoint_url="https://custom-agentcore.example.com",
        )

        invoke_agent_runtime(
            agent_id="agent-123",
            session_id="session-456",
            input_text="test",
            config=config,
            client=mock_client,
        )

        call_args = mock_client.request.call_args
        url = call_args.kwargs.get("url") or call_args[1].get("url")
        assert url.startswith("https://custom-agentcore.example.com/")


class TestReadStreamingResponse:
    """Tests for streaming response reading."""

    def test_read_single_event(self):
        """Should yield a single parsed JSON event."""
        mock_stream = MagicMock()
        mock_stream.stream.return_value = [
            b'{"chunk": {"text": "Hello"}}\n',
        ]
        response = AgentCoreResponse(status_code=200, stream=mock_stream)

        events = list(read_streaming_response(response))
        assert len(events) == 1
        assert events[0] == {"chunk": {"text": "Hello"}}

    def test_read_multiple_events(self):
        """Should yield multiple parsed JSON events."""
        mock_stream = MagicMock()
        mock_stream.stream.return_value = [
            b'{"chunk": {"text": "Hello "}}\n{"chunk": {"text": "World"}}\n',
        ]
        response = AgentCoreResponse(status_code=200, stream=mock_stream)

        events = list(read_streaming_response(response))
        assert len(events) == 2
        assert events[0] == {"chunk": {"text": "Hello "}}
        assert events[1] == {"chunk": {"text": "World"}}

    def test_read_events_across_chunks(self):
        """Should handle events split across multiple network chunks."""
        mock_stream = MagicMock()
        mock_stream.stream.return_value = [
            b'{"chunk": {"te',
            b'xt": "Hello"}}\n',
        ]
        response = AgentCoreResponse(status_code=200, stream=mock_stream)

        events = list(read_streaming_response(response))
        assert len(events) == 1
        assert events[0] == {"chunk": {"text": "Hello"}}

    def test_read_skips_empty_lines(self):
        """Should skip empty lines in the stream."""
        mock_stream = MagicMock()
        mock_stream.stream.return_value = [
            b'\n\n{"chunk": {"text": "data"}}\n\n',
        ]
        response = AgentCoreResponse(status_code=200, stream=mock_stream)

        events = list(read_streaming_response(response))
        assert len(events) == 1

    def test_read_handles_malformed_json(self):
        """Should skip malformed JSON lines without raising."""
        mock_stream = MagicMock()
        mock_stream.stream.return_value = [
            b'not valid json\n{"chunk": {"text": "valid"}}\n',
        ]
        response = AgentCoreResponse(status_code=200, stream=mock_stream)

        events = list(read_streaming_response(response))
        assert len(events) == 1
        assert events[0] == {"chunk": {"text": "valid"}}

    def test_read_error_response_raises(self):
        """Should raise ValueError for error responses."""
        response = AgentCoreResponse(
            status_code=500,
            error={"code": "HTTP_500", "message": "Server error"},
        )

        with pytest.raises(ValueError, match="Cannot read stream from error"):
            list(read_streaming_response(response))

    def test_read_no_stream_raises(self):
        """Should raise ValueError when response has no stream."""
        response = AgentCoreResponse(status_code=200, stream=None)

        with pytest.raises(ValueError, match="Response has no stream"):
            list(read_streaming_response(response))

    def test_read_remaining_buffer(self):
        """Should process remaining data in buffer after stream ends."""
        mock_stream = MagicMock()
        mock_stream.stream.return_value = [
            b'{"chunk": {"text": "final"}}',  # No trailing newline
        ]
        response = AgentCoreResponse(status_code=200, stream=mock_stream)

        events = list(read_streaming_response(response))
        assert len(events) == 1
        assert events[0] == {"chunk": {"text": "final"}}


class TestCollectStreamingResponse:
    """Tests for collecting streaming responses into a single result."""

    def test_collect_text_chunks(self):
        """Should assemble text chunks into output."""
        mock_stream = MagicMock()
        mock_stream.stream.return_value = [
            b'{"chunk": {"text": "Hello "}}\n',
            b'{"chunk": {"text": "World"}}\n',
        ]
        response = AgentCoreResponse(status_code=200, stream=mock_stream)

        result = collect_streaming_response(response)
        assert result["output"] == "Hello World"
        assert len(result["events"]) == 2

    def test_collect_base64_chunks(self):
        """Should decode base64 bytes chunks into output."""
        import base64

        encoded = base64.b64encode(b"decoded text").decode("utf-8")
        mock_stream = MagicMock()
        mock_stream.stream.return_value = [
            f'{{"chunk": {{"bytes": "{encoded}"}}}}\n'.encode("utf-8"),
        ]
        response = AgentCoreResponse(status_code=200, stream=mock_stream)

        result = collect_streaming_response(response)
        assert result["output"] == "decoded text"

    def test_collect_text_events(self):
        """Should handle top-level text events."""
        mock_stream = MagicMock()
        mock_stream.stream.return_value = [
            b'{"text": "direct text"}\n',
        ]
        response = AgentCoreResponse(status_code=200, stream=mock_stream)

        result = collect_streaming_response(response)
        assert result["output"] == "direct text"

    def test_collect_empty_stream(self):
        """Should handle empty stream gracefully."""
        mock_stream = MagicMock()
        mock_stream.stream.return_value = []
        response = AgentCoreResponse(status_code=200, stream=mock_stream)

        result = collect_streaming_response(response)
        assert result["output"] == ""
        assert result["events"] == []

    def test_collect_mixed_events(self):
        """Should handle mix of text and non-text events."""
        mock_stream = MagicMock()
        mock_stream.stream.return_value = [
            b'{"trace": {"type": "start"}}\n',
            b'{"chunk": {"text": "output"}}\n',
            b'{"trace": {"type": "end"}}\n',
        ]
        response = AgentCoreResponse(status_code=200, stream=mock_stream)

        result = collect_streaming_response(response)
        assert result["output"] == "output"
        assert len(result["events"]) == 3
