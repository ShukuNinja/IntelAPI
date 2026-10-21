from contextlib import contextmanager
from uuid import UUID, uuid4

SPEC = """openapi: 3.1.0
info:
  title: Route test API
  version: '1.0'
paths:
  /items:
    get:
      summary: List items
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                required: [items]
                properties:
                  items:
                    type: array
"""


def _project(client) -> str:
    response = client.post("/api/v1/projects", json={"name": f"flow-{uuid4()}"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _saved_request(client, project_id: str) -> str:
    response = client.post(
        f"/api/v1/projects/{project_id}/requests",
        json={
            "name": "Example health request",
            "method": "GET",
            "url_template": "https://example.com/health",
            "headers": {},
            "query_params": {},
            "body": None,
            "body_type": "none",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_import_specification_persists_operations_facts_and_preview(authenticated_client):
    client = authenticated_client
    project_id = _project(client)
    imported = client.post(
        f"/api/v1/projects/{project_id}/specifications/import",
        json={"content": SPEC},
    )
    assert imported.status_code == 201, imported.text
    specification_id = imported.json()["id"]
    assert imported.json()["operation_count"] == 1

    operations = client.get(f"/api/v1/specifications/{specification_id}/operations")
    assert operations.status_code == 200, operations.text
    operation = operations.json()["items"][0]
    assert operation["operation_key"] == "GET /items"

    facts = client.get(f"/api/v1/operations/{operation['id']}/knowledge-facts")
    assert facts.status_code == 200, facts.text
    assert any(fact["fact_type"] == "response_schema" for fact in facts.json())

    preview = client.post(f"/api/v1/operations/{operation['id']}/candidates/preview", json={})
    assert preview.status_code == 200, preview.text
    assert preview.json()["persisted"] is False


def test_campaign_creation_is_durable_and_cancellable(authenticated_client):
    client = authenticated_client
    project_id = _project(client)
    request_id = _saved_request(client, project_id)
    response = client.post(
        f"/api/v1/projects/{project_id}/campaigns",
        json={"name": "Bounded check", "saved_request_ids": [request_id]},
    )
    assert response.status_code == 202, response.text
    campaign = response.json()
    campaign_id = campaign["id"]
    assert campaign["state"] == "queued"
    assert campaign["test_count"] == 1

    tests = client.get(f"/api/v1/campaigns/{campaign_id}/tests")
    events = client.get(f"/api/v1/campaigns/{campaign_id}/events")
    assert tests.status_code == 200 and len(tests.json()) == 1
    assert events.status_code == 200
    assert events.json()[0]["event_type"] == "campaign_queued"

    cancelled = client.post(f"/api/v1/campaigns/{campaign_id}/cancel", json={})
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["cancel_requested_at"] is not None


def test_openapi_operation_campaign_generates_persisted_cases(authenticated_client):
    client = authenticated_client
    project_id = _project(client)
    imported = client.post(
        f"/api/v1/projects/{project_id}/specifications/import", json={"content": SPEC}
    )
    assert imported.status_code == 201, imported.text
    specification_id = imported.json()["id"]
    operations = client.get(f"/api/v1/specifications/{specification_id}/operations")
    operation_id = operations.json()["items"][0]["id"]
    environment = client.post(
        f"/api/v1/projects/{project_id}/environments",
        json={"name": "Campaign target", "base_url": "https://example.com"},
    )
    assert environment.status_code == 201, environment.text

    response = client.post(
        f"/api/v1/projects/{project_id}/campaigns",
        json={
            "name": "OpenAPI validation",
            "operation_ids": [operation_id],
            "categories": ["positive", "schema"],
            "environment_id": environment.json()["id"],
        },
    )
    assert response.status_code == 202, response.text
    assert response.json()["configuration"]["input_type"] == "openapi_operations"
    assert response.json()["test_count"] >= 1
    cases = client.get(f"/api/v1/campaigns/{response.json()['id']}/tests")
    assert cases.status_code == 200, cases.text
    assert all(case["request_override"]["source"] == "openapi_candidate" for case in cases.json())
    positive = next(case for case in cases.json() if case["category"] == "positive")
    assert positive["expected_behavior"]["assertions"]


def test_health_run_records_results_and_creates_evidence_backed_finding(
    authenticated_client, monkeypatch
):
    from app.api.health_checks import router as health_router
    from app.models.execution import Execution

    client = authenticated_client
    project_id = _project(client)
    request_id = _saved_request(client, project_id)
    created = client.post(
        f"/api/v1/projects/{project_id}/health-checks",
        json={
            "name": "Expected healthy response",
            "saved_request_id": request_id,
            "assertions": [{"type": "status_code", "expected": 200}],
        },
    )
    assert created.status_code == 201, created.text

    def fake_execute(db, saved_request, owner_user_id, environment_override_id, timeout_seconds):
        del owner_user_id, environment_override_id, timeout_seconds
        execution = Execution(
            project_id=saved_request.project_id,
            saved_request_id=saved_request.id,
            status="completed",
            method="GET",
            url="https://example.com/health",
            response_status_code=503,
            response_headers={"content-type": "application/json"},
            response_body="{}",
            duration_ms=4,
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return execution

    monkeypatch.setattr(health_router, "execute_saved_request", fake_execute)
    run = client.post(f"/api/v1/health-checks/{created.json()['id']}/run", json={})
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "degraded"
    assert run.json()["assertions"][0]["actual"] == 503

    findings = client.get(f"/api/v1/projects/{project_id}/findings")
    assert findings.status_code == 200, findings.text
    finding = findings.json()["items"][0]
    assert finding["classification"] == "assertion_mismatch"
    assert finding["evidence_count"] == 2
    evidence = client.get(f"/api/v1/findings/{finding['id']}/evidence")
    assert evidence.status_code == 200 and len(evidence.json()) == 2

    triaged = client.patch(
        f"/api/v1/findings/{finding['id']}",
        json={"user_status": "confirmed", "user_severity": "high", "triage_note": "Reviewed"},
    )
    assert triaged.status_code == 200, triaged.text
    assert triaged.json()["classification"] == "assertion_mismatch"
    assert triaged.json()["user_status"] == "confirmed"


def test_health_response_schema_assertion_records_validity(authenticated_client, monkeypatch):
    from app.api.health_checks import router as health_router
    from app.models.execution import Execution

    client = authenticated_client
    project_id = _project(client)
    request_id = _saved_request(client, project_id)
    invalid = client.post(
        f"/api/v1/projects/{project_id}/health-checks",
        json={
            "name": "Unsupported remote schema",
            "saved_request_id": request_id,
            "assertions": [
                {"type": "response_schema", "expected": {"$ref": "https://example.com/schema"}}
            ],
        },
    )
    assert invalid.status_code == 422
    created = client.post(
        f"/api/v1/projects/{project_id}/health-checks",
        json={
            "name": "Response schema",
            "saved_request_id": request_id,
            "assertions": [
                {
                    "type": "response_schema",
                    "expected": {
                        "type": "object",
                        "required": ["items"],
                        "properties": {"items": {"type": "array", "items": {"type": "string"}}},
                    },
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    body = {"value": "{}"}

    def fake_execute(db, saved_request, owner_user_id, environment_override_id, timeout_seconds):
        del owner_user_id, environment_override_id, timeout_seconds
        execution = Execution(
            project_id=saved_request.project_id,
            saved_request_id=saved_request.id,
            status="completed",
            method="GET",
            url="https://example.com/health",
            response_status_code=200,
            response_headers={"content-type": "application/json"},
            response_body=body["value"],
            duration_ms=3,
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return execution

    monkeypatch.setattr(health_router, "execute_saved_request", fake_execute)
    first = client.post(f"/api/v1/health-checks/{created.json()['id']}/run", json={})
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "degraded"
    assert first.json()["assertions"][0]["actual"]["valid"] is False
    assert any(
        "required property is missing" in issue
        for issue in first.json()["assertions"][0]["actual"]["violations"]
    )

    body["value"] = '{"items": ["one", "two"]}'
    second = client.post(f"/api/v1/health-checks/{created.json()['id']}/run", json={})
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "healthy"
    assert second.json()["assertions"][0]["actual"]["valid"] is True


def test_transport_failure_is_unavailable_not_a_potential_finding(
    authenticated_client, monkeypatch
):
    from app.api.health_checks import router as health_router
    from app.models.execution import Execution

    client = authenticated_client
    project_id = _project(client)
    request_id = _saved_request(client, project_id)
    created = client.post(
        f"/api/v1/projects/{project_id}/health-checks",
        json={
            "name": "Unavailable target",
            "saved_request_id": request_id,
            "assertions": [{"type": "status_code", "expected": 200}],
        },
    )
    assert created.status_code == 201, created.text

    def failed_execute(db, saved_request, owner_user_id, environment_override_id, timeout_seconds):
        del owner_user_id, environment_override_id, timeout_seconds
        execution = Execution(
            project_id=saved_request.project_id,
            saved_request_id=saved_request.id,
            status="failed",
            method="GET",
            url="https://example.com/health",
            response_headers={},
            error_code="NETWORK_ERROR",
            error_message="Unable to reach target.",
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return execution

    monkeypatch.setattr(health_router, "execute_saved_request", failed_execute)
    run = client.post(f"/api/v1/health-checks/{created.json()['id']}/run", json={})
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "unavailable"
    history = client.get(f"/api/v1/health-checks/{created.json()['id']}/results")
    assert history.status_code == 200, history.text
    assert history.json()[0]["execution_status"] == "failed"
    findings = client.get(f"/api/v1/projects/{project_id}/findings")
    assert findings.status_code == 200
    assert findings.json()["items"] == []


def test_campaign_worker_claims_lease_executes_once_and_completes(
    authenticated_client, monkeypatch
):
    import app.worker as worker_module
    from app.db.session import get_db as original_get_db
    from app.main import app
    from app.models.campaign import Campaign
    from app.models.execution import Execution
    from app.worker import claim_job, process_campaign

    client = authenticated_client
    project_id = _project(client)
    request_id = _saved_request(client, project_id)
    queued = client.post(
        f"/api/v1/projects/{project_id}/campaigns",
        json={"name": "Worker verification", "saved_request_ids": [request_id]},
    )
    assert queued.status_code == 202, queued.text
    campaign_id = queued.json()["id"]
    db_generator = app.dependency_overrides[original_get_db]()
    db = next(db_generator)

    class SessionProxy:
        def __enter__(self):
            return db

        def __exit__(self, *args):
            return False

    def session_factory():
        return SessionProxy()

    @contextmanager
    def nested_transaction():
        with db.begin_nested():
            yield db

    session_factory.begin = nested_transaction
    monkeypatch.setattr(worker_module, "SessionLocal", session_factory)

    def fake_execute(
        db_session, saved_request, owner_id, environment_id, timeout, campaign, test_case
    ):
        del owner_id, environment_id, timeout
        execution = Execution(
            project_id=saved_request.project_id,
            saved_request_id=saved_request.id,
            campaign_id=campaign,
            test_case_id=test_case,
            status="completed",
            method=saved_request.method,
            url=saved_request.url_template,
            response_status_code=200,
            response_headers={},
            response_body="ok",
            duration_ms=1,
        )
        db_session.add(execution)
        db_session.commit()
        db_session.refresh(execution)
        return execution

    monkeypatch.setattr(worker_module, "execute_saved_request", fake_execute)
    assert claim_job("test-worker") == UUID(campaign_id)
    process_campaign(UUID(campaign_id))
    db.expire_all()
    campaign = db.get(Campaign, UUID(campaign_id))
    assert campaign is not None and campaign.state == "completed"
    events = client.get(f"/api/v1/campaigns/{campaign_id}/events").json()
    assert [event["event_type"] for event in events] == [
        "campaign_queued",
        "campaign_started",
        "test_execution_started",
        "test_execution_completed",
        "campaign_completed",
    ]


def test_operation_campaign_worker_records_schema_finding(authenticated_client, monkeypatch):
    import app.worker as worker_module
    from app.db.session import get_db as original_get_db
    from app.main import app
    from app.models.campaign import Campaign
    from app.models.execution import Execution
    from app.worker import claim_job, process_campaign

    client = authenticated_client
    project_id = _project(client)
    imported = client.post(
        f"/api/v1/projects/{project_id}/specifications/import", json={"content": SPEC}
    )
    operation_id = client.get(f"/api/v1/specifications/{imported.json()['id']}/operations").json()[
        "items"
    ][0]["id"]
    environment = client.post(
        f"/api/v1/projects/{project_id}/environments",
        json={"name": "Simulated target", "base_url": "https://example.com"},
    )
    queued = client.post(
        f"/api/v1/projects/{project_id}/campaigns",
        json={
            "name": "Simulated operation run",
            "operation_ids": [operation_id],
            "categories": ["positive", "schema"],
            "environment_id": environment.json()["id"],
        },
    )
    assert queued.status_code == 202, queued.text
    campaign_id = queued.json()["id"]
    db_generator = app.dependency_overrides[original_get_db]()
    db = next(db_generator)

    class SessionProxy:
        def __enter__(self):
            return db

        def __exit__(self, *args):
            return False

    def session_factory():
        return SessionProxy()

    @contextmanager
    def nested_transaction():
        with db.begin_nested():
            yield db

    session_factory.begin = nested_transaction
    monkeypatch.setattr(worker_module, "SessionLocal", session_factory)

    def fake_execute(db_session, campaign, test_case):
        execution = Execution(
            project_id=campaign.project_id,
            campaign_id=campaign.id,
            test_case_id=test_case.id,
            environment_id=UUID(campaign.configuration["environment_id"]),
            status="completed",
            method="GET",
            url="https://example.com/items",
            response_status_code=200,
            response_headers={"content-type": "application/json"},
            response_body="{}",
            duration_ms=1,
        )
        db_session.add(execution)
        db_session.commit()
        db_session.refresh(execution)
        return execution

    monkeypatch.setattr(worker_module, "_execute_case", fake_execute)
    assert claim_job("test-operation-worker") == UUID(campaign_id)
    process_campaign(UUID(campaign_id))
    db.expire_all()
    campaign = db.get(Campaign, UUID(campaign_id))
    assert campaign is not None and campaign.state == "completed"
    findings = client.get(f"/api/v1/projects/{project_id}/findings")
    assert findings.status_code == 200, findings.text
    assert findings.json()["total"] >= 1
    finding = findings.json()["items"][0]
    assert finding["campaign_id"] == campaign_id
    evidence = client.get(f"/api/v1/findings/{finding['id']}/evidence")
    assert evidence.status_code == 200, evidence.text
    assert any(item["operation_id"] == operation_id for item in evidence.json())
    events = client.get(f"/api/v1/campaigns/{campaign_id}/events").json()
    adaptive = [event for event in events if event["event_type"] == "adaptive_candidate_selected"]
    assert len(adaptive) == 2
    assert adaptive[0]["payload"]["category"] == "positive"
    assert adaptive[1]["payload"]["category"] == "schema"
    assert adaptive[1]["payload"]["evidence_ids"]
