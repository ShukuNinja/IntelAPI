from fastapi.testclient import TestClient

from app.main import app


def test_liveness_does_not_require_database() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_meta_route_is_versioned() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/meta")
    assert response.status_code == 200
    assert response.json()["name"] == "API Intelligence Platform"
