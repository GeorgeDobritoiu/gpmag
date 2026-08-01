"""Tests for the separate read-only Google Analytics MCP server."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gomag_mcp.analytics_client import (
    AnalyticsClient,
    validate_date,
    validate_dimensions,
    validate_limit,
    validate_metrics,
)
from gomag_mcp.analytics_config import AnalyticsSettings


def _settings(tmp_path: Path) -> AnalyticsSettings:
    return AnalyticsSettings(
        property_id="449177742",
        google_credentials_file=str(tmp_path / "credentials.json"),
    )


def test_analytics_settings_use_dedicated_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANALYTICS_PROPERTY_ID", "449177742")
    monkeypatch.setenv(
        "ANALYTICS_GOOGLE_CREDENTIALS_FILE", str(tmp_path / "google.json")
    )
    settings = AnalyticsSettings()
    assert settings.property_id == "449177742"
    assert settings.google_credentials_file.endswith("google.json")


def test_analytics_validators_reject_unapproved_or_unbounded_queries() -> None:
    assert validate_date("28daysAgo") == "28daysAgo"
    assert validate_dimensions(["country", "country"]) == ["country"]
    assert validate_metrics(["sessions"]) == ["sessions"]
    assert validate_limit(1000) == 1000
    with pytest.raises(ValueError, match="Dates"):
        validate_date("last month")
    with pytest.raises(ValueError, match="Unsupported Analytics dimensions"):
        validate_dimensions(["userId"])
    with pytest.raises(ValueError, match="Unsupported Analytics metrics"):
        validate_metrics(["privateMetric"])
    with pytest.raises(ValueError, match="between 1 and 1000"):
        validate_limit(1001)


@pytest.mark.asyncio
async def test_analytics_client_builds_read_only_report(tmp_path: Path) -> None:
    client = AnalyticsClient(_settings(tmp_path))
    fake = AsyncMock()
    fake.run_report.return_value = SimpleNamespace(
        row_count=1,
        rows=[
            SimpleNamespace(
                dimension_values=[SimpleNamespace(value="Organic Search")],
                metric_values=[SimpleNamespace(value="42")],
            )
        ],
    )
    client._client = fake

    result = await client.run_report(
        start_date="7daysAgo",
        end_date="yesterday",
        dimensions=["sessionDefaultChannelGroup"],
        metrics=["sessions"],
        limit=10,
    )

    request = fake.run_report.await_args.kwargs["request"]
    assert request.property == "properties/449177742"
    assert request.limit == 10
    assert result["property_id"] == "449177742"
    assert result["rows"] == [
        {"sessionDefaultChannelGroup": "Organic Search", "sessions": "42"}
    ]


def test_analytics_tools_are_all_read_only() -> None:
    from gomag_mcp.analytics_server import mcp

    tools = mcp._tool_manager._tools
    assert set(tools) == {
        "analytics_custom_report",
        "analytics_overview",
        "analytics_products",
        "analytics_realtime",
        "analytics_schema",
        "analytics_top_pages",
        "analytics_traffic_sources",
    }
    assert all(tool.annotations.readOnlyHint is True for tool in tools.values())
    assert all(tool.annotations.destructiveHint is False for tool in tools.values())
    assert all(tool.annotations.idempotentHint is True for tool in tools.values())


def test_analytics_remote_transport_requires_oauth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gomag_mcp.analytics_server import _create_analytics_mcp

    monkeypatch.setenv("ANALYTICS_MCP_TRANSPORT", "streamable-http")
    monkeypatch.delenv("ANALYTICS_MCP_PUBLIC_URL", raising=False)
    monkeypatch.delenv("ANALYTICS_OAUTH_ISSUER_URL", raising=False)
    with pytest.raises(RuntimeError, match="ANALYTICS_MCP_PUBLIC_URL"):
        _create_analytics_mcp()


def test_analytics_remote_tools_require_read_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gomag_mcp.analytics_server import (
        _create_analytics_mcp,
        _register_analytics_tools,
    )

    monkeypatch.setenv("ANALYTICS_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("ANALYTICS_MCP_PUBLIC_URL", "https://analytics.example.com")
    monkeypatch.setenv("ANALYTICS_OAUTH_ISSUER_URL", "https://auth.example.com/")
    monkeypatch.setenv(
        "ANALYTICS_OAUTH_AUDIENCE", "https://analytics.example.com/mcp"
    )
    monkeypatch.setenv("ANALYTICS_OAUTH_REQUIRED_SCOPES", "analytics:read")
    server, transport = _create_analytics_mcp()
    _register_analytics_tools(server, oauth_required=True)
    assert transport == "streamable-http"
    assert server.settings.auth.required_scopes == ["analytics:read"]
    assert server._tool_manager._tools["analytics_overview"].meta[
        "securitySchemes"
    ] == [{"type": "oauth2", "scopes": ["analytics:read"]}]


@pytest.mark.asyncio
async def test_analytics_remote_endpoint_rejects_missing_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    from gomag_mcp.analytics_server import _create_analytics_mcp

    monkeypatch.setenv("ANALYTICS_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("ANALYTICS_MCP_PUBLIC_URL", "https://analytics.example.com")
    monkeypatch.setenv("ANALYTICS_OAUTH_ISSUER_URL", "https://auth.example.com/")
    monkeypatch.setenv(
        "ANALYTICS_OAUTH_AUDIENCE", "https://analytics.example.com/mcp"
    )
    server, _ = _create_analytics_mcp()
    transport = httpx.ASGITransport(app=server.streamable_http_app())
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://analytics.example.com",
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
    assert metadata.json()["resource"] == "https://analytics.example.com/mcp"
