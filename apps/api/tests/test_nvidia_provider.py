import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from app.integrations.llm.models import LLMRequest
from app.integrations.llm.nvidia_provider import NVIDIAProvider
from app.integrations.llm.provider import LLMProviderError


def make_request() -> LLMRequest:
    return LLMRequest(
        system_prompt="You are an API testing assistant.",
        user_prompt="Generate one test case.",
        max_output_tokens=100,
    )


def make_response(content: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ]
    )


def make_provider(client: Mock) -> NVIDIAProvider:
    return NVIDIAProvider(
        api_key="test-key",
        model="openai/gpt-oss-20b",
        client=client,
    )


def test_generate_returns_llm_response() -> None:
    client = Mock()
    client.chat.completions.create.return_value = make_response('{"name": "valid response"}')
    provider = make_provider(client)

    result = provider.generate(make_request())

    assert result.text == '{"name": "valid response"}'
    assert result.provider == "nvidia"
    assert result.model == "openai/gpt-oss-20b"

    client.chat.completions.create.assert_called_once_with(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": "You are an API testing assistant.",
            },
            {
                "role": "user",
                "content": "Generate one test case.",
            },
        ],
        max_tokens=100,
    )


def test_generate_rejects_empty_choices() -> None:
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(choices=[])
    provider = make_provider(client)

    with pytest.raises(LLMProviderError, match="no completion choices"):
        provider.generate(make_request())


@pytest.mark.parametrize("content", [None, "", "   "])
def test_generate_rejects_empty_content(
    content: str | None,
) -> None:
    client = Mock()
    client.chat.completions.create.return_value = make_response(content)
    provider = make_provider(client)

    with pytest.raises(LLMProviderError, match="no usable text"):
        provider.generate(make_request())


def test_generate_wraps_provider_errors() -> None:
    client = Mock()
    client.chat.completions.create.side_effect = RuntimeError("simulated provider failure")
    provider = make_provider(client)

    with pytest.raises(
        LLMProviderError,
        match="could not complete the request",
    ):
        provider.generate(make_request())


@pytest.mark.parametrize(
    ("api_key", "model"),
    [
        ("", "openai/gpt-oss-20b"),
        ("   ", "openai/gpt-oss-20b"),
        ("test-key", ""),
        ("test-key", "   "),
    ],
)
def test_constructor_rejects_blank_configuration(
    api_key: str,
    model: str,
) -> None:
    with pytest.raises(ValueError):
        NVIDIAProvider(api_key=api_key, model=model)


def test_constructor_configures_nvidia_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.integrations.llm.nvidia_provider import NVIDIA_BASE_URL

    mock_client = Mock()
    openai_module = ModuleType("openai")
    openai_factory = Mock(return_value=mock_client)
    openai_module.OpenAI = openai_factory  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "openai", openai_module)

    provider = NVIDIAProvider(
        api_key="test-key",
        model="openai/gpt-oss-20b",
    )

    openai_factory.assert_called_once_with(
        base_url=NVIDIA_BASE_URL,
        api_key="test-key",
    )
    assert provider._client is mock_client
