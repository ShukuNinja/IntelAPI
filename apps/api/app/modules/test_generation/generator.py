"""Deterministic test candidate generation from normalized operations."""

import hashlib
import json
import math
from typing import Any, TypeGuard

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


def _finite_number(value: Any) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _has_contradictory_bounds(schema: Any) -> bool:
    """Detect contradictory numeric, string-length, or array-size bounds."""
    if not isinstance(schema, dict):
        return False

    schema_type = schema.get("type")

    if isinstance(schema_type, str) and schema_type in {"integer", "number"}:
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")

        if _finite_number(minimum) and _finite_number(maximum):
            if minimum > maximum:
                return True

            if schema_type == "integer" and math.ceil(minimum) > math.floor(maximum):
                return True

    elif schema_type == "string":
        minimum = schema.get("minLength")
        maximum = schema.get("maxLength")

        if (
            isinstance(minimum, int)
            and not isinstance(minimum, bool)
            and isinstance(maximum, int)
            and not isinstance(maximum, bool)
            and minimum > maximum
        ):
            return True

    elif schema_type == "array":
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")

        if (
            isinstance(minimum, int)
            and not isinstance(minimum, bool)
            and isinstance(maximum, int)
            and not isinstance(maximum, bool)
            and minimum > maximum
        ):
            return True

    properties = schema.get("properties", {})
    if isinstance(properties, dict) and any(
        _has_contradictory_bounds(property_schema) for property_schema in properties.values()
    ):
        return True

    items = schema.get("items")
    if isinstance(items, dict) and _has_contradictory_bounds(items):
        return True

    return False


def _schema_example(schema: Any) -> Any:
    """Create a deterministic example from a supported JSON Schema subset."""
    if not isinstance(schema, dict):
        return None

    if _has_contradictory_bounds(schema):
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
            if isinstance(key, str) and key in properties
        }

    if schema_type == "array":
        minimum = schema.get("minItems", 1)
        maximum = schema.get("maxItems")

        if not isinstance(minimum, int) or isinstance(minimum, bool):
            minimum = 1

        if minimum < 0 or minimum > 100:
            return None

        count = minimum

        if isinstance(maximum, int) and not isinstance(maximum, bool):
            if maximum < 0:
                return None
            count = min(count, maximum)

        item = _schema_example(schema.get("items", {}))
        return [item for _ in range(count)]

    if schema_type == "string":
        minimum = schema.get("minLength", 0)
        maximum = schema.get("maxLength")

        if not isinstance(minimum, int) or isinstance(minimum, bool):
            minimum = 0

        if minimum < 0 or minimum > 100:
            return None

        if isinstance(maximum, int) and not isinstance(maximum, bool):
            if maximum < 0:
                return None
            length = min(max(7, minimum), maximum)
        else:
            length = max(7, minimum)

        if length < minimum:
            return None

        return "example"[:length].ljust(length, "x")

    if schema_type == "integer":
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")

        lower = math.ceil(minimum) if _finite_number(minimum) else None
        upper = math.floor(maximum) if _finite_number(maximum) else None

        if lower is not None and upper is not None and lower > upper:
            return None

        value = max(1, lower) if lower is not None else 1

        if upper is not None:
            value = min(value, upper)

        return value

    if schema_type == "number":
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")

        if _finite_number(minimum) and _finite_number(maximum):
            if minimum > maximum:
                return None

        number_value = float(minimum) if _finite_number(minimum) else 1.0

        if _finite_number(maximum):
            number_value = min(number_value, float(maximum))

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

    if _has_contradictory_bounds(schema):
        return []

    results: list[tuple[str, Any, CandidateCategory, str]] = []
    schema_type = schema.get("type")

    if isinstance(schema_type, str) and schema_type in {"integer", "number"}:
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        step: int | float = 1 if schema_type == "integer" else 1.0

        if _finite_number(minimum):
            results.append(
                (
                    "minimum",
                    minimum,
                    CandidateCategory.BOUNDARY,
                    "Tests the declared minimum value.",
                )
            )
            results.append(
                (
                    "below minimum",
                    minimum - step,
                    CandidateCategory.NEGATIVE,
                    "Tests a value below the declared minimum.",
                )
            )

        if _finite_number(maximum):
            results.append(
                (
                    "maximum",
                    maximum,
                    CandidateCategory.BOUNDARY,
                    "Tests the declared maximum value.",
                )
            )
            results.append(
                (
                    "above maximum",
                    maximum + step,
                    CandidateCategory.NEGATIVE,
                    "Tests a value above the declared maximum.",
                )
            )

    elif schema_type == "string":
        minimum = schema.get("minLength")
        maximum = schema.get("maxLength")

        if isinstance(minimum, int) and not isinstance(minimum, bool) and 0 <= minimum <= 100:
            results.append(
                (
                    "minimum length",
                    "x" * minimum,
                    CandidateCategory.BOUNDARY,
                    "Tests the declared minimum string length.",
                )
            )
            if minimum > 0:
                results.append(
                    (
                        "below minimum length",
                        "x" * (minimum - 1),
                        CandidateCategory.NEGATIVE,
                        "Tests a string shorter than the declared minimum.",
                    )
                )

        if isinstance(maximum, int) and not isinstance(maximum, bool) and 0 <= maximum <= 100:
            results.append(
                (
                    "maximum length",
                    "x" * maximum,
                    CandidateCategory.BOUNDARY,
                    "Tests the declared maximum string length.",
                )
            )
            results.append(
                (
                    "above maximum length",
                    "x" * (maximum + 1),
                    CandidateCategory.NEGATIVE,
                    "Tests a string longer than the declared maximum.",
                )
            )

    elif schema_type == "array":
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        item = _schema_example(schema.get("items", {}))

        if isinstance(minimum, int) and not isinstance(minimum, bool) and 0 <= minimum <= 100:
            results.append(
                (
                    "minimum items",
                    [item for _ in range(minimum)],
                    CandidateCategory.BOUNDARY,
                    "Tests the declared minimum array length.",
                )
            )
            if minimum > 0:
                results.append(
                    (
                        "below minimum items",
                        [item for _ in range(minimum - 1)],
                        CandidateCategory.NEGATIVE,
                        "Tests an array shorter than the declared minimum.",
                    )
                )

        if isinstance(maximum, int) and not isinstance(maximum, bool) and 0 <= maximum <= 100:
            results.append(
                (
                    "maximum items",
                    [item for _ in range(maximum)],
                    CandidateCategory.BOUNDARY,
                    "Tests the declared maximum array length.",
                )
            )
            results.append(
                (
                    "above maximum items",
                    [item for _ in range(maximum + 1)],
                    CandidateCategory.NEGATIVE,
                    "Tests an array longer than the declared maximum.",
                )
            )

    enum = schema.get("enum")
    if isinstance(enum, list):
        for index, value in enumerate(enum[:100]):
            results.append(
                (
                    f"enum value {index + 1}",
                    value,
                    CandidateCategory.BOUNDARY,
                    "Tests a value explicitly allowed by the declared enum.",
                )
            )

    return results


