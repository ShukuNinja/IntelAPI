from collections.abc import Generator
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.modules.api_understanding.service import generate_candidates
from app.modules.execution import router as execution_router
from app.modules.test_generation import router as test_generation_router


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides = previous_overrides
        engine.dispose()


def test_project_create_and_list(client: TestClient) -> None:
    created = client.post("/api/v1/projects", json={"name": "Payments", "description": "Fixture"})
    assert created.status_code == 201
    project = created.json()
    assert project["name"] == "Payments"
    assert client.get("/api/v1/projects").json() == [project]


def test_project_lifecycle_and_overview_aggregate(client: TestClient) -> None:
    created = client.post("/api/v1/projects", json={"name": "Lifecycle"}).json()
    root = f"/api/v1/projects/{created['id']}"
    assert client.get(root).json()["name"] == "Lifecycle"
    updated = client.put(root, json={"name": "Research workspace", "description": "demo"})
    assert updated.status_code == 200
    overview = client.get(f"{root}/overview")
    assert overview.status_code == 200
    assert overview.json()["project"]["name"] == "Research workspace"
    assert overview.json()["counts"]["executions"] == 0
    archived = client.delete(root)
    assert archived.status_code == 204
    assert client.get(root).status_code == 404
    assert all(item["id"] != created["id"] for item in client.get("/api/v1/projects").json())


def test_imported_specification_persists_and_deduplicates(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Catalog"}).json()
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "Catalog API", "version": "1"},
        "servers": [
            {"url": "https://user:pass@api.example.com/v2?token=secret#frag"},
            {"url": "https://{tenant}.example.com/v{version}"},
        ],
        "paths": {"/items": {"get": {"operationId": "listItems"}}},
    }
    endpoint = f"/api/v1/projects/{project['id']}/specifications/import"
    source_url = "https://api.example.com/openapi.json?token=must-not-be-persisted"
    first = client.post(endpoint, json={"document": spec, "source_url": source_url})
    second = client.post(endpoint, json={"document": spec})
    assert first.status_code == 201
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    records = client.get(f"/api/v1/projects/{project['id']}/specifications")
    assert len(records.json()) == 1
    assert records.json()[0]["operation_count"] == 1
    assert records.json()[0]["servers"] == ["https://api.example.com/v2"]
    assert records.json()[0]["source_url"] == "https://api.example.com/openapi.json"
    detail = client.get(f"/api/v1/projects/{project['id']}/specifications/{first.json()['id']}")
    assert detail.status_code == 200
    assert detail.json()["operations"][0]["path"] == "/items"
    assert detail.json()["source_url"] == "https://api.example.com/openapi.json"
    assert detail.json()["servers"] == ["https://api.example.com/v2"]
    assert detail.json()["document"]["servers"][0]["url"] == "https://api.example.com/v2"
    assert "url" not in detail.json()["document"]["servers"][1]
    assert first.json()["servers"] == ["https://api.example.com/v2"]


def test_unknown_project_cannot_receive_specification(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/projects/{UUID(int=1)}/specifications/import",
        json={"document": {"openapi": "3.1.0", "info": {}, "paths": {}}},
    )
    assert response.status_code == 404


def test_execution_response_and_history_are_project_scoped(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = client.post("/api/v1/projects", json={"name": "Execution"}).json()
    monkeypatch.setattr(
        execution_router,
        "execute_request",
        AsyncMock(
            return_value={
                "status_code": 200,
                "elapsed_ms": 12,
                "response_bytes": 16,
                "headers": {"content-type": "application/json"},
                "body": {"ok": True},
                "origin": "http://localhost:9000",
                "outcome": "http_response",
            }
        ),
    )
    endpoint = f"/api/v1/projects/{project['id']}/executions"
    response = client.post(
        endpoint,
        json={"method": "GET", "url": "http://localhost:9000/health", "headers": {}},
    )
    assert response.status_code == 201
    assert response.json()["body"] == {"ok": True}
    history = client.get(endpoint)
    assert len(history.json()) == 1
    assert history.json()[0]["status_code"] == 200
    assert "body" not in history.json()[0]


def test_generation_report_is_persisted_reopenable_and_exportable(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Reports"}).json()
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "Orders API", "version": "1"},
        "paths": {
            "/orders": {
                "get": {
                    "operationId": "listOrders",
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "integer", "minimum": 1},
                        }
                    ],
                },
                "post": {
                    "operationId": "createOrder",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["name"],
                                    "properties": {"name": {"type": "string"}},
                                }
                            }
                        },
                    },
                },
            }
        },
    }
    saved_spec = client.post(
        f"/api/v1/projects/{project['id']}/specifications/import", json={"document": spec}
    ).json()
    endpoint = (
        f"/api/v1/projects/{project['id']}/specifications/{saved_spec['id']}/generation-reports"
    )
    created = client.post(endpoint, json={"per_operation_limit": 10})
    assert created.status_code == 201
    report = created.json()
    assert report["specification"]["title"] == "Orders API"
    assert report["summary"]["candidate_count"] >= 2
    assert len(client.get(f"/api/v1/projects/{project['id']}/generation-reports").json()) == 1
    reopened = client.get(f"/api/v1/projects/{project['id']}/generation-reports/{report['id']}")
    assert reopened.json()["endpoints"] == report["endpoints"]
    markdown = client.get(
        f"/api/v1/projects/{project['id']}/generation-reports/{report['id']}/export?format=markdown"
    )
    csv_export = client.get(
        f"/api/v1/projects/{project['id']}/generation-reports/{report['id']}/export?format=csv"
    )
    assert "Orders API" in markdown.text
    assert "candidate_id" in csv_export.text


