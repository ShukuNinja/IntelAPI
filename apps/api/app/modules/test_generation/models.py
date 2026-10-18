"""Typed models for deterministic test candidate generation."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class CandidateCategory(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    BOUNDARY = "boundary"
    SCHEMA = "schema"
    WORKFLOW = "workflow"


@dataclass(frozen=True, slots=True)
class TestCandidate:
    """A proposed API test that has not been executed."""
    __test__ = False

    candidate_id: str
    operation_key: str
    category: CandidateCategory
    title: str
    method: str
    path: str
    parameters: dict[str, Any]
    body: dict[str, Any] | None
    rationale: str
