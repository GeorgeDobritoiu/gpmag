"""
Review tools — /api/v1/review/*

Tools
-----
review_list   GET  /api/v1/review/read/json
review_create POST /api/v1/review/write/json
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from gomag_mcp.context import get_context

_PATH_READ = "/api/v1/review/read/json"
_PATH_WRITE = "/api/v1/review/write/json"


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def review_list(
        product_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        approved: Optional[bool] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        List product reviews.

        Parameters
        ----------
        product_id  : Filter by product ID.
        customer_id : Filter by customer ID.
        approved    : Filter by approval status (true = approved only).
        page        : Page number.
        limit       : Results per page (1–100).
        """
        ctx = get_context()
        params = {
            "productId": product_id,
            "customerId": customer_id,
            "approved": approved,
            "page": page,
            "limit": limit,
        }
        async with ctx.audit.tool_call("review_list", params, "GET", _PATH_READ) as ar:
            result = await ctx.client.get(_PATH_READ, params=params)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def review_create(
        product_id: int,
        rating: int,
        title: str,
        content: str,
        author_name: str,
        author_email: str,
        approved: Optional[bool] = None,
    ) -> dict[str, Any]:
        """
        Submit a product review.

        Parameters
        ----------
        product_id   : ID of the product being reviewed.
        rating       : Star rating (1–5).
        title        : Short review title/summary.
        content      : Full review text.
        author_name  : Reviewer's display name.
        author_email : Reviewer's e-mail address.
        approved     : Set approval status immediately (true/false; defaults to
                       store's moderation setting).
        """
        if not (1 <= rating <= 5):
            raise ValueError(f"rating must be between 1 and 5, got {rating}")
        ctx = get_context()
        payload: dict[str, Any] = {
            "productId": product_id,
            "rating": rating,
            "title": title,
            "content": content,
            "authorName": author_name,
            "authorEmail": author_email,
        }
        if approved is not None:
            payload["approved"] = approved

        log_params = {"product_id": product_id, "rating": rating, "author_email": author_email}
        async with ctx.audit.tool_call("review_create", log_params, "POST", _PATH_WRITE) as ar:
            result = await ctx.client.post(_PATH_WRITE, payload=payload)
            ar.update(result)
            return result["data"]
