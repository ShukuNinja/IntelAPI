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

    with pytest.raises(
        LLMProviderError, match="could not complete the generation request"
    ) as error:
        provider.generate(request())

    assert "private provider response" not in str(error.value)


def test_groq_provider_preserves_safe_http_400_reason() -> None:
    class Provider400Error(Exception):
        status_code = 400
        code = "invalid_request_error"
        body = {"error": {"code": "invalid_request_error", "message": "Invalid JSON schema."}}

    client = Mock()
    client.chat.completions.create.side_effect = Provider400Error()
    provider = GroqProvider(api_key="test-key", model="test-model", client=client)

    with pytest.raises(LLMProviderError, match="Invalid JSON schema") as error:
        provider.generate(request())

    assert error.value.code == "invalid_request"


def test_groq_provider_maps_spend_limit_400_separately() -> None:
    class SpendLimitError(Exception):
        status_code = 400
        code = "blocked_api_access"
        body = {"error": {"code": "blocked_api_access", "message": "Spend limit reached."}}

    client = Mock()
    client.chat.completions.create.side_effect = SpendLimitError()
    provider = GroqProvider(api_key="test-key", model="test-model", client=client)

    with pytest.raises(LLMProviderError, match="spend limit") as error:
        provider.generate(request())

    assert error.value.code == "billing_limit_reached"


def test_groq_provider_maps_generated_json_validation_error() -> None:
    class JsonValidationError(Exception):
        status_code = 400
        code = "json_validate_failed"
        body = {
            "error": {
                "code": "json_validate_failed",
                "message": "Failed to validate JSON. Please adjust your prompt.",
                "failed_generation": "",
            }
        }

    client = Mock()
    client.chat.completions.create.side_effect = JsonValidationError()
    provider = GroqProvider(api_key="test-key", model="test-model", client=client)

    with pytest.raises(LLMProviderError, match="could not validate its generated JSON") as error:
        provider.generate(request())

    assert error.value.code == "json_validate_failed"
