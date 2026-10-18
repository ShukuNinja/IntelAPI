from app.modules.api_understanding.normalizer import normalize_operations
from app.modules.api_understanding.parser import parse_openapi_document
from app.modules.knowledge import FactProvenance, extract_knowledge

SPEC = """
openapi: 3.1.0
info:
  title: Knowledge Test API
  version: "1.0"
paths:
  /users:
    get:
      operationId: listUsers
      summary: List users
      parameters:
        - name: limit
          in: query
          schema:
            type: integer
      security:
        - bearerAuth: []
      responses:
        "200":
          description: OK
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
              required: [name]
              properties:
                name:
                  type: string
      responses:
        "201":
          description: Created
"""


def _extract():
    document = parse_openapi_document(SPEC)
    operations = normalize_operations(document)
    return extract_knowledge(operations)


def test_extracts_operation_and_parameter_facts() -> None:
    facts = _extract()

    operation_facts = [fact for fact in facts if fact.fact_type == "operation"]
    parameter_facts = [fact for fact in facts if fact.fact_type == "parameter"]

    assert len(operation_facts) == 2
    assert operation_facts[0].value["operation_key"] == "GET /users"
    assert operation_facts[0].value["operation_id"] == "listUsers"
    assert len(parameter_facts) == 1
    assert parameter_facts[0].value["name"] == "limit"


def test_extracts_request_and_response_schemas() -> None:
    facts = _extract()

    request_facts = [fact for fact in facts if fact.fact_type == "request_body_schema"]
    response_facts = [fact for fact in facts if fact.fact_type == "response_schema"]

    assert len(request_facts) == 1
    assert request_facts[0].value["schema"]["required"] == ["name"]
    assert len(response_facts) == 1
    assert response_facts[0].value["response_key"] == "200:application/json"


def test_extracts_security_requirements() -> None:
    facts = _extract()

    security_facts = [fact for fact in facts if fact.fact_type == "security_requirement"]

    assert len(security_facts) == 1
    assert security_facts[0].value == {"bearerAuth": []}


def test_facts_have_provenance_and_source_references() -> None:
    facts = _extract()

    assert facts
    assert all(fact.provenance is FactProvenance.EXTRACTED for fact in facts)
    assert all(fact.source_ref.pointer.startswith("#/paths/") for fact in facts)


def test_extraction_is_deterministic() -> None:
    first = _extract()
    second = _extract()

    assert first == second
    assert [fact.fact_key for fact in first] == [fact.fact_key for fact in second]


def test_operation_without_optional_details_still_produces_fact() -> None:
    document = parse_openapi_document(
        """
openapi: 3.0.3
info:
  title: Minimal API
  version: "1"
paths:
  /health:
    get:
      responses:
        "200":
          description: OK
"""
    )
    operations = normalize_operations(document)
    facts = extract_knowledge(operations)

    assert len(facts) == 1
    assert facts[0].fact_type == "operation"
    assert facts[0].value["operation_key"] == "GET /health"
