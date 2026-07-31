"""
Category tools — /api/v1/category/*

Tools
-----
category_list   GET  /api/v1/category/read/json
category_create POST /api/v1/category/write/json
category_update POST /api/v1/category/patch/json
category_delete POST /api/v1/category/delete/json
"""

from __future__ import annotations

import json as _json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from gomag_mcp.context import get_context

_PATH_READ = "/api/v1/category/read/json"
_PATH_WRITE = "/api/v1/category/write/json"
_PATH_PATCH = "/api/v1/category/patch/json"
_PATH_DELETE = "/api/v1/category/delete/json"


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def category_list(
        id: Optional[int] = None,
        parent_id: Optional[int] = None,
        view: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        List product categories.

        Parameters
        ----------
        id        : Filter by specific category ID.
        parent_id : Filter by parent category ID (0 = root categories).
        view      : Language code for localised names (e.g. "ro", "en").
        page      : Page number for pagination.
        limit     : Results per page (1–100).
        """
        ctx = get_context()
        params = {"id": id, "parentId": parent_id, "view": view, "page": page, "limit": limit}
        async with ctx.audit.tool_call("category_list", params, "GET", _PATH_READ) as ar:
            result = await ctx.client.get(_PATH_READ, params=params)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def category_create(data: str) -> dict[str, Any]:
        """
        Create one or more categories.

        Parameters
        ----------
        data : JSON array of category objects. Each object may include:
               - name        (dict, keyed by language e.g. {"ro": "...", "en": "..."})
               - description (dict, keyed by language)
               - parent_id   (int, ID of parent category; omit or 0 for root)
               - enabled     (0 or 1)
               - image       (URL string)

        Example
        -------
        '[{"name": {"ro": "Electrocasnice", "en": "Appliances"}, "enabled": 1}]'
        """
        ctx = get_context()
        async with ctx.audit.tool_call("category_create", {"data": "<payload>"}, "POST", _PATH_WRITE) as ar:
            try:
                payload = _json.loads(data)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in `data` parameter: {exc}") from exc
            result = await ctx.client.post(_PATH_WRITE, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def category_update(data: str) -> dict[str, Any]:
        """
        Update (patch) existing categories.

        Parameters
        ----------
        data : JSON array of partial category objects. Must include "id" plus
               the fields to change.

        Example
        -------
        '[{"id": 12, "name": {"ro": "Electronice", "en": "Electronics"}}]'
        """
        ctx = get_context()
        async with ctx.audit.tool_call("category_update", {"data": "<payload>"}, "POST", _PATH_PATCH) as ar:
            try:
                payload = _json.loads(data)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in `data` parameter: {exc}") from exc
            result = await ctx.client.post(_PATH_PATCH, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def category_delete(data: str) -> dict[str, Any]:
        """
        Delete categories. Only empty categories (no products, no sub-categories)
        can be deleted.

        Parameters
        ----------
        data : JSON array of objects with "id" fields.

        Example
        -------
        '[{"id": 12}]'
        """
        ctx = get_context()
        async with ctx.audit.tool_call("category_delete", {"data": "<payload>"}, "POST", _PATH_DELETE) as ar:
            try:
                payload = _json.loads(data)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in `data` parameter: {exc}") from exc
            result = await ctx.client.post(_PATH_DELETE, payload=payload)
            ar.update(result)
            return result["data"]
