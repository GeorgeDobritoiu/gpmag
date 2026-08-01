"""Async, read-only client for aggregated Google Analytics 4 reports."""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Any, Iterable

from google.analytics.data_v1beta import BetaAnalyticsDataAsyncClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunRealtimeReportRequest,
    RunReportRequest,
)
from google.oauth2 import service_account

from gomag_mcp.analytics_config import AnalyticsSettings

_READ_ONLY_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
_DATE_RE = re.compile(
    r"^(today|yesterday|[0-9]{1,4}daysAgo|[0-9]{4}-[0-9]{2}-[0-9]{2})$"
)

ALLOWED_DIMENSIONS = frozenset(
    {
        "browser",
        "city",
        "country",
        "date",
        "deviceCategory",
        "eventName",
        "firstUserDefaultChannelGroup",
        "firstUserSourceMedium",
        "itemBrand",
        "itemCategory",
        "itemId",
        "itemName",
        "landingPagePlusQueryString",
        "newVsReturning",
        "operatingSystem",
        "pagePath",
        "pageTitle",
        "sessionCampaignName",
        "sessionDefaultChannelGroup",
        "sessionSourceMedium",
    }
)
ALLOWED_METRICS = frozenset(
    {
        "activeUsers",
        "averageSessionDuration",
        "bounceRate",
        "ecommercePurchases",
        "engagedSessions",
        "engagementRate",
        "eventCount",
        "itemRevenue",
        "itemsAddedToCart",
        "itemsPurchased",
        "itemsViewed",
        "keyEvents",
        "newUsers",
        "purchaseRevenue",
        "screenPageViews",
        "screenPageViewsPerSession",
        "sessionKeyEventRate",
        "sessions",
        "totalRevenue",
        "totalUsers",
        "transactions",
        "userEngagementDuration",
    }
)


class AnalyticsClient:
    """Run bounded GA4 Data API reports using service-account credentials."""

    def __init__(self, settings: AnalyticsSettings) -> None:
        self.settings = settings
        self._client: BetaAnalyticsDataAsyncClient | None = None

    async def __aenter__(self) -> "AnalyticsClient":
        credentials_path = Path(self.settings.google_credentials_file)
        if not credentials_path.is_file():
            raise RuntimeError("Google Analytics credentials file was not found")
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=[_READ_ONLY_SCOPE],
        )
        self._client = BetaAnalyticsDataAsyncClient(credentials=credentials)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client is None:
            return
        result = self._client.transport.close()
        if inspect.isawaitable(result):
            await result
        self._client = None

    async def run_report(
        self,
        *,
        start_date: str,
        end_date: str,
        dimensions: Iterable[str],
        metrics: Iterable[str],
        limit: int = 100,
    ) -> dict[str, Any]:
        """Return a standard aggregated report with validated fields."""
        client = self._require_client()
        dimension_names = validate_dimensions(dimensions)
        metric_names = validate_metrics(metrics)
        validate_date(start_date)
        validate_date(end_date)
        limit = validate_limit(limit)
        request = RunReportRequest(
            property=f"properties/{self.settings.property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[Dimension(name=name) for name in dimension_names],
            metrics=[Metric(name=name) for name in metric_names],
            limit=limit,
        )
        response = await client.run_report(request=request)
        return _serialise_report(
            response,
            property_id=self.settings.property_id,
            dimensions=dimension_names,
            metrics=metric_names,
        )

    async def run_realtime(self, *, limit: int = 100) -> dict[str, Any]:
        """Return a bounded, aggregated snapshot for the last 30 minutes."""
        client = self._require_client()
        dimensions = ["country", "deviceCategory"]
        metrics = ["activeUsers", "eventCount"]
        request = RunRealtimeReportRequest(
            property=f"properties/{self.settings.property_id}",
            dimensions=[Dimension(name=name) for name in dimensions],
            metrics=[Metric(name=name) for name in metrics],
            limit=validate_limit(limit),
        )
        response = await client.run_realtime_report(request=request)
        return _serialise_report(
            response,
            property_id=self.settings.property_id,
            dimensions=dimensions,
            metrics=metrics,
        )

    def _require_client(self) -> BetaAnalyticsDataAsyncClient:
        if self._client is None:
            raise RuntimeError("Analytics client has not been started")
        return self._client


def validate_date(value: str) -> str:
    if not _DATE_RE.fullmatch(value):
        raise ValueError(
            "Dates must be YYYY-MM-DD, today, yesterday, or a value such as 28daysAgo"
        )
    return value


def validate_dimensions(values: Iterable[str]) -> list[str]:
    names = list(dict.fromkeys(values))
    invalid = sorted(set(names) - ALLOWED_DIMENSIONS)
    if invalid:
        raise ValueError(f"Unsupported Analytics dimensions: {', '.join(invalid)}")
    if len(names) > 4:
        raise ValueError("A report may request at most 4 dimensions")
    return names


def validate_metrics(values: Iterable[str]) -> list[str]:
    names = list(dict.fromkeys(values))
    invalid = sorted(set(names) - ALLOWED_METRICS)
    if invalid:
        raise ValueError(f"Unsupported Analytics metrics: {', '.join(invalid)}")
    if not names:
        raise ValueError("At least one metric is required")
    if len(names) > 10:
        raise ValueError("A report may request at most 10 metrics")
    return names


def validate_limit(value: int) -> int:
    if not 1 <= value <= 1_000:
        raise ValueError("limit must be between 1 and 1000")
    return value


def _serialise_report(
    response: Any,
    *,
    property_id: str,
    dimensions: list[str],
    metrics: list[str],
) -> dict[str, Any]:
    rows = []
    for row in response.rows:
        item: dict[str, str] = {}
        item.update(
            (name, value.value)
            for name, value in zip(dimensions, row.dimension_values, strict=True)
        )
        item.update(
            (name, value.value)
            for name, value in zip(metrics, row.metric_values, strict=True)
        )
        rows.append(item)
    return {
        "property_id": property_id,
        "row_count": response.row_count,
        "dimensions": dimensions,
        "metrics": metrics,
        "rows": rows,
    }
