"""Read-only MCP tools for aggregated Google Analytics 4 data."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from gomag_mcp.analytics_client import ALLOWED_DIMENSIONS, ALLOWED_METRICS
from gomag_mcp.analytics_context import get_analytics_context


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def analytics_overview(
        start_date: str = "28daysAgo",
        end_date: str = "yesterday",
    ) -> dict[str, Any]:
        """Aggregated GA4 users, sessions, engagement, conversions, and revenue."""
        return await get_analytics_context().client.run_report(
            start_date=start_date,
            end_date=end_date,
            dimensions=[],
            metrics=[
                "activeUsers",
                "newUsers",
                "sessions",
                "engagedSessions",
                "engagementRate",
                "keyEvents",
                "ecommercePurchases",
                "purchaseRevenue",
                "totalRevenue",
            ],
            limit=1,
        )

    @mcp.tool()
    async def analytics_traffic_sources(
        start_date: str = "28daysAgo",
        end_date: str = "yesterday",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Traffic acquisition grouped by GA4 channel and source/medium."""
        return await get_analytics_context().client.run_report(
            start_date=start_date,
            end_date=end_date,
            dimensions=["sessionDefaultChannelGroup", "sessionSourceMedium"],
            metrics=[
                "sessions",
                "activeUsers",
                "engagedSessions",
                "keyEvents",
                "totalRevenue",
            ],
            limit=limit,
        )

    @mcp.tool()
    async def analytics_top_pages(
        start_date: str = "28daysAgo",
        end_date: str = "yesterday",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Top site pages by views, users, engagement, and key events."""
        return await get_analytics_context().client.run_report(
            start_date=start_date,
            end_date=end_date,
            dimensions=["pagePath", "pageTitle"],
            metrics=[
                "screenPageViews",
                "activeUsers",
                "userEngagementDuration",
                "keyEvents",
            ],
            limit=limit,
        )

    @mcp.tool()
    async def analytics_products(
        start_date: str = "28daysAgo",
        end_date: str = "yesterday",
        limit: int = 100,
    ) -> dict[str, Any]:
        """GA4 ecommerce item views, carts, purchases, and item revenue."""
        return await get_analytics_context().client.run_report(
            start_date=start_date,
            end_date=end_date,
            dimensions=["itemId", "itemName"],
            metrics=["itemsViewed", "itemsAddedToCart", "itemsPurchased", "itemRevenue"],
            limit=limit,
        )

    @mcp.tool()
    async def analytics_realtime(limit: int = 100) -> dict[str, Any]:
        """Aggregated active users and events from the last 30 minutes."""
        return await get_analytics_context().client.run_realtime(limit=limit)

    @mcp.tool()
    async def analytics_custom_report(
        metrics: list[str],
        dimensions: list[str] | None = None,
        start_date: str = "28daysAgo",
        end_date: str = "yesterday",
        limit: int = 100,
    ) -> dict[str, Any]:
        """Run a bounded GA4 report with approved dimensions and metrics.

        Call analytics_schema first to discover allowed fields. This tool never
        requests user-level identifiers and cannot modify Analytics data.
        """
        return await get_analytics_context().client.run_report(
            start_date=start_date,
            end_date=end_date,
            dimensions=dimensions or [],
            metrics=metrics,
            limit=limit,
        )

    @mcp.tool()
    async def analytics_schema() -> dict[str, list[str]]:
        """List dimensions and metrics approved for custom GA4 reports."""
        return {
            "dimensions": sorted(ALLOWED_DIMENSIONS),
            "metrics": sorted(ALLOWED_METRICS),
        }
