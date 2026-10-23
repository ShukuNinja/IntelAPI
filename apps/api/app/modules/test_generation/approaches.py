"""Distinct candidate-generation policies for experimental runs."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.integrations.llm import LLMProvider, LLMProviderError, LLMResponse, create_llm_provider
from app.modules.api_understanding.models import NormalizedOperation
from app.modules.test_generation.deduplication import deduplicate_candidates
from app.modules.test_generation.generator import generate_candidates
from app.modules.test_generation.llm_assisted import bounded_semantic_facts, generate_llm_candidates
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
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_token_usage: int | None = None
    rejected_candidates: tuple[dict[str, Any], ...] = ()
    valid_candidate_count: int | None = None
    llm_request_attempted: bool = False
    requested_candidate_count: int = 0
    generation_errors: tuple[dict[str, Any], ...] = ()
    attempt_count: int = 0
    completion_received: bool = False
    local_parse_succeeded: bool = False
    local_validation_succeeded: bool = False
    validation_duration_ms: int = 0


POLICY_VERSIONS = {
    GenerationApproach.LLM_BASELINE: "llm-baseline-v1",
    GenerationApproach.SEMANTIC_ASSISTED: "semantic-context-v1",
    GenerationApproach.FEEDBACK_GUIDED: "feedback-seed-v1",
    GenerationApproach.EVIDENCE_BACKED: "evidence-priority-v1",
}


def _attempt_count(errors: Sequence[dict[str, Any]], response_count: int) -> int:
    local_failures = {"local_validation_failed", "malformed_output", "output_truncated"}
    provider_error_count = sum(item.get("category") not in local_failures for item in errors)
    return response_count + provider_error_count


def generate_for_approach(
    approach: GenerationApproach,
    operations: tuple[NormalizedOperation, ...],
    *,
    semantic_facts_by_operation: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    provider: LLMProvider | None = None,
    allow_llm: bool = True,
    llm_provider_name: str | None = None,
    llm_model_name: str | None = None,
    candidate_count: int = 4,
    max_attempts: int = 2,
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
                len(
                    bounded_semantic_facts(
                        semantic_facts_by_operation.get(operation.operation_key, ())
                    )
                )
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
    rejected_candidates: list[dict[str, Any]] = []
    generation_errors: list[dict[str, Any]] = []
    parse_results: list[bool] = []
    validation_results: list[bool] = []
    validation_duration_ms = 0
    validation_durations: list[int] = []
    try:
        configured_provider = (
            provider
            if provider is not None
            else create_llm_provider(
                provider_name=llm_provider_name,
                model_name=llm_model_name,
            )
        )
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
        responses: list[LLMResponse] = []

        def record_rejection(item: dict[str, Any]) -> None:
            rejected_candidates.append(item)
            if item.get("kind") == "candidate":
                generation_errors.append(
                    {
                        "category": "local_validation_failed",
                        "message": str(item.get("reason", "Candidate failed validation."))[:300],
                        "http_status": None,
                        "provider": getattr(configured_provider, "provider_name", None),
                        "model": getattr(configured_provider, "model_name", None),
                        "attempt": 1,
                        "retryable": False,
                        "failed_generation": None,
                        "completion_received": True,
                        "local_parse_succeeded": True,
                        "local_validation_succeeded": False,
                    }
                )

        def record_validation_duration(duration_ms: int) -> None:
            validation_durations.append(duration_ms)

        for operation in operations:
            facts: Sequence[Mapping[str, Any]] = ()
            if approach is GenerationApproach.SEMANTIC_ASSISTED and semantic_facts_by_operation:
                facts = bounded_semantic_facts(
                    semantic_facts_by_operation.get(operation.operation_key, ())
                )
            operation_candidates = generate_llm_candidates(
                operation,
                configured_provider,
                semantic_facts=facts,
                on_response=responses.append,
                on_rejection=record_rejection,
                candidate_count=candidate_count,
                max_attempts=max_attempts,
                on_error=generation_errors.append,
                on_parse_result=parse_results.append,
                on_validation_result=validation_results.append,
                on_validation_duration=record_validation_duration,
            )
            validation_duration_ms = sum(validation_durations)
            proposals.extend(operation_candidates)
    except LLMProviderError as exc:
        return _fallback_result(
            approach,
            fallback,
            semantic_count,
            f"LLM provider error [{exc.code}]: {exc} Deterministic candidates were used.",
            "failed",
            rejected_candidates,
            len(proposals),
            llm_request_attempted=True,
            requested_candidate_count=candidate_count,
            generation_errors=generation_errors,
            attempt_count=_attempt_count(generation_errors, len(responses)),
            completion_received=bool(responses),
            local_parse_succeeded=bool(parse_results) and all(parse_results),
            local_validation_succeeded=bool(validation_results) and all(validation_results),
            validation_duration_ms=validation_duration_ms,
        )
    except Exception:
        return _fallback_result(
            approach,
            fallback,
            semantic_count,
            "LLM candidate generation failed unexpectedly. Deterministic candidates were used.",
            "failed",
            rejected_candidates,
            len(proposals),
            llm_request_attempted=True,
            requested_candidate_count=candidate_count,
            generation_errors=generation_errors,
            attempt_count=_attempt_count(generation_errors, len(responses)),
            completion_received=bool(responses),
            local_parse_succeeded=bool(parse_results) and all(parse_results),
            local_validation_succeeded=bool(validation_results) and all(validation_results),
            validation_duration_ms=validation_duration_ms,
        )

    unique_proposals = deduplicate_candidates(proposals)
    if not unique_proposals:
        return _fallback_result(
            approach,
            fallback,
            semantic_count,
            "The LLM returned no candidates; deterministic candidates were used.",
            "empty",
            rejected_candidates,
            len(proposals),
            llm_request_attempted=True,
            requested_candidate_count=candidate_count,
            generation_errors=generation_errors,
            attempt_count=_attempt_count(generation_errors, len(responses)),
            completion_received=bool(responses),
            local_parse_succeeded=bool(parse_results) and all(parse_results),
            local_validation_succeeded=bool(validation_results) and all(validation_results),
            validation_duration_ms=validation_duration_ms,
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
        llm_provider=(
            responses[0].provider
            if responses
            else getattr(configured_provider, "provider_name", None)
        ),
        llm_model=(
            responses[0].model if responses else getattr(configured_provider, "model_name", None)
        ),
        llm_token_usage=(
            sum(response.total_tokens or 0 for response in responses)
            if responses and all(response.total_tokens is not None for response in responses)
            else None
        ),
        rejected_candidates=tuple(rejected_candidates),
        valid_candidate_count=len(unique_proposals),
        llm_request_attempted=True,
        requested_candidate_count=candidate_count,
        generation_errors=tuple(generation_errors),
        attempt_count=_attempt_count(generation_errors, len(responses)),
        completion_received=bool(responses),
        local_parse_succeeded=bool(parse_results) and all(parse_results),
        local_validation_succeeded=bool(validation_results) and all(validation_results),
        validation_duration_ms=validation_duration_ms,
    )


def _fallback_result(
    approach: GenerationApproach,
    candidates: tuple[TestCandidate, ...],
    semantic_fact_count: int,
    warning: str,
    llm_status: str,
    rejected_candidates: Sequence[dict[str, Any]] = (),
    valid_candidate_count: int | None = None,
    llm_request_attempted: bool = False,
    requested_candidate_count: int = 0,
    generation_errors: Sequence[dict[str, Any]] = (),
    attempt_count: int = 0,
    completion_received: bool = False,
    local_parse_succeeded: bool = False,
    local_validation_succeeded: bool = False,
    validation_duration_ms: int = 0,
) -> ApproachGenerationResult:
    return ApproachGenerationResult(
        approach=approach,
        candidates=candidates,
        generation_policy_version=POLICY_VERSIONS[approach],
        generation_mode="deterministic_fallback",
        llm_status=llm_status,
        warning=warning,
        semantic_fact_count=semantic_fact_count,
        rejected_candidates=tuple(rejected_candidates),
        valid_candidate_count=valid_candidate_count,
        llm_request_attempted=llm_request_attempted,
        requested_candidate_count=requested_candidate_count,
        generation_errors=tuple(generation_errors),
        attempt_count=attempt_count,
        completion_received=completion_received,
        local_parse_succeeded=local_parse_succeeded,
        local_validation_succeeded=local_validation_succeeded,
        validation_duration_ms=validation_duration_ms,
    )
