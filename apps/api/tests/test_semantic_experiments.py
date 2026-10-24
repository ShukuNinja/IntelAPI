from app.modules.api_understanding.service import generate_candidates, parse_specification
from app.modules.experiments.semantic import candidate_semantic_score, extract_semantic_facts

SPEC = {
    "openapi": "3.1.0",
    "info": {"title": "Orders", "version": "1"},
    "paths": {
        "/orders/{order_id}": {
            "parameters": [
                {
                    "name": "order_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "integer", "minimum": 1, "maximum": 100},
                }
            ],
            "get": {
                "operationId": "getOrder",
                "summary": "Retrieve an order",
                "responses": {"200": {"description": "Order"}},
            },
            "delete": {
                "operationId": "deleteOrder",
                "summary": "Cancel order",
                "responses": {"204": {"description": "Deleted"}},
            },
        },
        "/orders": {
            "post": {
                "operationId": "createOrder",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Order"}}
                    },
                },
                "responses": {"201": {"description": "Created"}},
            }
        },
    },
    "components": {
        "schemas": {
            "Order": {
                "type": "object",
                "required": ["email"],
                "properties": {"email": {"type": "string", "format": "email", "maxLength": 100}},
            }
        }
    },
}


def test_local_schema_reference_is_resolved_without_fetching() -> None:
    operations = parse_specification(SPEC)["operations"]
    create = next(operation for operation in operations if operation["method"] == "POST")
    schema = create["request_body"]["content"]["application/json"]["schema"]
    assert schema["properties"]["email"]["format"] == "email"
    assert schema["required"] == ["email"]


def test_semantic_facts_preserve_location_rule_and_evidence() -> None:
    facts = extract_semantic_facts(parse_specification(SPEC)["operations"])
    intent = next(
        fact
        for fact in facts
        if fact["fact_type"] == "operation_intent" and fact["value"] == "create"
    )
    constraint = next(
        fact
        for fact in facts
        if fact["fact_type"] == "field_constraint" and fact["value"]["constraint"] == "maxLength"
    )
    assert intent["evidence"] == "direct"
    assert constraint["source_location"].endswith("maxLength")
    assert constraint["rule"] == "openapi_schema_constraint"
    assert 0 <= constraint["evidence_strength"] <= 1


def test_semantic_ranking_changes_selection_and_is_repeatable() -> None:
    operations = parse_specification(SPEC)["operations"]
    operation = next(item for item in operations if item["method"] == "GET")
    candidates = generate_candidates(operation, 100)
    facts = extract_semantic_facts(operations)
    ranked = sorted(
        candidates,
        key=lambda candidate: (
            -candidate_semantic_score(candidate, operation, facts)[0],
            candidate["id"],
        ),
    )
    baseline = sorted(
        candidates,
        key=lambda candidate: (0 if "required" in candidate["kind"] else 2, candidate["id"]),
    )
    assert ranked[0]["id"] != baseline[0]["id"]
    again = sorted(
        candidates,
        key=lambda candidate: (
            -candidate_semantic_score(candidate, operation, facts)[0],
            candidate["id"],
        ),
    )
    assert [candidate["id"] for candidate in ranked] == [candidate["id"] for candidate in again]
