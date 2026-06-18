from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_guidance_outcome import (
    CORTEX_GUIDANCE_OUTCOME_FILENAME,
    CortexGuidanceOutcomeJsonlStore,
)
from hex_cortex.memory.cortex_memory_first_readiness_seal import (
    CORTEX_MEMORY_FIRST_READINESS_SEAL_FILENAME,
    CortexMemoryFirstReadinessSealJsonlStore,
)

CORTEX_LOOP_CLOSE_REPORT_FILENAME = "cortex-loop-close-report.jsonl"


class CortexLoopCloseReportRecord(BaseModel):
    report_id: str = Field(default_factory=lambda: f"cortex_loop_close_report_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_seal_hash: str | None
    source_outcome_hash: str | None
    active_skill_count: int = Field(ge=0)
    selected_skill_key: str | None
    report_status: str
    report_decision: str
    report_allowed: bool
    closeout_summary: str
    next_action: str
    blockers: list[str]
    report_hash: str
    reasons: list[str]


class CortexLoopCloseReportJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexLoopCloseReportRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexLoopCloseReportRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex loop close report {line_number}") from exc
        return records

    def save(self, records: list[CortexLoopCloseReportRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_loop_close_report(profile: Path) -> dict[str, object]:
    seal = _latest(CortexMemoryFirstReadinessSealJsonlStore(profile / CORTEX_MEMORY_FIRST_READINESS_SEAL_FILENAME).load())
    outcome = _latest(CortexGuidanceOutcomeJsonlStore(profile / CORTEX_GUIDANCE_OUTCOME_FILENAME).load())
    record = _report_record(profile, seal, outcome)
    path = profile / CORTEX_LOOP_CLOSE_REPORT_FILENAME
    store = CortexLoopCloseReportJsonlStore(path)
    current = store.load()
    count = store.save([*current, record])
    return {
        "report_type": "cortex_loop_close_report",
        "profile_path": str(profile),
        "report_path": str(path),
        "report_count": count,
        "report_records": [record.model_dump(mode="json")],
    }


def summarize_cortex_loop_close_reports(path: Path) -> dict[str, object]:
    records = CortexLoopCloseReportJsonlStore(path).load()
    latest = records[-1] if records else None
    closed = [record for record in records if record.report_allowed]
    return {
        "inspect_type": "cortex_loop_close_report",
        "path": str(path),
        "exists": path.exists(),
        "total_report_count": len(records),
        "closed_report_count": len(closed),
        "latest_report_id": latest.report_id if latest else None,
        "latest_report_status": latest.report_status if latest else None,
        "latest_report_decision": latest.report_decision if latest else None,
        "latest_report_allowed": latest.report_allowed if latest else None,
        "latest_selected_skill_key": latest.selected_skill_key if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_report_hash": latest.report_hash if latest else None,
    }


def _latest(records):
    return records[-1] if records else None


def _report_record(profile: Path, seal, outcome) -> CortexLoopCloseReportRecord:
    blockers = []
    if seal is None:
        blockers.append("missing_seal")
    elif seal.seal_allowed is not True:
        blockers.append("seal_not_allowed")
    if outcome is None:
        blockers.append("missing_guidance_outcome")
    elif outcome.outcome_allowed is not True:
        blockers.append("guidance_outcome_not_allowed")
    allowed = not blockers
    status = "complete" if allowed else "blocked"
    decision = "loop_close_complete" if allowed else "loop_close_blocked"
    next_action = "operate_with_controlled_skill_feedback_loop" if allowed else "repair_loop_close"
    reasons = ["seal_ready", "guidance_outcome_ready", "loop_closed"] if allowed else blockers
    selected_skill_key = outcome.selected_skill_key if outcome else (seal.latest_skill_key if seal else None)
    summary = "HEX-CORTEX first controlled skill loop is closed." if allowed else "HEX-CORTEX close report is blocked."
    report_hash = _hash(str(profile), seal.seal_hash if seal else "missing_seal", outcome.outcome_hash if outcome else "missing_outcome", decision, next_action, *reasons)
    return CortexLoopCloseReportRecord(
        profile_path=str(profile),
        source_seal_hash=seal.seal_hash if seal else None,
        source_outcome_hash=outcome.outcome_hash if outcome else None,
        active_skill_count=seal.active_skill_count if seal else 0,
        selected_skill_key=selected_skill_key,
        report_status=status,
        report_decision=decision,
        report_allowed=allowed,
        closeout_summary=summary,
        next_action=next_action,
        blockers=blockers,
        report_hash=report_hash,
        reasons=reasons,
    )


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
