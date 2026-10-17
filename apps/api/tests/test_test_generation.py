from dataclasses import replace

import pytest

import app.modules.test_generation.generator as generator_module
from app.modules.api_understanding.normalizer import normalize_operations
from app.modules.api_understanding.parser import parse_openapi_document
from app.modules.test_generation import (
    CandidateCategory,
    CandidateDeduplicationError,
    generate_candidates,
)

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
def test_generation_rejects_conflicting_candidate_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_candidate = generator_module._candidate

    def candidate_with_duplicate_id(*args, **kwargs):
        candidate = original_candidate(*args, **kwargs)
        return replace(candidate, candidate_id="forced-duplicate-id")

    monkeypatch.setattr(
        generator_module,
        "_candidate",
        candidate_with_duplicate_id,
    )

    with pytest.raises(CandidateDeduplicationError):
        _generate()

def test_schema_boundary_values_cover_numeric_string_and_array_constraints() -> None:
    from app.modules.test_generation.generator import _schema_boundary_values

    numeric = _schema_boundary_values(
        {"type": "integer", "minimum": 1, "maximum": 5}
    )
    assert (
        "minimum",
        1,
        CandidateCategory.BOUNDARY,
        "Tests the declared minimum value.",
    ) in numeric
    assert (
        "below minimum",
        0,
        CandidateCategory.NEGATIVE,
        "Tests a value below the declared minimum.",
    ) in numeric
    assert (
        "maximum",
        5,
        CandidateCategory.BOUNDARY,
        "Tests the declared maximum value.",
    ) in numeric
    assert (
        "above maximum",
        6,
        CandidateCategory.NEGATIVE,
        "Tests a value above the declared maximum.",
    ) in numeric

    strings = _schema_boundary_values(
        {"type": "string", "minLength": 2, "maxLength": 4}
    )
    assert any(name == "below minimum length" and value == "x" for name, value, _, _ in strings)
    assert any(name == "above maximum length" and value == "xxxxx" for name, value, _, _ in strings)

    arrays = _schema_boundary_values(
        {"type": "array", "minItems": 1, "maxItems": 2, "items": {"type": "string"}}
    )
    assert any(name == "below minimum items" and value == [] for name, value, _, _ in arrays)
    assert any(name == "above maximum items" and len(value) == 3 for name, value, _, _ in arrays)