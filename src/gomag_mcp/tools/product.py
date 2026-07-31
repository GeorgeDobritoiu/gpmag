"""
Product tools — /api/v1/product/*

Tools
-----
product_list            GET  /api/v1/product/read/json
product_create          POST /api/v1/product/write/json
product_update          POST /api/v1/product/patch/json
product_update_inventory POST /api/v1/product/inventory/json
product_delete          POST /api/v1/product/delete/json
"""

from __future__ import annotations

import json as _json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from gomag_mcp.context import get_context

_PATH_READ = "/api/v1/product/read/json"
_PATH_WRITE = "/api/v1/product/write/json"
_PATH_PATCH = "/api/v1/product/patch/json"
_PATH_INVENTORY = "/api/v1/product/inventory/json"
_PATH_DELETE = "/api/v1/product/delete/json"


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def product_list(
        page: Optional[int] = None,
        limit: Optional[int] = None,
        id: Optional[int] = None,
        sku: Optional[str] = None,
        category: Optional[int] = None,
        brand: Optional[int] = None,
        updated: Optional[str] = None,
        add_versions: Optional[bool] = None,
        include_files: Optional[bool] = None,
        include_videos: Optional[bool] = None,
        promo_tag: Optional[str] = None,
        view: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        List products from the Gomag store.

        Parameters
        ----------
        page         : Page number (pagination).
        limit        : Results per page (1–100).
        id           : Filter by internal product ID.
        sku          : Filter by product SKU/code.
        category     : Filter by category ID.
        brand        : Filter by brand ID.
        updated      : Filter products modified on/after this date (YYYY-MM-DD).
        add_versions : Include product variants/versions (true/false).
        include_files: Include attached files (true/false).
        include_videos: Include attached videos (true/false).
        promo_tag    : Filter by promotional tag key (e.g. "new", "recommended").
        view         : Language code for localised fields (e.g. "ro", "en", "hu").
        """
        ctx = get_context()
        params = {
            "page": page,
            "limit": limit,
            "id": id,
            "sku": sku,
            "category": category,
            "brand": brand,
            "updated": updated,
            "addVersions": add_versions,
            "includeFiles": include_files,
            "includeVideos": include_videos,
            "promoTag": promo_tag,
            "view": view,
        }
        async with ctx.audit.tool_call("product_list", params, "GET", _PATH_READ) as ar:
            result = await ctx.client.get(_PATH_READ, params=params)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def product_create(data: str) -> dict[str, Any]:
        """
        Create one or more products.

        Parameters
        ----------
        data : JSON array of product objects. Each object may include:
               - name (dict, keyed by language code e.g. {"ro": "...", "en": "..."})
               - description (dict, keyed by language)
               - enabled (0 or 1)
               - vat (VAT percentage, e.g. 19)
               - currency (e.g. "RON")
               - brand (brand name string)
               - categories (array of category path arrays)
               - versions (array of variant objects with sku, price, stock, weight, ean, ...)

        Example
        -------
        '[{"name": {"ro": "Produs test", "en": "Test product"}, "enabled": 1,
           "vat": 19, "currency": "RON",
           "versions": [{"sku": "TEST-001", "price": 99.99, "stock": 10}]}]'
        """
        ctx = get_context()
        async with ctx.audit.tool_call("product_create", {"data": "<payload>"}, "POST", _PATH_WRITE) as ar:
            try:
                payload = _json.loads(data)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in `data` parameter: {exc}") from exc
            result = await ctx.client.post(_PATH_WRITE, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def product_update(data: str) -> dict[str, Any]:
        """
        Update (patch) existing products.

        Parameters
        ----------
        data : JSON array of partial product objects. Must include an identifier
               field (id or sku) plus the fields to update.

        Example
        -------
        '[{"sku": "TEST-001", "versions": [{"sku": "TEST-001", "price": 79.99}]}]'
        """
        ctx = get_context()
        async with ctx.audit.tool_call("product_update", {"data": "<payload>"}, "POST", _PATH_PATCH) as ar:
            try:
                payload = _json.loads(data)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in `data` parameter: {exc}") from exc
            result = await ctx.client.post(_PATH_PATCH, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def product_update_inventory(data: str) -> dict[str, Any]:
        """
        Bulk-update product price and/or stock (inventory sync).

        Parameters
        ----------
        data : JSON array of inventory update objects, each containing:
               - sku      (required) product SKU
               - price    (optional) new price
               - stock    (optional) new stock quantity
               - specialPrice (optional) discounted price

        Example
        -------
        '[{"sku": "TEST-001", "price": 89.99, "stock": 50}]'
        """
        ctx = get_context()
        async with ctx.audit.tool_call("product_update_inventory", {"data": "<payload>"}, "POST", _PATH_INVENTORY) as ar:
            try:
                payload = _json.loads(data)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in `data` parameter: {exc}") from exc
            result = await ctx.client.post(_PATH_INVENTORY, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def product_delete(data: str) -> dict[str, Any]:
        """
        Delete products by SKU or ID.

        Parameters
        ----------
        data : JSON array of objects identifying the products to delete.
               Each object should contain either "id" or "sku".

        Example
        -------
        '[{"sku": "TEST-001"}, {"id": 42}]'
        """
        ctx = get_context()
        async with ctx.audit.tool_call("product_delete", {"data": "<payload>"}, "POST", _PATH_DELETE) as ar:
            try:
                payload = _json.loads(data)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in `data` parameter: {exc}") from exc
            result = await ctx.client.post(_PATH_DELETE, payload=payload)
            ar.update(result)
            return result["data"]
