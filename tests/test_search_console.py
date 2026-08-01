"""Tests for the separate read-only Google Search Console MCP server."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gomag_mcp.search_console_client import (
    READ_ONLY_SCOPE,
    SearchConsoleClient,
    normalise_dates,
    validate_dimensions,
    validate_limit,
)
from gomag_mcp.search_console_config import SearchConsoleSettings


def _settings(tmp_path: Path) -> SearchConsoleSettings:
    return SearchConsoleSettings(
        site_url="sc-domain:example.com",
        google_credentials_file=str(tmp_path / "credentials.json"),
    )


def test_search_console_settings_use_dedicated_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEARCH_CONSOLE_SITE_URL", "sc-domain:example.com")
    monkeypatch.setenv(
        "SEARCH_CONSOLE_GOOGLE_CREDENTIALS_FILE", str(tmp_path / "google.json")
    )
    settings = SearchConsoleSettings()
    assert settings.site_url == "sc-domain:example.com"
    assert settings.google_credentials_file.endswith("google.json")


def test_search_console_validators_bound_reports() -> None:
    assert normalise_dates("2026-01-01", "2026-01-31") == (
        "2026-01-01",
        "2026-01-31",
    )
    assert validate_dimensions(["query", "query"]) == ["query"]
    assert validate_limit(1000) == 1000
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        normalise_dates("last month", "2026-01-31")
    with pytest.raises(ValueError, match="before or equal"):
        normalise_dates("2026-02-01", "2026-01-31")
    with pytest.raises(ValueError, match="Unsupported Search Console dimensions"):
        validate_dimensions(["userId"])
    with pytest.raises(ValueError, match="between 1 and 1000"):
        validate_limit(1001)


@pytest.mark.asyncio
async def test_search_console_client_builds_read_only_query(tmp_path: Path) -> None:
    client = SearchConsoleClient(_settings(tmp_path))
    execute = MagicMock(
        return_value={
            "rows": [
                {
                    "keys": ["softshell"],
                    "clicks": 12,
                    "impressions": 120,
                    "ctr": 0.1,
                    "position": 4.2,
                }
            ],
            "responseAggregationType": "byProperty",
        }
    )
    query = MagicMock(return_value=MagicMock(execute=execute))
    client._service = MagicMock(
        searchanalytics=MagicMock(return_value=MagicMock(query=query))
    )

    result = await client.query(
        start_date="2026-01-01",
        end_date="2026-01-31",
        dimensions=["query"],
        limit=10,
    )

    kwargs = query.call_args.kwargs
    assert kwargs["siteUrl"] == "sc-domain:example.com"
    assert kwargs["body"]["dataState"] == "final"
    assert kwargs["body"]["rowLimit"] == 10
    assert kwargs["body"]["dimensions"] == ["query"]
    assert result["rows"] == [
        {
            "query": "softshell",
            "clicks": 12,
            "impressions": 120,
            "ctr": 0.1,
            "position": 4.2,
        }
    ]


def test_search_console_scope_is_google_read_only() -> None:
    assert READ_ONLY_SCOPE == "https://www.googleapis.com/auth/webmasters.readonly"


def test_search_console_tools_are_all_read_only() -> None:
    from gomag_mcp.search_console_server import mcp

    tools = mcp._tool_manager._tools
    assert set(tools) == {
        "search_console_countries",
        "search_console_custom_report",
        "search_console_devices",
        "search_console_overview",
        "search_console_pages",
        "search_console_queries",
        "search_console_schema",
        "search_console_search_appearance",
    }
    assert all(tool.annotations.readOnlyHint is True for tool in tools.values())
    assert all(tool.annotations.destructiveHint is False for tool in tools.values())
    assert all(tool.annotations.idempotentHint is True for tool in tools.values())


def test_search_console_remote_transport_requires_oauth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gomag_mcp.search_console_server import _create_search_console_mcp

    monkeypatch.setenv("SEARCH_CONSOLE_MCP_TRANSPORT", "streamable-http")
    monkeypatch.delenv("SEARCH_CONSOLE_MCP_PUBLIC_URL", raising=False)
    monkeypatch.delenv("SEARCH_CONSOLE_OAUTH_ISSUER_URL", raising=False)
    with pytest.raises(RuntimeError, match="SEARCH_CONSOLE_MCP_PUBLIC_URL"):
        _create_search_console_mcp()


def test_search_console_remote_tools_require_read_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gomag_mcp.search_console_server import (
        _create_search_console_mcp,
        _register_search_console_tools,
    )

    monkeypatch.setenv("SEARCH_CONSOLE_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv(
        "SEARCH_CONSOLE_MCP_PUBLIC_URL", "https://search-console.example.com"
    )
    monkeypatch.setenv("SEARCH_CONSOLE_OAUTH_ISSUER_URL", "https://auth.example.com/")
    monkeypatch.setenv(
        "SEARCH_CONSOLE_OAUTH_AUDIENCE", "https://search-console.example.com/mcp"
    )
    server, transport = _create_search_console_mcp()
    _register_search_console_tools(server, oauth_required=True)
    assert transport == "streamable-http"
    assert server.settings.auth.required_scopes == ["search-console:read"]
    assert server._tool_manager._tools["search_console_overview"].meta[
        "securitySchemes"
    ] == [{"type": "oauth2", "scopes": ["search-console:read"]}]


@pytest.mark.asyncio
async def test_search_console_remote_endpoint_rejects_missing_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    from gomag_mcp.search_console_server import _create_search_console_mcp

    monkeypatch.setenv("SEARCH_CONSOLE_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv(
        "SEARCH_CONSOLE_MCP_PUBLIC_URL", "https://search-console.example.com"
    )
    monkeypatch.setenv("SEARCH_CONSOLE_OAUTH_ISSUER_URL", "https://auth.example.com/")
    monkeypatch.setenv(
        "SEARCH_CONSOLE_OAUTH_AUDIENCE", "https://search-console.example.com/mcp"
    )
    server, _ = _create_search_console_mcp()
    transport = httpx.ASGITransport(app=server.streamable_http_app())
    async with httpx.AsyncClient(
        transport=transport, base_url="https://search-console.example.com"
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
    assert metadata.json()["resource"] == "https://search-console.example.com/mcp"
