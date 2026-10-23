"""Groq chat completions through its OpenAI-compatible API."""

import logging
from typing import Any

from app.integrations.llm.models import LLMRequest, LLMResponse
from app.integrations.llm.provider import LLMProviderError

logger = logging.getLogger(__name__)
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider:
    """Generate text through Groq without exposing credentials to callers."""

    def __init__(self, api_key: str, model: str, client: Any | None = None) -> None:
        if not api_key.strip():
            raise ValueError("A Groq API key is required.")
        if not model.strip():
            raise ValueError("A Groq model is required.")

        self._model = model
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise LLMProviderError("The OpenAI-compatible SDK is not installed.") from exc

            client = OpenAI(
                base_url=GROQ_BASE_URL,
                api_key=api_key,
                timeout=30.0,
                max_retries=1,
            )
        self._client = client

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_prompt},
                ],
                max_tokens=request.max_output_tokens,
            )
            if not response.choices:
                raise LLMProviderError("Groq returned no completion choices.")
            text = response.choices[0].message.content
            if not isinstance(text, str) or not text.strip():
                raise LLMProviderError("Groq returned no usable text.")
            usage = getattr(response, "usage", None)
            return LLMResponse(
                text=text,
                provider="groq",
                model=self._model,
                prompt_tokens=getattr(usage, "prompt_tokens", None),
                completion_tokens=getattr(usage, "completion_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
            )
        except LLMProviderError:
            raise
        except Exception as exc:
            logger.warning("Groq generation failed: exception_type=%s", type(exc).__name__)
            raise LLMProviderError("The Groq provider could not complete the request.") from exc
