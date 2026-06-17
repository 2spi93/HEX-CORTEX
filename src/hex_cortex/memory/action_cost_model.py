"""Action cost model for world-state skill scores."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.world_state_skill_score import (
    WORLD_STATE_SKILL_SCORE_FILENAME,
    WorldStateSkillScoreJsonlStore,
)

ACTION_COST_FILENAME = "action-cost.jsonl"


class ActionCostRecord(BaseModel):
    """One persisted action cost estimate."""

    cost_id: str = Field(default_factory=lambda: f"action_cost_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    score_id: str
    suggested_skill: str
    candidate_action: str
    cognitive_cost: float = Field(ge=0.0, le=1.0)
    operator_cost: float = Field(ge=0.0, le=1.0)
    risk_cost: float = Field(ge=0.0, le=1.0)
    time_cost: float = Field(ge=0.0, le=1.0)
    overall_cost: float = Field(ge=0.0, le=1.0)
    action_score: float = Field(ge=0.0, le=1.0)
    verdict: str
    reasons: list[str]


class ActionCostSummary(BaseModel):
    """Summary of persisted action cost estimates."""

    inspect_type: str = "action_cost_model"
    path: str
    exists: bool
    total_cost_count: int = Field(ge=0)
    latest_cost_id: str | None
    latest_suggested_skill: str | None
    latest_overall_cost: float | None
    latest_action_score: float | None
    latest_verdict: str | None


class ActionCostJsonlStore:
    """Persist action costs as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ActionCostRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(ActionCostRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid action cost record at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ActionCostRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ActionCostRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def estimate_latest_action_cost(profile: Path) -> dict[str, object]:
    """Estimate and persist the latest action cost from the skill score."""

    scores = WorldStateSkillScoreJsonlStore(
        profile / WORLD_STATE_SKILL_SCORE_FILENAME
    ).load()
    if not scores:
        record = _missing_skill_score_action_cost(profile)
    else:
        record = _estimate_from_skill_score(profile, scores[-1])
    path = profile / ACTION_COST_FILENAME
    count = ActionCostJsonlStore(path).append(record)
    return {
        "cost_type": "action_cost_model",
        "profile_path": str(profile),
        "cost_path": str(path),
        "cost_count": count,
        "cost_record": record.model_dump(mode="json"),
    }


def summarize_action_costs(path: Path) -> dict[str, object]:
    records = ActionCostJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ActionCostSummary(
        path=str(path),
        exists=path.exists(),
        total_cost_count=len(records),
        latest_cost_id=latest.cost_id if latest else None,
        latest_suggested_skill=latest.suggested_skill if latest else None,
        latest_overall_cost=latest.overall_cost if latest else None,
        latest_action_score=latest.action_score if latest else None,
        latest_verdict=latest.verdict if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_skill_score_action_cost(profile: Path) -> ActionCostRecord:
    return ActionCostRecord(
        profile_path=str(profile),
        score_id="none",
        suggested_skill="world_state_skill_score_missing",
        candidate_action="score_world_state_skill",
        cognitive_cost=0.4,
        operator_cost=0.4,
        risk_cost=0.8,
        time_cost=0.4,
        overall_cost=0.5,
        action_score=0.2,
        verdict="action_cost_missing_skill_score",
        reasons=["world_state_skill_score_missing"],
    )


def _estimate_from_skill_score(profile: Path, score) -> ActionCostRecord:
    cognitive_cost = _cognitive_cost(score.suggested_skill)
    operator_cost = float(score.predicted_cost)
    risk_cost = _risk_cost(score.predicted_risk)
    time_cost = _time_cost(score.suggested_skill)
    overall_cost = round(
        (cognitive_cost + operator_cost + risk_cost + time_cost) / 4,
        4,
    )
    action_score = round((1 - overall_cost) * score.skill_score * score.confidence, 4)
    reasons = _reasons(overall_cost, action_score)
    return ActionCostRecord(
        profile_path=str(profile),
        score_id=score.score_id,
        suggested_skill=score.suggested_skill,
        candidate_action=score.candidate_action,
        cognitive_cost=cognitive_cost,
        operator_cost=operator_cost,
        risk_cost=risk_cost,
        time_cost=time_cost,
        overall_cost=overall_cost,
        action_score=action_score,
        verdict=_verdict(action_score, reasons),
        reasons=reasons or ["action_cost_quality_ok"],
    )


def _cognitive_cost(skill: str) -> float:
    if skill == "operator_watch_review":
        return 0.2
    if skill == "world_state_builder":
        return 0.4
    if skill == "profile_readiness_repair":
        return 0.5
    if skill == "pipeline_result_observer":
        return 0.6
    return 0.5


def _risk_cost(predicted_risk: str) -> float:
    if predicted_risk == "low":
        return 0.1
    if predicted_risk == "medium":
        return 0.5
    return 0.9


def _time_cost(skill: str) -> float:
    if skill == "operator_watch_review":
        return 0.2
    if skill == "profile_readiness_repair":
        return 0.5
    if skill == "pipeline_result_observer":
        return 0.6
    return 0.4


def _reasons(overall_cost: float, action_score: float) -> list[str]:
    reasons = []
    if overall_cost > 0.7:
        reasons.append("high_overall_cost")
    if action_score < 0.5:
        reasons.append("low_action_score")
    return reasons


def _verdict(action_score: float, reasons: list[str]) -> str:
    if action_score >= 0.75 and not reasons:
        return "action_cost_valid"
    if action_score >= 0.5:
        return "action_cost_watch"
    return "action_cost_blocked"
