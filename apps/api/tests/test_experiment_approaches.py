from app.integrations.llm import LLMRequest, LLMResponse
from app.modules.api_understanding.normalizer import normalize_operations
from app.modules.api_understanding.parser import parse_openapi_document
from app.modules.test_generation import GenerationApproach, generate_for_approach

SPEC = """
openapi: 3.1.0
info:
  title: Experimental API
  version: "1"
paths:
  /items:
    get:
      summary: List items
      responses:
        "200":
          description: OK
"""


class FakeProvider:
    def __init__(self, text: str | None = None) -> None:
        self.requests: list[LLMRequest] = []
        self.text = text or (
            '{"candidates":[{"category":"positive","title":"List items",'
            '"parameters_json":"{}","body_json":null,"rationale":"Checks the list operation."}]}'
        )

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(text=self.text, provider="fake", model="fake-model", total_tokens=17)


def _operations():
    return normalize_operations(parse_openapi_document(SPEC))


def test_semantic_approach_supplies_facts_that_baseline_does_not() -> None:
    operation = _operations()[0]
    fact = {
        "fact_type": "parameter",
        "fact_value": {"name": "page", "in": "query", "description": "List inventory page"},
        "provenance": "EXTRACTED",
    }
    baseline_provider = FakeProvider()
    semantic_provider = FakeProvider()

    baseline = generate_for_approach(
        GenerationApproach.LLM_BASELINE,
        (operation,),
        semantic_facts_by_operation={operation.operation_key: [fact]},
        provider=baseline_provider,
    )
    semantic = generate_for_approach(
        GenerationApproach.SEMANTIC_ASSISTED,
        (operation,),
        semantic_facts_by_operation={operation.operation_key: [fact]},
        provider=semantic_provider,
    )

    assert baseline.generation_mode == "llm"
    assert semantic.generation_mode == "llm"
    assert '"description":"List inventory page"' not in baseline_provider.requests[0].user_prompt
    assert '"description":"List inventory page"' in semantic_provider.requests[0].user_prompt
    assert semantic.semantic_fact_count == 1
    assert baseline.llm_provider == "fake"
    assert baseline.llm_model == "fake-model"
    assert baseline.llm_token_usage == 17


def test_llm_approaches_use_a_deterministic_fallback_without_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.test_generation.approaches.create_llm_provider", lambda **_kwargs: None
    )
    operations = _operations()

    result = generate_for_approach(GenerationApproach.LLM_BASELINE, operations, provider=None)

    assert result.generation_mode == "deterministic_fallback"
    assert result.llm_status == "not_configured"
    assert result.candidates
    assert result.warning is not None


def test_feedback_and_evidence_approaches_share_generation_but_have_distinct_policies() -> None:
    operations = _operations()

    feedback = generate_for_approach(GenerationApproach.FEEDBACK_GUIDED, operations)
    evidence = generate_for_approach(GenerationApproach.EVIDENCE_BACKED, operations)

    assert feedback.candidates == evidence.candidates
    assert feedback.generation_policy_version != evidence.generation_policy_version
    assert feedback.generation_mode == "deterministic_pool"
    assert evidence.generation_mode == "deterministic_pool"


def test_semantic_facts_are_validated_and_bounded() -> None:
    from app.modules.test_generation.llm_assisted import bounded_semantic_facts

    facts = [
        {"fact_type": "parameter", "fact_value": {"name": "secret"}, "provenance": "INFERRED"},
        {
            "fact_type": "security_requirement",
            "fact_value": {"apiKey": "secret"},
            "provenance": "EXTRACTED",
        },
        {"fact_type": "parameter", "fact_value": {"name": "id"}, "provenance": "EXTRACTED"},
    ]
    assert bounded_semantic_facts(facts) == (
        {
            "fact_type": "parameter",
            "fact_value": {"name": "id"},
            "provenance": "EXTRACTED",
        },
    )


def test_failed_llm_run_records_provider_error_and_uses_fallback() -> None:
    from app.integrations.llm import LLMProviderError

    class RejectedProvider:
        provider_name = "groq"
        model_name = "openai/gpt-oss-120b"

        def generate(self, request: LLMRequest) -> LLMResponse:
            raise LLMProviderError(
                "Groq schema validation failed",
                code="json_validate_failed",
                status_code=400,
                provider=self.provider_name,
                model=self.model_name,
                failed_generation='{"api_key":"gsk_redacted"}',
            )

    result = generate_for_approach(
        GenerationApproach.LLM_BASELINE,
        _operations(),
        provider=RejectedProvider(),
        candidate_count=3,
    )
    assert result.generation_mode == "deterministic_fallback"
    assert result.llm_status == "failed"
    assert result.requested_candidate_count == 3
    assert result.attempt_count == 1
    assert result.generation_errors[0]["category"] == "json_validate_failed"
    assert result.generation_errors[0]["http_status"] == 400
    assert result.generation_errors[0]["model"] == "openai/gpt-oss-120b"
    assert result.generation_errors[0]["failed_generation"] == '{"api_key":"[redacted]"}'


def test_malformed_llm_completion_is_distinguished_from_provider_failure() -> None:
    result = generate_for_approach(
        GenerationApproach.LLM_BASELINE,
        _operations(),
        provider=FakeProvider("not JSON"),
    )
    assert result.generation_mode == "deterministic_fallback"
    assert result.generation_errors[0]["category"] == "malformed_output"
    assert result.completion_received is True
    assert result.local_parse_succeeded is False


def test_experiment_state_surfaces_fallback_completion() -> None:
    from app.api.experiments.router import _experiment_state

    assert _experiment_state(["completed_with_fallback"]) == "completed_with_fallback"
    assert _experiment_state(["completed", "completed_with_fallback"]) == "completed_with_fallback"
    assert _experiment_state(["completed", "failed"]) == "partial"


def test_empty_llm_output_is_recorded_and_falls_back_to_deterministic_candidates() -> None:
    result = generate_for_approach(
        GenerationApproach.LLM_BASELINE,
        _operations(),
        provider=FakeProvider("[]"),
    )

    assert result.generation_mode == "deterministic_fallback"
    assert result.llm_status == "empty"
    assert result.candidates
