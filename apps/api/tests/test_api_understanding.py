import pytest

from app.modules.api_understanding.errors import (
    OpenAPIParseError,
    OpenAPIReferenceError,
    OpenAPIValidationError,
    UnsupportedOpenAPIVersionError,
)
from app.modules.api_understanding.normalizer import normalize_operations
from app.modules.api_understanding.parser import parse_openapi_document

VALID_SPEC = """
openapi: 3.1.0
info:
  title: Example API
  version: "1.0"
paths:
  /users:
    get:
      operationId: listUsers
      summary: List users
      responses:
        "200":
          description: Successful response
          content:
            application/json:
              schema:
                type: array
                items:
                  type: object
    post:
      summary: Create user
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
      responses:
        "201":
          description: Created
"""


def test_parse_yaml_openapi_document() -> None:
    document = parse_openapi_document(VALID_SPEC)
    assert document["openapi"] == "3.1.0"
    assert document["info"]["title"] == "Example API"


def test_parse_json_openapi_document() -> None:
    content = (
        '{"openapi":"3.0.3","info":{"title":"Example","version":"1"},'
        '"paths":{}}'
    )
    assert parse_openapi_document(content)["openapi"] == "3.0.3"


def test_reject_invalid_document() -> None:
    with pytest.raises(OpenAPIParseError):
        parse_openapi_document("openapi: [invalid")


def test_reject_unsupported_version() -> None:
    content = '{"openapi":"2.0","info":{"title":"Example","version":"1"},"paths":{}}'
    with pytest.raises(UnsupportedOpenAPIVersionError):
        parse_openapi_document(content)


def test_reject_missing_required_fields() -> None:
    with pytest.raises(OpenAPIValidationError):
        parse_openapi_document('{"openapi":"3.1.0","paths":{}}')


def test_enforce_document_size_limit() -> None:
    with pytest.raises(OpenAPIValidationError):
        parse_openapi_document(VALID_SPEC, max_bytes=10)


def test_reject_remote_references() -> None:
    content = """
openapi: 3.1.0
info:
  title: Example
  version: "1"
paths:
  /users:
    get:
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: https://example.com/schema.json
"""
    with pytest.raises(OpenAPIReferenceError):
        parse_openapi_document(content)


def test_normalize_operations_deterministically() -> None:
    document = parse_openapi_document(VALID_SPEC)
    first = normalize_operations(document)
    second = normalize_operations(document)

    assert first == second
    assert [operation.operation_key for operation in first] == [
        "GET /users",
        "POST /users",
    ]
    assert first[0].operation_id == "listUsers"
    assert first[0].response_schemas["200:application/json"]["type"] == "array"
    assert first[1].request_body_schema == {"type": "object"}
    assert first[0].source_ref.pointer == "#/paths/~1users/get"

def test_operation_parameter_overrides_path_parameter() -> None:
    document = {
        "paths": {
            "/items": {
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {
                            "type": "integer",
                            "minimum": 1,
                        },
                    },
                    {
                        "name": "tenant",
                        "in": "header",
                        "schema": {
                            "type": "string",
                        },
                    },
                ],
                "get": {
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {
                                "type": "integer",
                                "minimum": 5,
                            },
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Success",
                        }
                    },
                },
            }
        }
    }

    operations = normalize_operations(document)

    assert len(operations) == 1

    parameters = {
        (parameter["name"], parameter["in"]): parameter
        for parameter in operations[0].parameters
    }

    assert len(operations[0].parameters) == 2
    assert parameters[("limit", "query")]["schema"]["minimum"] == 5
    assert ("tenant", "header") in parameters