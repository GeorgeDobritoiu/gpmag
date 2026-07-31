"""
Miscellaneous reference-data and utility tools.

Tools
-----
currency_list  GET  /api/v1/currency/read/json
payment_list   GET  /api/v1/payment/read/json
brand_list     GET  /api/v1/brand/read/json
filter_list    GET  /api/v1/filter/read/json
banner_list    GET  /api/v1/banner/read/json
fidelity_read  POST /api/v1/fidelity/read/json
rulecart_add   POST /api/v1/rulecart/add/json
"""

from __future__ import annotations

import json as _json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from gomag_mcp.context import get_context


def register(mcp: FastMCP) -> None:

    # ------------------------------------------------------------------
    # Read-only reference data
    # ------------------------------------------------------------------

    @mcp.tool()
    async def currency_list() -> dict[str, Any]:
        """Return the list of currencies configured in the Gomag store."""
        ctx = get_context()
        path = "/api/v1/currency/read/json"
        async with ctx.audit.tool_call("currency_list", {}, "GET", path) as ar:
            result = await ctx.client.get(path)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def payment_list() -> dict[str, Any]:
        """Return the list of payment methods available in the store."""
        ctx = get_context()
        path = "/api/v1/payment/read/json"
        async with ctx.audit.tool_call("payment_list", {}, "GET", path) as ar:
            result = await ctx.client.get(path)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def brand_list(
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Return the list of brands (manufacturers) defined in the store.

        Parameters
        ----------
        page  : Page number.
        limit : Results per page (1–100).
        """
        ctx = get_context()
        path = "/api/v1/brand/read/json"
        params = {"page": page, "limit": limit}
        async with ctx.audit.tool_call("brand_list", params, "GET", path) as ar:
            result = await ctx.client.get(path, params=params)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def filter_list(
        category_id: int,
        view: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Return the filterable attributes for a specific category.

        Parameters
        ----------
        category_id : Category ID to retrieve filters for (required).
        view        : Language code (e.g. "ro", "en").
        """
        ctx = get_context()
        path = "/api/v1/filter/read/json"
        params = {"category": category_id, "view": view}
        async with ctx.audit.tool_call("filter_list", params, "GET", path) as ar:
            result = await ctx.client.get(path, params=params)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def banner_list(
        position: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Return banners (promotional images/links) defined in the store.

        Parameters
        ----------
        position : Filter by banner position/zone (store-defined key).
        page     : Page number.
        limit    : Results per page.
        """
        ctx = get_context()
        path = "/api/v1/banner/read/json"
        params = {"position": position, "page": page, "limit": limit}
        async with ctx.audit.tool_call("banner_list", params, "GET", path) as ar:
            result = await ctx.client.get(path, params=params)
            ar.update(result)
            return result["data"]

    # ------------------------------------------------------------------
    # Write / action endpoints
    # ------------------------------------------------------------------

    @mcp.tool()
    async def fidelity_read(
        customer_id: Optional[int] = None,
        email: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Retrieve a customer's fidelity (loyalty) points balance.

        Parameters
        ----------
        customer_id : Customer's internal ID.
        email       : Customer e-mail (alternative identifier).
        """
        ctx = get_context()
        path = "/api/v1/fidelity/read/json"
        payload: dict[str, Any] = {}
        if customer_id is not None:
            payload["customerId"] = customer_id
        if email is not None:
            payload["email"] = email

        log_params = {"customer_id": customer_id, "email": email}
        async with ctx.audit.tool_call("fidelity_read", log_params, "POST", path) as ar:
            result = await ctx.client.post(path, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def rulecart_add(data: str) -> dict[str, Any]:
        """
        Create a shopping cart rule (discount / promotion).

        Parameters
        ----------
        data : JSON object describing the cart rule. Key fields:
               - name        (string) rule name
               - discount    (float)  discount amount or percentage
               - type        (string) "fixed" | "percent"
               - code        (string) voucher code (leave empty for auto-apply)
               - dateFrom    (YYYY-MM-DD) start date (optional)
               - dateTo      (YYYY-MM-DD) end date (optional)
               - usesPerCode (int) maximum total uses (0 = unlimited)
               - usesPerCustomer (int) maximum uses per customer (0 = unlimited)
               - enabled     (0 or 1)

        Example
        -------
        '{"name": "Spring Sale 10%", "discount": 10, "type": "percent",
          "code": "SPRING10", "enabled": 1, "usesPerCode": 100}'
        """
        ctx = get_context()
        path = "/api/v1/rulecart/add/json"
        async with ctx.audit.tool_call("rulecart_add", {"data": "<payload>"}, "POST", path) as ar:
            try:
                payload = _json.loads(data)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in `data` parameter: {exc}") from exc
            result = await ctx.client.post(path, payload=payload)
            ar.update(result)
            return result["data"]
