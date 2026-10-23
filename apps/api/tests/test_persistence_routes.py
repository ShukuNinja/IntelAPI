from collections.abc import Generator
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
