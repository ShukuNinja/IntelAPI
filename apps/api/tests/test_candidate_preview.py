import pytest

import app.modules.test_generation.preview as preview_module
from app.modules.test_generation.models import CandidateCategory, TestCandidate
from app.modules.test_generation.orchestration import (
    CandidateGenerationResult,
    LLMGenerationStatus,
)


def _candidate(
    candidate_id: str,
    category: CandidateCategory,
) -> TestCandidate:
    return TestCandidate(
        candidate_id=candidate_id,
        operation_key="GET /users",
        category=category,
        title=f"Candidate {candidate_id}",
        method="GET",
        path="/users",
        parameters={},
        body=None,
        rationale="Unit-test candidate.",
    )


def _stub_generation(monkeypatch, candidates):
    def fake_generate(operations, provider=None):
        return CandidateGenerationResult(
            candidates=tuple(candidates),
            llm_status=LLMGenerationStatus.NOT_CONFIGURED,
        )

    monkeypatch.setattr(
        preview_module,
        "generate_candidates_with_llm",
        fake_generate,
    )


def test_preview_returns_candidates_without_persistence(monkeypatch):
    candidates = [
        _candidate("positive-1", CandidateCategory.POSITIVE),
        _candidate("negative-1", CandidateCategory.NEGATIVE),
    ]
    _stub_generation(monkeypatch, candidates)

    result = preview_module.preview_candidates(())

    assert result.candidates == tuple(
        sorted(candidates, key=lambda candidate: candidate.candidate_id)
    )
    assert result.llm_status is LLMGenerationStatus.NOT_CONFIGURED
    assert result.llm_error is None


def test_preview_filters_categories_before_applying_limit(monkeypatch):
    candidates = [
        _candidate("positive-1", CandidateCategory.POSITIVE),
        _candidate("negative-1", CandidateCategory.NEGATIVE),
        _candidate("positive-2", CandidateCategory.POSITIVE),
    ]
    _stub_generation(monkeypatch, candidates)

    result = preview_module.preview_candidates(
        (),
        categories=(CandidateCategory.POSITIVE,),
        limit=1,
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].category is CandidateCategory.POSITIVE


@pytest.mark.parametrize("limit", [0, -1, 101, True, 1.5])
def test_preview_rejects_invalid_limit(limit):
    with pytest.raises(preview_module.CandidatePreviewError):
        preview_module.preview_candidates((), limit=limit)


def test_preview_rejects_empty_category_selection():
    with pytest.raises(preview_module.CandidatePreviewError):
        preview_module.preview_candidates((), categories=())


def test_preview_rejects_invalid_category():
    with pytest.raises(preview_module.CandidatePreviewError):
        preview_module.preview_candidates(
            (),
            categories=("positive",),
        )


def test_preview_preserves_llm_failure_status(monkeypatch):
    def fake_generate(operations, provider=None):
        return CandidateGenerationResult(
            candidates=(_candidate("baseline", CandidateCategory.POSITIVE),),
            llm_status=LLMGenerationStatus.FAILED,
            llm_error="LLM candidate generation failed: TimeoutError",
        )

    monkeypatch.setattr(
        preview_module,
        "generate_candidates_with_llm",
        fake_generate,
    )

    result = preview_module.preview_candidates(())

    assert len(result.candidates) == 1
    assert result.llm_status is LLMGenerationStatus.FAILED
    assert result.llm_error == "LLM candidate generation failed: TimeoutError"
