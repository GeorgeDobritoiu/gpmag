"""
Async HTTP client for the Gomag Public API.

Key behaviours
--------------
- GET  → query parameters (None values are stripped)
- POST → multipart/form-data with a single `data` field containing the JSON-
         serialised payload (as required by the Gomag API)
- Auth → ApiShop and Apikey headers on every request
- User-Agent → custom (Gomag rejects the default PostmanRuntime value)
- Retry → exponential back-off for HTTP 429 and 5xx responses
- Rate limits → response headers are parsed and exposed on the client instance

Rate-limit headers (Leaky-Bucket algorithm)
-------------------------------------------
Api-RateLimit-Read-Remaining  / Api-RateLimit-Write-Remaining
Api-RateLimit-Read-Burst      / Api-RateLimit-Write-Burst
Api-RateLimit-Read            / Api-RateLimit-Write
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from gomag_mcp.config import Settings

logger = logging.getLogger(__name__)

# HTTP status codes that are worth retrying
_RETRYABLE = frozenset({429, 500, 502, 503, 504})


@dataclass
class RateLimitState:
    read_remaining: Optional[int] = field(default=None)
    write_remaining: Optional[int] = field(default=None)
    read_burst: Optional[int] = field(default=None)
    write_burst: Optional[int] = field(default=None)
    read_rate: Optional[float] = field(default=None)
    write_rate: Optional[float] = field(default=None)

    def update_from_headers(self, headers: httpx.Headers) -> None:
        def _int(key: str) -> Optional[int]:
            val = headers.get(key)
            return int(val) if val is not None else None

        def _float(key: str) -> Optional[float]:
            val = headers.get(key)
            return float(val) if val is not None else None

        if (v := _int("Api-RateLimit-Read-Remaining")) is not None:
            self.read_remaining = v
        if (v := _int("Api-RateLimit-Write-Remaining")) is not None:
            self.write_remaining = v
        if (v := _int("Api-RateLimit-Read-Burst")) is not None:
            self.read_burst = v
        if (v := _int("Api-RateLimit-Write-Burst")) is not None:
            self.write_burst = v
        if (v := _float("Api-RateLimit-Read")) is not None:
            self.read_rate = v
        if (v := _float("Api-RateLimit-Write")) is not None:
            self.write_rate = v


class GomagAPIError(Exception):
    """Raised when the API returns a non-2xx HTTP response after retries."""

    def __init__(self, status_code: int, message: str, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class GomagNetworkError(Exception):
    """Raised when a network-level error persists after all retries."""


class GomagClient:
    """
    Async context-manager wrapper around httpx.AsyncClient.

    Usage
    -----
    async with GomagClient(settings) as client:
        data = await client.get("/api/v1/product/read/json", params={"page": 1})
        data = await client.post("/api/v1/product/write/json", payload=[{...}])
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.rate_limit = RateLimitState()
        self._http: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "GomagClient":
        self._http = httpx.AsyncClient(
            base_url=self._settings.base_url,
            timeout=self._settings.request_timeout,
            headers={
                "User-Agent": self._settings.user_agent,
                "ApiShop": self._settings.api_shop,
                "Apikey": self._settings.api_key,
            },
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30,
            ),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Perform a GET request with optional query parameters."""
        return await self._request("GET", path, query_params=params)

    async def post(
        self,
        path: str,
        payload: Any,
    ) -> dict[str, Any]:
        """
        Perform a POST request.

        The *payload* (dict or list) is JSON-serialised and sent as the value
        of the `data` form field — the format required by all Gomag write endpoints.
        """
        return await self._request("POST", path, post_payload=payload)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _assert_started(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError(
                "GomagClient is not started. Use it as an async context manager: "
                "`async with GomagClient(settings) as client: ...`"
            )
        return self._http

    async def _request(
        self,
        method: str,
        path: str,
        query_params: Optional[dict[str, Any]] = None,
        post_payload: Any = None,
    ) -> dict[str, Any]:
        http = self._assert_started()

        # Build kwargs
        kwargs: dict[str, Any] = {}
        if query_params:
            # Strip None values so optional params don't pollute the URL
            kwargs["params"] = {k: v for k, v in query_params.items() if v is not None}
        if post_payload is not None:
            # Gomag expects a single form field "data" whose value is a JSON string
            kwargs["data"] = {"data": json.dumps(post_payload, ensure_ascii=False)}

        last_exc: Optional[Exception] = None

        for attempt in range(self._settings.max_retries):
            try:
                response = await http.request(method, path, **kwargs)
                self.rate_limit.update_from_headers(response.headers)

                if response.status_code in _RETRYABLE and attempt < self._settings.max_retries - 1:
                    wait = self._backoff(attempt, is_rate_limit=(response.status_code == 429))
                    logger.warning(
                        "Retryable HTTP %d for %s %s — attempt %d/%d, sleeping %.1fs",
                        response.status_code,
                        method,
                        path,
                        attempt + 1,
                        self._settings.max_retries,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                if response.status_code in _RETRYABLE:
                    # Final attempt still retryable
                    raise GomagAPIError(
                        status_code=response.status_code,
                        message=f"HTTP {response.status_code} after {self._settings.max_retries} retries on {path}",
                        body=self._safe_json(response),
                    )

                response.raise_for_status()

                try:
                    body = response.json()
                except ValueError:
                    raise GomagAPIError(
                        status_code=response.status_code,
                        message=f"Non-JSON response from {path}",
                        body=response.text,
                    )

                return {
                    "data": body,
                    "http_status": response.status_code,
                    "rate_limit_remaining_read": self.rate_limit.read_remaining,
                    "rate_limit_remaining_write": self.rate_limit.write_remaining,
                }

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code not in _RETRYABLE:
                    raise GomagAPIError(
                        status_code=exc.response.status_code,
                        message=f"HTTP {exc.response.status_code}: {path}",
                        body=self._safe_json(exc.response),
                    ) from exc
                # Retryable — loop will handle
                if attempt == self._settings.max_retries - 1:
                    raise GomagAPIError(
                        status_code=exc.response.status_code,
                        message=f"HTTP {exc.response.status_code} after {self._settings.max_retries} retries",
                        body=self._safe_json(exc.response),
                    ) from exc
                wait = self._backoff(attempt, is_rate_limit=(exc.response.status_code == 429))
                await asyncio.sleep(wait)

            except httpx.RequestError as exc:
                last_exc = exc
                if attempt == self._settings.max_retries - 1:
                    raise GomagNetworkError(
                        f"Network error after {self._settings.max_retries} retries: {exc}"
                    ) from exc
                wait = self._backoff(attempt, is_rate_limit=False)
                await asyncio.sleep(wait)

        raise GomagNetworkError(f"All retries exhausted. Last error: {last_exc}")

    def _backoff(self, attempt: int, *, is_rate_limit: bool) -> float:
        base = self._settings.retry_backoff_factor * (2**attempt)
        if is_rate_limit:
            # Respect leaky-bucket by waiting at least 1 s on a 429
            return max(base, 1.0)
        return base

    @property
    def settings(self) -> Settings:
        """Read-only access to the client configuration."""
        return self._settings

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except Exception:
            return response.text
