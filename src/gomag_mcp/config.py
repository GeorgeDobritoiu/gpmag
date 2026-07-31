from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All configuration is loaded from environment variables (prefix: GOMAG_)
    or from a .env file in the current working directory.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GOMAG_",
        case_sensitive=False,
        extra="ignore",
    )

    # --- API credentials (required) ---
    api_key: str = Field(description="Gomag API key sent as the Apikey header on write requests")
    api_shop: str = Field(description="Gomag shop URL sent as the ApiShop header on every request")

    # --- API connection ---
    base_url: str = Field(default="https://api.gomag.ro", description="Gomag API base URL")
    user_agent: str = Field(default="GomagMCP/1.0", description="Custom User-Agent (must not be PostmanRuntime)")
    request_timeout: float = Field(default=30.0, description="HTTP request timeout in seconds")

    # --- Retry / rate-limit ---
    max_retries: int = Field(default=3, description="Maximum retry attempts for 429 / 5xx responses")
    retry_backoff_factor: float = Field(default=1.0, description="Base multiplier for exponential backoff (seconds)")

    # --- Audit logging ---
    audit_log_file: str = Field(default="gomag_audit.jsonl", description="Path to the rotating JSON-Lines audit log")
    audit_log_max_bytes: int = Field(default=10_485_760, description="Max size per audit log file (default 10 MB)")
    audit_log_backup_count: int = Field(default=5, description="Number of rotated backup files to keep")
    audit_log_to_stderr: bool = Field(default=True, description="Also emit audit events to stderr")
