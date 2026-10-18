"""Tests for deterministic adaptive candidate scoring."""

import pytest

from app.modules.adaptive import (
    AdaptiveScoringConfig,
    CandidateSignals,
    rank_candidates,
    select_next_candidates,
)
from app.modules.test_generation.models import CandidateCategory
from app.modules.test_generation.models import TestCandidate as Candidate


def make_candidate(
    candidate_id: str,
    category: CandidateCategory = CandidateCategory.POSITIVE,
    operation_key: str = "GET /items",
) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        operation_key=operation_key,
        category=category,
        title=f"Test {candidate_id}",
        method="GET",
        path="/items",
        parameters={},
        body=None,
        rationale="Test fixture",
    )


def make_signals(candidate_id: str, **overrides) -> CandidateSignals:
    values = {
        "candidate_id": candidate_id,
        "unexpectedness": 0.5,
        "novelty": 0.5,
        "boundary_relevance": 0.5,
        "inconsistency": 0.5,
        "exploration_value": 0.5,
        "cost_risk_penalty": 0.0,
    }
    values.update(overrides)
    return CandidateSignals(**values)


def test_higher_signal_score_ranks_first():
    candidates = [make_candidate("a"), make_candidate("b")]
    signals = {
        "a": make_signals("a", unexpectedness=0.1),
        "b": make_signals("b", unexpectedness=1.0),
    }

    result = rank_candidates(candidates, signals)

    assert [item.candidate.candidate_id for item in result] == ["b", "a"]
    assert result[0].score > result[1].score


def test_cost_risk_reduces_score():
    candidate = make_candidate("a")
    low_risk = make_signals("a", cost_risk_penalty=0.0)
    high_risk = make_signals("a", cost_risk_penalty=1.0)

    low = rank_candidates([candidate], {"a": low_risk})[0]
    high = rank_candidates([candidate], {"a": high_risk})[0]

    assert low.score > high.score
    assert high.components[-1].contribution < 0


def test_ineligible_candidate_is_never_selected():
    candidates = [make_candidate("unsafe"), make_candidate("safe")]
    signals = {
        "unsafe": make_signals("unsafe", unexpectedness=1.0, eligible=False),
        "safe": make_signals("safe", unexpectedness=0.1),
    }

    result = rank_candidates(candidates, signals)

    assert [item.candidate.candidate_id for item in result] == ["safe"]


def test_ties_use_candidate_id_for_stable_order():
    candidates = [make_candidate("z"), make_candidate("a")]
    signals = {
        "z": make_signals("z"),
        "a": make_signals("a"),
    }

    result = rank_candidates(candidates, signals)

    assert [item.candidate.candidate_id for item in result] == ["a", "z"]
    assert [item.rank for item in result] == [1, 2]


def test_limit_selects_only_top_candidates():
    candidates = [make_candidate("a"), make_candidate("b"), make_candidate("c")]
    signals = {
        "a": make_signals("a", novelty=0.1),
        "b": make_signals("b", novelty=0.9),
        "c": make_signals("c", novelty=0.5),
    }

    result = select_next_candidates(candidates, signals, limit=2)

    assert len(result) == 2
    assert [item.candidate.candidate_id for item in result] == ["b", "c"]


def test_zero_limit_returns_no_candidates():
    result = rank_candidates(
        [make_candidate("a")],
        {"a": make_signals("a")},
        limit=0,
    )

    assert result == ()


def test_negative_limit_is_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        rank_candidates([], {}, limit=-1)


def test_missing_signals_are_rejected():
    with pytest.raises(ValueError, match="Missing scoring signals"):
        rank_candidates([make_candidate("a")], {})


def test_signal_values_must_be_normalized():
    with pytest.raises(ValueError, match="between 0 and 1"):
        make_signals("a", novelty=1.5)


def test_scoring_config_requires_a_positive_weight():
    with pytest.raises(ValueError, match="positive scoring weight"):
        AdaptiveScoringConfig(
            unexpectedness_weight=0.0,
            novelty_weight=0.0,
            boundary_relevance_weight=0.0,
            inconsistency_weight=0.0,
            exploration_value_weight=0.0,
        )


def test_decision_is_deterministic_and_explainable():
    candidate = make_candidate("a")
    signals = make_signals("a", novelty=0.9, evidence_ids=("evidence-1",))

    first = rank_candidates([candidate], {"a": signals})
    second = rank_candidates([candidate], {"a": signals})

    assert first == second
    assert first[0].policy_version == "adaptive-v1"
    assert first[0].evidence_ids == ("evidence-1",)
    assert first[0].components
    assert "not a probability" in first[0].rationale


def test_duplicate_candidate_ids_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        rank_candidates(
            [make_candidate("a"), make_candidate("a")],
            {"a": make_signals("a")},
        )


def test_selection_respects_explicit_cost_budget():
    candidates = [
        make_candidate("a"),
        make_candidate("b"),
        make_candidate("c"),
    ]
    signals = {
        "a": make_signals("a", novelty=1.0),
        "b": make_signals("b", novelty=0.8),
        "c": make_signals("c", novelty=0.6),
    }

    result = select_next_candidates(
        candidates,
        signals,
        limit=3,
        max_cost=2.0,
        candidate_costs={"a": 1.5, "b": 1.0, "c": 1.0},
        diversify=False,
    )

    assert [item.candidate.candidate_id for item in result] == ["a"]
    assert (
        sum({"a": 1.5, "b": 1.0, "c": 1.0}[item.candidate.candidate_id] for item in result) <= 2.0
    )


def test_selection_prefers_a_different_category():
    candidates = [
        make_candidate("a"),
        make_candidate("b", category=CandidateCategory.NEGATIVE),
        make_candidate("c"),
    ]
    signals = {
        "a": make_signals("a", novelty=1.0),
        "b": make_signals("b", novelty=0.9),
        "c": make_signals("c", novelty=0.8),
    }

    result = select_next_candidates(candidates, signals, limit=2)

    assert [item.candidate.candidate_id for item in result] == ["a", "b"]


def test_selection_with_zero_budget_selects_nothing():
    result = select_next_candidates(
        [make_candidate("a")],
        {"a": make_signals("a")},
        limit=2,
        max_cost=0.0,
    )

    assert result == ()


def test_negative_cost_budget_is_rejected():
    with pytest.raises(ValueError, match="max_cost"):
        select_next_candidates([], {}, max_cost=-1.0)


def test_negative_candidate_cost_is_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        select_next_candidates(
            [make_candidate("a")],
            {"a": make_signals("a")},
            candidate_costs={"a": -1.0},
        )


def test_selection_is_deterministic_with_diversity_enabled():
    candidates = [make_candidate("b"), make_candidate("a")]
    signals = {
        "a": make_signals("a"),
        "b": make_signals("b"),
    }

    first = select_next_candidates(candidates, signals, limit=2)
    second = select_next_candidates(candidates, signals, limit=2)

    assert first == second
    assert [item.rank for item in first] == [1, 2]


@pytest.mark.parametrize("invalid_cost", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_candidate_cost_is_rejected(invalid_cost: float):
    with pytest.raises(ValueError, match="finite and non-negative"):
        select_next_candidates(
            [make_candidate("a")],
            {"a": make_signals("a")},
            candidate_costs={"a": invalid_cost},
        )


@pytest.mark.parametrize("invalid_budget", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_budget_is_rejected(invalid_budget: float):
    with pytest.raises(ValueError, match="finite and non-negative"):
        select_next_candidates(
            [],
            {},
            max_cost=invalid_budget,
        )
