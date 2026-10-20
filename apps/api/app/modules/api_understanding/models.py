"""Typed domain models for normalized OpenAPI operations."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Location of a fact in the original OpenAPI document."""

    pointer: str
    provenance: str = "DECLARED"


@dataclass(frozen=True, slots=True)
class NormalizedOperation:
    """A deterministic, normalized HTTP operation."""

    operation_key: str
    method: str
    path: str
    summary: str | None
    operation_id: str | None
    parameters: tuple[dict[str, Any], ...]
    request_body_schema: dict[str, Any] | None
    response_schemas: dict[str, Any]
    security_requirements: tuple[dict[str, Any], ...]
    source_ref: SourceReference
