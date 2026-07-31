"""
AWB (shipping / tracking) tools — /api/v1/awb/*

Tools
-----
awb_carrier_list  GET  /api/v1/awb/carrier/read/json
awb_list          GET  /api/v1/awb/read/json
awb_create        POST /api/v1/awb/add/json
awb_generate      POST /api/v1/awb/generate/json
awb_delete        POST /api/v1/awb/delete/json
awb_print         POST /api/v1/awb/print/json
awb_update_status POST /api/v1/awb/status/update/json
"""

from __future__ import annotations

import json as _json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from gomag_mcp.context import get_context

_PATH_CARRIER = "/api/v1/awb/carrier/read/json"
_PATH_READ = "/api/v1/awb/read/json"
_PATH_ADD = "/api/v1/awb/add/json"
_PATH_GENERATE = "/api/v1/awb/generate/json"
_PATH_DELETE = "/api/v1/awb/delete/json"
_PATH_PRINT = "/api/v1/awb/print/json"
_PATH_STATUS = "/api/v1/awb/status/update/json"


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def awb_carrier_list() -> dict[str, Any]:
        """
        Return the list of configured shipping carriers/couriers available in the store.
        """
        ctx = get_context()
        async with ctx.audit.tool_call("awb_carrier_list", {}, "GET", _PATH_CARRIER) as ar:
            result = await ctx.client.get(_PATH_CARRIER)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def awb_list(
        order_id: Optional[int] = None,
        awb_number: Optional[str] = None,
        carrier_id: Optional[int] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        List AWB (Air Waybill / tracking numbers) records.

        Parameters
        ----------
        order_id   : Filter by the order's internal ID.
        awb_number : Filter by specific AWB tracking number.
        carrier_id : Filter by carrier/courier ID.
        page       : Page number.
        limit      : Results per page (1–100).
        """
        ctx = get_context()
        params = {
            "orderId": order_id,
            "awbNumber": awb_number,
            "carrierId": carrier_id,
            "page": page,
            "limit": limit,
        }
        async with ctx.audit.tool_call("awb_list", params, "GET", _PATH_READ) as ar:
            result = await ctx.client.get(_PATH_READ, params=params)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def awb_create(data: str) -> dict[str, Any]:
        """
        Manually create an AWB record for an order.

        Parameters
        ----------
        data : JSON object with AWB details. Key fields:
               - orderId    (int)    internal order ID
               - carrierId  (int)    carrier ID from awb_carrier_list()
               - awbNumber  (string) tracking number issued by the carrier
               - packages   (int)    number of packages
               - weight     (float)  total shipment weight in kg

        Example
        -------
        '{"orderId": 100, "carrierId": 3, "awbNumber": "1Z999AA10123456784",
          "packages": 1, "weight": 1.5}'
        """
        ctx = get_context()
        async with ctx.audit.tool_call("awb_create", {"data": "<payload>"}, "POST", _PATH_ADD) as ar:
            try:
                payload = _json.loads(data)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in `data` parameter: {exc}") from exc
            result = await ctx.client.post(_PATH_ADD, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def awb_generate(data: str) -> dict[str, Any]:
        """
        Generate an AWB automatically through the carrier's integrated API.

        Parameters
        ----------
        data : JSON object with generation details. Key fields:
               - orderId    (int)  internal order ID
               - carrierId  (int)  carrier ID from awb_carrier_list()
               - packages   (int)  number of packages (default 1)
               - weight     (float) total weight in kg

        Example
        -------
        '{"orderId": 100, "carrierId": 3, "packages": 1, "weight": 2.0}'
        """
        ctx = get_context()
        async with ctx.audit.tool_call("awb_generate", {"data": "<payload>"}, "POST", _PATH_GENERATE) as ar:
            try:
                payload = _json.loads(data)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in `data` parameter: {exc}") from exc
            result = await ctx.client.post(_PATH_GENERATE, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def awb_delete(awb_id: int) -> dict[str, Any]:
        """
        Delete an AWB record.

        Parameters
        ----------
        awb_id : Internal AWB record ID.
        """
        ctx = get_context()
        payload = {"id": awb_id}
        async with ctx.audit.tool_call("awb_delete", {"awb_id": awb_id}, "POST", _PATH_DELETE) as ar:
            result = await ctx.client.post(_PATH_DELETE, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def awb_print(awb_id: int) -> dict[str, Any]:
        """
        Generate a printable shipping label (PDF or similar) for an AWB.

        Parameters
        ----------
        awb_id : Internal AWB record ID.

        Returns a response typically containing a URL or base64-encoded label content.
        """
        ctx = get_context()
        payload = {"id": awb_id}
        async with ctx.audit.tool_call("awb_print", {"awb_id": awb_id}, "POST", _PATH_PRINT) as ar:
            result = await ctx.client.post(_PATH_PRINT, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def awb_update_status(
        awb_id: int,
        status: str,
        update_order_status: Optional[bool] = None,
    ) -> dict[str, Any]:
        """
        Update the delivery status of an AWB.

        Parameters
        ----------
        awb_id               : Internal AWB record ID.
        status               : New status string (carrier-specific, e.g. "delivered",
                               "in_transit", "returned").
        update_order_status  : If true, also update the parent order's status accordingly.
        """
        ctx = get_context()
        payload: dict[str, Any] = {"id": awb_id, "status": status}
        if update_order_status is not None:
            payload["updateOrderStatus"] = update_order_status

        params = {"awb_id": awb_id, "status": status}
        async with ctx.audit.tool_call("awb_update_status", params, "POST", _PATH_STATUS) as ar:
            result = await ctx.client.post(_PATH_STATUS, payload=payload)
            ar.update(result)
            return result["data"]
