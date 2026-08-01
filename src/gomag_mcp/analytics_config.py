"""Configuration for the separate, read-only Google Analytics MCP server."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalyticsSettings(BaseSettings):
    """Load GA4 settings from ``ANALYTICS_*`` environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ANALYTICS_",
        case_sensitive=False,
        extra="ignore",
    )

    property_id: str = Field(description="Numeric Google Analytics 4 property ID")
    google_credentials_file: str = Field(
        description="Path to a Google service-account JSON secret file"
    )
