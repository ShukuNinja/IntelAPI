from fastapi.testclient import TestClient

from app.main import app


def test_liveness_does_not_require_database() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_meta_route_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/meta")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "UNAUTHENTICATED",
            "message": "A valid application session is required.",
        }
    }


def test_meta_route_is_versioned_and_authenticated(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.get("/api/v1/meta")

    assert response.status_code == 200
    assert response.json() == {
        "name": "API Intelligence Platform",
        "version": "0.1.0",
        "status": "scaffold",
    }
