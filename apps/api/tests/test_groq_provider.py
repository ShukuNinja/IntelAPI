import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from app.integrations.llm.groq_provider import GROQ_BASE_URL, GroqProvider
from app.integrations.llm.models import LLMRequest
from app.integrations.llm.provider import LLMProviderError


def request() -> LLMRequest:
    return LLMRequest(system_prompt="System", user_prompt="Prompt", max_output_tokens=64)


def test_groq_provider_uses_compatible_endpoint_and_records_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )
    openai_module = ModuleType("openai")
    openai_factory = Mock(return_value=client)
    openai_module.OpenAI = openai_factory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openai", openai_module)

    provider = GroqProvider(api_key="private-test-key", model="test-model")
    response = provider.generate(request())

    openai_factory.assert_called_once_with(
        base_url=GROQ_BASE_URL,
        api_key="private-test-key",
        timeout=30.0,
        max_retries=1,
    )
    assert (response.provider, response.model, response.total_tokens) == ("groq", "test-model", 15)


def test_groq_provider_requests_json_schema_when_provided() -> None:
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))],
    )
    schema = {"type": "array", "items": {"type": "string"}}
    provider = GroqProvider(api_key="test-key", model="test-model", client=client)

    provider.generate(LLMRequest("System", "Prompt", 64, json_schema=schema))

    assert client.chat.completions.create.call_args.kwargs["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "api_test_candidates", "strict": True, "schema": schema},
    }


def test_groq_provider_sanitizes_errors() -> None:
    client = Mock()
    client.chat.completions.create.side_effect = RuntimeError("private provider response")
    provider = GroqProvider(api_key="private-test-key", model="test-model", client=client)

    with pytest.raises(LLMProviderError, match="could not complete the request") as error:
        provider.generate(request())

    assert "private provider response" not in str(error.value)
