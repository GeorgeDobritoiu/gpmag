"""
Attribute tools — /api/v1/attribute/*

Tools
-----
attribute_list   GET  /api/v1/attribute/read/json
attribute_create POST /api/v1/attribute/write/json
attribute_update POST /api/v1/attribute/patch/json
"""

from __future__ import annotations

import json as _json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from gomag_mcp.context import get_context

_PATH_READ = "/api/v1/attribute/read/json"
_PATH_WRITE = "/api/v1/attribute/write/json"
_PATH_PATCH = "/api/v1/attribute/patch/json"


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def attribute_list(
        id: Optional[int] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        List product attributes defined in the store.

        Parameters
        ----------
        id    : Filter by specific attribute ID.
        page  : Page number.
        limit : Results per page (1–100).
        """
        ctx = get_context()
        params = {"id": id, "page": page, "limit": limit}
        async with ctx.audit.tool_call("attribute_list", params, "GET", _PATH_READ) as ar:
            result = await ctx.client.get(_PATH_READ, params=params)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def attribute_create(data: str) -> dict[str, Any]:
        """
        Create one or more product attributes.

        Parameters
        ----------
        data : JSON array of attribute objects. Each object may include:
               - name   (dict, keyed by language e.g. {"ro": "Culoare", "en": "Color"})
               - type   (string) attribute type (e.g. "select", "text", "multiselect")
               - values (array of value objects, each with a localised "name" dict)

        Example
        -------
        '[{"name": {"ro": "Culoare", "en": "Color"}, "type": "select",
           "values": [{"name": {"ro": "Rosu", "en": "Red"}},
                      {"name": {"ro": "Albastru", "en": "Blue"}}]}]'
        """
        ctx = get_context()
        async with ctx.audit.tool_call("attribute_create", {"data": "<payload>"}, "POST", _PATH_WRITE) as ar:
            try:
                payload = _json.loads(data)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in `data` parameter: {exc}") from exc
            result = await ctx.client.post(_PATH_WRITE, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def attribute_update(data: str) -> dict[str, Any]:
        """
        Update (patch) existing product attributes.

        Parameters
        ----------
        data : JSON array of partial attribute objects. Must include "id" plus
               the fields to update.

        Example
        -------
        '[{"id": 5, "name": {"ro": "Marime", "en": "Size"}}]'
        """
        ctx = get_context()
        async with ctx.audit.tool_call("attribute_update", {"data": "<payload>"}, "POST", _PATH_PATCH) as ar:
            try:
                payload = _json.loads(data)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in `data` parameter: {exc}") from exc
            result = await ctx.client.post(_PATH_PATCH, payload=payload)
            ar.update(result)
            return result["data"]