def test_candidate_execution_applies_boundary_and_persists_metadata(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = client.post("/api/v1/projects", json={"name": "Candidate runs"}).json()
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "Items API", "version": "1"},
        "paths": {
            "/items": {
                "get": {
                    "operationId": "listItems",
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "integer", "minimum": 1},
                        }
                    ],
                }
            }
        },
    }
    saved = client.post(
        f"/api/v1/projects/{project['id']}/specifications/import", json={"document": spec}
    ).json()
    operation = saved["operations"][0]
    candidate = next(
        item
        for item in generate_candidates(operation)
        if item["kind"] == "parameter-minimum-boundary"
    )
    mocked_execute = AsyncMock(
        return_value={
            "status_code": 200,
            "elapsed_ms": 8,
            "response_bytes": 12,
            "headers": {"content-type": "application/json"},
            "body": {"items": []},
            "origin": "http://localhost:9000",
            "outcome": "http_response",
        }
    )
    monkeypatch.setattr(test_generation_router, "execute_request", mocked_execute)
    endpoint = (
        f"/api/v1/projects/{project['id']}/specifications/{saved['id']}/operations/"
        f"{operation['id']}/candidates/{candidate['id']}/execute"
    )
    response = client.post(
        endpoint,
        json={
            "base_url": "http://localhost:9000",
            "query_parameters": {"limit": 10},
            "path_parameters": {},
            "expected_status_code": 200,
            "assertions": [{"kind": "json_pointer_exists", "pointer": "/items"}],
        },
    )
    assert response.status_code == 201
    assert response.json()["body"] == {"items": []}
    assert response.json()["run_report"]["assertions"][0]["passed"] is True
    assert response.json()["run_report"]["assertions"][1]["passed"] is True
    assert mocked_execute.await_args.kwargs["url"] == "http://localhost:9000/items?limit=0"
    history = client.get(f"/api/v1/projects/{project['id']}/executions")
    assert history.json()[0]["status_code"] == 200
    assert history.json()[0]["method"] == "GET"
    reports = client.get(f"/api/v1/projects/{project['id']}/execution-reports")
    assert len(reports.json()) == 1
    report_id = reports.json()[0]["id"]
    markdown = client.get(
        f"/api/v1/projects/{project['id']}/execution-reports/{report_id}/export?format=markdown"
    )
    assert "Candidate execution report" in markdown.text


