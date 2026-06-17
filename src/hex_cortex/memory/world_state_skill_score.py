"""Score operator skills from local world-state candidates."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.world_state_candidate import (
    WORLD_STATE_FILENAME,
    WorldStateCandidateJsonlStore,
)
from hex_cortex.memory.world_state_candidate_evaluation import (
    WORLD_STATE_EVALUATION_FILENAME,
    WorldStateCandidateEvaluationJsonlStore,
)

WORLD_STATE_SKILL_SCORE_FILENAME = "world-state-skill-score.jsonl"


class WorldStateSkillScoreRecord(BaseModel):
    """One persisted world-state skill score."""

    score_id: str = Field(default_factory=lambda: f"skill_score_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    candidate_id: str
    evaluation_id: str | None
    candidate_action: str
    suggested_skill: str
    skill_score: float = Field(ge=0.0, le=1.0)
    skill_reason: str
    world_verdict: str | None
    predicted_risk: str
    predicted_cost: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class WorldStateSkillScoreSummary(BaseModel):
    """Summary of persisted world-state skill scores."""

    inspect_type: str = "world_state_skill_score"
    path: str
    exists: bool
    total_score_count: int = Field(ge=0)
    latest_score_id: str | None
    latest_candidate_id: str | None
    latest_suggested_skill: str | None
    latest_skill_score: float | None
    latest_skill_reason: str | None


class WorldStateSkillScoreJsonlStore:
    """Persist world-state skill scores as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[WorldStateSkillScoreRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(WorldStateSkillScoreRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid world state skill score at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[WorldStateSkillScoreRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: WorldStateSkillScoreRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def score_latest_world_state_skill(profile: Path) -> dict[str, object]:
    """Score the best operator skill from the latest world-state candidate."""

    candidates = WorldStateCandidateJsonlStore(profile / WORLD_STATE_FILENAME).load()
    evaluations = WorldStateCandidateEvaluationJsonlStore(
        profile / WORLD_STATE_EVALUATION_FILENAME
    ).load()
    if not candidates:
        record = _missing_candidate_skill_score(profile)
    else:
        latest_candidate = candidates[-1]
        latest_evaluation = evaluations[-1] if evaluations else None
        record = _score_candidate(profile, latest_candidate, latest_evaluation)
    path = profile / WORLD_STATE_SKILL_SCORE_FILENAME
    count = WorldStateSkillScoreJsonlStore(path).append(record)
    return {
        "score_type": "world_state_skill_score",
        "profile_path": str(profile),
        "score_path": str(path),
        "score_count": count,
        "score_record": record.model_dump(mode="json"),
    }


def summarize_world_state_skill_scores(path: Path) -> dict[str, object]:
    records = WorldStateSkillScoreJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = WorldStateSkillScoreSummary(
        path=str(path),
        exists=path.exists(),
        total_score_count=len(records),
        latest_score_id=latest.score_id if latest else None,
        latest_candidate_id=latest.candidate_id if latest else None,
        latest_suggested_skill=latest.suggested_skill if latest else None,
        latest_skill_score=latest.skill_score if latest else None,
        latest_skill_reason=latest.skill_reason if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_candidate_skill_score(profile: Path) -> WorldStateSkillScoreRecord:
    return WorldStateSkillScoreRecord(
        profile_path=str(profile),
        candidate_id="none",
        evaluation_id=None,
        candidate_action="build_world_state_candidate",
        suggested_skill="world_state_builder",
        skill_score=0.2,
        skill_reason="world_state_candidate_missing",
        world_verdict=None,
        predicted_risk="high",
        predicted_cost=0.4,
        confidence=0.2,
    )


def _score_candidate(profile: Path, candidate, evaluation) -> WorldStateSkillScoreRecord:
    suggested_skill = _skill_for_action(candidate.candidate_action)
    skill_reason = _skill_reason(candidate, evaluation)
    score = _skill_score(candidate, evaluation)
    return WorldStateSkillScoreRecord(
        profile_path=str(profile),
        candidate_id=candidate.candidate_id,
        evaluation_id=evaluation.evaluation_id if evaluation else None,
        candidate_action=candidate.candidate_action,
        suggested_skill=suggested_skill,
        skill_score=score,
        skill_reason=skill_reason,
        world_verdict=evaluation.verdict if evaluation else None,
        predicted_risk=candidate.predicted_risk,
        predicted_cost=candidate.predicted_cost,
        confidence=candidate.confidence,
    )


def _skill_for_action(action: str) -> str:
    if action == "review_watch_reasons":
        return "operator_watch_review"
    if action == "repair_profile_readiness":
        return "profile_readiness_repair"
    if action == "observe_pipeline_result":
        return "pipeline_result_observer"
    if action == "build_trace":
        return "cognitive_trace_builder"
    return "operator_state_inspector"


def _skill_reason(candidate, evaluation) -> str:
    if not evaluation:
        return "world_candidate_not_evaluated"
    if evaluation.verdict == "world_candidate_valid" and candidate.predicted_risk == "low":
        return "low_risk_high_confidence_world_candidate"
    if evaluation.verdict == "world_candidate_valid":
        return "valid_world_candidate"
    return "world_candidate_requires_review"


def _skill_score(candidate, evaluation) -> float:
    if not evaluation:
        return round(candidate.confidence * 0.4, 4)
    risk_factor = 1.0 if candidate.predicted_risk == "low" else 0.6
    return round(evaluation.overall_score * risk_factor * candidate.confidence, 4)
