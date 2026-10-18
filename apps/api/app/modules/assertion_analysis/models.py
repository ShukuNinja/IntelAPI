"""Typed domain models for API assertion analysis."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.modules.api_understanding.models import SourceReference
from app.modules.knowledge.models import FactProvenance


class AssertionType(StrEnum):
    """Kinds of checks proposed by assertion analysis."""

    STATUS_CODE = "status_code"
    REQUIRED_PROPERTY = "required_property"
    PROPERTY_TYPE = "property_type"


@dataclass(frozen=True, slots=True)
class ProposedAssertion:
    """An evidence-backed assertion that has not been executed."""

    assertion_id: str
    operation_key: str
    assertion_type: AssertionType
    response_key: str
    target: str
    expected: Any
    provenance: FactProvenance
    source_ref: SourceReference
    rationale: str
