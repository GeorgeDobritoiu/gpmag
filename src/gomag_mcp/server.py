"""
Gomag MCP Server — entry point.

Start with:
    gomag-mcp                    # after `pip install -e .`
    python -m gomag_mcp.server   # from repo root with PYTHONPATH=src

Transport: stdio (standard MCP transport for Claude Desktop / claude CLI)

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
import sys
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from gomag_mcp.audit import AuditLogger
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

mcp = FastMCP(
    name="gomag-api",
    instructions=(
        "This server exposes the Gomag Public API as MCP tools. "
        "It covers products, categories, orders, customers, shipping (AWB), "
        "invoices, attributes, reviews, wishlists, and store configuration. "
        "All write operations are fully audit-logged. "
        "Use order_status_types() or awb_carrier_list() first to discover "
        "valid enum values before calling write tools."
    ),
    lifespan=_lifespan,
)

# Register all tool modules
product.register(mcp)
category.register(mcp)
order.register(mcp)
customer.register(mcp)
awb.register(mcp)
invoice.register(mcp)
attribute.register(mcp)
review.register(mcp)
wishlist.register(mcp)
misc.register(mcp)


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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
