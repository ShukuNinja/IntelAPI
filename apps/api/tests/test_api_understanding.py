import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.api_understanding.service import (
    SpecificationError,
    generate_candidates,
    generate_generation_report,
    parse_specification,
    parse_specification_content,
)

SPECIFICATION = {
    "openapi": "3.1.0",
    "info": {"title": "Fixture API", "version": "1.0"},
    "paths": {
        "/users/{user_id}": {
            "parameters": [
                {
                    "name": "user_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "integer", "minimum": 1},
                }
            ],
            "get": {"operationId": "getUser", "summary": "Get user"},
        },
        "/users": {
            "post": {
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["email"],
                                "properties": {"email": {"type": "string"}},
                            }
                        }
                    }
                }
            }
        },
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


def test_candidate_ids_are_scoped_to_the_operation() -> None:
    operation = parse_specification(SPECIFICATION)["operations"][0]
    other_operation = {**operation, "id": "another-operation"}
    assert generate_candidates(operation)[0]["id"] != generate_candidates(other_operation)[0]["id"]


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
        response = client.post(
            "/api/v1/specifications/parse", json={"document": {"openapi": "2.0", "paths": {}}}
        )
    assert response.status_code == 422


def test_missing_openapi_info_is_rejected() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/specifications/parse",
            json={"document": {"openapi": "3.1.0", "paths": {}}},
        )
    assert response.status_code == 422


def test_openapi_yaml_parses_to_same_operation_model() -> None:
    document = """
openapi: 3.1.0
info:
  title: YAML Fixture
  version: '1.0'
paths:
  /health:
    get:
      operationId: health
      summary: Health check
"""
    result = parse_specification_content(document, "yaml")
    assert result["specification"]["title"] == "YAML Fixture"
    assert result["operations"][0]["operation_id"] == "health"


def test_swagger_2_is_normalized_with_body_schema() -> None:
    document = {
        "swagger": "2.0",
        "info": {"title": "Legacy API", "version": "1"},
        "host": "api.example.test",
        "basePath": "/v1",
        "schemes": ["https"],
        "paths": {
            "/users": {
                "post": {
                    "parameters": [
                        {
                            "name": "body",
                            "in": "body",
                            "required": True,
                            "schema": {
                                "type": "object",
                                "required": ["email"],
                                "properties": {"email": {"type": "string"}},
                            },
                        }
                    ],
                    "responses": {"201": {"description": "Created"}},
                }
            }
        },
    }
    result = parse_specification(document)
    operation = result["operations"][0]
    assert operation["method"] == "POST"
    assert operation["request_body"]["required"] is True
    assert operation["request_body"]["content"]["application/json"]["schema"]["required"] == [
        "email"
    ]


def test_swagger_formdata_is_converted_to_form_request_body() -> None:
    document = {
        "swagger": "2.0",
        "info": {"title": "Form API", "version": "1"},
        "paths": {
            "/upload": {
                "post": {
                    "parameters": [
                        {"name": "file", "in": "formData", "type": "file", "required": True},
                        {"name": "label", "in": "formData", "type": "string"},
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    operation = parse_specification(document)["operations"][0]
    schema = operation["request_body"]["content"]["multipart/form-data"]["schema"]
    assert schema["required"] == ["file"]
    assert schema["properties"]["file"] == {"type": "string", "format": "binary"}


def test_yaml_is_safe_and_bounded() -> None:
    with pytest.raises(SpecificationError, match="Invalid YAML"):
        parse_specification_content("document: !!python/object/apply:os.system ['echo no']", "yaml")
    with pytest.raises(SpecificationError, match="2 MB"):
        parse_specification_content(" " * 2_000_001, "json")


def test_parse_route_accepts_yaml_content() -> None:
    document = "openapi: 3.1.0\ninfo: {title: Route YAML, version: '1'}\npaths: {}\n"
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/specifications/parse",
            json={"content": document, "source_format": "yaml"},
        )
    assert response.status_code == 200
    assert response.json()["specification"]["title"] == "Route YAML"


def test_generation_report_is_endpoint_wise_deterministic_and_bounded() -> None:
    operations = parse_specification(SPECIFICATION)["operations"]
    first = generate_generation_report(operations, per_operation_limit=1)
    second = generate_generation_report(operations, per_operation_limit=1)
    assert first == second
    assert first["summary"] == {
        "operation_count": 2,
        "candidate_count": 2,
        "endpoints_with_candidates": 2,
        "truncated": True,
    }
    assert first["endpoints"][0]["operation"]["path"] == "/users/{user_id}"
    assert first["endpoints"][0]["candidates"][0]["reason"]


def test_generation_report_route_returns_actual_endpoint_candidates() -> None:
    operations = parse_specification(SPECIFICATION)["operations"]
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/specifications/candidates/report",
            json={"operations": operations},
        )
    assert response.status_code == 200
    report = response.json()
    assert report["policy_version"] == "schema-preview-v1"
    assert report["summary"]["candidate_count"] > 0
    assert report["endpoints"][0]["operation"]["id"] == operations[0]["id"]


def test_generation_report_rejects_more_than_one_hundred_operations() -> None:
    operation = parse_specification(SPECIFICATION)["operations"][0]
    with pytest.raises(ValueError, match="between 1 and 100"):
        generate_generation_report([operation] * 101)


def test_generation_report_stops_at_global_candidate_budget() -> None:
    operation = {
        "id": "large",
        "method": "POST",
        "path": "/large",
        "parameters": [
            {
                "name": f"field_{index}",
                "in": "query",
                "required": True,
                "schema": {"type": "integer", "minimum": 1},
            }
            for index in range(60)
        ],
    }
    report = generate_generation_report([operation] * 26)
    assert report["summary"]["candidate_count"] == 500
    assert report["summary"]["truncated"] is True
