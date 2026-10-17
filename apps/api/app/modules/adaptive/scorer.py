"""Explainable scoring and follow-up selection for test candidates."""

from collections.abc import Mapping, Sequence

from app.modules.adaptive.models import (
    AdaptiveScoringConfig,
    CandidateSignals,
    RankedCandidate,
    ScoreComponent,
)
from app.modules.test_generation.models import TestCandidate

DEFAULT_SCORING_CONFIG = AdaptiveScoringConfig()


def rank_candidates(
    candidates: Sequence[TestCandidate],
    signals_by_candidate: Mapping[str, CandidateSignals],
    *,
    limit: int | None = None,
    config: AdaptiveScoringConfig = DEFAULT_SCORING_CONFIG,
) -> tuple[RankedCandidate, ...]:
    """Rank eligible candidates using a deterministic weighted heuristic.

    All candidates must have matching signal records. Ineligible candidates
    are excluded before scoring. Equal scores are ordered by candidate ID.
    This function does not execute requests or persist decisions.
    """
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative or None")

    candidate_ids = [candidate.candidate_id for candidate in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("Candidate IDs must be unique")

    scored: list[tuple[TestCandidate, CandidateSignals, float, tuple[ScoreComponent, ...]]] = []

    positive_weights = (
        ("unexpectedness", config.unexpectedness_weight),
        ("novelty", config.novelty_weight),
        ("boundary_relevance", config.boundary_relevance_weight),
        ("inconsistency", config.inconsistency_weight),
        ("exploration_value", config.exploration_value_weight),
    )
    weight_total = sum(weight for _, weight in positive_weights)

    for candidate in candidates:
        signals = signals_by_candidate.get(candidate.candidate_id)
        if signals is None:
            raise ValueError(
                f"Missing scoring signals for candidate {candidate.candidate_id!r}"
            )
        if signals.candidate_id != candidate.candidate_id:
            raise ValueError("Signal candidate ID does not match its mapping key")
        if not signals.eligible:
            continue

        component_list: list[ScoreComponent] = []
        positive_score = 0.0

        for name, weight in positive_weights:
            raw_value = getattr(signals, name)
            normalized_weight = weight / weight_total
            contribution = raw_value * normalized_weight
            positive_score += contribution
            component_list.append(
                ScoreComponent(
                    name=name,
                    raw_value=raw_value,
                    weight=normalized_weight,
                    contribution=contribution,
                )
            )

        risk_contribution = (
            signals.cost_risk_penalty * config.cost_risk_weight
        )
        score = round(max(0.0, positive_score - risk_contribution), 6)
        component_list.append(
            ScoreComponent(
                name="cost_risk_penalty",
                raw_value=signals.cost_risk_penalty,
                weight=config.cost_risk_weight,
                contribution=-risk_contribution,
            )
        )
        scored.append((candidate, signals, score, tuple(component_list
        )))

    scored.sort(key=lambda item: (-item[2], item[0].candidate_id))

    if limit is not None:
        scored = scored[:limit]

    ranked: list[RankedCandidate] = []
    for rank, (candidate, signals, score, components) in enumerate(scored, start=1):
        component_tuple = tuple(components)
        strongest = sorted(
            (component for component in components if component.contribution > 0),
            key=lambda component: (-component.contribution, component.name),
        )[:2]
        strongest_text = ", ".join(
            f"{component.name.replace('_', ' ')}"
            for component in strongest
        )
        rationale = (
            f"Score {score:.3f} under {config.policy_version}; "
            f"highest positive contributors: {strongest_text or 'none'}. "
            f"Cost/risk penalty: {signals.cost_risk_penalty:.2f}. "
            "This is a prioritization heuristic, not a probability of failure."
        )
        ranked.append(
            RankedCandidate(
                rank=rank,
                candidate=candidate,
                score=score,
                components=component_tuple,
                evidence_ids=signals.evidence_ids,
                rationale=rationale,
                policy_version=config.policy_version,
            )
        )

    return tuple(ranked)


def select_next_candidates(
    candidates: Sequence[TestCandidate],
    signals_by_candidate: Mapping[str, CandidateSignals],
    *,
    limit: int = 1,
    config: AdaptiveScoringConfig = DEFAULT_SCORING_CONFIG,
) -> tuple[RankedCandidate, ...]:
    """Return the highest-ranked eligible candidates for the next iteration."""
    return rank_candidates(
        candidates,
        signals_by_candidate,
        limit=limit,
        config=config,
    )
