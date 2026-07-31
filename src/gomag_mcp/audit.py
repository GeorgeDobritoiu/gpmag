"""
Structured audit logging for every MCP tool invocation.

Every tool call produces one JSON-Lines record written to:
  - a rotating file  (gomag_audit.jsonl by default)
  - stderr           (when GOMAG_AUDIT_LOG_TO_STDERR=true)

Log record schema
-----------------
{
  "timestamp":                  "2026-03-27T10:00:00.123456+00:00",
  "level":                      "AUDIT",
  "event_type":                 "tool_call" | "tool_error",
  "request_id":                 "<uuid4>",
  "tool_name":                  "product_list",
  "parameters":                 { ... sanitized ... },
  "api_method":                 "GET" | "POST",
  "api_path":                   "/api/v1/product/read/json",
  "http_status":                200,
  "duration_ms":                123.45,
  "success":                    true,
  "error_message":              null,
  "rate_limit_remaining_read":  45,
  "rate_limit_remaining_write": 10
}

Sensitive field names that are always redacted
-----------------------------------------------
password, confirmpassword, apikey, api_key, token, secret, authorization
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any, Optional

from gomag_mcp.config import Settings

# Fields whose values are replaced with "***REDACTED***" regardless of case
_SENSITIVE = frozenset(
    {"password", "confirmpassword", "apikey", "api_key", "token", "secret", "authorization"}
)


def _sanitize(params: Any) -> Any:
    """Return a deep copy of *params* with sensitive values masked."""
    if isinstance(params, dict):
        return {
            k: "***REDACTED***" if k.lower() in _SENSITIVE else _sanitize(v)
            for k, v in params.items()
        }
    if isinstance(params, list):
        return [_sanitize(item) for item in params]
    return params


class _JsonLinesFormatter(logging.Formatter):
    """Emits each log record as a single compact JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, Any] = getattr(record, "audit_event", {})
        return json.dumps(event, ensure_ascii=False, default=str)


class AuditLogger:
    """
    Thread-safe, async-compatible audit logger.

    Usage
    -----
    async with audit.tool_call("product_list", params, "GET", "/api/v1/...") as result:
        api_response = await client.get(...)
        result.update(
            http_status=api_response["http_status"],
            rate_limit_remaining_read=api_response.get("rate_limit_remaining_read"),
            rate_limit_remaining_write=api_response.get("rate_limit_remaining_write"),
        )
        return api_response["data"]
    # On exception the error is logged automatically and re-raised.
    """

    def __init__(self, settings: Settings) -> None:
        self._logger = self._build_logger(settings)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_logger(settings: Settings) -> logging.Logger:
        logger = logging.getLogger("gomag_mcp.audit")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        # Avoid duplicate handlers when tests re-initialise the logger
        if logger.handlers:
            logger.handlers.clear()

        formatter = _JsonLinesFormatter()

        file_handler = RotatingFileHandler(
            settings.audit_log_file,
            maxBytes=settings.audit_log_max_bytes,
            backupCount=settings.audit_log_backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        if settings.audit_log_to_stderr:
            stderr_handler = logging.StreamHandler()
            stderr_handler.setFormatter(formatter)
            logger.addHandler(stderr_handler)

        return logger

    def _emit(self, event: dict[str, Any]) -> None:
        record = logging.LogRecord(
            name="gomag_mcp.audit",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="",
            args=(),
            exc_info=None,
        )
        record.audit_event = event  # type: ignore[attr-defined]
        self._logger.handle(record)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def tool_call(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        api_method: str,
        api_path: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Async context manager that logs one audit record per tool invocation.

        The caller receives a mutable *result* dict and should populate it with:
          - http_status
          - rate_limit_remaining_read  (optional)
          - rate_limit_remaining_write (optional)

        On success  → event_type = "tool_call",  success = True
        On exception → event_type = "tool_error", success = False, error_message set
        """
        request_id = str(uuid.uuid4())
        start = time.monotonic()
        result: dict[str, Any] = {}

        try:
            yield result

            duration_ms = (time.monotonic() - start) * 1000
            self._emit(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "AUDIT",
                    "event_type": "tool_call",
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "parameters": _sanitize(parameters),
                    "api_method": api_method,
                    "api_path": api_path,
                    "http_status": result.get("http_status"),
                    "duration_ms": round(duration_ms, 3),
                    "success": True,
                    "error_message": None,
                    "rate_limit_remaining_read": result.get("rate_limit_remaining_read"),
                    "rate_limit_remaining_write": result.get("rate_limit_remaining_write"),
                }
            )

        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            self._emit(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "AUDIT",
                    "event_type": "tool_error",
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "parameters": _sanitize(parameters),
                    "api_method": api_method,
                    "api_path": api_path,
                    "http_status": result.get("http_status"),
                    "duration_ms": round(duration_ms, 3),
                    "success": False,
                    "error_message": str(exc),
                    "rate_limit_remaining_read": result.get("rate_limit_remaining_read"),
                    "rate_limit_remaining_write": result.get("rate_limit_remaining_write"),
                }
            )
            raise
