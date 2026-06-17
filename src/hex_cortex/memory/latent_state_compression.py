"""Symbolic latent-state compression for operator planning."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.action_cost_model import (
    ACTION_COST_FILENAME,
    ActionCostJsonlStore,
)
from hex_cortex.memory.world_state_candidate import (
    WORLD_STATE_FILENAME,
    WorldStateCandidateJsonlStore,
)
from hex_cortex.memory.world_state_skill_score import (
    WORLD_STATE_SKILL_SCORE_FILENAME,
    WorldStateSkillScoreJsonlStore,
)

LATENT_STATE_FILENAME = "latent-state.jsonl"
LATENT_VERSION = "symbolic_v1"


class LatentStateRecord(BaseModel):
    """One compressed symbolic latent state."""

    latent_id: str = Field(default_factory=lambda: f"latent_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_candidate_id: str | None
    source_score_id: str | None
    source_cost_id: str | None
    latent_version: str = LATENT_VERSION
    tokens: list[str]
    vector: list[float]
    vector_dim: int = Field(ge=0)
    compression_score: float = Field(ge=0.0, le=1.0)
    suggested_skill: str
    candidate_action: str
    action_score: float = Field(ge=0.0, le=1.0)
    verdict: str
    reasons: list[str]


class LatentStateSummary(BaseModel):
    """Summary of persisted latent states."""

    inspect_type: str = "latent_state"
    path: str
    exists: bool
    total_latent_count: int = Field(ge=0)
    latest_latent_id: str | None
    latest_suggested_skill: str | None
    latest_candidate_action: str | None
    latest_action_score: float | None
    latest_compression_score: float | None
    latest_verdict: str | None
    latest_vector_dim: int | None


class LatentStateJsonlStore:
    """Persist latent states as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[LatentStateRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(LatentStateRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid latent state at line {line_number}") from exc
        return records

    def save(self, records: list[LatentStateRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: LatentStateRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def compress_latest_latent_state(profile: Path) -> dict[str, object]:
    """Compress latest operator planning state into a compact latent state."""

    candidates = WorldStateCandidateJsonlStore(profile / WORLD_STATE_FILENAME).load()
    skill_scores = WorldStateSkillScoreJsonlStore(
        profile / WORLD_STATE_SKILL_SCORE_FILENAME
    ).load()
    action_costs = ActionCostJsonlStore(profile / ACTION_COST_FILENAME).load()
    if not action_costs:
        record = _missing_action_cost_latent(profile)
    else:
        candidate = candidates[-1] if candidates else None
        skill_score = skill_scores[-1] if skill_scores else None
        record = _compress_from_sources(profile, candidate, skill_score, action_costs[-1])
    path = profile / LATENT_STATE_FILENAME
    count = LatentStateJsonlStore(path).append(record)
    return {
        "latent_type": "latent_state_compression",
        "profile_path": str(profile),
        "latent_path": str(path),
        "latent_count": count,
        "latent_record": record.model_dump(mode="json"),
    }


def summarize_latent_states(path: Path) -> dict[str, object]:
    records = LatentStateJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = LatentStateSummary(
        path=str(path),
        exists=path.exists(),
        total_latent_count=len(records),
        latest_latent_id=latest.latent_id if latest else None,
        latest_suggested_skill=latest.suggested_skill if latest else None,
        latest_candidate_action=latest.candidate_action if latest else None,
        latest_action_score=latest.action_score if latest else None,
        latest_compression_score=latest.compression_score if latest else None,
        latest_verdict=latest.verdict if latest else None,
        latest_vector_dim=latest.vector_dim if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_action_cost_latent(profile: Path) -> LatentStateRecord:
    vector = [0.0] * 8
    return LatentStateRecord(
        profile_path=str(profile),
        source_candidate_id=None,
        source_score_id=None,
        source_cost_id=None,
        tokens=["missing:action_cost"],
        vector=vector,
        vector_dim=len(vector),
        compression_score=0.0,
        suggested_skill="action_cost_builder",
        candidate_action="estimate_action_cost",
        action_score=0.0,
        verdict="latent_missing_action_cost",
        reasons=["action_cost_missing"],
    )


def _compress_from_sources(profile: Path, candidate, skill_score, action_cost) -> LatentStateRecord:
    tokens = _tokens(candidate, skill_score, action_cost)
    vector = _vector(candidate, skill_score, action_cost)
    compression_score = _compression_score(vector, tokens)
    return LatentStateRecord(
        profile_path=str(profile),
        source_candidate_id=candidate.candidate_id if candidate else None,
        source_score_id=skill_score.score_id if skill_score else None,
        source_cost_id=action_cost.cost_id,
        tokens=tokens,
        vector=vector,
        vector_dim=len(vector),
        compression_score=compression_score,
        suggested_skill=action_cost.suggested_skill,
        candidate_action=action_cost.candidate_action,
        action_score=action_cost.action_score,
        verdict=_verdict(action_cost.verdict, compression_score),
        reasons=["latent_state_compressed"],
    )


def _tokens(candidate, skill_score, action_cost) -> list[str]:
    current_state = candidate.current_state if candidate else "state=unknown"
    risk = skill_score.predicted_risk if skill_score else "unknown"
    return [
        f"state:{_state_token(current_state)}",
        f"action:{action_cost.candidate_action}",
        f"skill:{action_cost.suggested_skill}",
        f"risk:{risk}",
        f"cost:{_cost_token(action_cost.overall_cost)}",
        f"verdict:{action_cost.verdict}",
    ]


def _vector(candidate, skill_score, action_cost) -> list[float]:
    current_state = candidate.current_state if candidate else "state=unknown"
    risk = skill_score.predicted_risk if skill_score else "unknown"
    skill_value = skill_score.skill_score if skill_score else 0.0
    confidence = skill_score.confidence if skill_score else 0.0
    return [
        _state_value(current_state),
        _action_value(action_cost.candidate_action),
        _risk_value(risk),
        round(1 - action_cost.overall_cost, 4),
        action_cost.action_score,
        skill_value,
        confidence,
        _verdict_value(action_cost.verdict),
    ]


def _compression_score(vector: list[float], tokens: list[str]) -> float:
    if not tokens or not vector:
        return 0.0
    return round(sum(vector) / len(vector), 4)


def _state_token(current_state: str) -> str:
    if "status=ready" in current_state:
        return "ready"
    if "status=watch" in current_state:
        return "watch"
    if "trace_missing" in current_state:
        return "missing"
    return "unknown"


def _state_value(current_state: str) -> float:
    token = _state_token(current_state)
    if token == "ready":
        return 1.0
    if token == "watch":
        return 0.6
    if token == "missing":
        return 0.1
    return 0.3


def _action_value(action: str) -> float:
    if action == "review_watch_reasons":
        return 0.8
    if action == "repair_profile_readiness":
        return 0.6
    if action == "observe_pipeline_result":
        return 0.7
    if action == "estimate_action_cost":
        return 0.3
    return 0.4


def _risk_value(predicted_risk: str) -> float:
    if predicted_risk == "low":
        return 1.0
    if predicted_risk == "medium":
        return 0.5
    if predicted_risk == "high":
        return 0.1
    return 0.3


def _cost_token(cost: float) -> str:
    if cost <= 0.3:
        return "low"
    if cost <= 0.7:
        return "medium"
    return "high"


def _verdict_value(verdict: str) -> float:
    if verdict == "action_cost_valid":
        return 1.0
    if verdict == "action_cost_watch":
        return 0.6
    if verdict == "action_cost_blocked":
        return 0.2
    return 0.1


def _verdict(action_cost_verdict: str, compression_score: float) -> str:
    if action_cost_verdict == "action_cost_valid" and compression_score >= 0.7:
        return "latent_state_valid"
    if compression_score >= 0.5:
        return "latent_state_watch"
    return "latent_state_blocked"
