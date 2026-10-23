import json
from unittest import result

from app.integrations.llm import LLMProviderError, LLMRequest, LLMResponse
from app.modules.api_understanding.normalizer import normalize_operations
from app.modules.api_understanding.parser import parse_openapi_document
from app.modules.test_generation.generator import generate_candidates
from app.modules.test_generation.orchestration import (
    LLMGenerationStatus,
    generate_candidates_with_llm,
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
  /health:
    get:
      summary: Health check
      responses:
        "200":
          description: OK
"""


class FakeProvider:
    def __init__(self, text: str = "[]") -> None:
        self.text = text
        self.calls = 0

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        return LLMResponse(text=self.text, provider="fake", model="fake-model")


class BrokenProvider:
    def generate(self, request: LLMRequest) -> LLMResponse:
        raise LLMProviderError("Sensitive provider details")


class UnexpectedFailureProvider:
    def generate(self, request: LLMRequest) -> LLMResponse:
        raise RuntimeError("Unexpected sensitive details")


def _operations():
    return normalize_operations(parse_openapi_document(SPEC))


def _proposal():
    return {
        "category": "negative",
        "title": "Reject unsupported query",
        "parameters": {"unexpected": "value"},
        "body": None,
        "rationale": "Explores handling of an unsupported query parameter.",
    }


def test_without_provider_returns_deterministic_baseline(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.test_generation.orchestration.create_llm_provider",
        lambda: None,
    )

    operations = _operations()

    result = generate_candidates_with_llm(operations)

    assert result.candidates == generate_candidates(operations)
    assert result.llm_status is LLMGenerationStatus.NOT_CONFIGURED
    assert result.llm_error is None


def test_uses_configured_provider_when_none_is_injected(monkeypatch) -> None:
    operations = _operations()
    provider = FakeProvider("[]")

    monkeypatch.setattr(
        "app.modules.test_generation.orchestration.create_llm_provider",
        lambda: provider,
    )

    result = generate_candidates_with_llm(operations)

    assert result.llm_status is LLMGenerationStatus.SUCCEEDED
    assert result.candidates == generate_candidates(operations)
    assert provider.calls == len(operations)


def test_provider_factory_failure_returns_deterministic_baseline(monkeypatch) -> None:
    operations = _operations()

    def fail_factory():
        raise RuntimeError("Sensitive initialization details")

    monkeypatch.setattr(
        "app.modules.test_generation.orchestration.create_llm_provider",
        fail_factory,
    )

    result = generate_candidates_with_llm(operations)

    assert result.candidates == generate_candidates(operations)
    assert result.llm_status is LLMGenerationStatus.FAILED
    assert result.llm_error == "LLM candidate generation failed: RuntimeError"
    assert "Sensitive initialization details" not in result.llm_error


def test_success_merges_and_deduplicates_candidates() -> None:
    operations = _operations()
    provider = FakeProvider(json.dumps([_proposal()]))

    result = generate_candidates_with_llm(operations, provider)

    assert result.llm_status is LLMGenerationStatus.SUCCEEDED
    assert result.llm_error is None
    assert len(result.candidates) == len(
        {candidate.candidate_id for candidate in result.candidates}
    )
    assert any(candidate.title == "Reject unsupported query" for candidate in result.candidates)
    assert provider.calls == len(operations)


def test_provider_failure_returns_baseline_and_safe_status() -> None:
    operations = _operations()

    result = generate_candidates_with_llm(operations, BrokenProvider())

    assert result.candidates == generate_candidates(operations)
    assert result.llm_status is LLMGenerationStatus.FAILED
    assert result.llm_error == "LLM candidate generation failed: LLMProviderError"
    assert "Sensitive provider details" not in result.llm_error


def test_unexpected_provider_failure_returns_baseline_without_leaking_message() -> None:
    operations = _operations()

    result = generate_candidates_with_llm(operations, UnexpectedFailureProvider())

    assert result.candidates == generate_candidates(operations)
    assert result.llm_status is LLMGenerationStatus.FAILED
    assert result.llm_error is not None
    assert result.llm_error.startswith(
    "LLM candidate generation failed: LLMProposalError:"
)
    assert "Unexpected sensitive details" not in result.llm_error


def test_malformed_output_returns_baseline_and_failure_status() -> None:
    operations = _operations()
    provider = FakeProvider("not JSON")

    result = generate_candidates_with_llm(operations, provider)

    assert result.candidates == generate_candidates(operations)
    assert result.llm_status is LLMGenerationStatus.FAILED
    assert result.llm_error == "LLM candidate generation failed: LLMProposalError"


def test_repeated_generation_is_stable() -> None:
    operations = _operations()
    proposal = json.dumps([_proposal()])

    first = generate_candidates_with_llm(operations, FakeProvider(proposal))
    second = generate_candidates_with_llm(operations, FakeProvider(proposal))

    assert first == second
