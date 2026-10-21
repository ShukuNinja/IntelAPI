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


def normalized_operation_from_document(data: dict[str, Any]) -> NormalizedOperation:
    """Reconstruct a normalized operation from its JSONB representation."""
    source_ref = data.get("source_ref")
    if not isinstance(source_ref, dict):
        raise ValueError("Normalized operation is missing its source reference.")
    parameters = data.get("parameters", [])
    security = data.get("security_requirements", [])
    if not isinstance(parameters, list) or not isinstance(security, list):
        raise ValueError("Normalized operation parameters are invalid.")
    return NormalizedOperation(
        operation_key=data["operation_key"],
        method=data["method"],
        path=data["path"],
        summary=data.get("summary"),
        operation_id=data.get("operation_id"),
        parameters=tuple(parameters),
        request_body_schema=data.get("request_body_schema"),
        response_schemas=data.get("response_schemas", {}),
        security_requirements=tuple(security),
        source_ref=SourceReference(**source_ref),
    )
