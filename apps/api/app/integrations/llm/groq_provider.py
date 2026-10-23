"""Groq chat completions through its OpenAI-compatible API."""

import logging
import re
from collections.abc import Mapping
from typing import Any

from app.integrations.llm.models import LLMRequest, LLMResponse
from app.integrations.llm.provider import LLMProviderError

logger = logging.getLogger(__name__)
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def _provider_error_details(exc: Exception) -> tuple[str | None, str | None]:
    """Extract a bounded, credential-scrubbed provider code and explanation."""
    body = getattr(exc, "body", None)
    if not isinstance(body, Mapping):
        return None, None
    error = body.get("error", body)
    if not isinstance(error, Mapping):
        return None, None
    code = error.get("code")
    message = error.get("message")
    if isinstance(code, str):
        code = re.sub(r"[^a-zA-Z0-9_-]", "", code)[:64]
    else:
        code = None
    if isinstance(message, str):
        message = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", message)
        message = re.sub(r"(?i)(gsk_[a-z0-9_-]+|sk-[a-z0-9_-]+)", "[redacted]", message)
        message = re.sub(r"[\r\n\t]+", " ", message).strip()[:300]
    else:
        message = None
    return code, message


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
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_prompt},
                ],
                max_tokens=request.max_output_tokens,
                **request_args,
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
            status_code = getattr(exc, "status_code", None)
            body_code, provider_message = _provider_error_details(exc)
            provider_code = body_code or getattr(exc, "code", None)
            provider_code = (
                re.sub(r"[^a-zA-Z0-9_-]", "", provider_code)[:64]
                if isinstance(provider_code, str)
                else ""
            )
            if status_code == 401:
                code, message = (
                    "authentication_failed",
                    "Groq rejected the API key. Check GROQ_API_KEY on the API service.",
                )
            elif status_code == 403:
                code, message = (
                    "access_denied",
                    "Groq denied access to this model or account. "
                    "Check model access and account status.",
                )
            elif status_code == 404 or provider_code in {"model_decommissioned", "model_not_found"}:
                code, message = (
                    "model_unavailable",
                    f"Groq model '{self._model}' is unavailable. "
                    "Choose an active model in the workbench.",
                )
            elif status_code == 429:
                code, message = (
                    "rate_limited",
                    "Groq rate limit or quota was reached. Check your plan and retry later.",
                )
            elif status_code == 400 and provider_code == "blocked_api_access":
                code, message = (
                    "billing_limit_reached",
                    "Groq blocked API access because the organization spend limit was reached. "
                    "Check Groq Billing → Limits.",
                )
            elif status_code == 400 and provider_code == "json_validate_failed":
                code = "json_validate_failed"
                message = (
                    f"Groq could not validate its generated JSON: {provider_message}"
                    if provider_message
                    else "Groq could not validate its generated JSON. "
                    "Increase the output budget or simplify the requested response."
                )
            elif status_code == 400:
                code = "invalid_request"
                message = (
                    f"Groq rejected the request (HTTP 400): {provider_message}"
                    if provider_message
                    else "Groq rejected the request (HTTP 400). "
                    "Check the model and response schema."
                )
            elif status_code is not None and status_code >= 500:
                code, message = (
                    "provider_unavailable",
                    "Groq is temporarily unavailable. Retry the experiment later.",
                )
            elif type(exc).__name__ in {"APITimeoutError", "TimeoutError"}:
                code, message = (
                    "provider_timeout",
                    "Groq did not respond before the request timed out. Retry the experiment.",
                )
            elif type(exc).__name__ == "APIConnectionError":
                code, message = (
                    "connection_failed",
                    "The API service could not connect to Groq. Check network access and retry.",
                )
            else:
                code = provider_code or "provider_request_failed"
                message = (
                    f"Groq rejected the request (HTTP {status_code}). "
                    "Check the selected model and provider limits."
                    if status_code
                    else "Groq could not complete the generation request. "
                    "Check the API logs for its status code."
                )
            logger.warning(
                "Groq generation failed: status=%s code=%s detail=%s",
                status_code,
                code,
                provider_message,
            )
            raise LLMProviderError(message, code=code) from exc
