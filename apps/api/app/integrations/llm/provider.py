"""Provider-neutral LLM interface."""

from typing import Protocol

from app.integrations.llm.models import LLMRequest, LLMResponse


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider cannot complete a generation request."""

    def __init__(self, message: str, *, code: str = "provider_error") -> None:
        super().__init__(message)
        self.code = code


class LLMProvider(Protocol):
    """Contract implemented by each concrete LLM provider adapter."""

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text without executing target API requests."""
        ...
