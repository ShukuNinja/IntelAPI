from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Fernet key used to encrypt environment secrets at rest.
    secret_encryption_key: SecretStr | None = None

    # Optional OpenAI-compatible LLM providers. API keys stay on the backend.
    llm_provider: Literal["nvidia", "groq"] = "nvidia"
    nvidia_api_key: SecretStr | None = None
    nvidia_model: str = Field(default="openai/gpt-oss-20b", min_length=1, max_length=160)
    groq_api_key: SecretStr | None = None
    groq_model: str = Field(default="openai/gpt-oss-120b", min_length=1, max_length=160)
    llm_generation_max_attempts: int = Field(default=2, ge=1, le=3)

    app_name: str = "API Intelligence Platform API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://api_app:replace-this-local-password@localhost:5432/api_intelligence"
    )

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
    )

    # Google OAuth / ID-token verification.
    # This is a public OAuth client ID, not a client secret.
    google_client_id: str = ""

    # Application session policy.
    session_ttl_seconds: int = Field(
        default=604800,
        gt=0,
        le=2592000,
    )
    session_cookie_name: str = "session"


@lru_cache
def get_settings() -> Settings:
    return Settings()
