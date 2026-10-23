import json

import pytest

from app.integrations.llm import LLMRequest, LLMResponse
from app.modules.api_understanding.normalizer import normalize_operations
from app.modules.api_understanding.parser import parse_openapi_document
from app.modules.test_generation.llm_assisted import (
    LLMProposalError,
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
        "parameters": {},
        "body": None,
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


@pytest.mark.parametrize(
    "response_text",
    [
        "not JSON",
        "{}",
        "[null]",
        json.dumps([_proposal(extra="unexpected")]),
        json.dumps([_proposal(category="unknown")]),
        json.dumps([_proposal(parameters=[])]),
        json.dumps([_proposal(parameters={"undocumented": "value"})]),
        json.dumps([_proposal(body=[])]),
        json.dumps([_proposal(title="")]),
    ],
)
def test_rejects_malformed_or_invalid_proposals(response_text: str) -> None:
    with pytest.raises(LLMProposalError):
        generate_llm_candidates(_operation(), FakeProvider(response_text))


def test_deduplicates_identical_proposals() -> None:
    proposal = _proposal()
    provider = FakeProvider(json.dumps([proposal, proposal]))

    candidates = generate_llm_candidates(_operation(), provider)

    assert len(candidates) == 1


def test_rejects_response_above_size_limit() -> None:
    provider = FakeProvider(" " * (64 * 1024 + 1))

    with pytest.raises(LLMProposalError, match="size limit"):
        generate_llm_candidates(_operation(), provider)


def test_prompt_contains_operation_context_and_execution_guardrail() -> None:
    provider = FakeProvider("[]")

    assert generate_llm_candidates(_operation(), provider) == ()

    request = provider.requests[0]
    assert "GET" in request.user_prompt
    assert "/users" in request.user_prompt
    assert "Do not execute requests" in request.system_prompt


def test_rejects_non_finite_json_numbers() -> None:
    provider = FakeProvider(
        '[{"category":"positive","title":"List users",'
        '"parameters":{"limit":NaN},"body":null,'
        '"rationale":"Checks list users."}]'
    )

    with pytest.raises(LLMProposalError):
        generate_llm_candidates(_operation(), provider)


def test_rejects_excessively_nested_json() -> None:
    nested = "[" * 1100 + "]" * 1100
    provider = FakeProvider(nested)

    with pytest.raises(LLMProposalError):
        generate_llm_candidates(_operation(), provider)


def test_wraps_unexpected_provider_exceptions() -> None:
    from app.integrations.llm import LLMProviderError

    class BrokenProvider:
        def generate(self, request: LLMRequest) -> LLMResponse:
            raise RuntimeError("Unexpected provider failure")

    with pytest.raises(LLMProviderError):
        generate_llm_candidates(_operation(), BrokenProvider())
