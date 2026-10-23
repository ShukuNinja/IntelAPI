from pydantic import SecretStr

from app.core.config import Settings
from app.integrations.llm.factory import create_llm_provider, get_llm_provider_options


def test_factory_selects_groq_without_exposing_key(monkeypatch) -> None:
    from app.integrations.llm import factory

    seen = {}

    class FakeGroq:
        def __init__(self, *, api_key: str, model: str) -> None:
            seen.update(api_key=api_key, model=model)

    monkeypatch.setattr(factory, "GroqProvider", FakeGroq)
    settings = Settings(
        _env_file=None,
        llm_provider="nvidia",
        nvidia_api_key=SecretStr(""),
        groq_api_key=SecretStr("groq-test-key"),
        groq_model="configured-groq-model",
    )

    provider = create_llm_provider(settings, provider_name="groq")

    assert isinstance(provider, FakeGroq)
    assert seen == {"api_key": "groq-test-key", "model": "configured-groq-model"}
    options = get_llm_provider_options(settings)
    assert options["providers"] == [
        {"id": "nvidia", "configured": False, "model": "openai/gpt-oss-20b"},
        {"id": "groq", "configured": True, "model": "configured-groq-model"},
    ]
    assert "groq-test-key" not in str(options)
