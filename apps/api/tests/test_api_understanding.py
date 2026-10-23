from fastapi.testclient import TestClient

from app.main import app
from app.modules.api_understanding.service import generate_candidates, parse_specification

SPECIFICATION = {
    "openapi": "3.1.0",
    "info": {"title": "Fixture API", "version": "1.0"},
    "paths": {
        "/users/{user_id}": {
            "parameters": [{"name": "user_id", "in": "path", "required": True, "schema": {"type": "integer", "minimum": 1}}],
            "get": {"operationId": "getUser", "summary": "Get user"},
        },
        "/users": {"post": {"requestBody": {"content": {"application/json": {"schema": {"type": "object", "required": ["email"], "properties": {"email": {"type": "string"}}}}}}}},
    },
}


def test_openapi_operations_have_stable_ids_and_inherit_path_parameters() -> None:
    first = parse_specification(SPECIFICATION)
    second = parse_specification(SPECIFICATION)
    assert len(first["operations"]) == 2
    assert first["operations"][0]["id"] == second["operations"][0]["id"]
    assert first["operations"][0]["parameters"][0]["name"] == "user_id"


def test_candidates_are_deterministic_and_explainable() -> None:
    operation = parse_specification(SPECIFICATION)["operations"][0]
    candidates = generate_candidates(operation)
    assert candidates == generate_candidates(operation)
    assert candidates[0]["kind"] == "required-parameter-omitted"
    assert candidates[0]["reason"]


def test_parse_route_returns_normalized_real_operations() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/specifications/parse", json={"document": SPECIFICATION})
    assert response.status_code == 200
    assert response.json()["specification"]["title"] == "Fixture API"
    assert len(response.json()["operations"]) == 2


def test_candidate_preview_route_returns_explainable_candidates() -> None:
    operation = parse_specification(SPECIFICATION)["operations"][0]
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/specifications/candidates/preview",
            json={"operation": operation},
        )
    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate["reason"]
    assert candidate["mutation"]["remove_parameter"]["name"] == "user_id"
    assert candidate["validation_status"] == "preview"


def test_invalid_openapi_version_is_rejected() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/specifications/parse", json={"document": {"openapi": "2.0", "paths": {}}})
    assert response.status_code == 422


def test_missing_openapi_info_is_rejected() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/specifications/parse",
            json={"document": {"openapi": "3.1.0", "paths": {}}},
        )
    assert response.status_code == 422
