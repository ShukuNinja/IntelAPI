"""Factory for constructing the configured LLM provider."""

from app.core.config import Settings, get_settings
from app.integrations.llm.groq_provider import GroqProvider
from app.integrations.llm.nvidia_provider import NVIDIAProvider
from app.integrations.llm.provider import LLMProvider


def create_llm_provider(
    settings: Settings | None = None,
    *,
    provider_name: str | None = None,
    model_name: str | None = None,
) -> LLMProvider | None:
    """Return a configured provider; return None when its server key is absent."""
    configured_settings = settings if settings is not None else get_settings()
    selected_provider = provider_name or configured_settings.llm_provider
    if selected_provider == "nvidia":
        api_key = configured_settings.nvidia_api_key
        selected_model = model_name or configured_settings.nvidia_model
    elif selected_provider == "groq":
        api_key = configured_settings.groq_api_key
        selected_model = model_name or configured_settings.groq_model
    else:
        raise ValueError("Unsupported LLM provider.")

    if api_key is None:
        return None

    secret = api_key.get_secret_value().strip()
    if not secret:
        return None

    if selected_provider == "nvidia":
        return NVIDIAProvider(api_key=secret, model=selected_model)
    return GroqProvider(api_key=secret, model=selected_model)


def get_llm_provider_options(settings: Settings | None = None) -> dict[str, object]:
    """Return safe provider/model options without returning secret values."""
    configured_settings = settings if settings is not None else get_settings()
    providers = [
        {
            "id": "nvidia",
            "configured": bool(
                configured_settings.nvidia_api_key
                and configured_settings.nvidia_api_key.get_secret_value().strip()
            ),
            "model": configured_settings.nvidia_model,
        },
        {
            "id": "groq",
            "configured": bool(
                configured_settings.groq_api_key
                and configured_settings.groq_api_key.get_secret_value().strip()
            ),
            "model": configured_settings.groq_model,
        },
    ]
    return {
        "default_provider": configured_settings.llm_provider,
        "providers": providers,
    }
