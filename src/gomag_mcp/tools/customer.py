"""
Customer tools — /api/v1/customer/*

Tools
-----
customer_list              GET  /api/v1/customer/read/json
customer_ordered_products  GET  /api/v1/customer/orderedproducts/json
customer_create            POST /api/v1/customer/add/json
customer_update            POST /api/v1/customer/update/json
customer_login             POST /api/v1/customer/login/json
customer_change_password   POST /api/v1/customer/passwordchange/json
customer_password_recovery POST /api/v1/customer/passwordrecovery/json
customer_delete_request    POST /api/v1/customer/deleterequest/json
"""

from __future__ import annotations

import json as _json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from gomag_mcp.context import get_context

_PATH_READ = "/api/v1/customer/read/json"
_PATH_ORDERED = "/api/v1/customer/orderedproducts/json"
_PATH_ADD = "/api/v1/customer/add/json"
_PATH_UPDATE = "/api/v1/customer/update/json"
_PATH_LOGIN = "/api/v1/customer/login/json"
_PATH_PWD_CHANGE = "/api/v1/customer/passwordchange/json"
_PATH_PWD_RECOVERY = "/api/v1/customer/passwordrecovery/json"
_PATH_DELETE_REQ = "/api/v1/customer/deleterequest/json"


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def customer_list(
        id: Optional[int] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        updated: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        List customers registered in the Gomag store.

        Parameters
        ----------
        id      : Filter by internal customer ID.
        email   : Filter by e-mail address.
        phone   : Filter by phone number.
        updated : Filter customers modified on/after this date (YYYY-MM-DD).
        page    : Page number.
        limit   : Results per page (1–100).
        """
        ctx = get_context()
        params = {"id": id, "email": email, "phone": phone, "updated": updated, "page": page, "limit": limit}
        async with ctx.audit.tool_call("customer_list", params, "GET", _PATH_READ) as ar:
            result = await ctx.client.get(_PATH_READ, params=params)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def customer_ordered_products(
        customer_id: Optional[int] = None,
        email: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Get a list of products that a specific customer has ordered.

        Parameters
        ----------
        customer_id : Internal customer ID.
        email       : Customer e-mail (alternative to customer_id).
        page        : Page number.
        limit       : Results per page.
        """
        ctx = get_context()
        params = {"id": customer_id, "email": email, "page": page, "limit": limit}
        async with ctx.audit.tool_call("customer_ordered_products", params, "GET", _PATH_ORDERED) as ar:
            result = await ctx.client.get(_PATH_ORDERED, params=params)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def customer_create(
        email: str,
        firstname: str,
        lastname: str,
        password: str,
        confirm_password: str,
        phone: Optional[str] = None,
        newsletter: Optional[bool] = None,
    ) -> dict[str, Any]:
        """
        Create a new customer account.

        Parameters
        ----------
        email            : Customer e-mail address (unique).
        firstname        : First name.
        lastname         : Last name.
        password         : Account password (plain text — only use over HTTPS; never logged).
        confirm_password : Must match `password`.
        phone            : Optional phone number.
        newsletter       : Subscribe to newsletter (true/false).
        """
        ctx = get_context()
        payload: dict[str, Any] = {
            "email": email,
            "firstname": firstname,
            "lastname": lastname,
            "password": password,
            "confirmPassword": confirm_password,
        }
        if phone is not None:
            payload["phone"] = phone
        if newsletter is not None:
            payload["newsletter"] = newsletter

        # Log params without password
        log_params = {"email": email, "firstname": firstname, "lastname": lastname}
        async with ctx.audit.tool_call("customer_create", log_params, "POST", _PATH_ADD) as ar:
            result = await ctx.client.post(_PATH_ADD, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def customer_update(data: str) -> dict[str, Any]:
        """
        Update an existing customer's details.

        Parameters
        ----------
        data : JSON object with customer fields to update. Must include "id" or "email"
               to identify the customer, plus the fields to change.

        Example
        -------
        '{"id": 123, "phone": "0721000001", "newsletter": false}'
        """
        ctx = get_context()
        async with ctx.audit.tool_call("customer_update", {"data": "<payload>"}, "POST", _PATH_UPDATE) as ar:
            try:
                payload = _json.loads(data)
            except _json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in `data` parameter: {exc}") from exc
            result = await ctx.client.post(_PATH_UPDATE, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def customer_login(
        email: str,
        password: str,
    ) -> dict[str, Any]:
        """
        Authenticate a customer and return session/token data.

        Parameters
        ----------
        email    : Customer e-mail address.
        password : Customer password (plain text — only use over HTTPS; never logged).

        Returns the API response which typically includes a session token or
        authentication confirmation.
        """
        ctx = get_context()
        payload = {"email": email, "password": password}
        log_params = {"email": email}
        async with ctx.audit.tool_call("customer_login", log_params, "POST", _PATH_LOGIN) as ar:
            result = await ctx.client.post(_PATH_LOGIN, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def customer_change_password(
        email: str,
        old_password: str,
        new_password: str,
        confirm_new_password: str,
    ) -> dict[str, Any]:
        """
        Change a customer's password.

        Parameters
        ----------
        email                : Customer e-mail address.
        old_password         : Current password for verification (plain text — never logged).
        new_password         : New password to set (plain text — never logged).
        confirm_new_password : Must match `new_password`.
        """
        ctx = get_context()
        payload = {
            "email": email,
            "oldPassword": old_password,
            "newPassword": new_password,
            "confirmNewPassword": confirm_new_password,
        }
        log_params = {"email": email}
        async with ctx.audit.tool_call("customer_change_password", log_params, "POST", _PATH_PWD_CHANGE) as ar:
            result = await ctx.client.post(_PATH_PWD_CHANGE, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def customer_password_recovery(email: str) -> dict[str, Any]:
        """
        Trigger a password recovery e-mail for a customer.

        Parameters
        ----------
        email : Customer e-mail address to send the recovery link to.
        """
        ctx = get_context()
        payload = {"email": email}
        async with ctx.audit.tool_call("customer_password_recovery", {"email": email}, "POST", _PATH_PWD_RECOVERY) as ar:
            result = await ctx.client.post(_PATH_PWD_RECOVERY, payload=payload)
            ar.update(result)
            return result["data"]

    @mcp.tool()
    async def customer_delete_request(email: str) -> dict[str, Any]:
        """
        Submit a GDPR account-deletion request for a customer.

        The customer will be flagged for deletion in the store's admin panel.
        This does NOT immediately delete the account.

        Parameters
        ----------
        email : Customer e-mail address.
        """
        ctx = get_context()
        payload = {"email": email}
        async with ctx.audit.tool_call("customer_delete_request", {"email": email}, "POST", _PATH_DELETE_REQ) as ar:
            result = await ctx.client.post(_PATH_DELETE_REQ, payload=payload)
            ar.update(result)
            return result["data"]
