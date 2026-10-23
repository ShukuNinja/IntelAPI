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
    fact = {"fact_type": "operation", "fact_value": {"summary": "List inventory"}}
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
    assert "List inventory" not in baseline_provider.requests[0].user_prompt
    assert "List inventory" in semantic_provider.requests[0].user_prompt
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


def test_empty_llm_output_is_recorded_and_falls_back_to_deterministic_candidates() -> None:
    result = generate_for_approach(
        GenerationApproach.LLM_BASELINE,
        _operations(),
        provider=FakeProvider("[]"),
    )

    assert result.generation_mode == "deterministic_fallback"
    assert result.llm_status == "empty"
    assert result.candidates
