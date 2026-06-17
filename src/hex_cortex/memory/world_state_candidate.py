"""Local world-state candidates derived from evaluated cognitive traces."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cognitive_trace import (
    TRACE_FILENAME,
    CognitiveTraceJsonlStore,
)
from hex_cortex.memory.cognitive_trace_evaluation import (
    EVALUATION_FILENAME,
    CognitiveTraceEvaluationJsonlStore,
)

WORLD_STATE_FILENAME = "world-state-candidate.jsonl"


class WorldStateCandidateRecord(BaseModel):
    """One compact local world-state candidate."""

    candidate_id: str = Field(default_factory=lambda: f"world_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    trace_id: str
    evaluation_id: str | None
    current_state: str
    expected_state: str
    candidate_action: str
    predicted_risk: str
    predicted_cost: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    source_verdict: str | None


class WorldStateCandidateSummary(BaseModel):
    """Summary of persisted world-state candidates."""

    inspect_type: str = "world_state_candidate"
    path: str
    exists: bool
    total_candidate_count: int = Field(ge=0)
    latest_candidate_id: str | None
    latest_current_state: str | None
    latest_expected_state: str | None
    latest_candidate_action: str | None
    latest_predicted_risk: str | None
    latest_confidence: float | None


class WorldStateCandidateJsonlStore:
    """Persist world-state candidates as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[WorldStateCandidateRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(WorldStateCandidateRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid world state candidate at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[WorldStateCandidateRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: WorldStateCandidateRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_world_state_candidate(profile: Path) -> dict[str, object]:
    """Build and persist a local world-state candidate from the latest trace."""

    traces = CognitiveTraceJsonlStore(profile / TRACE_FILENAME).load()
    evaluations = CognitiveTraceEvaluationJsonlStore(profile / EVALUATION_FILENAME).load()
    if not traces:
        record = _missing_trace_candidate(profile)
    else:
        latest_trace = traces[-1]
        latest_evaluation = evaluations[-1] if evaluations else None
        record = _candidate_from_trace(profile, latest_trace, latest_evaluation)
    path = profile / WORLD_STATE_FILENAME
    count = WorldStateCandidateJsonlStore(path).append(record)
    return {
        "candidate_type": "world_state_candidate",
        "profile_path": str(profile),
        "candidate_path": str(path),
        "candidate_count": count,
        "candidate_record": record.model_dump(mode="json"),
    }


def summarize_world_state_candidates(path: Path) -> dict[str, object]:
    records = WorldStateCandidateJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = WorldStateCandidateSummary(
        path=str(path),
        exists=path.exists(),
        total_candidate_count=len(records),
        latest_candidate_id=latest.candidate_id if latest else None,
        latest_current_state=latest.current_state if latest else None,
        latest_expected_state=latest.expected_state if latest else None,
        latest_candidate_action=latest.candidate_action if latest else None,
        latest_predicted_risk=latest.predicted_risk if latest else None,
        latest_confidence=latest.confidence if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_trace_candidate(profile: Path) -> WorldStateCandidateRecord:
    return WorldStateCandidateRecord(
        profile_path=str(profile),
        trace_id="none",
        evaluation_id=None,
        current_state="trace_missing",
        expected_state="build_cognitive_trace",
        candidate_action="build_trace",
        predicted_risk="high",
        predicted_cost=0.4,
        confidence=0.2,
        source_verdict=None,
    )


def _candidate_from_trace(
    profile: Path,
    trace,
    evaluation,
) -> WorldStateCandidateRecord:
    current_state = f"status={trace.status}; decision={trace.decision}"
    expected_state = _expected_state(trace.final_action)
    confidence = _confidence_from_evaluation(evaluation)
    return WorldStateCandidateRecord(
        profile_path=str(profile),
        trace_id=trace.trace_id,
        evaluation_id=evaluation.evaluation_id if evaluation else None,
        current_state=current_state,
        expected_state=expected_state,
        candidate_action=trace.final_action,
        predicted_risk=_predicted_risk(trace.final_action, evaluation),
        predicted_cost=_predicted_cost(trace.final_action),
        confidence=confidence,
        source_verdict=evaluation.verdict if evaluation else None,
    )


def _expected_state(final_action: str) -> str:
    if final_action == "review_watch_reasons":
        return "operator_reviews_watch_reasons"
    if final_action == "repair_profile_readiness":
        return "profile_readiness_repaired"
    if final_action == "observe_pipeline_result":
        return "pipeline_result_observed"
    return "operator_state_inspected"


def _predicted_risk(final_action: str, evaluation) -> str:
    if not evaluation or evaluation.overall_score < 0.6:
        return "high"
    if final_action == "observe_pipeline_result":
        return "medium"
    return "low"


def _predicted_cost(final_action: str) -> float:
    if final_action == "observe_pipeline_result":
        return 0.7
    if final_action == "repair_profile_readiness":
        return 0.5
    return 0.2


def _confidence_from_evaluation(evaluation) -> float:
    if not evaluation:
        return 0.4
    return float(evaluation.overall_score)