def _schema_candidates(
    operation: NormalizedOperation,
) -> list[TestCandidate]:
    """Generate bounded candidates from request-body schemas."""
    schema = operation.request_body_schema
    if not isinstance(schema, dict):
        return []

    if _has_contradictory_bounds(schema):
        return []

    example = _schema_example(schema)
    if not isinstance(example, dict):
        return []

    candidates = [
        _candidate(
            operation,
            CandidateCategory.POSITIVE,
            "Request body with required fields",
            body=example,
            rationale="Builds a conservative request body from the declared schema.",
        )
    ]

    max_depth = 5
    max_candidates = 100

    def walk(
        current_schema: Any,
        current_value: Any,
        path: tuple[str, ...],
        depth: int,
    ) -> None:
        if depth > max_depth or len(candidates) >= max_candidates:
            return
        if not isinstance(current_schema, dict) or not isinstance(current_value, dict):
            return

        required = current_schema.get("required", [])
        properties = current_schema.get("properties", {})

        if not isinstance(required, list) or not isinstance(properties, dict):
            return

        # Omit each present required property at this object level.
        for field in required:
            if len(candidates) >= max_candidates:
                return
            if not isinstance(field, str) or field not in current_value:
                continue

            negative_body = _copy_json_object(example)
            target = negative_body

            for parent in path:
                child = target.get(parent)
                if not isinstance(child, dict):
                    target = {}
                    break
                target = child

            if field not in target:
                continue

            target.pop(field)
            full_path = ".".join((*path, field))
            candidates.append(
                _candidate(
                    operation,
                    CandidateCategory.NEGATIVE,
                    f"Omit required field: {full_path}",
                    body=negative_body,
                    rationale=f"Checks handling when required field {full_path!r} is omitted.",
                )
            )

        # Generate scalar boundaries and recurse into nested objects.
        for field, field_schema in sorted(properties.items()):
            if len(candidates) >= max_candidates:
                return
            if not isinstance(field, str):
                continue

            child_value = current_value.get(field)
            field_path = (*path, field)

            if isinstance(field_schema, dict):
                for boundary_name, value, category, rationale in _schema_boundary_values(
                    field_schema
                ):
                    if len(candidates) >= max_candidates:
                        return

                    boundary_body = _copy_json_object(example)
                    target = boundary_body

                    for parent in path:
                        child = target.get(parent)
                        if not isinstance(child, dict):
                            target = {}
                            break
                        target = child

                    target[field] = value
                    candidates.append(
                        _candidate(
                            operation,
                            category,
                            f"{'.'.join(field_path)}: {boundary_name}",
                            body=boundary_body,
                            rationale=rationale,
                        )
                    )

                if isinstance(child_value, dict):
                    walk(field_schema, child_value, field_path, depth + 1)

    walk(schema, example, (), 0)
    return candidates


def _copy_json_object(value: dict[str, Any]) -> dict[str, Any]:
    """Copy a JSON-compatible object without sharing nested dictionaries."""
    copied: Any = json.loads(json.dumps(value))
    if not isinstance(copied, dict):
        raise TypeError("Expected a JSON object after copying.")
    return copied


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
                    parameters={},
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
