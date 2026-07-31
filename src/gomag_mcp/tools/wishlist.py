"""
Wishlist (Produse Favorite) tools — /api/v1/wishlist/*

Tools
-----
wishlist_list   GET  /api/v1/wishlist/read/json
wishlist_add    POST /api/v1/wishlist/add/json
wishlist_remove POST /api/v1/wishlist/delete/json
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from gomag_mcp.context import get_context

_PATH_READ = "/api/v1/wishlist/read/json"
_PATH_ADD = "/api/v1/wishlist/add/json"
_PATH_DELETE = "/api/v1/wishlist/delete/json"


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def wishlist_list(
        customer_id: Optional[int] = None,
        email: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        List a customer's saved (wishlist) products.

        Parameters
        ----------
        customer_id : Customer's internal ID.
        email       : Customer e-mail (alternative identifier).
        page        : Page number.
        limit       : Results per page (1–100).
        """
        ctx = get_context()
        params = {"customerId": customer_id, "email": email, "page": page, "limit": limit}
        async with ctx.audit.tool_call("wishlist_list", params, "GET", _PATH_READ) as ar:
            result = await ctx.client.get(_PATH_READ, params=params)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def wishlist_add(
        customer_id: int,
        product_id: int,
    ) -> dict[str, Any]:
        """
        Add a product to a customer's wishlist.

        Parameters
        ----------
        customer_id : Customer's internal ID.
        product_id  : Product's internal ID.
        """
        ctx = get_context()
        payload = {"customerId": customer_id, "productId": product_id}
        params = {"customer_id": customer_id, "product_id": product_id}
        async with ctx.audit.tool_call("wishlist_add", params, "POST", _PATH_ADD) as ar:
            result = await ctx.client.post(_PATH_ADD, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def wishlist_remove(
        customer_id: int,
        product_id: int,
    ) -> dict[str, Any]:
        """
        Remove a product from a customer's wishlist.

        Parameters
        ----------
        customer_id : Customer's internal ID.
        product_id  : Product's internal ID.
        """
        ctx = get_context()
        payload = {"customerId": customer_id, "productId": product_id}
        params = {"customer_id": customer_id, "product_id": product_id}
        async with ctx.audit.tool_call("wishlist_remove", params, "POST", _PATH_DELETE) as ar:
            result = await ctx.client.post(_PATH_DELETE, payload=payload)
            ar.update(result)
            return result["data"]
