"""Provider-independent request and response models for LLM integrations."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """A bounded text-generation request independent of any provider SDK."""

    system_prompt: str
    user_prompt: str
    max_output_tokens: int = 2048

    def __post_init__(self) -> None:
        if not self.system_prompt.strip():
            raise ValueError("system_prompt must not be empty.")

        if not self.user_prompt.strip():
            raise ValueError("user_prompt must not be empty.")

        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive.")


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Text returned by a provider, before domain-level parsing or validation."""

    text: str
    provider: str
    model: str