def test_saved_requests_and_environments_are_project_scoped(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Client resources"}).json()
    root = f"/api/v1/projects/{project['id']}"
    saved = client.post(
        f"{root}/saved-requests",
        json={
            "name": "List orders",
            "collection_name": "Orders",
            "method": "GET",
            "url": "{{baseUrl}}/orders?token={{token}}",
            "headers": {"Accept": "application/json"},
        },
    )
    assert saved.status_code == 201
    assert client.get(f"{root}/saved-requests").json()[0]["name"] == "List orders"
    updated = client.put(
        f"{root}/saved-requests/{saved.json()['id']}",
        json={
            "name": "List open orders",
            "collection_name": "Orders",
            "method": "GET",
            "url": "{{baseUrl}}/orders?status=open",
            "headers": {},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "List open orders"

    environment = client.post(
        f"{root}/environments",
        json={"name": "Local", "base_url": "http://localhost:9000", "variables": {"token": "test"}},
    )
    assert environment.status_code == 201
    assert client.get(f"{root}/environments").json()[0]["variables"] == {"token": "test"}
    invalid = client.post(
        f"{root}/environments",
        json={"name": "Invalid", "variables": {"bad-key": "value"}},
    )
    assert invalid.status_code == 422


def test_experiment_approaches_persist_and_use_different_selection(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Research"}).json()
    specification = {
        "openapi": "3.1.0",
        "info": {"title": "Widget API", "version": "1"},
        "paths": {
            "/widgets/{widget_id}": {
                "parameters": [
                    {
                        "name": "widget_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer", "minimum": 1},
                    }
                ],
                "get": {
                    "operationId": "getWidget",
                    "summary": "Retrieve widget",
                    "responses": {"200": {"description": "Widget"}},
                },
            }
        },
    }
    saved = client.post(
        f"/api/v1/projects/{project['id']}/specifications/import", json={"document": specification}
    ).json()
    root = f"/api/v1/projects/{project['id']}/specifications/{saved['id']}/experiments"
    baseline = client.post(root, json={"approach": "contract_baseline", "candidate_budget": 1})
    semantic = client.post(root, json={"approach": "semantic_guided", "candidate_budget": 1})
    assert baseline.status_code == semantic.status_code == 201
    a, b = baseline.json(), semantic.json()
    assert a["result"]["selected_candidates"][0]["kind"] == "required-parameter-omitted"
    assert b["result"]["selected_candidates"][0]["kind"] == "parameter-minimum-boundary"
    assert b["result"]["selected_candidates"][0]["score_breakdown"]["field_semantics"] > 0
    assert b["result"]["facts"]
    assert len(client.get(root).json()) == 2
    reopened = client.get(f"{root}/{b['id']}")
    assert reopened.status_code == 200
    assert reopened.json()["result"]["selected_candidates"] == b["result"]["selected_candidates"]
    compared = client.get(
        f"{root}/comparison", params={"baseline_run_id": a["id"], "semantic_run_id": b["id"]}
    )
    assert compared.status_code == 200
    assert compared.json()["same_candidate_budget"] is True
    export = client.get(
        f"{root}/comparison/export",
        params={"baseline_run_id": a["id"], "semantic_run_id": b["id"], "format": "markdown"},
    )
    assert export.status_code == 200
    assert "Approach A" in export.text


def test_experiment_execution_records_seeded_detection_and_redacts_inputs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = client.post("/api/v1/projects", json={"name": "Seeded benchmark"}).json()
    specification = {
        "openapi": "3.1.0",
        "info": {"title": "Benchmark", "version": "1"},
        "x-intelapi-benchmark": {
            "id": "intelapi-seeded-v1",
            "defects": [{"id": "B-001", "operationId": "getWidget"}],
        },
        "paths": {
            "/widgets/{widget_id}": {
                "parameters": [
                    {
                        "name": "widget_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer", "minimum": 1},
                    }
                ],
                "get": {
                    "operationId": "getWidget",
                    "responses": {
                        "200": {
                            "description": "Widget",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["id"],
                                        "properties": {"id": {"type": "integer"}},
                                    }
                                }
                            },
                        },
                        "404": {"description": "Not found"},
                    },
                },
            }
        },
    }
    saved = client.post(
        f"/api/v1/projects/{project['id']}/specifications/import",
        json={"document": specification},
    ).json()
    operation = saved["operations"][0]

    async def controlled_execution(**request: object) -> dict[str, object]:
        is_positive = request["url"].endswith("/13")
        return {
            "status_code": 200 if is_positive else 404,
            "elapsed_ms": 4,
            "response_bytes": 12,
            "headers": {"content-type": "application/json"},
            "body": {"id": "13"} if is_positive else {"detail": "Not found"},
            "origin": "http://localhost:8000",
            "outcome": "http_response",
        }

    monkeypatch.setattr(test_generation_router, "execute_request", controlled_execution)
    root = f"/api/v1/projects/{project['id']}/specifications/{saved['id']}/experiments"
    generated = client.post(
        root, json={"approach": "semantic_guided", "candidate_budget": 10}
    ).json()
    executed = client.post(
        f"{root}/{generated['id']}/execute",
        json={
            "base_url": "http://localhost:8000/api/v1/research-benchmark",
            "baselines": {
                operation["id"]: {
                    "path_parameters": {"widget_id": "13"},
                    "headers": {"Authorization": "never-persist-this"},
                }
            },
            "execution_budget": 10,
        },
    )
    assert executed.status_code == 200
    result = executed.json()
    assert result["status"] == "executed"
    assert result["result"]["metrics"]["known_seeded_defects_detected"] == 1
    assert result["result"]["metrics"]["detection_rate"] == 1.0
    assert result["result"]["ground_truth"]["confusion_matrix"]["true_positive"] == 1
    assert "never-persist-this" not in str(result)
