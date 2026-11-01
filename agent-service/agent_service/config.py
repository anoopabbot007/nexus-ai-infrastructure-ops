from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    llm_temperature: float = 0.0
    llm_timeout_seconds: float = 15.0
    workflow_timeout_seconds: float = 45.0
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"
    telemetry_mode: Literal["real", "mock"] = "real"
    prometheus_url: str = "http://prometheus:9090"
    loki_url: str = "http://loki:3100"
    mcp_server_url: str = "http://mcp-server:8001/mcp"
    investigation_lookback_minutes: int = Field(default=15, ge=1, le=1440)
    max_log_results: int = Field(default=100, ge=1, le=1000)
    query_step_seconds: int = Field(default=30, ge=5, le=300)
    telemetry_http_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    mcp_timeout_seconds: float = Field(default=20.0, gt=0, le=90)

    @property
    def provider(self) -> str:
        requested = self.llm_provider.strip().lower()
        if requested == "openai" and self.openai_api_key:
            return "openai"
        if requested in {"azure", "azure_openai"} and all(
            [self.azure_openai_endpoint, self.azure_openai_api_key, self.azure_openai_deployment]
        ):
            return "azure_openai"
        return "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()

