"""
Invoice tools — /api/v1/invoice/*

Tools
-----
invoice_create   POST /api/v1/invoice/add/json
invoice_generate POST /api/v1/invoice/generate/json
invoice_cancel   POST /api/v1/invoice/cancel/json
"""

from __future__ import annotations

import json as _json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from gomag_mcp.context import get_context

_PATH_ADD = "/api/v1/invoice/add/json"
_PATH_GENERATE = "/api/v1/invoice/generate/json"
_PATH_CANCEL = "/api/v1/invoice/cancel/json"


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def invoice_create(data: str) -> dict[str, Any]:
        """
        Create (register) an invoice for an order.

        Parameters
        ----------
        data : JSON object with invoice details. Key fields:
               - orderId     (int)    internal order ID
               - number      (string) invoice number/series
               - date        (YYYY-MM-DD) invoice date
               - series      (string) invoice series (e.g. "FCT")
               - dueDate     (YYYY-MM-DD) payment due date (optional)

        Example
        -------
        '{"orderId": 100, "series": "FCT", "number": "0001234",
          "date": "2026-03-27"}'
        """
        ctx = get_context()
        async with ctx.audit.tool_call("invoice_create", {"data": "<payload>"}, "POST", _PATH_ADD) as ar:
            try:
                payload = _json.loads(data)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in `data` parameter: {exc}") from exc
            result = await ctx.client.post(_PATH_ADD, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def invoice_generate(
        order_id: int,
        series: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Auto-generate an invoice for an order using the store's configured
        invoicing settings.

        Parameters
        ----------
        order_id : Internal order ID.
        series   : Invoice series to use (optional; uses store default if omitted).
        """
        ctx = get_context()
        payload: dict[str, Any] = {"orderId": order_id}
        if series is not None:
            payload["series"] = series

        params = {"order_id": order_id}
        async with ctx.audit.tool_call("invoice_generate", params, "POST", _PATH_GENERATE) as ar:
            result = await ctx.client.post(_PATH_GENERATE, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def invoice_cancel(invoice_id: int) -> dict[str, Any]:
        """
        Cancel (void) an invoice.

        Parameters
        ----------
        invoice_id : Internal invoice ID to cancel.
        """
        ctx = get_context()
        payload = {"id": invoice_id}
        async with ctx.audit.tool_call("invoice_cancel", {"invoice_id": invoice_id}, "POST", _PATH_CANCEL) as ar:
            result = await ctx.client.post(_PATH_CANCEL, payload=payload)
            ar.update(result)
            return result["data"]
