from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import AssertionResultRecord, ExecutionRecord, HealthCheckRecord, Project, User
from app.modules.health_checks.router import (
    AssertionInput,
    _evaluate_assertion,
    _resolve_pointer,
    list_health_check_runs,
)


@pytest.mark.parametrize(
    ("assertion", "response", "passed"),
    [
        (
            {"type": "status_code", "status_code": 204},
            {"status_code": 204, "elapsed_ms": 4, "headers": {}, "body": None},
            True,
        ),
        (
            {"type": "latency_ms", "max_ms": 40},
            {"status_code": 200, "elapsed_ms": 41, "headers": {}, "body": {}},
            False,
        ),
        (
            {"type": "json_pointer", "pointer": "/ok", "operator": "equals", "expected": True},
            {"status_code": 200, "elapsed_ms": 1, "headers": {}, "body": {"ok": True}},
            True,
        ),
        (
            {"type": "header_equals", "header": "content-type", "expected": "application/json"},
            {
                "status_code": 200,
                "elapsed_ms": 1,
                "headers": {"content-type": "application/json"},
                "body": {},
            },
            True,
        ),
    ],
)
def test_assertion_types_evaluate_deterministically(assertion, response, passed) -> None:
    payload = AssertionInput.model_validate(assertion).model_dump()
    assert _evaluate_assertion(payload, response)["passed"] is passed


def test_json_pointer_reports_only_presence_and_type_not_sensitive_response_value() -> None:
    response = {
        "status_code": 200,
        "elapsed_ms": 10,
        "headers": {},
        "body": {"token": "private-access-token"},
    }
    assertion = AssertionInput.model_validate(
        {
            "type": "json_pointer",
            "pointer": "/token",
            "operator": "type",
            "expected_type": "integer",
        }
    ).model_dump()
    result = _evaluate_assertion(assertion, response)
    assert result["passed"] is False
    assert "private-access-token" not in str(result)
    assert _resolve_pointer(response["body"], "/token") == (True, "private-access-token")


def test_disallowed_response_headers_are_rejected_by_assertion_schema() -> None:
    with pytest.raises(ValidationError):
        AssertionInput.model_validate(
            {"type": "header_equals", "header": "set-cookie", "expected": "secret"}
        )


def test_health_check_run_history_returns_saved_assertion_metadata_only() -> None:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            user = User(google_sub="intelapi-local-single-user", display_name="Local user")
            db.add(user)
            db.flush()
            project = Project(owner_user_id=user.id, name="Monitoring")
            db.add(project)
            db.flush()
            check = HealthCheckRecord(
                project_id=project.id,
                name="Status check",
                definition={
                    "assertions": [
                        {"type": "status_code", "status_code": 200},
                        {"type": "json_pointer", "pointer": "/token", "operator": "exists"},
                    ]
                },
                enabled=True,
            )
            db.add(check)
            db.commit()
            execution = ExecutionRecord(
                project_id=project.id,
                outcome="http_response",
                request_snapshot={
                    "method": "GET",
                    "origin": "http://localhost:9000",
                    "health_check_id": str(check.id),
                },
                status_code=200,
                duration_ms=8,
                response_headers={"content-type": "application/json"},
                response_size_bytes=30,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            db.add(execution)
            db.flush()
            db.add_all(
                [
                    AssertionResultRecord(
                        execution_id=execution.id,
                        assertion_type="status_code",
                        passed=True,
                        expected=200,
                        actual=None,
                        message="Assertion passed.",
                    ),
                    AssertionResultRecord(
                        execution_id=execution.id,
                        assertion_type="json_pointer",
                        passed=True,
                        expected=None,
                        actual=None,
                        message="JSON pointer /token matched.",
                    ),
                ]
            )
            db.commit()
            history = list_health_check_runs(project.id, check.id, db, limit=50)

            assert history[0]["passed"] is True
            assert len(history[0]["assertions"]) == 2
            assert "private-access-token" not in str(history)
    finally:
        engine.dispose()
