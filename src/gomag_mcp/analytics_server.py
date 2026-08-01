"""Separate read-only Google Analytics MCP server for ChatGPT Business."""

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

from gomag_mcp import analytics_tools
from gomag_mcp.analytics_client import AnalyticsClient
from gomag_mcp.analytics_config import AnalyticsSettings
from gomag_mcp.analytics_context import AnalyticsContext, set_analytics_context
from gomag_mcp.auth import JWTTokenVerifier

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
        settings = AnalyticsSettings()  # type: ignore[call-arg]
    except Exception as exc:
        logger.error(
            "ANALYTICS_PROPERTY_ID and ANALYTICS_GOOGLE_CREDENTIALS_FILE are required: %s",
            type(exc).__name__,
        )
        raise
    client = AnalyticsClient(settings)
    async with client:
        set_analytics_context(AnalyticsContext(client=client))
        logger.info("Google Analytics MCP ready for property %s", settings.property_id)
        try:
            yield
        finally:
            set_analytics_context(None)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for authenticated Streamable HTTP")
    return value


def _create_analytics_mcp() -> tuple[FastMCP, str]:
    transport = os.getenv("ANALYTICS_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in _VALID_TRANSPORTS:
        raise RuntimeError("ANALYTICS_MCP_TRANSPORT must be 'stdio' or 'streamable-http'")

    kwargs: dict[str, Any] = {}
    if transport == "streamable-http":
        public_url = _required_env("ANALYTICS_MCP_PUBLIC_URL").rstrip("/")
        issuer = _required_env("ANALYTICS_OAUTH_ISSUER_URL")
        resource_url = f"{public_url}/mcp"
        audience = os.getenv("ANALYTICS_OAUTH_AUDIENCE", resource_url).strip()
        jwks_url = os.getenv(
            "ANALYTICS_OAUTH_JWKS_URL",
            f"{issuer.rstrip('/')}/.well-known/jwks.json",
        ).strip()
        scopes = [
            scope
            for scope in os.getenv(
                "ANALYTICS_OAUTH_REQUIRED_SCOPES", "analytics:read"
            ).split()
            if scope
        ]
        hostname = urlparse(public_url).netloc
        if not public_url.startswith("https://") or not hostname:
            raise RuntimeError("ANALYTICS_MCP_PUBLIC_URL must be an absolute HTTPS URL")
        if not issuer.startswith("https://") or not jwks_url.startswith("https://"):
            raise RuntimeError("Analytics OAuth issuer and JWKS URLs must use HTTPS")
        kwargs.update(
            host="0.0.0.0",
            port=int(os.getenv("PORT", os.getenv("ANALYTICS_MCP_PORT", "8000"))),
            streamable_http_path="/mcp",
            stateless_http=True,
            json_response=True,
            token_verifier=JWTTokenVerifier(
                issuer=issuer,
                audience=audience,
                jwks_url=jwks_url,
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
        name="drimus-analytics",
        instructions=(
            "Read aggregated Google Analytics 4 data for the Drimus website. "
            "Every tool is read-only. Never claim to modify Analytics data and "
            "never request or expose user-level identifiers or credentials."
        ),
        lifespan=_lifespan,
        **kwargs,
    )
    return server, transport


def _register_analytics_tools(server: FastMCP, *, oauth_required: bool) -> None:
    analytics_tools.register(server)
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


mcp, _transport = _create_analytics_mcp()
_register_analytics_tools(mcp, oauth_required=_transport == "streamable-http")


@mcp.custom_route("/health", methods=["GET"])
async def http_health(_: Request) -> JSONResponse:
    """Unauthenticated liveness endpoint without Analytics data or identifiers."""
    return JSONResponse(
        {
            "status": "ok",
            "service": "drimus-analytics",
            "transport": _transport,
            "authentication": "oauth" if _transport == "streamable-http" else "stdio",
        }
    )


def main() -> None:
    mcp.run(transport=_transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
