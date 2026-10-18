"""Contract tests for the provider-neutral LLM interface."""

import pytest

from app.integrations.llm import (
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
)


class FakeLLMProvider:
    """Deterministic provider used to test the interface contract."""

    def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text=f"Generated response for: {request.user_prompt}",
            provider="fake",
            model="fake-model",
        )


def test_llm_request_accepts_valid_input() -> None:
    request = LLMRequest(
        system_prompt="Generate test candidates.",
        user_prompt="Analyze GET /users.",
        max_output_tokens=512,
    )

    assert request.max_output_tokens == 512
    assert request.user_prompt == "Analyze GET /users."


@pytest.mark.parametrize(
    ("system_prompt", "user_prompt", "max_output_tokens"),
    [
        ("", "Generate candidates.", 100),
        ("   ", "Generate candidates.", 100),
        ("System prompt.", "", 100),
        ("System prompt.", "   ", 100),
        ("System prompt.", "Generate candidates.", 0),
        ("System prompt.", "Generate candidates.", -1),
    ],
)
def test_llm_request_rejects_invalid_input(
    system_prompt: str,
    user_prompt: str,
    max_output_tokens: int,
) -> None:
    with pytest.raises(ValueError):
        LLMRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=max_output_tokens,
        )


def test_llm_request_uses_default_output_token_limit() -> None:
    request = LLMRequest(
        system_prompt="System prompt.",
        user_prompt="User prompt.",
    )

    assert request.max_output_tokens == 2048


def test_fake_provider_satisfies_provider_protocol() -> None:
    provider: LLMProvider = FakeLLMProvider()

    response = provider.generate(
        LLMRequest(
            system_prompt="Generate candidates.",
            user_prompt="Analyze GET /users.",
        )
    )

    assert response.provider == "fake"
    assert response.model == "fake-model"
    assert "Analyze GET /users." in response.text


def test_provider_error_is_a_runtime_error() -> None:
    error = LLMProviderError("Provider request failed.")

    assert isinstance(error, RuntimeError)
    assert str(error) == "Provider request failed."
