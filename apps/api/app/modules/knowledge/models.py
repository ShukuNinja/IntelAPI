"""Domain models for API knowledge and fact provenance."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.modules.api_understanding.models import SourceReference


class FactProvenance(StrEnum):
    """Origin or epistemic status of a knowledge fact."""

    DECLARED = "DECLARED"
    EXTRACTED = "EXTRACTED"
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"


@dataclass(frozen=True, slots=True)
class KnowledgeFact:
    """A fact with a stable key, structured value, provenance, and source."""

    fact_key: str
    fact_type: str
    value: dict[str, Any]
    provenance: FactProvenance
    source_ref: SourceReference
