"""Domain models for deterministic, evidence-based API analysis."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.modules.api_understanding.models import SourceReference
from app.modules.knowledge.models import FactProvenance


class ObservationKind(StrEnum):
    """Kinds of execution observations accepted by the classifier."""

    ASSERTION_MISMATCH = "assertion_mismatch"
    SCHEMA_MISMATCH = "schema_mismatch"
    HTTP_RESPONSE = "http_response"
    TRANSPORT_FAILURE = "transport_failure"


class FindingCategory(StrEnum):
    """Machine-derived categories for potential findings."""

    CONTRACT_MISMATCH = "contract_mismatch"


class ClassificationDisposition(StrEnum):
    """Whether evidence supports a potential finding or only an observation."""

    OBSERVATION = "observation"
    POTENTIAL_FINDING = "potential_finding"


@dataclass(frozen=True, slots=True)
class AnalysisObservation:
    """A normalized observation; it does not mutate execution evidence."""

    observation_id: str
    operation_key: str
    kind: ObservationKind
    summary: str
    source_ref: SourceReference
    provenance: FactProvenance
    expected: Any = None
    actual: Any = None
    has_expected: bool = False
    has_actual: bool = False
    status_code: int | None = None
    assertion_id: str | None = None


@dataclass(frozen=True, slots=True)
class FindingCandidate:
    """A potential finding derived from explicit mismatch evidence."""

    candidate_id: str
    operation_key: str
    category: FindingCategory
    title: str
    confidence: float
    rationale: str
    observation_id: str
    assertion_id: str | None
    source_ref: SourceReference
    provenance: FactProvenance


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Deterministic classification output for one observation."""

    observation_id: str
    disposition: ClassificationDisposition
    rationale: str
    finding: FindingCandidate | None = None
