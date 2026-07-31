"""
Gomag MCP Server — entry point.

Start with:
    gomag-mcp                    # after `pip install -e .`
    python -m gomag_mcp.server   # from repo root with PYTHONPATH=src

Transport: stdio locally, or authenticated Streamable HTTP for ChatGPT/Render

Lifespan
--------
On startup:
  1. Load Settings from environment / .env
  2. Start GomagClient (httpx connection pool)
  3. Initialise AuditLogger (rotating JSON-Lines file + stderr)
  4. Set the shared AppContext so all tool handlers can call get_context()
  5. Register all tool modules

On shutdown:
  1. Flush + close AuditLogger handlers
  2. Close httpx connection pool
  3. Clear AppContext

Resources
---------
gomag://rate-limit   — Current rate-limit state from the most recent API call
gomag://health       — Server health (config reachability check)
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

from gomag_mcp.audit import AuditLogger
from gomag_mcp.auth import JWTTokenVerifier
from gomag_mcp.client import GomagClient
from gomag_mcp.config import Settings
from gomag_mcp.context import AppContext, get_context, set_context
from gomag_mcp.tools import attribute, awb, category, customer, invoice, misc, order, product, review, wishlist

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(server: FastMCP):
    """Initialise and tear down shared resources."""
    try:
        settings = Settings()  # type: ignore[call-arg]
    except Exception as exc:
        logger.error(
            "Failed to load configuration. "
            "Ensure GOMAG_API_KEY and GOMAG_API_SHOP environment variables are set. "
            "Error: %s",
            exc,
        )
        raise

    audit = AuditLogger(settings)
    client = GomagClient(settings)

    logger.info(
        "Starting Gomag MCP server (shop: %s, audit: %s)",
        settings.api_shop,
        settings.audit_log_file,
    )

    async with client:
        set_context(AppContext(client=client, audit=audit))
        logger.info("Gomag MCP server ready — %d tools registered", _count_tools(server))
        try:
            yield
        finally:
            set_context(None)
            logger.info("Gomag MCP server shut down")


def _count_tools(server: FastMCP) -> int:
    try:
        return len(server._tool_manager._tools)  # type: ignore[attr-defined]
    except Exception:
        return -1


# ---------------------------------------------------------------------------
# MCP application
# ---------------------------------------------------------------------------

_VALID_TRANSPORTS = {"stdio", "streamable-http"}


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for authenticated Streamable HTTP")
    return value


def _create_mcp() -> tuple[FastMCP, str]:
    transport = os.getenv("GOMAG_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in _VALID_TRANSPORTS:
        raise RuntimeError(
            "GOMAG_MCP_TRANSPORT must be 'stdio' or 'streamable-http'"
        )

    kwargs: dict[str, Any] = {}
    if transport == "streamable-http":
        public_url = _required_env("GOMAG_MCP_PUBLIC_URL").rstrip("/")
        issuer = _required_env("GOMAG_OAUTH_ISSUER_URL")
        resource_url = f"{public_url}/mcp"
        audience = os.getenv("GOMAG_OAUTH_AUDIENCE", resource_url).strip()
        jwks_url = os.getenv(
            "GOMAG_OAUTH_JWKS_URL",
            f"{issuer.rstrip('/')}/.well-known/jwks.json",
        ).strip()
        if not audience:
            raise RuntimeError("GOMAG_OAUTH_AUDIENCE cannot be empty")
        if not issuer.startswith("https://"):
            raise RuntimeError("GOMAG_OAUTH_ISSUER_URL must use HTTPS")
        if not jwks_url.startswith("https://"):
            raise RuntimeError("GOMAG_OAUTH_JWKS_URL must use HTTPS")
        required_scopes = [
            scope
            for scope in os.getenv("GOMAG_OAUTH_REQUIRED_SCOPES", "gomag:access").split()
            if scope
        ]
        hostname = urlparse(public_url).netloc
        if not hostname:
            raise RuntimeError("GOMAG_MCP_PUBLIC_URL must be an absolute HTTPS URL")
        if not public_url.startswith("https://"):
            raise RuntimeError("GOMAG_MCP_PUBLIC_URL must use HTTPS")

        kwargs.update(
            host="0.0.0.0",
            port=int(os.getenv("PORT", os.getenv("GOMAG_MCP_PORT", "8000"))),
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
                required_scopes=required_scopes,
            ),
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=[hostname, "localhost:*", "127.0.0.1:*"],
                allowed_origins=[],
            ),
        )

    server = FastMCP(
        name="gomag-api",
        instructions=(
            "This server exposes the Gomag Public API as MCP tools. "
            "Read current data before every write, explain the proposed change, "
            "and obtain user confirmation before any consequential action. "
            "All write operations are audit-logged. Use order_status_types() or "
            "awb_carrier_list() first to discover valid enum values."
        ),
        lifespan=_lifespan,
        **kwargs,
    )
    return server, transport


mcp, _transport = _create_mcp()


_READ_ONLY_TOOLS = {
    "attribute_list",
    "awb_carrier_list",
    "awb_list",
    "awb_print",
    "banner_list",
    "brand_list",
    "category_list",
    "currency_list",
    "customer_list",
    "customer_ordered_products",
    "fidelity_read",
    "filter_list",
    "order_list",
    "order_status_types",
    "payment_list",
    "product_list",
    "review_list",
    "wishlist_list",
}
_DESTRUCTIVE_TOOLS = {
    "awb_delete",
    "category_delete",
    "customer_change_password",
    "customer_delete_request",
    "invoice_cancel",
    "product_delete",
}


def _apply_tool_annotations(server: FastMCP, *, oauth_required: bool) -> None:
    tools = server._tool_manager._tools  # type: ignore[attr-defined]
    oauth_scopes = (
        server.settings.auth.required_scopes
        if oauth_required and server.settings.auth is not None
        else []
    )
    for name, tool in tools.items():
        read_only = name in _READ_ONLY_TOOLS
        destructive = name in _DESTRUCTIVE_TOOLS
        tool.annotations = ToolAnnotations(
            readOnlyHint=read_only,
            destructiveHint=destructive,
            idempotentHint=read_only,
            openWorldHint=True,
        )
        if oauth_required:
            tool.meta = {
                **(tool.meta or {}),
                "securitySchemes": [
                    {"type": "oauth2", "scopes": oauth_scopes},
                ],
            }


def _register_tools(server: FastMCP, *, oauth_required: bool) -> None:
    product.register(server)
    category.register(server)
    order.register(server)
    customer.register(server)
    awb.register(server)
    invoice.register(server)
    attribute.register(server)
    review.register(server)
    wishlist.register(server)
    misc.register(server)
    _apply_tool_annotations(server, oauth_required=oauth_required)


_register_tools(mcp, oauth_required=_transport == "streamable-http")


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("gomag://rate-limit")
async def rate_limit_resource() -> dict[str, Any]:
    """
    Current API rate-limit state (updated after every request).

    Returns the most recently observed values from the Gomag API response
    headers:
      - read_remaining  — read requests remaining before throttling
      - write_remaining — write requests remaining before throttling
      - read_burst      — max read burst capacity
      - write_burst     — max write burst capacity
      - read_rate       — read requests processed per second
      - write_rate      — write requests processed per second
    """
    rl = get_context().client.rate_limit
    return {
        "read_remaining": rl.read_remaining,
        "write_remaining": rl.write_remaining,
        "read_burst": rl.read_burst,
        "write_burst": rl.write_burst,
        "read_rate": rl.read_rate,
        "write_rate": rl.write_rate,
    }


@mcp.resource("gomag://health")
async def health_resource() -> dict[str, Any]:
    """
    Server health status.

    Returns configuration info (without secrets) and the rate-limit state.
    Use this to confirm the server started correctly and the API shop is set.
    """
    ctx = get_context()
    settings = ctx.client.settings
    rl = ctx.client.rate_limit
    return {
        "status": "ok",
        "api_shop": settings.api_shop,
        "base_url": settings.base_url,
        "user_agent": settings.user_agent,
        "rate_limit": {
            "read_remaining": rl.read_remaining,
            "write_remaining": rl.write_remaining,
        },
    }


@mcp.custom_route("/health", methods=["GET"])
async def http_health(_: Request) -> JSONResponse:
    """Unauthenticated liveness endpoint for Render; contains no shop data."""
    return JSONResponse(
        {
            "status": "ok",
            "transport": _transport,
            "authentication": "oauth" if _transport == "streamable-http" else "stdio",
        }
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the configured local or remote MCP transport."""
    mcp.run(transport=_transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
