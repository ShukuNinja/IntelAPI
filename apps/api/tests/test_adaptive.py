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


def make_candidate(candidate_id: str) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        operation_key="GET /items",
        category=CandidateCategory.POSITIVE,
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
