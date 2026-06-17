"""Public cognitive traces for multi-step operator reasoning."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

TRACE_FILENAME = "cognitive-trace.jsonl"


class CognitiveTraceStep(BaseModel):
    """One public, compact reasoning step."""

    index: int = Field(ge=0)
    label: str
    observation: str
    decision: str
    confidence: float = Field(ge=0.0, le=1.0)


class CognitiveTraceRecord(BaseModel):
    """Persisted multi-step cognitive trace."""

    trace_id: str = Field(default_factory=lambda: f"trace_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_type: str
    status: str
    decision: str
    final_action: str
    final_reason: str
    steps: list[CognitiveTraceStep]


class CognitiveTraceSummary(BaseModel):
    """Summary of persisted cognitive traces."""

    inspect_type: str = "cognitive_trace"
    path: str
    exists: bool
    total_trace_count: int = Field(ge=0)
    latest_trace_id: str | None
    latest_status: str | None
    latest_decision: str | None
    latest_final_action: str | None
    latest_step_count: int = Field(ge=0)


class CognitiveTraceJsonlStore:
    """Persist cognitive traces as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CognitiveTraceRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CognitiveTraceRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid cognitive trace at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[CognitiveTraceRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: CognitiveTraceRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def record_cognitive_trace(profile: Path, trace: CognitiveTraceRecord) -> dict[str, object]:
    path = profile / TRACE_FILENAME
    count = CognitiveTraceJsonlStore(path).append(trace)
    return {
        "record_type": "cognitive_trace",
        "profile_path": str(profile),
        "trace_path": str(path),
        "trace_count": count,
        "trace_record": trace.model_dump(mode="json"),
    }


def summarize_cognitive_traces(path: Path) -> dict[str, object]:
    records = CognitiveTraceJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = CognitiveTraceSummary(
        path=str(path),
        exists=path.exists(),
        total_trace_count=len(records),
        latest_trace_id=latest.trace_id if latest else None,
        latest_status=latest.status if latest else None,
        latest_decision=latest.decision if latest else None,
        latest_final_action=latest.final_action if latest else None,
        latest_step_count=len(latest.steps) if latest else 0,
    )
    return summary.model_dump(mode="json")
