"""Explicit, bounded follow-up decisions based on persisted run evidence."""

from typing import Any


def decide_follow_up(
    *,
    outcome: str,
    assertions: list[dict[str, Any]],
    contract_findings: list[dict[str, Any]],
    candidate_ids: list[str],
    current_candidate_id: str,
    proposal_budget: int,
) -> dict[str, Any]:
    """Choose proposals without executing requests or claiming a defect."""
    if proposal_budget < 0 or proposal_budget > 20:
        raise ValueError("proposal_budget must be between 0 and 20.")
    if outcome != "http_response":
        action, reason = (
            "stop_for_transport_review",
            f"The request ended with '{outcome}'; transport/policy outcomes are not "
            "API contract evidence.",
        )
        proposals: list[str] = []
    elif any(assertion.get("passed") is False for assertion in assertions):
        action, reason = (
            "stop_for_assertion_review",
            "At least one explicit assertion failed. Review its evidence before "
            "generating follow-ups.",
        )
        proposals = []
    elif any(item.get("classification") == "contract_observation" for item in contract_findings):
        action, reason = (
            "stop_for_contract_review",
            "A contract observation needs review before additional cases are selected.",
        )
        proposals = []
    elif any(item.get("classification") == "analysis_limit" for item in contract_findings):
        action, reason = (
            "stop_for_analysis_limit_review",
            "A response-contract check was incomplete; review the skipped schema "
            "before continuing.",
        )
        proposals = []
    elif proposal_budget == 0:
        action, reason = (
            "stop_proposal_budget_exhausted",
            "The configured follow-up proposal budget is zero.",
        )
        proposals = []
    else:
        seen = {current_candidate_id}
        proposals = []
        for candidate_id in candidate_ids:
            if candidate_id not in seen:
                seen.add(candidate_id)
                proposals.append(candidate_id)
                if len(proposals) >= proposal_budget:
                    break
        if proposals:
            action = "propose_next_candidates"
            reason = (
                "No assertion or contract observation stopped exploration; propose "
                "distinct candidate IDs with no prior run report in this project."
            )
        else:
            action = "stop_no_unseen_candidates"
            reason = "No distinct candidate IDs remain for this operation."

    return {
        "policy_version": "feedback-rules-v1",
        "action": action,
        "reason": reason,
        "proposal_budget": proposal_budget,
        "proposed_candidate_ids": proposals,
        "automatic_execution": False,
    }
