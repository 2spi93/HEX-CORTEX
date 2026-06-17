from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.final_end_state_certificate import FINAL_END_STATE_CERTIFICATE_FILENAME
from hex_cortex.memory.final_end_state_certificate import summarize_final_end_state_certificates
from hex_cortex.memory.final_freeze_stamp import FINAL_FREEZE_STAMP_FILENAME
from hex_cortex.memory.final_freeze_stamp import summarize_final_freeze_stamps
from hex_cortex.memory.final_seal_stamp import FINAL_SEAL_STAMP_FILENAME
from hex_cortex.memory.final_seal_stamp import summarize_final_seal_stamps
from hex_cortex.memory.operator_handoff_runbook import OPERATOR_HANDOFF_RUNBOOK_FILENAME
from hex_cortex.memory.operator_handoff_runbook import summarize_operator_handoff_runbooks
from hex_cortex.memory.operator_runtime_ready import OPERATOR_RUNTIME_READY_FILENAME
from hex_cortex.memory.operator_runtime_ready import summarize_operator_runtime_ready

OPERATOR_COCKPIT_SNAPSHOT_FILENAME = "operator-cockpit-snapshot.jsonl"


class OperatorCockpitSnapshotRecord(BaseModel):
    cockpit_id: str = Field(default_factory=lambda: f"operator_cockpit_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str | None
    cockpit_status: str
    cockpit_decision: str
    cockpit_allowed: bool
    cockpit_mode: str
    next_action: str
    blocker_count: int = Field(ge=0)
    active_blockers: list[str]
    source_hashes: list[str]
    cockpit_hash: str
    reasons: list[str]


class OperatorCockpitSnapshotJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[OperatorCockpitSnapshotRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(OperatorCockpitSnapshotRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid operator cockpit snapshot {line_number}") from exc
        return records

    def save(self, records: list[OperatorCockpitSnapshotRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: OperatorCockpitSnapshotRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_operator_cockpit_snapshot(profile: Path) -> dict[str, object]:
    record = _snapshot(profile)
    path = profile / OPERATOR_COCKPIT_SNAPSHOT_FILENAME
    count = OperatorCockpitSnapshotJsonlStore(path).append(record)
    return {
        "cockpit_type": "operator_cockpit_snapshot",
        "profile_path": str(profile),
        "cockpit_path": str(path),
        "cockpit_count": count,
        "cockpit_record": record.model_dump(mode="json"),
    }


def summarize_operator_cockpit_snapshots(path: Path) -> dict[str, object]:
    records = OperatorCockpitSnapshotJsonlStore(path).load()
    latest = records[-1] if records else None
    return {
        "inspect_type": "operator_cockpit_snapshot",
        "path": str(path),
        "exists": path.exists(),
        "total_cockpit_count": len(records),
        "latest_cockpit_id": latest.cockpit_id if latest else None,
        "latest_selected_skill": latest.selected_skill if latest else None,
        "latest_cockpit_status": latest.cockpit_status if latest else None,
        "latest_cockpit_decision": latest.cockpit_decision if latest else None,
        "latest_cockpit_allowed": latest.cockpit_allowed if latest else None,
        "latest_cockpit_mode": latest.cockpit_mode if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_blocker_count": latest.blocker_count if latest else None,
        "latest_cockpit_hash": latest.cockpit_hash if latest else None,
    }


def _snapshot(profile: Path) -> OperatorCockpitSnapshotRecord:
    cert = summarize_final_end_state_certificates(profile / FINAL_END_STATE_CERTIFICATE_FILENAME)
    freeze = summarize_final_freeze_stamps(profile / FINAL_FREEZE_STAMP_FILENAME)
    seal = summarize_final_seal_stamps(profile / FINAL_SEAL_STAMP_FILENAME)
    handoff = summarize_operator_handoff_runbooks(profile / OPERATOR_HANDOFF_RUNBOOK_FILENAME)
    runtime = summarize_operator_runtime_ready(profile / OPERATOR_RUNTIME_READY_FILENAME)
    blockers = _blockers(cert, freeze, seal, handoff, runtime)
    allowed = not blockers
    source_hashes = [
        str(cert.get("latest_certificate_hash")),
        str(freeze.get("latest_stamp_hash")),
        str(seal.get("latest_seal_hash")),
        str(handoff.get("latest_runbook_hash")),
        str(runtime.get("latest_runtime_hash")),
    ]
    decision = "operator_cockpit_ready" if allowed else "operator_cockpit_blocked"
    next_action = "await_operator_command" if allowed else _repair_action(blockers)
    reasons = ["all_operator_surfaces_ready"] if allowed else blockers
    cockpit_hash = _hash(str(profile), *source_hashes, decision, next_action, *reasons)
    return OperatorCockpitSnapshotRecord(
        profile_path=str(profile),
        selected_skill=_first(runtime, handoff, seal, freeze, cert),
        cockpit_status="ready" if allowed else "blocked",
        cockpit_decision=decision,
        cockpit_allowed=allowed,
        cockpit_mode="command" if allowed else "repair",
        next_action=next_action,
        blocker_count=len(blockers),
        active_blockers=blockers,
        source_hashes=source_hashes,
        cockpit_hash=cockpit_hash,
        reasons=reasons,
    )


def _blockers(cert, freeze, seal, handoff, runtime) -> list[str]:
    blockers = []
    if cert.get("latest_certificate_allowed") is not True:
        blockers.append("certificate_not_ready")
    if freeze.get("latest_stamp_allowed") is not True:
        blockers.append("freeze_stamp_not_ready")
    if seal.get("latest_seal_allowed") is not True:
        blockers.append("seal_not_ready")
    if handoff.get("latest_handoff_allowed") is not True:
        blockers.append("handoff_not_ready")
    if runtime.get("latest_runtime_allowed") is not True:
        blockers.append("runtime_not_ready")
    if runtime.get("latest_next_action") != "await_operator_command":
        blockers.append("runtime_not_awaiting_operator")
    return blockers


def _repair_action(blockers: list[str]) -> str:
    for blocker, action in [
        ("certificate_not_ready", "build_final_end_state_certificate"),
        ("freeze_stamp_not_ready", "prepare_freeze_stamp"),
        ("seal_not_ready", "build_final_seal_stamp"),
        ("handoff_not_ready", "build_operator_handoff_runbook"),
        ("runtime_not_ready", "operator_runtime_ready"),
    ]:
        if blocker in blockers:
            return action
    return "repair_operator_cockpit"


def _first(*summaries: dict[str, object]) -> str | None:
    for summary in summaries:
        value = summary.get("latest_selected_skill")
        if isinstance(value, str):
            return value
    return None


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
