"""Separate read-only Google Search Console MCP server for ChatGPT Business."""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

from gomag_mcp import search_console_tools
from gomag_mcp.auth import JWTTokenVerifier
from gomag_mcp.search_console_client import SearchConsoleClient
from gomag_mcp.search_console_config import SearchConsoleSettings
from gomag_mcp.search_console_context import (
    SearchConsoleContext,
    set_search_console_context,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)
_VALID_TRANSPORTS = {"stdio", "streamable-http"}


@asynccontextmanager
async def _lifespan(_: FastMCP):
    try:
        settings = SearchConsoleSettings()  # type: ignore[call-arg]
    except Exception as exc:
        logger.error(
            "SEARCH_CONSOLE_SITE_URL and SEARCH_CONSOLE_GOOGLE_CREDENTIALS_FILE are required: %s",
            type(exc).__name__,
        )
        raise
    client = SearchConsoleClient(settings)
    async with client:
        set_search_console_context(SearchConsoleContext(client=client))
        logger.info("Search Console MCP ready")
        try:
            yield
        finally:
            set_search_console_context(None)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for authenticated Streamable HTTP")
    return value


def _create_search_console_mcp() -> tuple[FastMCP, str]:
    transport = os.getenv("SEARCH_CONSOLE_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in _VALID_TRANSPORTS:
        raise RuntimeError(
            "SEARCH_CONSOLE_MCP_TRANSPORT must be 'stdio' or 'streamable-http'"
        )

    kwargs: dict[str, Any] = {}
    if transport == "streamable-http":
        public_url = _required_env("SEARCH_CONSOLE_MCP_PUBLIC_URL").rstrip("/")
        issuer = _required_env("SEARCH_CONSOLE_OAUTH_ISSUER_URL")
        resource_url = f"{public_url}/mcp"
        audience = os.getenv("SEARCH_CONSOLE_OAUTH_AUDIENCE", resource_url).strip()
        jwks_url = os.getenv(
            "SEARCH_CONSOLE_OAUTH_JWKS_URL",
            f"{issuer.rstrip('/')}/.well-known/jwks.json",
        ).strip()
        scopes = [
            scope
            for scope in os.getenv(
                "SEARCH_CONSOLE_OAUTH_REQUIRED_SCOPES", "search-console:read"
            ).split()
            if scope
        ]
        hostname = urlparse(public_url).netloc
        if not public_url.startswith("https://") or not hostname:
            raise RuntimeError(
                "SEARCH_CONSOLE_MCP_PUBLIC_URL must be an absolute HTTPS URL"
            )
        if not issuer.startswith("https://") or not jwks_url.startswith("https://"):
            raise RuntimeError("Search Console OAuth issuer and JWKS URLs must use HTTPS")
        kwargs.update(
            host="0.0.0.0",
            port=int(os.getenv("PORT", os.getenv("SEARCH_CONSOLE_MCP_PORT", "8000"))),
            streamable_http_path="/mcp",
            stateless_http=True,
            json_response=True,
            token_verifier=JWTTokenVerifier(
                issuer=issuer, audience=audience, jwks_url=jwks_url
            ),
            auth=AuthSettings(
                issuer_url=issuer,
                resource_server_url=resource_url,
                required_scopes=scopes,
            ),
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=[hostname, "localhost:*", "127.0.0.1:*"],
                allowed_origins=[],
            ),
        )

    server = FastMCP(
        name="drimus-search-console",
        instructions=(
            "Read aggregate Google Search Console performance for the Drimus website. "
            "Every tool is read-only. Never claim to modify Search Console or the site, "
            "and never request or expose Google credentials."
        ),
        lifespan=_lifespan,
        **kwargs,
    )
    return server, transport


def _register_search_console_tools(server: FastMCP, *, oauth_required: bool) -> None:
    search_console_tools.register(server)
    scopes = (
        server.settings.auth.required_scopes
        if oauth_required and server.settings.auth is not None
        else []
    )
    for tool in server._tool_manager._tools.values():  # type: ignore[attr-defined]
        tool.annotations = ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        )
        if oauth_required:
            tool.meta = {
                **(tool.meta or {}),
                "securitySchemes": [{"type": "oauth2", "scopes": scopes}],
            }


mcp, _transport = _create_search_console_mcp()
_register_search_console_tools(mcp, oauth_required=_transport == "streamable-http")


@mcp.custom_route("/health", methods=["GET"])
async def http_health(_: Request) -> JSONResponse:
    """Unauthenticated liveness endpoint without property or credential data."""
    return JSONResponse(
        {
            "status": "ok",
            "service": "drimus-search-console",
            "transport": _transport,
            "authentication": "oauth" if _transport == "streamable-http" else "stdio",
        }
    )


def main() -> None:
    mcp.run(transport=_transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
