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
from app.modules.execution import router as execution_router


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


def test_imported_specification_persists_and_deduplicates(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Catalog"}).json()
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "Catalog API", "version": "1"},
        "paths": {"/items": {"get": {"operationId": "listItems"}}},
    }
    endpoint = f"/api/v1/projects/{project['id']}/specifications/import"
    first = client.post(endpoint, json={"document": spec})
    second = client.post(endpoint, json={"document": spec})
    assert first.status_code == 201
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    records = client.get(f"/api/v1/projects/{project['id']}/specifications")
    assert len(records.json()) == 1
    assert records.json()[0]["operation_count"] == 1
    detail = client.get(f"/api/v1/projects/{project['id']}/specifications/{first.json()['id']}")
    assert detail.status_code == 200
    assert detail.json()["operations"][0]["path"] == "/items"


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
