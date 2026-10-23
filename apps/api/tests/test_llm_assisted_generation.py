import json

import pytest

from app.integrations.llm import LLMRequest, LLMResponse
from app.modules.api_understanding.normalizer import normalize_operations
from app.modules.api_understanding.parser import parse_openapi_document
from app.modules.test_generation.llm_assisted import (
    PROPOSALS_JSON_SCHEMA,
    generate_llm_candidates,
)

SPEC = """
openapi: 3.1.0
info:
  title: Candidate API
  version: "1"
paths:
  /users:
    get:
      summary: List users
      responses:
        "200":
          description: OK
"""


class FakeProvider:
    def __init__(self, text: str) -> None:
        self.text = text
        self.requests: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(text=self.text, provider="fake", model="fake-model")


def _operation():
    document = parse_openapi_document(SPEC)
    return normalize_operations(document)[0]


def _proposal(**overrides):
    proposal = {
        "category": "positive",
        "title": "List users",
        "parameters_json": "{}",
        "body_json": None,
        "rationale": "Checks the declared list-users operation.",
    }
    proposal.update(overrides)
    return proposal


def test_generates_valid_candidate_from_fake_provider() -> None:
    provider = FakeProvider(json.dumps([_proposal()]))

    candidates = generate_llm_candidates(_operation(), provider)

    assert len(candidates) == 1
    assert candidates[0].method == "GET"
    assert candidates[0].path == "/users"
    assert candidates[0].candidate_id
    assert len(provider.requests) == 1
    assert provider.requests[0].json_schema["type"] == "object"


def test_parses_closed_schema_envelope_and_json_encoded_values() -> None:
    proposal = _proposal(
        parameters_json="{}",
        body_json='{"name":"Ada"}',
    )
    provider = FakeProvider(json.dumps({"candidates": [proposal]}))

    candidates = generate_llm_candidates(_operation(), provider)

    assert len(candidates) == 1
    assert candidates[0].parameters == {}
    assert candidates[0].body == {"name": "Ada"}


def test_candidate_schema_matches_groq_strict_requirements_and_local_contract() -> None:
    assert PROPOSALS_JSON_SCHEMA["type"] == "object"
    assert PROPOSALS_JSON_SCHEMA["required"] == ["candidates"]
    assert PROPOSALS_JSON_SCHEMA["additionalProperties"] is False
    candidate = PROPOSALS_JSON_SCHEMA["properties"]["candidates"]["items"]
    assert candidate["additionalProperties"] is False
    assert set(candidate["required"]) == {
        "category",
        "title",
        "parameters_json",
        "body_json",
        "rationale",
    }
    assert candidate["properties"]["parameters_json"]["type"] == "string"
    assert candidate["properties"]["body_json"]["type"] == ["string", "null"]


@pytest.mark.parametrize(
    "response_text",
    [
        "not JSON",
        "{}",
        "[null]",
        json.dumps([_proposal(extra="unexpected")]),
        json.dumps([_proposal(category="unknown")]),
        json.dumps([_proposal(parameters_json="[]")]),
        json.dumps([_proposal(parameters_json='{"undocumented":"value"}')]),
        json.dumps([_proposal(body_json="[]")]),
        json.dumps([_proposal(title="")]),
    ],
)
def test_rejects_malformed_or_invalid_proposals(response_text: str) -> None:
    rejected: list[dict] = []
    candidates = generate_llm_candidates(
        _operation(), FakeProvider(response_text), on_rejection=rejected.append
    )
    assert not candidates
    assert rejected


def test_deduplicates_identical_proposals() -> None:
    proposal = _proposal()
    provider = FakeProvider(json.dumps([proposal, proposal]))

    candidates = generate_llm_candidates(_operation(), provider)

    assert len(candidates) == 1


def test_rejects_response_above_size_limit() -> None:
    provider = FakeProvider(" " * (64 * 1024 + 1))

    rejected: list[dict] = []
    assert not generate_llm_candidates(_operation(), provider, on_rejection=rejected.append)
    assert "size limit" in rejected[0]["reason"]


