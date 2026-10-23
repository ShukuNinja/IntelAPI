import pytest
from pydantic import ValidationError

from app.modules.test_generation.router import (
    CandidateAssertionInput,
    _candidate_run_report,
    _evaluate_candidate_assertion,
    _execution_report_markdown,
    _response_schema_mismatches,
)


def test_response_schema_mismatch_reports_paths_without_values() -> None:
    mismatches, skipped = _response_schema_mismatches(
        {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "integer"},
                "items": {"type": "array", "items": {"type": "string"}},
            },
        },
        {"id": "private-account-id", "items": ["ok", 42]},
    )
    assert {item["path"] for item in mismatches} == {"$/id", "$/items/1"}
    assert skipped == []
    assert all("private-account-id" not in str(item) for item in mismatches)


def test_response_schema_ref_is_reported_as_skipped_not_mismatch() -> None:
    mismatches, skipped = _response_schema_mismatches({"$ref": "#/components/schemas/User"}, {})
    assert mismatches == []
    assert skipped == ["$"]


def test_candidate_report_records_schema_paths_without_persisting_body_values() -> None:
    secret_value = "account-private-123"
    report = _candidate_run_report(
        operation={
            "id": "operation-1",
            "method": "GET",
            "path": "/account",
            "responses": {
                "200": {
                    "content": {
                        "application/json": {
                            "schema": {"type": "object", "properties": {"id": {"type": "integer"}}}
                        }
                    }
                }
            },
        },
        candidate={
            "id": "candidate-1",
            "kind": "schema",
            "reason": "Check response",
            "mutation": {},
        },
        execution_id="execution-1",
        method="GET",
        origin="http://localhost:8000",
        status_code=200,
        elapsed_ms=5,
        response_bytes=32,
        response_headers={"content-type": "application/json"},
        response_body={"id": secret_value},
        expected_status_code=None,
    )
    assert report["execution"]["response_body_persisted"] is False
    mismatch = next(
        item for item in report["contract_findings"] if item["kind"] == "response_schema_mismatch"
    )
    assert mismatch["mismatches"] == [{"path": "$/id", "rule": "type", "expected": "integer"}]
    assert secret_value not in str(report)
    markdown = _execution_report_markdown(
        {
            "id": "r1",
            "candidate_id": "candidate-1",
            **report,
            "feedback": {
                "action": "propose_next_candidates",
                "reason": "Continue within the proposal budget.",
                "proposal_budget": 1,
                "proposed_candidate_ids": ["candidate-2"],
            },
        }
    )
    assert "$/id" in markdown
    assert "Feedback decision" in markdown
    assert "candidate-2" in markdown


def test_user_json_assertions_record_only_type_and_presence_not_response_values() -> None:
    assertion = CandidateAssertionInput.model_validate(
        {"kind": "json_pointer_type", "pointer": "/account/id", "expected_type": "integer"}
    )
    result = _evaluate_candidate_assertion(
        assertion.model_dump(),
        status_code=200,
        response_headers={},
        response_body={"account": {"id": "private-account-123"}},
    )
    assert result["passed"] is False
    assert result["actual_type"] == "string"
    assert "private-account-123" not in str(result)


def test_header_assertion_is_limited_to_allowlisted_response_headers() -> None:
    assertion = CandidateAssertionInput.model_validate(
        {"kind": "header_equals", "name": "content-type", "expected": "application/json"}
    )
    result = _evaluate_candidate_assertion(
        assertion.model_dump(),
        status_code=200,
        response_headers={"content-type": "application/json"},
        response_body=None,
    )
    assert result["passed"] is True

    with pytest.raises(ValidationError):
        CandidateAssertionInput.model_validate(
            {"kind": "header_equals", "name": "set-cookie", "expected": "secret"}
        )
