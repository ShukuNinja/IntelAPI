"""Distinct candidate-generation policies for experimental runs."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.integrations.llm import LLMProvider, create_llm_provider
from app.modules.api_understanding.models import NormalizedOperation
from app.modules.test_generation.deduplication import deduplicate_candidates
from app.modules.test_generation.generator import generate_candidates
from app.modules.test_generation.llm_assisted import generate_llm_candidates
from app.modules.test_generation.models import TestCandidate


class GenerationApproach(StrEnum):
    """Selectable workbench approaches; policies are versioned independently."""

    LLM_BASELINE = "llm_baseline"
    SEMANTIC_ASSISTED = "semantic_assisted"
    FEEDBACK_GUIDED = "feedback_guided"
    EVIDENCE_BACKED = "evidence_backed"


@dataclass(frozen=True, slots=True)
class ApproachGenerationResult:
    """Candidate pool and auditable generation metadata for one approach."""

    approach: GenerationApproach
    candidates: tuple[TestCandidate, ...]
    generation_policy_version: str
    generation_mode: str
    llm_status: str
    warning: str | None = None
    semantic_fact_count: int = 0


POLICY_VERSIONS = {
    GenerationApproach.LLM_BASELINE: "llm-baseline-v1",
    GenerationApproach.SEMANTIC_ASSISTED: "semantic-context-v1",
    GenerationApproach.FEEDBACK_GUIDED: "feedback-seed-v1",
    GenerationApproach.EVIDENCE_BACKED: "evidence-priority-v1",
}


def generate_for_approach(
    approach: GenerationApproach,
    operations: tuple[NormalizedOperation, ...],
    *,
    semantic_facts_by_operation: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    provider: LLMProvider | None = None,
    allow_llm: bool = True,
) -> ApproachGenerationResult:
    """Generate a validated candidate pool using one explicit approach policy.

    Approaches A and B use LLM proposals when a provider is available and fall
    back to deterministic candidates otherwise. A receives only the normalized
    OpenAPI operation; B additionally receives the persisted extracted facts
    supplied by the caller. C and D start from the same deterministic pool;
    their execution-time selection policies are applied by the workbench runner.
    """
    if not isinstance(approach, GenerationApproach):
        raise ValueError("Unsupported experimental generation approach.")

    if approach in {GenerationApproach.FEEDBACK_GUIDED, GenerationApproach.EVIDENCE_BACKED}:
        return ApproachGenerationResult(
            approach=approach,
            candidates=generate_candidates(operations),
            generation_policy_version=POLICY_VERSIONS[approach],
            generation_mode="deterministic_pool",
            llm_status="not_used",
        )

    semantic_count = 0
    if approach is GenerationApproach.SEMANTIC_ASSISTED:
        semantic_count = (
            sum(
                len(semantic_facts_by_operation.get(operation.operation_key, ()))
                for operation in operations
            )
            if semantic_facts_by_operation is not None
            else 0
        )

    fallback = generate_candidates(operations)
    if not allow_llm:
        return _fallback_result(
            approach,
            fallback,
            semantic_count,
            "LLM generation is disabled for this experiment.",
            "disabled",
        )
    try:
        configured_provider = provider if provider is not None else create_llm_provider()
    except Exception:
        return _fallback_result(
            approach,
            fallback,
            semantic_count,
            "The configured LLM provider could not be initialized.",
            "failed",
        )

    if configured_provider is None:
        warning = "No LLM provider is configured; deterministic candidates were used."
        if approach is GenerationApproach.SEMANTIC_ASSISTED and semantic_count == 0:
            warning += " No extracted semantic facts were available."
        return _fallback_result(approach, fallback, semantic_count, warning, "not_configured")

    try:
        proposals: list[TestCandidate] = []
        for operation in operations:
            facts: Sequence[Mapping[str, Any]] = ()
            if approach is GenerationApproach.SEMANTIC_ASSISTED and semantic_facts_by_operation:
                facts = semantic_facts_by_operation.get(operation.operation_key, ())
            proposals.extend(
                generate_llm_candidates(operation, configured_provider, semantic_facts=facts)
            )
    except Exception as exc:
        return _fallback_result(
            approach,
            fallback,
            semantic_count,
            f"LLM candidate generation failed: {type(exc).__name__}.",
            "failed",
        )

    unique_proposals = deduplicate_candidates(proposals)
    if not unique_proposals:
        return _fallback_result(
            approach,
            fallback,
            semantic_count,
            "The LLM returned no candidates; deterministic candidates were used.",
            "empty",
        )

    return ApproachGenerationResult(
        approach=approach,
        candidates=unique_proposals,
        generation_policy_version=POLICY_VERSIONS[approach],
        generation_mode="llm",
        llm_status="succeeded",
        warning=(
            "No extracted semantic facts were available for this run."
            if approach is GenerationApproach.SEMANTIC_ASSISTED and semantic_count == 0
            else None
        ),
        semantic_fact_count=semantic_count,
    )


def _fallback_result(
    approach: GenerationApproach,
    candidates: tuple[TestCandidate, ...],
    semantic_fact_count: int,
    warning: str,
    llm_status: str,
) -> ApproachGenerationResult:
    return ApproachGenerationResult(
        approach=approach,
        candidates=candidates,
        generation_policy_version=POLICY_VERSIONS[approach],
        generation_mode="deterministic_fallback",
        llm_status=llm_status,
        warning=warning,
        semantic_fact_count=semantic_fact_count,
    )
