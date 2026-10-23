"""Provider-neutral LLM interface."""

import re
from typing import Protocol

from app.integrations.llm.models import LLMRequest, LLMResponse


def _redact_diagnostic(value: str, limit: int) -> str:
    value = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", value)
    value = re.sub(r"(?i)(gsk_[a-z0-9_-]+|sk-[a-z0-9_-]+)", "[redacted]", value)
    value = re.sub(
        r'(?i)(\\?"(?:api[_-]?key|authorization|access[_-]?token|password|secret|credential)\\?"\s*:\s*\\?")[^"\\]*\\?"',
        r'\1[redacted]"',
        value,
    )
    value = re.sub(
        r"(?i)(api[_ -]?key|authorization|access[_ -]?token|password|secret|credential)"
        r"(\s*[:=]\s*)[^,;\s}]+",
        r"\1\2[redacted]",
        value,
    )
    value = re.sub(r"[\r\n\t]+", " ", value).strip()
    return value[:limit]


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider cannot complete a generation request."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        status_code: int | None = None,
        provider: str | None = None,
        model: str | None = None,
        retryable: bool = False,
        failed_generation: str | None = None,
    ) -> None:
        super().__init__(_redact_diagnostic(message, 300))
        self.code = code
        self.status_code = status_code
        self.provider = provider
        self.model = model
        self.retryable = retryable
        self.failed_generation = (
            _redact_diagnostic(failed_generation, 512) if failed_generation is not None else None
        )

    def diagnostic(
        self, *, attempt: int, timeout_seconds: float, max_output_tokens: int
    ) -> dict[str, object]:
        """Return safe, bounded request diagnostics suitable for private run metadata."""
        return {
            "category": self.code,
            "message": str(self)[:300],
            "http_status": self.status_code,
            "provider": self.provider,
            "model": self.model,
            "attempt": attempt,
            "retryable": self.retryable,
            "failed_generation": self.failed_generation,
            "timeout_seconds": timeout_seconds,
            "max_output_tokens": max_output_tokens,
            "completion_received": False,
            "local_parse_succeeded": False,
            "local_validation_succeeded": False,
        }


class LLMProvider(Protocol):
    """Contract implemented by each concrete LLM provider adapter."""

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text without executing target API requests."""
        ...
