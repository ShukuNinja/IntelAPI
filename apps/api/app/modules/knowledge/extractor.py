"""Deterministic knowledge extraction from normalized OpenAPI operations."""

from typing import Any

from app.modules.api_understanding.models import NormalizedOperation
from app.modules.knowledge.models import FactProvenance, KnowledgeFact


def _make_fact(
    operation: NormalizedOperation,
    fact_type: str,
    ordinal: int,
    value: dict[str, Any],
) -> KnowledgeFact:
    """Build a deterministic fact linked to its originating operation."""
    return KnowledgeFact(
        fact_key=f"{operation.operation_key}::{fact_type}::{ordinal}",
        fact_type=fact_type,
        value=value,
        provenance=FactProvenance.EXTRACTED,
        source_ref=operation.source_ref,
    )


def extract_operation_facts(
    operation: NormalizedOperation,
) -> tuple[KnowledgeFact, ...]:
    """Extract structured facts from one normalized operation."""
    facts: list[KnowledgeFact] = [
        _make_fact(
            operation,
            "operation",
            0,
            {
                "operation_key": operation.operation_key,
                "method": operation.method,
                "path": operation.path,
                "summary": operation.summary,
                "operation_id": operation.operation_id,
            },
        )
    ]

    for index, parameter in enumerate(operation.parameters):
        facts.append(
            _make_fact(
                operation,
                "parameter",
                index,
                dict(parameter),
            )
        )

    if operation.request_body_schema is not None:
        facts.append(
            _make_fact(
                operation,
                "request_body_schema",
                0,
                {"schema": operation.request_body_schema},
            )
        )

    for index, (response_key, schema) in enumerate(sorted(operation.response_schemas.items())):
        facts.append(
            _make_fact(
                operation,
                "response_schema",
                index,
                {
                    "response_key": response_key,
                    "schema": schema,
                },
            )
        )

    for index, requirement in enumerate(operation.security_requirements):
        facts.append(
            _make_fact(
                operation,
                "security_requirement",
                index,
                dict(requirement),
            )
        )

    return tuple(facts)


def extract_knowledge(
    operations: tuple[NormalizedOperation, ...],
) -> tuple[KnowledgeFact, ...]:
    """Extract facts from operations in their supplied order."""
    facts: list[KnowledgeFact] = []
    for operation in operations:
        facts.extend(extract_operation_facts(operation))
    return tuple(facts)
