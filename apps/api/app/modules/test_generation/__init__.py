"""Public interfaces for test candidate generation."""

from app.modules.test_generation.deduplication import (
    CandidateDeduplicationError,
    deduplicate_candidates,
)
from app.modules.test_generation.generator import generate_candidates
from app.modules.test_generation.models import CandidateCategory, TestCandidate
from app.modules.test_generation.orchestration import (
    CandidateGenerationResult,
    LLMGenerationStatus,
    generate_candidates_with_llm,
)
from app.modules.test_generation.validation import (
    CandidateValidationError,
    validate_candidate,
)

__all__ = [
    "CandidateCategory",
    "CandidateDeduplicationError",
    "CandidateValidationError",
    "TestCandidate",
    "deduplicate_candidates",
    "generate_candidates",
    "validate_candidate",
    "CandidateGenerationResult",
    "LLMGenerationStatus",
    "generate_candidates_with_llm",
]
