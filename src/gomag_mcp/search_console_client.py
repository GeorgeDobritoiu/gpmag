"""Async, read-only client for aggregated Google Search Console reports."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from google.oauth2 import service_account
from googleapiclient.discovery import build

from gomag_mcp.search_console_config import SearchConsoleSettings

READ_ONLY_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
ALLOWED_DIMENSIONS = frozenset(
    {"country", "date", "device", "page", "query", "searchAppearance"}
)
ALLOWED_SEARCH_TYPES = frozenset(
    {"discover", "googleNews", "image", "news", "video", "web"}
)
ALLOWED_FILTER_OPERATORS = frozenset(
    {"contains", "equals", "excludingRegex", "includingRegex", "notContains", "notEquals"}
)
ALLOWED_AGGREGATION_TYPES = frozenset({"auto", "byPage", "byProperty"})


class SearchConsoleClient:
    """Run bounded Search Analytics queries with read-only credentials."""

    def __init__(self, settings: SearchConsoleSettings) -> None:
        self.settings = settings
        self._service: Any | None = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "SearchConsoleClient":
        credentials_path = Path(self.settings.google_credentials_file)
        if not credentials_path.is_file():
            raise RuntimeError("Google Search Console credentials file was not found")
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path), scopes=[READ_ONLY_SCOPE]
        )
        self._service = await asyncio.to_thread(
            build,
            "searchconsole",
            "v1",
            credentials=credentials,
            cache_discovery=False,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        service, self._service = self._service, None
        if service is not None and hasattr(service, "close"):
            await asyncio.to_thread(service.close)

    async def query(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        dimensions: Iterable[str] = (),
        search_type: str = "web",
        limit: int = 100,
        filter_dimension: str | None = None,
        filter_operator: str = "equals",
        filter_expression: str | None = None,
        aggregation_type: str = "auto",
    ) -> dict[str, Any]:
        """Return a finalized Search Analytics report with validated fields."""
        service = self._require_service()
        start_date, end_date = normalise_dates(start_date, end_date)
        dimension_names = validate_dimensions(dimensions)
        search_type = validate_choice(search_type, ALLOWED_SEARCH_TYPES, "search_type")
        aggregation_type = validate_choice(
            aggregation_type, ALLOWED_AGGREGATION_TYPES, "aggregation_type"
        )
        limit = validate_limit(limit)
        body: dict[str, Any] = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimension_names,
            "type": search_type,
            "aggregationType": aggregation_type,
            "dataState": "final",
            "rowLimit": limit,
        }
        if filter_dimension is not None or filter_expression is not None:
            if not filter_dimension or filter_expression is None:
                raise ValueError("filter_dimension and filter_expression must be used together")
            validate_choice(filter_dimension, ALLOWED_DIMENSIONS, "filter_dimension")
            validate_choice(filter_operator, ALLOWED_FILTER_OPERATORS, "filter_operator")
            if not 1 <= len(filter_expression) <= 4096:
                raise ValueError("filter_expression must contain between 1 and 4096 characters")
            body["dimensionFilterGroups"] = [
                {
                    "groupType": "and",
                    "filters": [
                        {
                            "dimension": filter_dimension,
                            "operator": filter_operator,
                            "expression": filter_expression,
                        }
                    ],
                }
            ]

        async with self._lock:
            response = await asyncio.to_thread(
                lambda: service.searchanalytics()
                .query(siteUrl=self.settings.site_url, body=body)
                .execute()
            )
        return serialise_report(
            response,
            site_url=self.settings.site_url,
            start_date=start_date,
            end_date=end_date,
            dimensions=dimension_names,
            search_type=search_type,
        )

    def _require_service(self) -> Any:
        if self._service is None:
            raise RuntimeError("Search Console client has not been started")
        return self._service


def normalise_dates(start_date: str | None, end_date: str | None) -> tuple[str, str]:
    yesterday = date.today() - timedelta(days=1)
    end = parse_date(end_date or yesterday.isoformat())
    start = parse_date(start_date or (end - timedelta(days=27)).isoformat())
    if start > end:
        raise ValueError("start_date must be before or equal to end_date")
    return start.isoformat(), end.isoformat()


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Dates must use YYYY-MM-DD format") from exc


def validate_dimensions(values: Iterable[str]) -> list[str]:
    names = list(dict.fromkeys(values))
    invalid = sorted(set(names) - ALLOWED_DIMENSIONS)
    if invalid:
        raise ValueError(f"Unsupported Search Console dimensions: {', '.join(invalid)}")
    if len(names) > 3:
        raise ValueError("A report may request at most 3 dimensions")
    return names


def validate_choice(value: str, allowed: frozenset[str], name: str) -> str:
    if value not in allowed:
        raise ValueError(f"Unsupported {name}: {value}")
    return value


def validate_limit(value: int) -> int:
    if not 1 <= value <= 1_000:
        raise ValueError("limit must be between 1 and 1000")
    return value


def serialise_report(
    response: dict[str, Any],
    *,
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: list[str],
    search_type: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for source in response.get("rows", []):
        item = dict(zip(dimensions, source.get("keys", []), strict=False))
        item.update(
            clicks=source.get("clicks", 0),
            impressions=source.get("impressions", 0),
            ctr=source.get("ctr", 0),
            position=source.get("position", 0),
        )
        rows.append(item)
    return {
        "site_url": site_url,
        "start_date": start_date,
        "end_date": end_date,
        "search_type": search_type,
        "dimensions": dimensions,
        "row_count": len(rows),
        "aggregation_type": response.get("responseAggregationType"),
        "rows": rows,
    }
