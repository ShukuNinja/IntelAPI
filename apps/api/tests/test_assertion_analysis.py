"""Tests for deterministic assertion analysis."""

import json

from app.modules.api_understanding.normalizer import normalize_operations
from app.modules.api_understanding.parser import parse_openapi_document
from app.modules.assertion_analysis import (
    AssertionType,
    analyze_operation,
    analyze_operations,
)
from app.modules.knowledge.models import FactProvenance

SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "Assertion Test API", "version": "1.0.0"},
    "paths": {
        "/users": {
            "get": {
                "operationId": "listUsers",
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["id", "email"],
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "email": {"type": "string"},
                                            "active": {"type": "boolean"},
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "404": {
                        "description": "Not found",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["message"],
                                    "properties": {"message": {"type": "string"}},
                                }
                            }
                        },
                    },
                    "default": {"description": "Unexpected error"},
                },
            }
        }
    },
}


def _operations():
    """Parse and normalize the test specification."""
    parsed = parse_openapi_document(json.dumps(SPEC))
    return normalize_operations(parsed)


def test_generates_declared_status_code_assertions():
    assertions = analyze_operations(_operations())

    status_assertions = [
        assertion
        for assertion in assertions
        if assertion.assertion_type == AssertionType.STATUS_CODE
    ]

    assert {assertion.expected for assertion in status_assertions} == {200, 404}
    assert all(assertion.target == "status" for assertion in status_assertions)


def test_generates_required_property_assertions_for_array_items():
    assertions = analyze_operations(_operations())

    required = {
        assertion.target
        for assertion in assertions
        if assertion.assertion_type == AssertionType.REQUIRED_PROPERTY
        and assertion.response_key.startswith("200:")
    }

    assert required == {"$[].id", "$[].email"}


def test_generates_property_type_assertions():
    assertions = analyze_operations(_operations())

    property_types = {
        (assertion.target, assertion.expected)
        for assertion in assertions
        if assertion.assertion_type == AssertionType.PROPERTY_TYPE
        and assertion.response_key.startswith("200:")
    }

    assert ("$[].id", "integer") in property_types
    assert ("$[].email", "string") in property_types
    assert ("$[].active", "boolean") in property_types


def test_analyzes_nested_object_properties():
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "Nested API", "version": "1.0.0"},
        "paths": {
            "/users/{id}": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "profile": {
                                                "type": "object",
                                                "required": ["displayName"],
                                                "properties": {"displayName": {"type": "string"}},
                                            }
                                        },
                                    }
                                }
                            },
                        }
                    }
                }
            }
        },
    }

    operations = normalize_operations(parse_openapi_document(json.dumps(spec)))
    assertions = analyze_operations(operations)

    assert any(
        assertion.assertion_type == AssertionType.REQUIRED_PROPERTY
        and assertion.target == "profile.displayName"
        for assertion in assertions
    )
    assert any(
        assertion.assertion_type == AssertionType.PROPERTY_TYPE
        and assertion.target == "profile.displayName"
        and assertion.expected == "string"
        for assertion in assertions
    )


def test_assertion_ids_are_stable_and_results_are_deterministic():
    operations = _operations()

    first = analyze_operations(operations)
    second = analyze_operations(operations)

    assert first == second
    assert [item.assertion_id for item in first] == [item.assertion_id for item in second]
    assert len({item.assertion_id for item in first}) == len(first)


def test_assertions_preserve_declared_provenance_and_source():
    operation = _operations()[0]
    assertions = analyze_operation(operation)

    assert assertions
    assert all(assertion.provenance == FactProvenance.DECLARED for assertion in assertions)
    assert all(assertion.source_ref == operation.source_ref for assertion in assertions)


def test_analysis_does_not_execute_or_persist_requests():
    assertions = analyze_operations(_operations())

    assert assertions
    assert all(assertion.operation_key for assertion in assertions)
    assert all(assertion.rationale for assertion in assertions)
    assert all(not hasattr(assertion, "response") for assertion in assertions)
