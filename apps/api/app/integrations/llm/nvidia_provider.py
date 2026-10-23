"""NVIDIA Build adapter using the OpenAI-compatible Python SDK."""

import logging
import re
from typing import Any

from app.integrations.llm.models import LLMRequest, LLMResponse
from app.integrations.llm.provider import LLMProviderError

logger = logging.getLogger(__name__)
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
                timeout=30.0,
                max_retries=1,
            )

        self._client = client

    @property
    def provider_name(self) -> str:
        return "nvidia"

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text without executing requests against target APIs."""
        try:
            request_args: dict[str, Any] = {}
            if request.json_schema is not None:
                request_args["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "api_test_candidates",
                        "strict": True,
                        "schema": request.json_schema,
                    },
                }
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
                **request_args,
            )

            if not response.choices:
                raise LLMProviderError("NVIDIA returned no completion choices.")

            text = response.choices[0].message.content

            if not isinstance(text, str) or not text.strip():
                raise LLMProviderError("NVIDIA returned no usable text.")

            usage = getattr(response, "usage", None)
            return LLMResponse(
                text=text,
                provider="nvidia",
                model=self._model,
                prompt_tokens=getattr(usage, "prompt_tokens", None),
                completion_tokens=getattr(usage, "completion_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
            )

        except LLMProviderError:
            raise
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            provider_code = getattr(exc, "code", None)
            provider_code = (
                re.sub(r"[^a-zA-Z0-9_-]", "", provider_code)[:64]
                if isinstance(provider_code, str)
                else ""
            )
            if status_code == 401:
                code, message = (
                    "authentication_failed",
                    "NVIDIA rejected the API key. Check NVIDIA_API_KEY on the API service.",
                )
            elif status_code == 403:
                code, message = (
                    "access_denied",
                    "NVIDIA denied access to this model or account. "
                    "Check model access and account status.",
                )
            elif status_code == 404 or provider_code in {"model_decommissioned", "model_not_found"}:
                code, message = (
                    "model_unavailable",
                    f"NVIDIA model '{self._model}' is unavailable. "
                    "Choose an active model in the workbench.",
                )
            elif status_code == 429:
                code, message = (
                    "rate_limited",
                    "NVIDIA rate limit or quota was reached. Check your plan and retry later.",
                )
            elif status_code is not None and status_code >= 500:
                code, message = (
                    "provider_unavailable",
                    "NVIDIA is temporarily unavailable. Retry the experiment later.",
                )
            elif type(exc).__name__ in {"APITimeoutError", "TimeoutError"}:
                code, message = (
                    "provider_timeout",
                    "NVIDIA did not respond before the request timed out. Retry the experiment.",
                )
            elif type(exc).__name__ == "APIConnectionError":
                code, message = (
                    "connection_failed",
                    "The API service could not connect to NVIDIA. Check network access and retry.",
                )
            else:
                code = provider_code or "provider_request_failed"
                message = (
                    f"NVIDIA rejected the request (HTTP {status_code}). "
                    "Check the selected model and provider limits."
                    if status_code
                    else "NVIDIA could not complete the generation request. "
                    "Check the API logs for its status code."
                )
            logger.warning("NVIDIA generation failed: status=%s code=%s", status_code, code)
            raise LLMProviderError(message, code=code) from exc
