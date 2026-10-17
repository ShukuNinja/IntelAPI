"""Validation for proposed API test candidates."""

import json
from typing import Any

from app.modules.test_generation.models import CandidateCategory, TestCandidate

DEFAULT_MAX_PAYLOAD_BYTES = 64 * 1024
_ALLOWED_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
    "HEAD",
    "TRACE",
}


class CandidateValidationError(ValueError):
    """Raised when a test candidate violates the candidate contract."""


def _serialized_size(value: Any, field: str) -> int:
    """Return the deterministic JSON size, rejecting unsupported values."""
    try:
        serialized = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise CandidateValidationError(f"{field} must contain JSON-serializable values.") from exc

    return len(serialized.encode("utf-8"))


def validate_candidate(
    candidate: TestCandidate,
    *,
    max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
) -> TestCandidate:
    """Validate a candidate without modifying or executing it."""
    if max_payload_bytes <= 0:
        raise ValueError("max_payload_bytes must be positive.")

    if not isinstance(candidate, TestCandidate):
        raise CandidateValidationError("candidate must be a TestCandidate.")

    for field in ("candidate_id", "operation_key", "title", "rationale"):
        value = getattr(candidate, field)
        if not isinstance(value, str) or not value.strip():
            raise CandidateValidationError(f"{field} must be a non-empty string.")

    if not isinstance(candidate.category, CandidateCategory):
        raise CandidateValidationError("category must be a CandidateCategory.")

    if not isinstance(candidate.method, str) or candidate.method != candidate.method.upper():
        raise CandidateValidationError("method must be an uppercase HTTP method.")

    if candidate.method not in _ALLOWED_METHODS:
        raise CandidateValidationError("method is not a supported HTTP method.")

    if (
        not isinstance(candidate.path, str)
        or not candidate.path.startswith("/")
        or any(character.isspace() for character in candidate.path)
    ):
        raise CandidateValidationError("path must start with '/' and contain no whitespace.")

    if not isinstance(candidate.parameters, dict):
        raise CandidateValidationError("parameters must be a dictionary.")

    if any(not isinstance(key, str) or not key for key in candidate.parameters):
        raise CandidateValidationError("parameter names must be non-empty strings.")

    if candidate.body is not None and not isinstance(candidate.body, dict):
        raise CandidateValidationError("body must be a dictionary or None.")

    for field, value in (
        ("parameters", candidate.parameters),
        ("body", candidate.body),
    ):
        if value is None:
            continue
        if _serialized_size(value, field) > max_payload_bytes:
            raise CandidateValidationError(f"{field} exceeds the {max_payload_bytes}-byte limit.")

    return candidate
