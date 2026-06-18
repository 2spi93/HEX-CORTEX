from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_controlled_skill_guidance_renderer import (
    CORTEX_CONTROLLED_SKILL_GUIDANCE_RENDERER_FILENAME,
    CortexControlledSkillGuidanceRendererJsonlStore,
    CortexControlledSkillGuidanceRendererRecord,
)

CORTEX_GUIDANCE_RECEIPT_FILENAME = "cortex-guidance-receipt.jsonl"


class CortexGuidanceReceiptRecord(BaseModel):
    receipt_id: str = Field(default_factory=lambda: f"cortex_guidance_receipt_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_guidance_id: str | None
    source_guidance_hash: str | None
    selected_skill_key: str | None
    guidance_rendered: bool
    receipt_status: str
    receipt_decision: str
    receipt_allowed: bool
    next_action: str
    blockers: list[str]
    receipt_hash: str
    reasons: list[str]


class CortexGuidanceReceiptJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexGuidanceReceiptRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexGuidanceReceiptRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex guidance receipt {line_number}") from exc
        return records

    def save(self, records: list[CortexGuidanceReceiptRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_guidance_receipt(profile: Path) -> dict[str, object]:
    guidance = _latest_guidance(profile)
    record = _receipt_record(profile, guidance)
    path = profile / CORTEX_GUIDANCE_RECEIPT_FILENAME
    store = CortexGuidanceReceiptJsonlStore(path)
    current = store.load()
    if record.source_guidance_hash and any(item.source_guidance_hash == record.source_guidance_hash for item in current):
        records: list[CortexGuidanceReceiptRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "receipt_type": "cortex_guidance_receipt",
        "profile_path": str(profile),
        "receipt_path": str(path),
        "receipt_count": count,
        "receipt_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_guidance_receipts(path: Path) -> dict[str, object]:
    records = CortexGuidanceReceiptJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.receipt_allowed]
    return {
        "inspect_type": "cortex_guidance_receipt",
        "path": str(path),
        "exists": path.exists(),
        "total_receipt_count": len(records),
        "allowed_receipt_count": len(allowed),
        "latest_receipt_id": latest.receipt_id if latest else None,
        "latest_receipt_status": latest.receipt_status if latest else None,
        "latest_receipt_decision": latest.receipt_decision if latest else None,
        "latest_receipt_allowed": latest.receipt_allowed if latest else None,
        "latest_selected_skill_key": latest.selected_skill_key if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_receipt_hash": latest.receipt_hash if latest else None,
    }


def _latest_guidance(profile: Path) -> CortexControlledSkillGuidanceRendererRecord | None:
    records = CortexControlledSkillGuidanceRendererJsonlStore(profile / CORTEX_CONTROLLED_SKILL_GUIDANCE_RENDERER_FILENAME).load()
    return records[-1] if records else None


def _receipt_record(profile: Path, guidance: CortexControlledSkillGuidanceRendererRecord | None) -> CortexGuidanceReceiptRecord:
    blockers = []
    if guidance is None:
        blockers.append("missing_guidance")
    elif guidance.guidance_allowed is not True:
        blockers.append("guidance_not_allowed")
    elif guidance.next_action != "record_guidance_receipt":
        blockers.append("guidance_not_waiting_receipt")
    allowed = not blockers
    status = "recorded" if allowed else "blocked"
    decision = "guidance_receipt_recorded" if allowed else "guidance_receipt_blocked"
    next_action = "record_guidance_outcome" if allowed else "repair_guidance"
    reasons = ["guidance_rendered", "receipt_recorded"] if allowed else blockers
    receipt_hash = _hash(str(profile), guidance.guidance_hash if guidance else "missing_guidance", decision, next_action, *reasons)
    return CortexGuidanceReceiptRecord(
        profile_path=str(profile),
        source_guidance_id=guidance.guidance_id if guidance else None,
        source_guidance_hash=guidance.guidance_hash if guidance else None,
        selected_skill_key=guidance.selected_skill_key if guidance else None,
        guidance_rendered=allowed,
        receipt_status=status,
        receipt_decision=decision,
        receipt_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        receipt_hash=receipt_hash,
        reasons=reasons,
    )


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
