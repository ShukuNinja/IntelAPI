"""NVIDIA Build adapter using the OpenAI-compatible Python SDK."""

from typing import Any

from app.integrations.llm.models import LLMRequest, LLMResponse
from app.integrations.llm.provider import LLMProviderError

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NVIDIAProvider:
    """Generate text through NVIDIA Build."""

    def __init__(
        self,
        api_key: str,
        model: str,
        client: Any | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("An NVIDIA API key is required.")

        if not model.strip():
            raise ValueError("An NVIDIA model is required.")

        self._model = model

        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise LLMProviderError("The OpenAI-compatible SDK is not installed.") from exc

            client = OpenAI(
                base_url=NVIDIA_BASE_URL,
                api_key=api_key,
            )

        self._client = client

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text without executing requests against target APIs."""
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": request.system_prompt,
                    },
                    {
                        "role": "user",
                        "content": request.user_prompt,
                    },
                ],
                max_tokens=request.max_output_tokens,
            )

            if not response.choices:
                raise LLMProviderError("NVIDIA returned no completion choices.")

            text = response.choices[0].message.content

            if not isinstance(text, str) or not text.strip():
                raise LLMProviderError("NVIDIA returned no usable text.")

            return LLMResponse(
                text=text,
                provider="nvidia",
                model=self._model,
            )

        except LLMProviderError:
            raise
        except Exception as exc:
            # Avoid exposing credentials or raw provider error details.
            raise LLMProviderError("The NVIDIA provider could not complete the request.") from exc
