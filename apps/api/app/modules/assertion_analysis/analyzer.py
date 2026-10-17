"""Deterministic assertion analysis from normalized API operations."""

import hashlib
import json
from typing import Any

from app.modules.api_understanding.models import NormalizedOperation
from app.modules.assertion_analysis.models import AssertionType, ProposedAssertion
from app.modules.knowledge.models import FactProvenance


def _make_assertion(
    operation: NormalizedOperation,
    assertion_type: AssertionType,
    response_key: str,
    target: str,
    expected: Any,
    rationale: str,
) -> ProposedAssertion:
    """Create an assertion with a stable content-derived identifier."""
    identity = {
        "operation_key": operation.operation_key,
        "assertion_type": assertion_type.value,
        "response_key": response_key,
        "target": target,
        "expected": expected,
    }
    canonical = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    assertion_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    return ProposedAssertion(
        assertion_id=assertion_id,
        operation_key=operation.operation_key,
        assertion_type=assertion_type,
        response_key=response_key,
        target=target,
        expected=expected,
        provenance=FactProvenance.DECLARED,
        source_ref=operation.source_ref,
        rationale=rationale,
    )


def _analyze_schema(
    operation: NormalizedOperation,
    response_key: str,
    schema: Any,
    target: str = "$",
) -> list[ProposedAssertion]:
    """Generate assertions for supported object schemas recursively."""
    if not isinstance(schema, dict):
        return []

    assertions: list[ProposedAssertion] = []
    schema_type = schema.get("type")

    if schema_type == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        if not isinstance(properties, dict):
            properties = {}
        if not isinstance(required, list):
            required = []

        for field in sorted(required):
            if isinstance(field, str):
                property_target = f"{target}.{field}" if target != "$" else field
                assertions.append(
                    _make_assertion(
                        operation,
                        AssertionType.REQUIRED_PROPERTY,
                        response_key,
                        property_target,
                        True,
                        f"Response schema declares {property_target!r} as required.",
                    )
                )

        for field in sorted(properties):
            if not isinstance(field, str):
                continue

            property_schema = properties[field]
            property_target = f"{target}.{field}" if target != "$" else field

            if isinstance(property_schema, dict):
                property_type = property_schema.get("type")
                if isinstance(property_type, str):
                    assertions.append(
                        _make_assertion(
                            operation,
                            AssertionType.PROPERTY_TYPE,
                            response_key,
                            property_target,
                            property_type,
                            f"Response schema declares {property_target!r} as {property_type}.",
                        )
                    )

                assertions.extend(
                    _analyze_schema(
                        operation,
                        response_key,
                        property_schema,
                        property_target,
                    )
                )

    elif schema_type == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            assertions.extend(
                _analyze_schema(
                    operation,
                    response_key,
                    items,
                    f"{target}[]",
                )
            )

    return assertions


def analyze_operation(
    operation: NormalizedOperation,
) -> tuple[ProposedAssertion, ...]:
    """Propose response assertions without executing API requests."""
    assertions: list[ProposedAssertion] = []

    for response_key, schema in sorted(operation.response_schemas.items()):
        status_text = response_key.split(":", maxsplit=1)[0]
        if status_text.isdigit():
            status_code = int(status_text)
            assertions.append(
                _make_assertion(
                    operation,
                    AssertionType.STATUS_CODE,
                    response_key,
                    "status",
                    status_code,
                    f"OpenAPI declares response status {status_code}.",
                )
            )

        assertions.extend(_analyze_schema(operation, response_key, schema))

    unique = {assertion.assertion_id: assertion for assertion in assertions}
    return tuple(unique[key] for key in sorted(unique))


def analyze_operations(
    operations: tuple[NormalizedOperation, ...],
) -> tuple[ProposedAssertion, ...]:
    """Analyze operations and return deduplicated assertions deterministically."""
    assertions: list[ProposedAssertion] = []

    for operation in operations:
        assertions.extend(analyze_operation(operation))

    unique = {assertion.assertion_id: assertion for assertion in assertions}
    return tuple(unique[key] for key in sorted(unique))
