"""Shared lifecycle context for Search Console MCP tools."""

from dataclasses import dataclass

from gomag_mcp.search_console_client import SearchConsoleClient


@dataclass(slots=True)
class SearchConsoleContext:
    client: SearchConsoleClient


_context: SearchConsoleContext | None = None


def set_search_console_context(context: SearchConsoleContext | None) -> None:
    global _context
    _context = context


def get_search_console_context() -> SearchConsoleContext:
    if _context is None:
        raise RuntimeError("Search Console context has not been initialised")
    return _context
