"""Non-persisting service for previewing generated test candidates."""

from dataclasses import dataclass

from app.integrations.llm import LLMProvider
from app.modules.api_understanding.models import NormalizedOperation
from app.modules.test_generation.deduplication import deduplicate_candidates
from app.modules.test_generation.models import CandidateCategory, TestCandidate
from app.modules.test_generation.orchestration import (
    LLMGenerationStatus,
    generate_candidates_with_llm,
)
from app.modules.test_generation.validation import validate_candidate

DEFAULT_PREVIEW_LIMIT = 20
MAX_PREVIEW_LIMIT = 100


class CandidatePreviewError(ValueError):
    """Raised when preview options violate the service contract."""


@dataclass(frozen=True, slots=True)
class CandidatePreviewResult:
    """Validated, bounded candidates returned without persistence."""

    candidates: tuple[TestCandidate, ...]
    llm_status: LLMGenerationStatus
    llm_error: str | None = None


def preview_candidates(
    operations: tuple[NormalizedOperation, ...],
    *,
    categories: tuple[CandidateCategory, ...] | None = None,
    limit: int = DEFAULT_PREVIEW_LIMIT,
    provider: LLMProvider | None = None,
) -> CandidatePreviewResult:
    """Generate a bounded candidate preview without executing or persisting it.

    When categories is None, candidates from all categories are eligible.
    The limit is applied after category filtering.
    """
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise CandidatePreviewError("limit must be an integer.")

    if not 1 <= limit <= MAX_PREVIEW_LIMIT:
        raise CandidatePreviewError(f"limit must be between 1 and {MAX_PREVIEW_LIMIT}.")

    if categories is not None:
        if not categories:
            raise CandidatePreviewError(
                "categories must contain at least one category when provided."
            )

        if any(not isinstance(category, CandidateCategory) for category in categories):
            raise CandidatePreviewError("categories must contain valid CandidateCategory values.")

        selected_categories = frozenset(categories)
    else:
        selected_categories = None

    generation = generate_candidates_with_llm(operations, provider)

    validated = tuple(validate_candidate(candidate) for candidate in generation.candidates)
    unique = deduplicate_candidates(validated)

    if selected_categories is not None:
        unique = tuple(
            candidate for candidate in unique if candidate.category in selected_categories
        )

    return CandidatePreviewResult(
        candidates=unique[:limit],
        llm_status=generation.llm_status,
        llm_error=generation.llm_error,
    )
