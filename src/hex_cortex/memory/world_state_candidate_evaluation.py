"""Evaluate local world-state candidates for planning quality."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.world_state_candidate import (
    WORLD_STATE_FILENAME,
    WorldStateCandidateJsonlStore,
)

WORLD_STATE_EVALUATION_FILENAME = "world-state-candidate-evaluation.jsonl"
LOW_RISK_ACTIONS = {"review_watch_reasons", "build_trace"}
MEDIUM_RISK_ACTIONS = {"repair_profile_readiness", "observe_pipeline_result"}


class WorldStateCandidateEvaluationRecord(BaseModel):
    """One persisted world-state candidate evaluation."""

    evaluation_id: str = Field(default_factory=lambda: f"world_eval_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    candidate_id: str
    transition_score: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=1.0)
    cost_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    overall_score: float = Field(ge=0.0, le=1.0)
    verdict: str
    reasons: list[str]


class WorldStateCandidateEvaluationSummary(BaseModel):
    """Summary of persisted world-state candidate evaluations."""

    inspect_type: str = "world_state_candidate_evaluation"
    path: str
    exists: bool
    total_evaluation_count: int = Field(ge=0)
    latest_evaluation_id: str | None
    latest_candidate_id: str | None
    latest_verdict: str | None
    latest_overall_score: float | None


class WorldStateCandidateEvaluationJsonlStore:
    """Persist world-state candidate evaluations as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[WorldStateCandidateEvaluationRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        WorldStateCandidateEvaluationRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid world candidate evaluation at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[WorldStateCandidateEvaluationRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: WorldStateCandidateEvaluationRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def evaluate_latest_world_state_candidate(profile: Path) -> dict[str, object]:
    """Evaluate and persist the latest world-state candidate for a profile."""

    candidates = WorldStateCandidateJsonlStore(profile / WORLD_STATE_FILENAME).load()
    if not candidates:
        record = _missing_candidate_evaluation(profile)
    else:
        record = _evaluate_candidate(profile, candidates[-1])
    path = profile / WORLD_STATE_EVALUATION_FILENAME
    count = WorldStateCandidateEvaluationJsonlStore(path).append(record)
    return {
        "evaluation_type": "world_state_candidate_evaluation",
        "profile_path": str(profile),
        "evaluation_path": str(path),
        "evaluation_count": count,
        "evaluation_record": record.model_dump(mode="json"),
    }


def summarize_world_state_candidate_evaluations(path: Path) -> dict[str, object]:
    records = WorldStateCandidateEvaluationJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = WorldStateCandidateEvaluationSummary(
        path=str(path),
        exists=path.exists(),
        total_evaluation_count=len(records),
        latest_evaluation_id=latest.evaluation_id if latest else None,
        latest_candidate_id=latest.candidate_id if latest else None,
        latest_verdict=latest.verdict if latest else None,
        latest_overall_score=latest.overall_score if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_candidate_evaluation(profile: Path) -> WorldStateCandidateEvaluationRecord:
    return WorldStateCandidateEvaluationRecord(
        profile_path=str(profile),
        candidate_id="none",
        transition_score=0.0,
        risk_score=0.0,
        cost_score=0.0,
        confidence_score=0.0,
        overall_score=0.0,
        verdict="world_candidate_missing",
        reasons=["no_world_state_candidate_available"],
    )


def _evaluate_candidate(profile: Path, candidate) -> WorldStateCandidateEvaluationRecord:
    reasons = []
    transition_score = _transition_score(candidate, reasons)
    risk_score = _risk_score(candidate, reasons)
    cost_score = _cost_score(candidate, reasons)
    confidence_score = float(candidate.confidence)
    overall_score = round(
        (transition_score + risk_score + cost_score + confidence_score) / 4,
        4,
    )
    verdict = _verdict(overall_score, reasons)
    return WorldStateCandidateEvaluationRecord(
        profile_path=str(profile),
        candidate_id=candidate.candidate_id,
        transition_score=transition_score,
        risk_score=risk_score,
        cost_score=cost_score,
        confidence_score=confidence_score,
        overall_score=overall_score,
        verdict=verdict,
        reasons=reasons or ["world_candidate_quality_ok"],
    )


def _transition_score(candidate, reasons: list[str]) -> float:
    expected_state = _expected_state_for_action(candidate.candidate_action)
    if candidate.expected_state == expected_state:
        return 1.0
    reasons.append("unexpected_expected_state")
    return 0.4


def _risk_score(candidate, reasons: list[str]) -> float:
    if candidate.predicted_risk == "low":
        return 1.0
    if candidate.predicted_risk == "medium":
        return 0.6
    reasons.append("high_predicted_risk")
    return 0.2


def _cost_score(candidate, reasons: list[str]) -> float:
    if candidate.predicted_cost <= 0.3:
        return 1.0
    if candidate.predicted_cost <= 0.7:
        return 0.6
    reasons.append("high_predicted_cost")
    return 0.2


def _expected_state_for_action(action: str) -> str:
    if action == "review_watch_reasons":
        return "operator_reviews_watch_reasons"
    if action == "repair_profile_readiness":
        return "profile_readiness_repaired"
    if action == "observe_pipeline_result":
        return "pipeline_result_observed"
    if action == "build_trace":
        return "build_cognitive_trace"
    return "operator_state_inspected"


def _verdict(overall_score: float, reasons: list[str]) -> str:
    if overall_score >= 0.85 and not reasons:
        return "world_candidate_valid"
    if overall_score >= 0.6:
        return "world_candidate_watch"
    return "world_candidate_blocked"
