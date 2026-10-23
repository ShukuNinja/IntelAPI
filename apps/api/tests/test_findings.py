from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import ExecutionReportRecord, Project, User
from app.modules.findings.router import (
    TriageInput,
    _observations,
    list_findings,
    update_finding_triage,
)


def test_findings_are_derived_from_contract_observations_and_failed_assertions_only() -> None:
    observations = _observations(
        {
            "contract_findings": [{"kind": "undocumented_status", "status_code": 418}],
            "assertions": [
                {"kind": "status_code", "passed": True},
                {"kind": "json_pointer_type", "pointer": "/id", "passed": False},
            ],
        }
    )

    assert [item["evidence_key"] for item in observations] == ["contract:0", "assertion:1"]
    assert "classification" not in observations[0]["details"]
    assert observations[1]["details"]["pointer"] == "/id"


def test_finding_triage_is_saved_without_promoting_other_observations() -> None:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            user = User(google_sub="intelapi-local-single-user", display_name="Local user")
            db.add(user)
            db.flush()
            project = Project(owner_user_id=user.id, name="Review")
            db.add(project)
            db.flush()
            report = ExecutionReportRecord(
                project_id=project.id,
                specification_id=uuid4(),
                execution_id=uuid4(),
                candidate_id="candidate-safe",
                report={
                    "operation": {"method": "GET", "path": "/items"},
                    "execution": {"status_code": 200},
                    "contract_findings": [{"kind": "undocumented_status"}],
                    "assertions": [{"kind": "json_pointer_exists", "passed": False}],
                },
            )
            db.add(report)
            db.commit()

            before = list_findings(project.id, db)
            assert [item["classification"] for item in before] == ["untriaged", "untriaged"]
            update_finding_triage(
                project.id,
                report.id,
                "assertion:0",
                TriageInput(classification="false_positive", notes="Expected on this endpoint"),
                db,
            )
            after = list_findings(project.id, db)

            assert after[0]["classification"] == "untriaged"
            assert after[1]["classification"] == "false_positive"
            assert after[1]["notes"] == "Expected on this endpoint"
    finally:
        engine.dispose()
