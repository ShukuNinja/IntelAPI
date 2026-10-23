from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )
    app_name: str = "API Intelligence Platform API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://api_app:replace-this-local-password@localhost:5432/api_intelligence"
    )
    environment_encryption_key: SecretStr | None = None
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"]
    )
    allow_local_targets: bool = True
    allow_private_network_targets: bool = False
    http_connect_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    http_read_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    http_max_response_bytes: int = Field(default=2_000_000, ge=1024, le=10_000_000)


@lru_cache
def get_settings() -> Settings:
    return Settings()
