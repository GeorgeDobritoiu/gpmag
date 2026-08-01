"""Read-only MCP tools for aggregated Google Search Console data."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from gomag_mcp.search_console_client import (
    ALLOWED_AGGREGATION_TYPES,
    ALLOWED_DIMENSIONS,
    ALLOWED_FILTER_OPERATORS,
    ALLOWED_SEARCH_TYPES,
)
from gomag_mcp.search_console_context import get_search_console_context


def register(mcp: FastMCP) -> None:
    async def report(
        dimension: str | None,
        start_date: str | None,
        end_date: str | None,
        limit: int,
        search_type: str,
    ) -> dict[str, Any]:
        return await get_search_console_context().client.query(
            start_date=start_date,
            end_date=end_date,
            dimensions=[dimension] if dimension else [],
            search_type=search_type,
            limit=limit,
        )

    @mcp.tool()
    async def search_console_overview(
        start_date: str | None = None,
        end_date: str | None = None,
        search_type: str = "web",
    ) -> dict[str, Any]:
        """Total organic clicks, impressions, CTR, and average position."""
        return await report(None, start_date, end_date, 1, search_type)

    @mcp.tool()
    async def search_console_queries(
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        search_type: str = "web",
    ) -> dict[str, Any]:
        """Top Google Search queries and their aggregate performance."""
        return await report("query", start_date, end_date, limit, search_type)

    @mcp.tool()
    async def search_console_pages(
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        search_type: str = "web",
    ) -> dict[str, Any]:
        """Top landing pages by Google organic search performance."""
        return await report("page", start_date, end_date, limit, search_type)

    @mcp.tool()
    async def search_console_countries(
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        search_type: str = "web",
    ) -> dict[str, Any]:
        """Organic search performance grouped by country."""
        return await report("country", start_date, end_date, limit, search_type)

    @mcp.tool()
    async def search_console_devices(
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 10,
        search_type: str = "web",
    ) -> dict[str, Any]:
        """Organic search performance grouped by device category."""
        return await report("device", start_date, end_date, limit, search_type)

    @mcp.tool()
    async def search_console_search_appearance(
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        search_type: str = "web",
    ) -> dict[str, Any]:
        """Performance grouped by search appearance and rich-result feature."""
        return await report("searchAppearance", start_date, end_date, limit, search_type)

    @mcp.tool()
    async def search_console_custom_report(
        dimensions: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        search_type: str = "web",
        limit: int = 100,
        filter_dimension: str | None = None,
        filter_operator: str = "equals",
        filter_expression: str | None = None,
        aggregation_type: str = "auto",
    ) -> dict[str, Any]:
        """Run a bounded report using only approved dimensions and one filter.

        Call search_console_schema first to discover allowed values. The result
        contains aggregate performance only and this tool cannot modify data.
        """
        return await get_search_console_context().client.query(
            start_date=start_date,
            end_date=end_date,
            dimensions=dimensions or [],
            search_type=search_type,
            limit=limit,
            filter_dimension=filter_dimension,
            filter_operator=filter_operator,
            filter_expression=filter_expression,
            aggregation_type=aggregation_type,
        )

    @mcp.tool()
    async def search_console_schema() -> dict[str, list[str]]:
        """List approved dimensions, search types, filters, and aggregations."""
        return {
            "dimensions": sorted(ALLOWED_DIMENSIONS),
            "search_types": sorted(ALLOWED_SEARCH_TYPES),
            "filter_operators": sorted(ALLOWED_FILTER_OPERATORS),
            "aggregation_types": sorted(ALLOWED_AGGREGATION_TYPES),
            "metrics": ["clicks", "impressions", "ctr", "position"],
        }
