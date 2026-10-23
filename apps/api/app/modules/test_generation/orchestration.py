"""Orchestration for deterministic and LLM-assisted candidate generation."""

from dataclasses import dataclass
from enum import StrEnum

from app.integrations.llm import LLMProvider, create_llm_provider
from app.modules.api_understanding.models import NormalizedOperation
from app.modules.test_generation.deduplication import deduplicate_candidates
from app.modules.test_generation.generator import generate_candidates
from app.modules.test_generation.llm_assisted import generate_llm_candidates
from app.modules.test_generation.models import TestCandidate


class LLMGenerationStatus(StrEnum):
    """Outcome of the optional LLM-assisted generation stage."""

    NOT_CONFIGURED = "not_configured"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CandidateGenerationResult:
    """Candidates and explicit status for optional LLM assistance."""

    candidates: tuple[TestCandidate, ...]
    llm_status: LLMGenerationStatus
    llm_error: str | None = None


def generate_candidates_with_llm(
    operations: tuple[NormalizedOperation, ...],
    provider: LLMProvider | None = None,
) -> CandidateGenerationResult:
    """Generate a deterministic baseline and optionally augment it with LLM proposals.

    An injected provider takes precedence. Otherwise, the configured provider
    factory is consulted. If no provider is configured, the deterministic
    baseline is returned. If LLM generation fails, the baseline is preserved.

    This function never executes requests against target APIs.
    """
    baseline = generate_candidates(operations)

    try:
        configured_provider = provider if provider is not None else create_llm_provider()
    except Exception as exc:
        return CandidateGenerationResult(
            candidates=baseline,
            llm_status=LLMGenerationStatus.FAILED,
            llm_error=f"LLM candidate generation failed: {type(exc).__name__}",
        )

    if configured_provider is None:
        return CandidateGenerationResult(
            candidates=baseline,
            llm_status=LLMGenerationStatus.NOT_CONFIGURED,
        )

    try:
        proposed: list[TestCandidate] = []
        rejected_responses: list[dict[str, str]] = []
        for operation in operations:
            operation_rejections: list[dict[str, str]] = []
            proposed.extend(
                generate_llm_candidates(
                    operation,
                    configured_provider,
                    on_rejection=operation_rejections.append,
                )
            )
            rejected_responses.extend(
                item for item in operation_rejections if item.get("kind") == "invalid_response"
            )

        if rejected_responses:
            return CandidateGenerationResult(
                candidates=baseline,
                llm_status=LLMGenerationStatus.FAILED,
                llm_error="LLM candidate generation failed: invalid JSON response",
            )

        merged = deduplicate_candidates([*baseline, *proposed])
    except Exception as exc:
        return CandidateGenerationResult(
            candidates=baseline,
            llm_status=LLMGenerationStatus.FAILED,
            llm_error=f"LLM candidate generation failed: {type(exc).__name__}",
        )

    return CandidateGenerationResult(
        candidates=merged,
        llm_status=LLMGenerationStatus.SUCCEEDED,
    )
