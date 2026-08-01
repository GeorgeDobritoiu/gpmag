"""Configuration for the separate, read-only Search Console MCP server."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SearchConsoleSettings(BaseSettings):
    """Load Search Console settings from ``SEARCH_CONSOLE_*`` variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SEARCH_CONSOLE_",
        case_sensitive=False,
        extra="ignore",
    )

    site_url: str = Field(
        description="Exact Search Console property URL or sc-domain identifier"
    )
    google_credentials_file: str = Field(
        description="Path to a Google service-account JSON secret file"
    )
