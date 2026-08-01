"""Shared lifecycle context for the Google Analytics MCP tools."""

from dataclasses import dataclass

from gomag_mcp.analytics_client import AnalyticsClient


@dataclass(slots=True)
class AnalyticsContext:
    client: AnalyticsClient


_context: AnalyticsContext | None = None


def set_analytics_context(context: AnalyticsContext | None) -> None:
    global _context
    _context = context


def get_analytics_context() -> AnalyticsContext:
    if _context is None:
        raise RuntimeError("Analytics context has not been initialised")
    return _context
