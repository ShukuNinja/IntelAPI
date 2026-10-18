"""Deterministic deduplication of test candidates."""

from app.modules.test_generation.models import TestCandidate
from app.modules.test_generation.validation import validate_candidate


class CandidateDeduplicationError(ValueError):
    """Raised when one candidate ID refers to conflicting candidates."""


def deduplicate_candidates(
    candidates: tuple[TestCandidate, ...] | list[TestCandidate],
) -> tuple[TestCandidate, ...]:
    """Deduplicate identical candidates and reject conflicting duplicate IDs."""
    unique: dict[str, TestCandidate] = {}

    for candidate in candidates:
        validate_candidate(candidate)

        existing = unique.get(candidate.candidate_id)
        if existing is not None and existing != candidate:
            raise CandidateDeduplicationError(
                f"Conflicting candidates share ID {candidate.candidate_id!r}."
            )

        unique[candidate.candidate_id] = candidate

    return tuple(unique[key] for key in sorted(unique))
