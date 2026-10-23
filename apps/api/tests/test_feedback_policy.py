import pytest

from app.modules.adaptive.feedback import decide_follow_up


def _decide(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "outcome": "http_response",
        "assertions": [],
        "contract_findings": [],
        "candidate_ids": ["candidate-a", "candidate-b", "candidate-b", "candidate-c"],
        "current_candidate_id": "candidate-a",
        "proposal_budget": 2,
    }
    values.update(overrides)
    return decide_follow_up(**values)  # type: ignore[arg-type]


def test_success_proposes_distinct_other_candidates_within_budget() -> None:
    result = _decide()
    assert result["action"] == "propose_next_candidates"
    assert result["proposed_candidate_ids"] == ["candidate-b", "candidate-c"]
    assert result["automatic_execution"] is False


@pytest.mark.parametrize(
    ("outcome", "assertions", "findings", "action"),
    [
        ("timeout", [], [], "stop_for_transport_review"),
        (
            "http_response",
            [{"passed": False}],
            [],
            "stop_for_assertion_review",
        ),
        (
            "http_response",
            [],
            [{"classification": "contract_observation", "kind": "response_schema_mismatch"}],
            "stop_for_contract_review",
        ),
        (
            "http_response",
            [],
            [{"classification": "analysis_limit"}],
            "stop_for_analysis_limit_review",
        ),
    ],
)
def test_evidence_branches_stop_follow_up_until_review(
    outcome: str,
    assertions: list[dict[str, bool]],
    findings: list[dict[str, str]],
    action: str,
) -> None:
    result = _decide(outcome=outcome, assertions=assertions, contract_findings=findings)
    assert result["action"] == action
    assert result["proposed_candidate_ids"] == []


def test_zero_budget_and_empty_candidate_pool_have_explicit_stop_reasons() -> None:
    assert _decide(proposal_budget=0)["action"] == "stop_proposal_budget_exhausted"
    assert _decide(candidate_ids=["candidate-a"])["action"] == "stop_no_unseen_candidates"


def test_budget_is_bounded() -> None:
    with pytest.raises(ValueError, match="between 0 and 20"):
        _decide(proposal_budget=21)
