"""Final seal stamps derived from final end-state certificates."""

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

FINAL_SEAL_STAMP_FILENAME = "final-seal-stamp.jsonl"


class FinalSealStampRecord(BaseModel):
    """One persisted final seal stamp."""

    seal_id: str = Field(default_factory=lambda: f"final_seal_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str | None
    source_certificate_id: str | None
    source_certificate_hash: str | None
    source_end_state: str | None
    safe_to_continue: bool
    registry_change_applied: bool
    seal_status: str
    seal_decision: str
    seal_allowed: bool
    seal_hash: str
    next_action: str
    reasons: list[str]


class FinalSealStampSummary(BaseModel):
    """Summary of persisted final seal stamps."""

    inspect_type: str = "final_seal_stamp"
    path: str
    exists: bool
    total_seal_count: int = Field(ge=0)
    latest_seal_id: str | None
    latest_selected_skill: str | None
    latest_source_certificate_id: str | None
    latest_source_end_state: str | None
    latest_seal_status: str | None
    latest_seal_decision: str | None
    latest_seal_allowed: bool | None
    latest_next_action: str | None
    latest_seal_hash: str | None


class FinalSealStampJsonlStore:
    """Persist final seal stamps as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[FinalSealStampRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(FinalSealStampRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid final seal stamp at line {line_number}") from exc
        return records

    def save(self, records: list[FinalSealStampRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: FinalSealStampRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_final_seal_stamp(profile: Path) -> dict[str, object]:
    """Build one final seal stamp from the latest final end-state certificate."""

    certificates = FinalEndStateCertificateJsonlStore(
        profile / FINAL_END_STATE_CERTIFICATE_FILENAME
    ).load()
    record = _seal_from_certificate(profile, certificates[-1] if certificates else None)
    path = profile / FINAL_SEAL_STAMP_FILENAME
    count = FinalSealStampJsonlStore(path).append(record)
    return {
        "seal_type": "final_seal_stamp",
        "profile_path": str(profile),
        "seal_path": str(path),
        "seal_count": count,
        "seal_record": record.model_dump(mode="json"),
    }


def summarize_final_seal_stamps(path: Path) -> dict[str, object]:
    records = FinalSealStampJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = FinalSealStampSummary(
        path=str(path),
        exists=path.exists(),
        total_seal_count=len(records),
        latest_seal_id=latest.seal_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_source_certificate_id=latest.source_certificate_id if latest else None,
        latest_source_end_state=latest.source_end_state if latest else None,
        latest_seal_status=latest.seal_status if latest else None,
        latest_seal_decision=latest.seal_decision if latest else None,
        latest_seal_allowed=latest.seal_allowed if latest else None,
        latest_next_action=latest.next_action if latest else None,
        latest_seal_hash=latest.seal_hash if latest else None,
    )
    return summary.model_dump(mode="json")


def _seal_from_certificate(profile: Path, certificate) -> FinalSealStampRecord:
    blockers = _seal_blockers(certificate)
    allowed = len(blockers) == 0
    decision = "final_seal_ready" if allowed else "final_seal_blocked"
    next_action = "build_operator_handoff_runbook" if allowed else "build_final_end_state_certificate"
    reasons = ["final_end_state_certified", "final_seal_prepared"] if allowed else blockers
    source_hash = certificate.certificate_hash if certificate else None
    seal_hash = _seal_hash(
        str(profile),
        source_hash or "certificate_missing",
        decision,
        next_action,
        *reasons,
    )
    return FinalSealStampRecord(
        profile_path=str(profile),
        selected_skill=certificate.selected_skill if certificate else "certificate_missing",
        source_certificate_id=certificate.certificate_id if certificate else None,
        source_certificate_hash=source_hash,
        source_end_state=certificate.end_state if certificate else None,
        safe_to_continue=bool(certificate.safe_to_continue) if certificate else False,
        registry_change_applied=(
            bool(certificate.registry_change_applied) if certificate else False
        ),
        seal_status="ready" if allowed else "blocked",
        seal_decision=decision,
        seal_allowed=allowed,
        seal_hash=seal_hash,
        next_action=next_action,
        reasons=reasons,
    )


def _seal_blockers(certificate) -> list[str]:
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
        blockers.append("registry_changed_before_seal")
    if certificate.next_action != "prepare_freeze_stamp":
        blockers.append("certificate_next_action_not_prepare_freeze_stamp")
    return blockers


def _seal_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
