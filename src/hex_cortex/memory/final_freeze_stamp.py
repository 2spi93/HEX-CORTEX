from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.final_end_state_certificate import (
    FINAL_END_STATE_CERTIFICATE_FILENAME,
    READY_AFTER_OPERATOR_ACCEPTANCE,
    FinalEndStateCertificateJsonlStore,
)

FINAL_FREEZE_STAMP_FILENAME = "final-freeze-stamp.jsonl"


class FinalFreezeStampRecord(BaseModel):
    stamp_id: str = Field(default_factory=lambda: f"final_stamp_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str | None
    source_certificate_id: str | None
    source_certificate_hash: str | None
    source_end_state: str | None
    safe_to_continue: bool
    registry_change_applied: bool
    stamp_status: str
    stamp_decision: str
    stamp_allowed: bool
    stamp_hash: str
    next_action: str
    reasons: list[str]


class FinalFreezeStampJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[FinalFreezeStampRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(FinalFreezeStampRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    message = f"invalid final freeze stamp at line {line_number}"
                    raise ValueError(message) from exc
        return records

    def save(self, records: list[FinalFreezeStampRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: FinalFreezeStampRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_final_freeze_stamp(profile: Path) -> dict[str, object]:
    certificates = FinalEndStateCertificateJsonlStore(
        profile / FINAL_END_STATE_CERTIFICATE_FILENAME
    ).load()
    certificate = certificates[-1] if certificates else None
    record = _stamp_from_certificate(profile, certificate)
    path = profile / FINAL_FREEZE_STAMP_FILENAME
    count = FinalFreezeStampJsonlStore(path).append(record)
    return {
        "stamp_type": "final_freeze_stamp",
        "profile_path": str(profile),
        "stamp_path": str(path),
        "stamp_count": count,
        "stamp_record": record.model_dump(mode="json"),
    }


def summarize_final_freeze_stamps(path: Path) -> dict[str, object]:
    records = FinalFreezeStampJsonlStore(path).load()
    latest = records[-1] if records else None
    return {
        "inspect_type": "final_freeze_stamp",
        "path": str(path),
        "exists": path.exists(),
        "total_stamp_count": len(records),
        "latest_stamp_id": latest.stamp_id if latest else None,
        "latest_selected_skill": latest.selected_skill if latest else None,
        "latest_source_certificate_id": latest.source_certificate_id if latest else None,
        "latest_source_end_state": latest.source_end_state if latest else None,
        "latest_stamp_status": latest.stamp_status if latest else None,
        "latest_stamp_decision": latest.stamp_decision if latest else None,
        "latest_stamp_allowed": latest.stamp_allowed if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_stamp_hash": latest.stamp_hash if latest else None,
    }


def _stamp_from_certificate(profile: Path, certificate) -> FinalFreezeStampRecord:
    blockers = _stamp_blockers(certificate)
    allowed = len(blockers) == 0
    decision = "final_stamp_ready" if allowed else "final_stamp_blocked"
    next_action = "build_operator_handoff_runbook" if allowed else "build_final_end_state_certificate"
    reasons = ["final_end_state_certified", "stamp_prepared"] if allowed else blockers
    source_hash = certificate.certificate_hash if certificate else None
    return FinalFreezeStampRecord(
        profile_path=str(profile),
        selected_skill=certificate.selected_skill if certificate else "certificate_missing",
        source_certificate_id=certificate.certificate_id if certificate else None,
        source_certificate_hash=source_hash,
        source_end_state=certificate.end_state if certificate else None,
        safe_to_continue=bool(certificate.safe_to_continue) if certificate else False,
        registry_change_applied=bool(certificate.registry_change_applied) if certificate else False,
        stamp_status="ready" if allowed else "blocked",
        stamp_decision=decision,
        stamp_allowed=allowed,
        stamp_hash=_stamp_hash(str(profile), source_hash or "missing", decision, next_action),
        next_action=next_action,
        reasons=reasons,
    )


def _stamp_blockers(certificate) -> list[str]:
    if certificate is None:
        return ["final_end_state_certificate_missing"]
    blockers: list[str] = []
    if certificate.certificate_allowed is not True:
        blockers.append("certificate_not_allowed")
    if certificate.certificate_status != "certified":
        blockers.append("certificate_not_certified")
    if certificate.certificate_decision != "final_end_state_certified":
        blockers.append("certificate_decision_not_final")
    if certificate.end_state != READY_AFTER_OPERATOR_ACCEPTANCE:
        blockers.append("end_state_not_ready_after_operator_acceptance")
    if certificate.safe_to_continue is not True:
        blockers.append("certificate_not_safe_to_continue")
    if certificate.registry_change_applied is not False:
        blockers.append("registry_changed_before_stamp")
    if certificate.next_action != "prepare_freeze_stamp":
        blockers.append("certificate_next_action_not_prepare_freeze_stamp")
    return blockers


def _stamp_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
