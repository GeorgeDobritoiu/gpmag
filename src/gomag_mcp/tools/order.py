"""
Order tools — /api/v1/order/*

Tools
-----
order_list          GET  /api/v1/order/read/json
order_status_types  GET  /api/v1/order/status/read/json
order_create        POST /api/v1/order/add/json
order_update_status POST /api/v1/order/status/json
order_add_note      POST /api/v1/order/note/add/json
order_add_file      POST /api/v1/order/file/add/json
"""

from __future__ import annotations

import json as _json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from gomag_mcp.context import get_context

_PATH_READ = "/api/v1/order/read/json"
_PATH_STATUS_READ = "/api/v1/order/status/read/json"
_PATH_ADD = "/api/v1/order/add/json"
_PATH_STATUS = "/api/v1/order/status/json"
_PATH_NOTE = "/api/v1/order/note/add/json"
_PATH_FILE = "/api/v1/order/file/add/json"


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def order_list(
        id: Optional[int] = None,
        number: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        List orders from the Gomag store.

        Parameters
        ----------
        id        : Filter by internal order ID.
        number    : Filter by order number.
        status    : Filter by status key (e.g. "sale", "return", "cancel").
        date_from : Include orders placed on/after this date (YYYY-MM-DD).
        date_to   : Include orders placed on/before this date (YYYY-MM-DD).
        email     : Filter by customer e-mail.
        phone     : Filter by customer phone number.
        page      : Page number.
        limit     : Results per page (1–100).
        """
        ctx = get_context()
        params = {
            "id": id,
            "number": number,
            "status": status,
            "dateFrom": date_from,
            "dateTo": date_to,
            "email": email,
            "phone": phone,
            "page": page,
            "limit": limit,
        }
        async with ctx.audit.tool_call("order_list", params, "GET", _PATH_READ) as ar:
            result = await ctx.client.get(_PATH_READ, params=params)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def order_status_types() -> dict[str, Any]:
        """Return the list of available order status types defined in the store."""
        ctx = get_context()
        async with ctx.audit.tool_call("order_status_types", {}, "GET", _PATH_STATUS_READ) as ar:
            result = await ctx.client.get(_PATH_STATUS_READ)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def order_create(data: str) -> dict[str, Any]:
        """
        Create a new order.

        Parameters
        ----------
        data : JSON object describing the order. Key fields:
               - number         (string) order reference number
               - date           (YYYY-MM-DD)
               - payment        (string) payment method key
               - currency       (e.g. "RON")
               - shippingValue  (string/number)
               - subtotal       (string/number)
               - billing        (object: lastname, firstname, address, city, region, country, phone, email)
               - shipping       (object: same fields + zipcode)
               - products       (array: sku, name, price, quantity, tax, weight)
               - discounts      (array: name, voucher, value) — optional

        Example
        -------
        '{"number": "ORD-001", "date": "2026-03-27", "payment": "cod",
          "currency": "RON", "shippingValue": "20", "subtotal": "199.99",
          "billing": {"lastname": "Doe", "firstname": "John",
                      "address": "Str. Test 1", "city": "Bucharest",
                      "region": "Ilfov", "country": "Romania",
                      "phone": "0721000000", "email": "john@example.com"},
          "shipping": {"lastname": "Doe", "firstname": "John",
                       "address": "Str. Test 1", "city": "Bucharest",
                       "region": "Ilfov", "country": "Romania",
                       "zipcode": "010101", "phone": "0721000000",
                       "email": "john@example.com"},
          "products": [{"sku": "PROD-1", "name": "Product", "price": "199.99",
                        "quantity": "1", "tax": "19", "weight": "500"}]}'
        """
        ctx = get_context()
        async with ctx.audit.tool_call("order_create", {"data": "<payload>"}, "POST", _PATH_ADD) as ar:
            try:
                payload = _json.loads(data)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in `data` parameter: {exc}") from exc
            result = await ctx.client.post(_PATH_ADD, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def order_update_status(
        order_id: int,
        status: str,
        notify_customer: Optional[bool] = None,
        note: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Update the status of an existing order.

        Parameters
        ----------
        order_id        : Internal order ID.
        status          : New status key (e.g. "sale", "return", "cancel").
                          Use order_status_types() to see available values.
        notify_customer : Send a notification e-mail to the customer (true/false).
        note            : Optional internal note to attach to the status change.
        """
        ctx = get_context()
        payload: dict[str, Any] = {"id": order_id, "status": status}
        if notify_customer is not None:
            payload["notifyCustomer"] = notify_customer
        if note is not None:
            payload["note"] = note

        params = {"order_id": order_id, "status": status}
        async with ctx.audit.tool_call("order_update_status", params, "POST", _PATH_STATUS) as ar:
            result = await ctx.client.post(_PATH_STATUS, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def order_add_note(
        order_id: int,
        note: str,
        is_public: Optional[bool] = None,
    ) -> dict[str, Any]:
        """
        Add a note to an order.

        Parameters
        ----------
        order_id  : Internal order ID.
        note      : Note text.
        is_public : If true the note is visible to the customer (default false).
        """
        ctx = get_context()
        payload: dict[str, Any] = {"id": order_id, "note": note}
        if is_public is not None:
            payload["isPublic"] = is_public

        params = {"order_id": order_id}
        async with ctx.audit.tool_call("order_add_note", params, "POST", _PATH_NOTE) as ar:
            result = await ctx.client.post(_PATH_NOTE, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def order_add_file(
        order_id: int,
        file_url: str,
        file_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Attach a file (by URL) to an order.

        Parameters
        ----------
        order_id  : Internal order ID.
        file_url  : Publicly accessible URL of the file to attach.
        file_name : Display name for the file (optional, defaults to the URL filename).
        """
        ctx = get_context()
        payload: dict[str, Any] = {"id": order_id, "fileUrl": file_url}
        if file_name is not None:
            payload["fileName"] = file_name

        params = {"order_id": order_id, "file_url": file_url}
        async with ctx.audit.tool_call("order_add_file", params, "POST", _PATH_FILE) as ar:
            result = await ctx.client.post(_PATH_FILE, payload=payload)
            ar.update(result)
            return result["data"]
