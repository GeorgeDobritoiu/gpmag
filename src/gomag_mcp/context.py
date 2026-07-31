"""
Module-level application context shared by all tool modules.

Holds the live GomagClient and AuditLogger instances.
The server's lifespan function calls set_context() on startup and
set_context(None) on shutdown.  All tool handlers call get_context()
to obtain the shared instances — no circular imports between server.py
and the tool modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from gomag_mcp.audit import AuditLogger
    from gomag_mcp.client import GomagClient


@dataclass
class AppContext:
    client: "GomagClient"
    audit: "AuditLogger"


_current: Optional[AppContext] = None


def set_context(ctx: Optional[AppContext]) -> None:
    """Called by server.py during lifespan setup / teardown."""
    global _current
    _current = ctx


def get_context() -> AppContext:
    """Return the live AppContext; raises RuntimeError if not initialised."""
    if _current is None:
        raise RuntimeError(
            "Application context has not been initialised. "
            "Ensure the MCP server lifespan is running."
        )
    return _current
