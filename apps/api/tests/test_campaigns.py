from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import (
    ApiSpecification,
    GenerationReportRecord,
    Project,
    User,
)
from app.modules.campaigns import service
from app.modules.campaigns.router import CampaignCreate, create_campaign


def test_campaign_creation_persists_test_cases_job_and_initial_event(monkeypatch) -> None:
    from app.core.config import Settings
    from app.modules.campaigns import router

    monkeypatch.setattr(router, "get_settings", lambda: Settings(app_env="development"))
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            user = User(google_sub="intelapi-local-single-user", display_name="Local user")
            db.add(user)
            db.flush()
            project = Project(owner_user_id=user.id, name="Campaign project")
            db.add(project)
            db.flush()
            operation_id = "operation-1"
            operation = {
                "id": operation_id,
                "method": "GET",
                "path": "/health",
                "parameters": [],
            }
            specification = ApiSpecification(
                project_id=project.id,
                title="Demo API",
                spec_version="3.1.0",
                source_format="json",
                content_hash="a" * 64,
                source_document={},
                normalized_operations=[operation],
            )
            db.add(specification)
            db.flush()
            generation_report = GenerationReportRecord(
                project_id=project.id,
                specification_id=specification.id,
                policy_version="schema-preview-v1",
                report={
                    "endpoints": [
                        {
                            "operation": {"id": operation_id},
                            "candidates": [
                                {
                                    "id": "candidate-1",
                                    "kind": "parameter-enum-boundary",
                                    "reason": "Probe an unusual query value.",
                                    "mutation": {
                                        "set_parameter": {
                                            "in": "query",
                                            "name": "mode",
                                            "value": "unexpected",
                                        }
                                    },
                                }
                            ],
                        }
                    ]
                },
            )
            db.add(generation_report)
            db.commit()

            response = create_campaign(
                project.id,
                CampaignCreate(
                    name="Demo run",
                    generation_report_id=generation_report.id,
                    base_url="https://api.example.com",
                ),
                db,
            )

            assert response["state"] == "queued"
            assert response["progress"]["test_count"] == 1
            assert db.query(service.CampaignJobRecord).count() == 1
            assert db.query(service.CampaignEventRecord).count() == 1
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_campaign_candidate_mutation_builds_bounded_request() -> None:
    case = service.TestCaseRecord(
        operation_id="operation-1",
        request_override={
            "operation": {
                "id": "operation-1",
                "method": "GET",
                "path": "/health/{region}",
                "parameters": [],
            },
            "candidate": {
                "id": "candidate-1",
                "mutation": {
                    "set_parameter": {
                        "in": "query",
                        "name": "mode",
                        "value": "unexpected",
                    }
                },
            },
        },
    )

    request = service._request_for_case(
        case,
        {
            "base_url": "https://api.example.com",
            "baseline_by_operation": {"operation-1": {"path_parameters": {"region": "us east"}}},
        },
    )

    assert request == {
        "method": "GET",
        "url": "https://api.example.com/health/us%20east?mode=unexpected",
        "headers": {},
        "body": None,
    }


def test_campaign_resolves_environment_values_only_at_execution_time() -> None:
    request = {
        "method": "GET",
        "url": "https://api.example.com/private",
        "headers": {"Authorization": "Bearer {{accessToken}}"},
        "body": '{"token":"{{accessToken}}"}',
    }

    resolved = service._resolve_request_templates(request, {"accessToken": "private-access-token"})

    assert resolved["headers"]["Authorization"] == "Bearer private-access-token"
    assert '"token":"private-access-token"' in resolved["body"]
    assert "private-access-token" not in str(request)
