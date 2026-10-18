"""Factory for constructing the configured LLM provider."""

from app.core.config import Settings, get_settings
from app.integrations.llm.nvidia_provider import NVIDIAProvider
from app.integrations.llm.provider import LLMProvider


def create_llm_provider(settings: Settings | None = None) -> LLMProvider | None:
    """Return the configured provider, or None when credentials are absent."""
    configured_settings = settings if settings is not None else get_settings()
    api_key = configured_settings.nvidia_api_key

    if api_key is None:
        return None

    secret = api_key.get_secret_value().strip()
    if not secret:
        return None

    return NVIDIAProvider(
        api_key=secret,
        model=configured_settings.nvidia_model,
    )
