"""Deterministic test candidate generation from normalized operations."""

import hashlib
import json
from typing import Any

from app.modules.api_understanding.models import NormalizedOperation
from app.modules.test_generation.deduplication import deduplicate_candidates
from app.modules.test_generation.models import CandidateCategory, TestCandidate


def _candidate(
    operation: NormalizedOperation,
    category: CandidateCategory,
    title: str,
    parameters: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    rationale: str = "",
) -> TestCandidate:
    """Create a candidate with a stable content-derived identifier."""
    payload = {
        "operation_key": operation.operation_key,
        "category": category.value,
        "title": title,
        "parameters": parameters or {},
        "body": body,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    candidate_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    return TestCandidate(
        candidate_id=candidate_id,
        operation_key=operation.operation_key,
        category=category,
        title=title,
        method=operation.method,
        path=operation.path,
        parameters=parameters or {},
        body=body,
        rationale=rationale,
    )


def _schema_example(schema: Any) -> Any:
    """Create a conservative example from a supported JSON Schema subset."""
    if not isinstance(schema, dict):
        return None

    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        return schema["enum"][0]

    schema_type = schema.get("type")
    if schema_type == "object":
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            return {}
        required = schema.get("required", [])
        keys = required if isinstance(required, list) else []
        return {key: _schema_example(properties[key]) for key in keys if key in properties}
    if schema_type == "array":
        return [_schema_example(schema.get("items", {}))]
    if schema_type == "string":
        return "example"
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 1.0
    if schema_type == "boolean":
        return True
    if schema_type == "null":
        return None

    return None


def _schema_candidates(
    operation: NormalizedOperation,
) -> list[TestCandidate]:
    candidates: list[TestCandidate] = []
    schema = operation.request_body_schema

    if schema is None:
        return candidates

    example = _schema_example(schema)
    if isinstance(example, dict):
        candidates.append(
            _candidate(
                operation,
                CandidateCategory.POSITIVE,
                "Request body with required fields",
                body=example,
                rationale="Builds a conservative request body from the declared schema.",
            )
        )

        required = schema.get("required", [])
        if isinstance(required, list):
            for field in required:
                if field in example:
                    negative_body = dict(example)
                    negative_body.pop(field)
                    candidates.append(
                        _candidate(
                            operation,
                            CandidateCategory.NEGATIVE,
                            f"Omit required field: {field}",
                            body=negative_body,
                            rationale=f"Checks handling when required field {field!r} is omitted.",
                        )
                    )

    return candidates


def generate_candidates(
    operations: tuple[NormalizedOperation, ...],
) -> tuple[TestCandidate, ...]:
    """Generate stable baseline candidates without executing requests."""
    candidates: list[TestCandidate] = []

    for operation in operations:
        candidates.append(
            _candidate(
                operation,
                CandidateCategory.POSITIVE,
                "Baseline request",
                rationale="Baseline candidate derived from a declared operation.",
            )
        )

        for parameter in operation.parameters:
            name = parameter.get("name")
            location = parameter.get("in")
            if not isinstance(name, str) or location not in {
                "query",
                "path",
                "header",
                "cookie",
            }:
                continue

            candidates.append(
                _candidate(
                    operation,
                    CandidateCategory.NEGATIVE,
                    f"Omit parameter: {name}",
                    parameters={name: None},
                    rationale=(
                        f"Explores behavior when the {location} parameter "
                        f"{name!r} is omitted or empty."
                    ),
                )
            )

        candidates.extend(_schema_candidates(operation))

        for response_key in sorted(operation.response_schemas):
            candidates.append(
                _candidate(
                    operation,
                    CandidateCategory.SCHEMA,
                    f"Validate response schema: {response_key}",
                    rationale=(
                        "Candidate for comparing a future response with "
                        "the declared response schema."
                    ),
                )
            )

    return deduplicate_candidates(candidates)
