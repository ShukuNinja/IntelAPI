from app.modules.api_understanding.normalizer import normalize_operations
from app.modules.api_understanding.parser import parse_openapi_document
from app.modules.test_generation import CandidateCategory, generate_candidates

SPEC = """
openapi: 3.1.0
info:
  title: Candidate API
  version: "1"
paths:
  /users:
    get:
      parameters:
        - name: limit
          in: query
          required: false
          schema:
            type: integer
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
                age:
                  type: integer
      responses:
        "201":
          description: Created
"""


def _generate():
    document = parse_openapi_document(SPEC)
    operations = normalize_operations(document)
    return generate_candidates(operations)


def test_generates_candidates_for_each_operation() -> None:
    candidates = _generate()

    assert any(
        candidate.operation_key == "GET /users" and candidate.category is CandidateCategory.POSITIVE
        for candidate in candidates
    )
    assert any(
        candidate.operation_key == "POST /users"
        and candidate.category is CandidateCategory.POSITIVE
        for candidate in candidates
    )


def test_generates_parameter_and_required_field_negative_cases() -> None:
    candidates = _generate()

    assert any(
        candidate.category is CandidateCategory.NEGATIVE
        and candidate.title == "Omit parameter: limit"
        for candidate in candidates
    )
    missing_name = [
        candidate for candidate in candidates if candidate.title == "Omit required field: name"
    ]
    assert len(missing_name) == 1
    assert missing_name[0].body == {}


def test_generates_response_schema_candidates() -> None:
    candidates = _generate()

    assert any(
        candidate.category is CandidateCategory.SCHEMA
        and candidate.title == "Validate response schema: 200:application/json"
        for candidate in candidates
    )


def test_generation_is_deterministic_and_deduplicated() -> None:
    first = _generate()
    second = _generate()

    assert first == second
    identifiers = [candidate.candidate_id for candidate in first]
    assert len(identifiers) == len(set(identifiers))


def test_candidate_ids_are_stable() -> None:
    first = _generate()
    second = _generate()

    assert [candidate.candidate_id for candidate in first] == [
        candidate.candidate_id for candidate in second
    ]


def test_candidates_are_not_executed_or_persisted() -> None:
    candidates = _generate()

    assert candidates
    assert all(candidate.method in {"GET", "POST"} for candidate in candidates)
    assert all(candidate.path == "/users" for candidate in candidates)
