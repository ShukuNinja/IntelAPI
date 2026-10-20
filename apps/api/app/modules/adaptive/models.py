"""Domain models for deterministic adaptive test selection."""

from dataclasses import dataclass
from math import isfinite

from app.modules.test_generation.models import TestCandidate


@dataclass(frozen=True, slots=True)
class CandidateSignals:
    """Normalized evidence signals supplied to the scoring engine."""

    candidate_id: str
    unexpectedness: float = 0.0
    novelty: float = 0.0
    boundary_relevance: float = 0.0
    inconsistency: float = 0.0
    exploration_value: float = 0.0
    cost_risk_penalty: float = 0.0
    eligible: bool = True
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject non-normalized or non-finite signal values."""
        for name in (
            "unexpectedness",
            "novelty",
            "boundary_relevance",
            "inconsistency",
            "exploration_value",
            "cost_risk_penalty",
        ):
            value = getattr(self, name)
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and between 0 and 1")


@dataclass(frozen=True, slots=True)
class AdaptiveScoringConfig:
    """Versioned weights for the deterministic scoring heuristic."""

    policy_version: str = "adaptive-v1"
    unexpectedness_weight: float = 0.25
    novelty_weight: float = 0.20
    boundary_relevance_weight: float = 0.15
    inconsistency_weight: float = 0.15
    exploration_value_weight: float = 0.25
    cost_risk_weight: float = 0.25

    def __post_init__(self) -> None:
        """Validate the scoring policy."""
        if not self.policy_version.strip():
            raise ValueError("policy_version must not be empty")

        weights = (
            self.unexpectedness_weight,
            self.novelty_weight,
            self.boundary_relevance_weight,
            self.inconsistency_weight,
            self.exploration_value_weight,
            self.cost_risk_weight,
        )
        if any(not isfinite(weight) or weight < 0.0 for weight in weights):
            raise ValueError("Scoring weights must be finite and non-negative")

        positive_total = sum(weights[:5])
        if positive_total <= 0.0:
            raise ValueError("At least one positive scoring weight is required")


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    """One explainable contribution to a candidate score."""

    name: str
    raw_value: float
    weight: float
    contribution: float


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    """A candidate ranked for possible follow-up selection."""

    rank: int
    candidate: TestCandidate
    score: float
    components: tuple[ScoreComponent, ...]
    evidence_ids: tuple[str, ...]
    rationale: str
    policy_version: str
