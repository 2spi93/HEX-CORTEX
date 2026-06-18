from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_guidance_receipt import (
    CORTEX_GUIDANCE_RECEIPT_FILENAME,
    CortexGuidanceReceiptJsonlStore,
    CortexGuidanceReceiptRecord,
)

CORTEX_GUIDANCE_OUTCOME_FILENAME = "cortex-guidance-outcome.jsonl"


class CortexGuidanceOutcomeRecord(BaseModel):
    outcome_id: str = Field(default_factory=lambda: f"cortex_guidance_outcome_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_receipt_id: str | None
    source_receipt_hash: str | None
    selected_skill_key: str | None
    outcome_status: str
    outcome_decision: str
    outcome_allowed: bool
    usefulness_score: float = Field(ge=0.0, le=1.0)
    next_action: str
    blockers: list[str]
    outcome_hash: str
    reasons: list[str]


class CortexGuidanceOutcomeJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexGuidanceOutcomeRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexGuidanceOutcomeRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex guidance outcome {line_number}") from exc
        return records

    def save(self, records: list[CortexGuidanceOutcomeRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_guidance_outcome(profile: Path, usefulness_score: float = 1.0) -> dict[str, object]:
    receipt = _latest_receipt(profile)
    record = _outcome_record(profile, receipt, usefulness_score)
    path = profile / CORTEX_GUIDANCE_OUTCOME_FILENAME
    store = CortexGuidanceOutcomeJsonlStore(path)
    current = store.load()
    if record.source_receipt_hash and any(item.source_receipt_hash == record.source_receipt_hash for item in current):
        records: list[CortexGuidanceOutcomeRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "outcome_type": "cortex_guidance_outcome",
        "profile_path": str(profile),
        "outcome_path": str(path),
        "outcome_count": count,
        "outcome_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_guidance_outcomes(path: Path) -> dict[str, object]:
    records = CortexGuidanceOutcomeJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.outcome_allowed]
    return {
        "inspect_type": "cortex_guidance_outcome",
        "path": str(path),
        "exists": path.exists(),
        "total_outcome_count": len(records),
        "allowed_outcome_count": len(allowed),
        "latest_outcome_id": latest.outcome_id if latest else None,
        "latest_outcome_status": latest.outcome_status if latest else None,
        "latest_outcome_decision": latest.outcome_decision if latest else None,
        "latest_outcome_allowed": latest.outcome_allowed if latest else None,
        "latest_selected_skill_key": latest.selected_skill_key if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_outcome_hash": latest.outcome_hash if latest else None,
    }


def _latest_receipt(profile: Path) -> CortexGuidanceReceiptRecord | None:
    records = CortexGuidanceReceiptJsonlStore(profile / CORTEX_GUIDANCE_RECEIPT_FILENAME).load()
    return records[-1] if records else None


def _outcome_record(profile: Path, receipt: CortexGuidanceReceiptRecord | None, usefulness_score: float) -> CortexGuidanceOutcomeRecord:
    blockers = []
    if receipt is None:
        blockers.append("missing_guidance_receipt")
    elif receipt.receipt_allowed is not True:
        blockers.append("guidance_receipt_not_allowed")
    elif receipt.next_action != "record_guidance_outcome":
        blockers.append("receipt_not_waiting_outcome")
    if usefulness_score < 0.75:
        blockers.append("guidance_usefulness_below_threshold")
    allowed = not blockers
    status = "accepted" if allowed else "blocked"
    decision = "guidance_outcome_accepted" if allowed else "guidance_outcome_blocked"
    next_action = "write_memory_first_closeout_report" if allowed else "repair_guidance_outcome"
    reasons = ["guidance_receipt_ready", "guidance_outcome_useful"] if allowed else blockers
    outcome_hash = _hash(str(profile), receipt.receipt_hash if receipt else "missing_receipt", str(usefulness_score), decision, next_action, *reasons)
    return CortexGuidanceOutcomeRecord(
        profile_path=str(profile),
        source_receipt_id=receipt.receipt_id if receipt else None,
        source_receipt_hash=receipt.receipt_hash if receipt else None,
        selected_skill_key=receipt.selected_skill_key if receipt else None,
        outcome_status=status,
        outcome_decision=decision,
        outcome_allowed=allowed,
        usefulness_score=usefulness_score,
        next_action=next_action,
        blockers=blockers,
        outcome_hash=outcome_hash,
        reasons=reasons,
    )


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