def test_prompt_contains_operation_context_and_execution_guardrail() -> None:
    provider = FakeProvider("[]")

    assert generate_llm_candidates(_operation(), provider) == ()

    request = provider.requests[0]
    assert "GET" in request.user_prompt
    assert "/users" in request.user_prompt
    assert "Do not execute requests" in request.system_prompt
    assert "no more than 4 candidates" in request.system_prompt
    assert request.max_output_tokens == 980


def test_candidate_count_is_bounded_and_configurable() -> None:
    provider = FakeProvider("[]")
    assert generate_llm_candidates(_operation(), provider, candidate_count=3) == ()
    assert "no more than 3 candidates" in provider.requests[0].system_prompt
    assert provider.requests[0].max_output_tokens == 800
    with pytest.raises(ValueError, match="between 1 and 10"):
        generate_llm_candidates(_operation(), provider, candidate_count=11)


def test_retries_only_transient_provider_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.integrations.llm import LLMProviderError

    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    class RetryThenSuccess:
        calls = 0

        def generate(self, request: LLMRequest) -> LLMResponse:
            self.calls += 1
            if self.calls == 1:
                raise LLMProviderError("temporary", code="provider_unavailable", retryable=True)
            return LLMResponse(json.dumps({"candidates": [_proposal()]}), "fake", "fake-model")

    provider = RetryThenSuccess()
    errors: list[dict] = []
    candidates = generate_llm_candidates(
        _operation(), provider, on_error=errors.append, max_attempts=2
    )
    assert len(candidates) == 1
    assert provider.calls == 2
    assert errors[0]["attempt"] == 1
    assert errors[0]["retry_scheduled"] is True
    assert errors[0]["completion_received"] is False


def test_does_not_retry_non_retryable_schema_failure() -> None:
    from app.integrations.llm import LLMProviderError

    class SchemaFailure:
        calls = 0

        def generate(self, request: LLMRequest) -> LLMResponse:
            self.calls += 1
            raise LLMProviderError("invalid schema output", code="json_validate_failed")

    provider = SchemaFailure()
    errors: list[dict] = []
    with pytest.raises(LLMProviderError):
        generate_llm_candidates(_operation(), provider, on_error=errors.append, max_attempts=3)
    assert provider.calls == 1
    assert len(errors) == 1
    assert errors[0]["retry_scheduled"] is False


def test_output_token_truncation_has_distinct_structured_diagnostic() -> None:
    class TruncatedProvider:
        def generate(self, request: LLMRequest) -> LLMResponse:
            return LLMResponse("{", "groq", "test-model", finish_reason="length")

    errors: list[dict] = []
    assert not generate_llm_candidates(_operation(), TruncatedProvider(), on_error=errors.append)
    assert errors[0]["category"] == "output_truncated"
    assert errors[0]["completion_received"] is True
    assert errors[0]["local_parse_succeeded"] is False


def test_rejects_non_finite_json_numbers() -> None:
    provider = FakeProvider(
        '[{"category":"positive","title":"List users",'
        '"parameters_json":"{\\"limit\\":NaN}","body_json":null,'
        '"rationale":"Checks list users."}]'
    )

    rejected: list[dict] = []
    assert not generate_llm_candidates(_operation(), provider, on_rejection=rejected.append)
    assert rejected


def test_rejects_excessively_nested_json() -> None:
    nested = "[" * 1100 + "]" * 1100
    provider = FakeProvider(nested)

    rejected: list[dict] = []
    assert not generate_llm_candidates(_operation(), provider, on_rejection=rejected.append)
    assert rejected


def test_wraps_unexpected_provider_exceptions() -> None:
    from app.integrations.llm import LLMProviderError

    class BrokenProvider:
        def generate(self, request: LLMRequest) -> LLMResponse:
            raise RuntimeError("Unexpected provider failure")

    with pytest.raises(LLMProviderError):
        generate_llm_candidates(_operation(), BrokenProvider())
