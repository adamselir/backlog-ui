"""Environment-driven settings for backlog-ui."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    platform_base_url: str = Field(
        ..., description="Cluster-internal URL to homelab-platform REST API"
    )
    request_timeout_s: float = Field(5.0, description="httpx connect/read timeout in seconds")
    log_level: str = Field("INFO", description="Python log level")
    # CF Access service token (`backlog-ui`) for cross-app calls to homelab-platform.
    # Token authorizes only the `automation-backlog-ui` policy on the homelab-platform
    # Access app — does NOT have implicit access to /mcp or other apps.
    # Empty in tests; required in prod (deployment will fail at first request without).
    cf_access_client_id: str = Field("", description="CF-Access-Client-Id header value")
    cf_access_client_secret: str = Field("", description="CF-Access-Client-Secret header value")
