"""Evaluate public cognitive traces for quality and safety."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cognitive_trace import (
    TRACE_FILENAME,
    CognitiveTraceJsonlStore,
)

EVALUATION_FILENAME = "cognitive-trace-evaluation.jsonl"
EXPECTED_STEP_LABELS = ["readiness", "next_action", "safety", "dispatch", "cycle"]
ACTIONABLE_FINAL_ACTIONS = {
    "observe_pipeline_result",
    "review_watch_reasons",
    "repair_profile_readiness",
}


class CognitiveTraceEvaluationRecord(BaseModel):
    """One persisted trace evaluation."""

    evaluation_id: str = Field(default_factory=lambda: f"trace_eval_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    trace_id: str
    coherence_score: float = Field(ge=0.0, le=1.0)
    safety_score: float = Field(ge=0.0, le=1.0)
    completeness_score: float = Field(ge=0.0, le=1.0)
    actionability_score: float = Field(ge=0.0, le=1.0)
    overall_score: float = Field(ge=0.0, le=1.0)
    verdict: str
    reasons: list[str]


class CognitiveTraceEvaluationSummary(BaseModel):
    """Summary of persisted trace evaluations."""

    inspect_type: str = "cognitive_trace_evaluation"
    path: str
    exists: bool
    total_evaluation_count: int = Field(ge=0)
    latest_evaluation_id: str | None
    latest_trace_id: str | None
    latest_verdict: str | None
    latest_overall_score: float | None


class CognitiveTraceEvaluationJsonlStore:
    """Persist trace evaluations as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CognitiveTraceEvaluationRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        CognitiveTraceEvaluationRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid cognitive trace evaluation at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[CognitiveTraceEvaluationRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: CognitiveTraceEvaluationRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def evaluate_latest_cognitive_trace(profile: Path) -> dict[str, object]:
    """Evaluate and persist the latest cognitive trace for a profile."""

    trace_path = profile / TRACE_FILENAME
    traces = CognitiveTraceJsonlStore(trace_path).load()
    if not traces:
        record = _empty_evaluation(profile)
    else:
        record = _evaluate_trace(profile, traces[-1])
    evaluation_path = profile / EVALUATION_FILENAME
    count = CognitiveTraceEvaluationJsonlStore(evaluation_path).append(record)
    return {
        "evaluation_type": "cognitive_trace_evaluation",
        "profile_path": str(profile),
        "evaluation_path": str(evaluation_path),
        "evaluation_count": count,
        "evaluation_record": record.model_dump(mode="json"),
    }


def summarize_cognitive_trace_evaluations(path: Path) -> dict[str, object]:
    records = CognitiveTraceEvaluationJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = CognitiveTraceEvaluationSummary(
        path=str(path),
        exists=path.exists(),
        total_evaluation_count=len(records),
        latest_evaluation_id=latest.evaluation_id if latest else None,
        latest_trace_id=latest.trace_id if latest else None,
        latest_verdict=latest.verdict if latest else None,
        latest_overall_score=latest.overall_score if latest else None,
    )
    return summary.model_dump(mode="json")


def _empty_evaluation(profile: Path) -> CognitiveTraceEvaluationRecord:
    return CognitiveTraceEvaluationRecord(
        profile_path=str(profile),
        trace_id="none",
        coherence_score=0.0,
        safety_score=0.0,
        completeness_score=0.0,
        actionability_score=0.0,
        overall_score=0.0,
        verdict="trace_missing",
        reasons=["no_cognitive_trace_available"],
    )


def _evaluate_trace(profile: Path, trace) -> CognitiveTraceEvaluationRecord:
    labels = [step.label for step in trace.steps]
    reasons = []
    coherence_score = _coherence_score(labels, reasons)
    safety_score = _safety_score(trace, reasons)
    completeness_score = _completeness_score(labels, reasons)
    actionability_score = _actionability_score(trace, reasons)
    overall_score = round(
        (coherence_score + safety_score + completeness_score + actionability_score) / 4,
        4,
    )
    verdict = _verdict(overall_score, reasons)
    return CognitiveTraceEvaluationRecord(
        profile_path=str(profile),
        trace_id=trace.trace_id,
        coherence_score=coherence_score,
        safety_score=safety_score,
        completeness_score=completeness_score,
        actionability_score=actionability_score,
        overall_score=overall_score,
        verdict=verdict,
        reasons=reasons or ["trace_quality_ok"],
    )


def _coherence_score(labels: list[str], reasons: list[str]) -> float:
    if labels == EXPECTED_STEP_LABELS:
        return 1.0
    reasons.append("unexpected_step_sequence")
    return 0.5


def _safety_score(trace, reasons: list[str]) -> float:
    safety_steps = [step for step in trace.steps if step.label == "safety"]
    if not safety_steps:
        reasons.append("safety_step_missing")
        return 0.0
    if safety_steps[0].decision in {"allow", "block"}:
        return 1.0
    reasons.append("unknown_safety_decision")
    return 0.5


def _completeness_score(labels: list[str], reasons: list[str]) -> float:
    missing = [label for label in EXPECTED_STEP_LABELS if label not in labels]
    if not missing:
        return 1.0
    reasons.append("missing_steps:" + ",".join(missing))
    return round((len(EXPECTED_STEP_LABELS) - len(missing)) / len(EXPECTED_STEP_LABELS), 4)


def _actionability_score(trace, reasons: list[str]) -> float:
    if trace.final_action in ACTIONABLE_FINAL_ACTIONS:
        return 1.0
    reasons.append("final_action_not_actionable")
    return 0.4


def _verdict(overall_score: float, reasons: list[str]) -> str:
    if overall_score >= 0.9 and not any(reason.endswith("missing") for reason in reasons):
        return "trace_valid"
    if overall_score >= 0.6:
        return "trace_watch"
    return "trace_blocked"
