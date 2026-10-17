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
    """Create a deterministic example from a supported JSON Schema subset."""
    if not isinstance(schema, dict):
        return None

    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]

    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]

    schema_type = schema.get("type")

    if schema_type == "object":
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            return {}

        required = schema.get("required", [])
        keys = required if isinstance(required, list) else []
        return {
            key: _schema_example(properties[key])
            for key in keys
            if key in properties
        }

    if schema_type == "array":
        minimum = schema.get("minItems", 1)
        count = minimum if isinstance(minimum, int) and minimum >= 0 else 1
        count = min(count, 100)
        item = _schema_example(schema.get("items", {}))
        return [item for _ in range(count)]

    if schema_type == "string":
        minimum = schema.get("minLength", 0)
        minimum = (
            minimum
            if isinstance(minimum, int) and not isinstance(minimum, bool)
            else 0
        )
        minimum = min(max(minimum, 0), 100)

        maximum = schema.get("maxLength")
        if isinstance(maximum, int) and not isinstance(maximum, bool):
            maximum = min(max(maximum, 0), 100)
            length = max(minimum, min(7, maximum))
        else:
            length = max(7, minimum)

        return "example"[:length].ljust(length, "x")

    if schema_type == "integer":
        integer_minimum = schema.get("minimum")
        integer_maximum = schema.get("maximum")

        if isinstance(integer_minimum, (int, float)) and not isinstance(
            integer_minimum, bool
        ):
            value = (
                int(integer_minimum)
                if integer_minimum == int(integer_minimum)
                else int(integer_minimum) + 1
            )
        else:
            value = 1

        if isinstance(integer_maximum, (int, float)) and not isinstance(
            integer_maximum, bool
        ):
            value = min(value, int(integer_maximum))

        return value
    if schema_type == "number":
        number_minimum = schema.get("minimum")
        number_maximum = schema.get("maximum")

        number_value: float = (
            float(number_minimum)
            if isinstance(number_minimum, (int, float))
            and not isinstance(number_minimum, bool)
            else 1.0
        )

        if isinstance(number_maximum, (int, float)) and not isinstance(
            number_maximum, bool
        ):
            number_value = min(number_value, float(number_maximum))

        return number_value



    if schema_type == "boolean":
        return True

    if schema_type == "null":
        return None

    return None

def _schema_boundary_values(
    schema: Any,
) -> list[tuple[str, Any, CandidateCategory, str]]:
    """Return deterministic boundary values for supported schema constraints."""
    if not isinstance(schema, dict):
        return []

    results: list[tuple[str, Any, CandidateCategory, str]] = []
    schema_type = schema.get("type")

    if schema_type in {"integer", "number"}:
        numeric_minimum = schema.get("minimum")
        numeric_maximum = schema.get("maximum")
        step: int | float = 1 if schema_type == "integer" else 1.0

        if isinstance(numeric_minimum, (int, float)) and not isinstance(
            numeric_minimum, bool
        ):
            results.append((
                "minimum",
                numeric_minimum,
                CandidateCategory.BOUNDARY,
                "Tests the declared minimum value.",
            ))
            results.append((
                "below minimum",
                numeric_minimum - step,
                CandidateCategory.NEGATIVE,
                "Tests a value below the declared minimum.",
            ))

        if isinstance(numeric_maximum, (int, float)) and not isinstance(
            numeric_maximum, bool
        ):
            results.append((
                "maximum",
                numeric_maximum,
                CandidateCategory.BOUNDARY,
                "Tests the declared maximum value.",
            ))
            results.append((
                "above maximum",
                numeric_maximum + step,
                CandidateCategory.NEGATIVE,
                "Tests a value above the declared maximum.",
            ))

    elif schema_type == "string":
        minimum = schema.get("minLength")
        maximum = schema.get("maxLength")

        if isinstance(minimum, int) and not isinstance(minimum, bool) and 0 <= minimum <= 100:
            results.append((
                "minimum length",
                "x" * minimum,
                CandidateCategory.BOUNDARY,
                "Tests the declared minimum string length.",
            ))
            if minimum > 0:
                results.append((
                    "below minimum length",
                    "x" * (minimum - 1),
                    CandidateCategory.NEGATIVE,
                    "Tests a string shorter than the declared minimum.",
                ))

        if isinstance(maximum, int) and not isinstance(maximum, bool) and 0 <= maximum <= 100:
            results.append((
                "maximum length",
                "x" * maximum,
                CandidateCategory.BOUNDARY,
                "Tests the declared maximum string length.",
            ))
            results.append((
                "above maximum length",
                "x" * (maximum + 1),
                CandidateCategory.NEGATIVE,
                "Tests a string longer than the declared maximum.",
            ))

    elif schema_type == "array":
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        item = _schema_example(schema.get("items", {}))

        if isinstance(minimum, int) and not isinstance(minimum, bool) and 0 <= minimum <= 100:
            results.append((
                "minimum items",
                [item for _ in range(minimum)],
                CandidateCategory.BOUNDARY,
                "Tests the declared minimum array length.",
            ))
            if minimum > 0:
                results.append((
                    "below minimum items",
                    [item for _ in range(minimum - 1)],
                    CandidateCategory.NEGATIVE,
                    "Tests an array shorter than the declared minimum.",
                ))

        if isinstance(maximum, int) and not isinstance(maximum, bool) and 0 <= maximum <= 100:
            results.append((
                "maximum items",
                [item for _ in range(maximum)],
                CandidateCategory.BOUNDARY,
                "Tests the declared maximum array length.",
            ))
            results.append((
                "above maximum items",
                [item for _ in range(maximum + 1)],
                CandidateCategory.NEGATIVE,
                "Tests an array longer than the declared maximum.",
            ))

    elif isinstance(schema.get("enum"), list):
        for index, value in enumerate(schema["enum"]):
            results.append((
                f"enum value {index + 1}",
                value,
                CandidateCategory.BOUNDARY,
                "Tests a value explicitly allowed by the declared enum.",
            ))

    return results



def _schema_candidates(
    operation: NormalizedOperation,
) -> list[TestCandidate]:
    candidates: list[TestCandidate] = []
    schema = operation.request_body_schema

    if schema is None:
        return candidates

    example = _schema_example(schema)
    if not isinstance(example, dict):
        return candidates

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
                        rationale=(
                            f"Checks handling when required field {field!r} is omitted."
                        ),
                    )
                )

    properties = schema.get("properties", {})
    if isinstance(properties, dict):
        for field, field_schema in sorted(properties.items()):
            for boundary_name, value, category, rationale in (
                _schema_boundary_values(field_schema)
            ):
                boundary_body = dict(example)
                boundary_body[field] = value
                candidates.append(
                    _candidate(
                        operation,
                        category,
                        f"{field}: {boundary_name}",
                        body=boundary_body,
                        rationale=rationale,
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
