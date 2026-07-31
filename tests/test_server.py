"""
Basic smoke tests for the Gomag MCP server.

These tests do NOT require live Gomag credentials — they use respx to mock
HTTP responses and validate that:
  1. Tools are registered with correct names
  2. The audit logger writes valid JSON-Lines records
  3. The HTTP client sends the right headers and body format
  4. Retry logic fires on 429 / 5xx
  5. Sensitive fields are redacted in audit output
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Return a minimal Settings instance pointing audit logs at tmp_path."""
    monkeypatch.setenv("GOMAG_API_KEY", "test-key")
    monkeypatch.setenv("GOMAG_API_SHOP", "https://test.gomag.ro")
    monkeypatch.setenv("GOMAG_AUDIT_LOG_FILE", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("GOMAG_AUDIT_LOG_TO_STDERR", "false")
    from gomag_mcp.config import Settings
    return Settings()


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestSettings:
    def test_loads_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        settings = _make_settings(tmp_path, monkeypatch)
        assert settings.api_key == "test-key"
        assert settings.api_shop == "https://test.gomag.ro"
        assert settings.base_url == "https://api.gomag.ro"
        assert settings.max_retries == 3

    def test_defaults(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        settings = _make_settings(tmp_path, monkeypatch)
        assert settings.user_agent == "GomagMCP/1.0"
        assert settings.request_timeout == 30.0


# ---------------------------------------------------------------------------
# Audit logger tests
# ---------------------------------------------------------------------------

class TestAuditLogger:
    @pytest.mark.asyncio
    async def test_writes_jsonl_on_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        settings = _make_settings(tmp_path, monkeypatch)
        from gomag_mcp.audit import AuditLogger

        audit = AuditLogger(settings)
        log_file = Path(settings.audit_log_file)

        async with audit.tool_call("test_tool", {"param": "value"}, "GET", "/test") as ar:
            ar["http_status"] = 200

        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["event_type"] == "tool_call"
        assert record["tool_name"] == "test_tool"
        assert record["success"] is True
        assert record["http_status"] == 200
        assert "request_id" in record
        assert record["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_writes_error_on_exception(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        settings = _make_settings(tmp_path, monkeypatch)
        from gomag_mcp.audit import AuditLogger

        audit = AuditLogger(settings)
        log_file = Path(settings.audit_log_file)

        with pytest.raises(ValueError, match="boom"):
            async with audit.tool_call("failing_tool", {}, "POST", "/fail"):
                raise ValueError("boom")

        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["event_type"] == "tool_error"
        assert record["success"] is False
        assert "boom" in record["error_message"]

    @pytest.mark.asyncio
    async def test_redacts_sensitive_fields(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        settings = _make_settings(tmp_path, monkeypatch)
        from gomag_mcp.audit import AuditLogger

        audit = AuditLogger(settings)
        log_file = Path(settings.audit_log_file)

        sensitive = {"password": "secret123", "apikey": "key", "email": "user@test.com"}
        async with audit.tool_call("login", sensitive, "POST", "/login") as ar:
            ar["http_status"] = 200

        record = json.loads(log_file.read_text().strip())
        params = record["parameters"]
        assert params["password"] == "***REDACTED***"
        assert params["apikey"] == "***REDACTED***"
        assert params["email"] == "user@test.com"  # not sensitive


# ---------------------------------------------------------------------------
# Client tests
# ---------------------------------------------------------------------------

def test_server_module_imports() -> None:
    """The installed MCP SDK must expose the FastMCP API used by the server."""
    import gomag_mcp.server

    assert gomag_mcp.server.mcp is not None


def test_all_tools_have_safety_annotations() -> None:
    from gomag_mcp.server import mcp

    tools = mcp._tool_manager._tools
    assert tools
    assert all(tool.annotations is not None for tool in tools.values())
    assert tools["product_list"].annotations.readOnlyHint is True
    assert tools["product_update"].annotations.readOnlyHint is False
    assert tools["product_delete"].annotations.destructiveHint is True
    assert tools["product_update"].annotations.openWorldHint is True


def test_remote_transport_requires_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    from gomag_mcp.server import _create_mcp

    monkeypatch.setenv("GOMAG_MCP_TRANSPORT", "streamable-http")
    monkeypatch.delenv("GOMAG_MCP_PUBLIC_URL", raising=False)
    monkeypatch.delenv("GOMAG_OAUTH_ISSUER_URL", raising=False)

    with pytest.raises(RuntimeError, match="GOMAG_MCP_PUBLIC_URL"):
        _create_mcp()


def test_remote_transport_is_oauth_protected(monkeypatch: pytest.MonkeyPatch) -> None:
    from gomag_mcp.server import _create_mcp, _register_tools

    monkeypatch.setenv("GOMAG_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("GOMAG_MCP_PUBLIC_URL", "https://gomag.example.com")
    monkeypatch.setenv("GOMAG_OAUTH_ISSUER_URL", "https://auth.example.com/")
    monkeypatch.setenv("GOMAG_OAUTH_AUDIENCE", "https://gomag.example.com/mcp")
    monkeypatch.setenv("GOMAG_OAUTH_REQUIRED_SCOPES", "gomag:access")
    monkeypatch.setenv("PORT", "9876")

    server, transport = _create_mcp()
    _register_tools(server, oauth_required=True)

    assert transport == "streamable-http"
    assert server.settings.host == "0.0.0.0"
    assert server.settings.port == 9876
    assert server.settings.streamable_http_path == "/mcp"
    assert server.settings.auth is not None
    assert server.settings.auth.required_scopes == ["gomag:access"]
    assert server._token_verifier is not None
    assert server._tool_manager._tools["product_list"].meta["securitySchemes"] == [
        {"type": "oauth2", "scopes": ["gomag:access"]}
    ]


@pytest.mark.asyncio
async def test_oauth_verifier_accepts_valid_rs256_token() -> None:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    from gomag_mcp.auth import JWTTokenVerifier

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": "https://auth.example.com/",
            "aud": "https://gomag.example.com/mcp",
            "sub": "user-1",
            "azp": "chatgpt",
            "scope": "openid profile",
            "permissions": ["gomag:access"],
            "iat": now,
            "exp": now + 300,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    verifier = JWTTokenVerifier(
        issuer="https://auth.example.com/",
        audience="https://gomag.example.com/mcp",
        jwks_url="https://auth.example.com/.well-known/jwks.json",
    )
    verifier._jwks = MagicMock()
    verifier._jwks.get_signing_key_from_jwt.return_value.key = private_key.public_key()

    access = await verifier.verify_token(token)

    assert access is not None
    assert access.client_id == "chatgpt"
    assert access.subject == "user-1"
    assert access.scopes == ["openid", "profile", "gomag:access"]


@pytest.mark.asyncio
async def test_remote_endpoint_rejects_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from gomag_mcp.server import _create_mcp

    monkeypatch.setenv("GOMAG_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("GOMAG_MCP_PUBLIC_URL", "https://gomag.example.com")
    monkeypatch.setenv("GOMAG_OAUTH_ISSUER_URL", "https://auth.example.com/")
    monkeypatch.setenv("GOMAG_OAUTH_AUDIENCE", "https://gomag.example.com/mcp")

    server, _ = _create_mcp()
    transport = httpx.ASGITransport(app=server.streamable_http_app())
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://gomag.example.com",
    ) as client:
        response = await client.post(
            "/mcp",
            headers={"Accept": "application/json, text/event-stream"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
        )
        metadata = await client.get("/.well-known/oauth-protected-resource/mcp")

    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["WWW-Authenticate"]
    assert metadata.status_code == 200
    assert metadata.json()["resource"] == "https://gomag.example.com/mcp"


class TestGomagClient:
    @pytest.mark.asyncio
    async def test_get_sends_api_shop_header(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        import respx
        import httpx

        settings = _make_settings(tmp_path, monkeypatch)
        from gomag_mcp.client import GomagClient

        async with respx.mock(base_url=settings.base_url) as mock:
            route = mock.get("/api/v1/product/read/json").mock(
                return_value=httpx.Response(200, json={"products": []})
            )
            async with GomagClient(settings) as client:
                result = await client.get("/api/v1/product/read/json")

        assert result["http_status"] == 200
        req = route.calls[0].request
        assert req.headers["ApiShop"] == settings.api_shop
        assert req.headers["User-Agent"] == settings.user_agent
        # Gomag requires the API key for read requests as well.
        assert req.headers["Apikey"] == settings.api_key

    @pytest.mark.asyncio
    async def test_post_sends_apikey_and_form_data(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        import respx
        import httpx

        settings = _make_settings(tmp_path, monkeypatch)
        from gomag_mcp.client import GomagClient

        payload = [{"sku": "TEST", "price": 10}]

        async with respx.mock(base_url=settings.base_url) as mock:
            route = mock.post("/api/v1/product/write/json").mock(
                return_value=httpx.Response(200, json={"created": 1})
            )
            async with GomagClient(settings) as client:
                result = await client.post("/api/v1/product/write/json", payload=payload)

        assert result["http_status"] == 200
        req = route.calls[0].request
        assert req.headers["Apikey"] == settings.api_key
        # Body should contain form field "data" with JSON
        body = req.content.decode()
        assert "data" in body
        assert "TEST" in body

    @pytest.mark.asyncio
    async def test_retries_on_429(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        import respx
        import httpx

        settings = _make_settings(tmp_path, monkeypatch)
        settings.max_retries = 2
        settings.retry_backoff_factor = 0.01  # speed up test
        from gomag_mcp.client import GomagClient

        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return httpx.Response(429, json={"error": "rate limited"})
            return httpx.Response(200, json={"ok": True})

        async with respx.mock(base_url=settings.base_url) as mock:
            mock.get("/api/v1/brand/read/json").mock(side_effect=side_effect)
            async with GomagClient(settings) as client:
                result = await client.get("/api/v1/brand/read/json")

        assert result["http_status"] == 200
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_strips_none_query_params(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        import respx
        import httpx

        settings = _make_settings(tmp_path, monkeypatch)
        from gomag_mcp.client import GomagClient

        async with respx.mock(base_url=settings.base_url) as mock:
            route = mock.get("/api/v1/product/read/json").mock(
                return_value=httpx.Response(200, json={})
            )
            async with GomagClient(settings) as client:
                await client.get("/api/v1/product/read/json", params={"page": 1, "limit": None})

        url = str(route.calls[0].request.url)
        assert "page=1" in url
        assert "limit" not in url


# ---------------------------------------------------------------------------
# Context tests
# ---------------------------------------------------------------------------

class TestContext:
    def test_raises_before_init(self):
        from gomag_mcp.context import get_context, set_context
        set_context(None)
        with pytest.raises(RuntimeError, match="not been initialised"):
            get_context()

    def test_set_and_get(self, tmp_path: Path):
        from gomag_mcp.context import AppContext, get_context, set_context
        mock_ctx = AppContext(client=MagicMock(), audit=MagicMock())
        set_context(mock_ctx)
        assert get_context() is mock_ctx
        set_context(None)  # cleanup
