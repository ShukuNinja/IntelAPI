"""Tests for candidate validation and deduplication."""

from dataclasses import replace

import pytest

from app.modules.test_generation import (
    CandidateCategory,
    CandidateDeduplicationError,
    CandidateValidationError,
    deduplicate_candidates,
    validate_candidate,
)
from app.modules.test_generation import TestCandidate as Candidate


@pytest.fixture
def candidate() -> Candidate:
    return Candidate(
        candidate_id="candidate-1",
        operation_key="GET /users",
        category=CandidateCategory.POSITIVE,
        title="Baseline request",
        method="GET",
        path="/users",
        parameters={"limit": 10},
        body=None,
        rationale="Baseline test.",
    )


def test_valid_candidate_is_returned_unchanged(
    candidate: Candidate,
) -> None:
    assert validate_candidate(candidate) is candidate


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("candidate_id", ""),
        ("operation_key", " "),
        ("title", ""),
        ("method", "get"),
        ("method", "INVALID"),
        ("path", "users"),
        ("path", "/users with spaces"),
        ("parameters", {1: "invalid"}),
        ("body", []),
    ],
)
def test_invalid_candidate_is_rejected(
    candidate: Candidate,
    field: str,
    value: object,
) -> None:
    invalid = replace(candidate, **{field: value})
    with pytest.raises(CandidateValidationError):
        validate_candidate(invalid)


def test_non_json_parameter_value_is_rejected(
    candidate: Candidate,
) -> None:
    invalid = replace(candidate, parameters={"value": object()})
    with pytest.raises(CandidateValidationError):
        validate_candidate(invalid)


def test_payload_size_limit_is_enforced(
    candidate: Candidate,
) -> None:
    invalid = replace(candidate, parameters={"value": "x" * 100})
    with pytest.raises(CandidateValidationError, match="limit"):
        validate_candidate(invalid, max_payload_bytes=10)


def test_identical_candidates_are_deduplicated(
    candidate: Candidate,
) -> None:
    result = deduplicate_candidates([candidate, candidate])

    assert result == (candidate,)


def test_conflicting_candidates_with_same_id_are_rejected(
    candidate: Candidate,
) -> None:
    conflicting = replace(candidate, title="Different candidate")

    with pytest.raises(CandidateDeduplicationError, match="Conflicting"):
        deduplicate_candidates([candidate, conflicting])


def test_deduplication_order_is_deterministic(
    candidate: Candidate,
) -> None:
    other = replace(candidate, candidate_id="candidate-2")

    first = deduplicate_candidates([other, candidate])
    second = deduplicate_candidates([candidate, other])

    assert first == second
    assert [item.candidate_id for item in first] == [
        "candidate-1",
        "candidate-2",
    ]
