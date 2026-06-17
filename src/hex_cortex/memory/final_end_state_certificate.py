"""Final end-state certificates derived from resync gates and panel snapshots."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.profile_panel_snapshot import (
    PROFILE_PANEL_SNAPSHOT_FILENAME,
    ProfilePanelSnapshotJsonlStore,
)
from hex_cortex.memory.profile_resync_gate import (
    PROFILE_RESYNC_GATE_FILENAME,
    ProfileResyncGateJsonlStore,
)

FINAL_END_STATE_CERTIFICATE_FILENAME = "final-end-state-certificate.jsonl"
READY_AFTER_OPERATOR_ACCEPTANCE = "READY_AFTER_OPERATOR_ACCEPTANCE"
FINAL_END_STATE_NOT_READY = "FINAL_END_STATE_NOT_READY"
PREPARE_FREEZE_STAMP = "prepare_freeze_stamp"


class FinalEndStateCertificateRecord(BaseModel):
    """One persisted final end-state certificate record."""

    certificate_id: str = Field(
        default_factory=lambda: f"final_end_state_certificate_{uuid4().hex}"
    )
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str | None
    source_gate_id: str | None
    source_gate_hash: str | None
    source_panel_id: str | None
    source_resync_decision: str | None
    source_gate_decision: str | None
    source_panel_display_state: str | None
    manual_choice: str | None
    safe_to_continue: bool
    registry_change_applied: bool
    next_action: str
    end_state: str
    certificate_status: str
    certificate_decision: str
    certificate_allowed: bool
    blocker_count: int = Field(ge=0)
    active_blockers: list[str]
    reasons: list[str]
    certificate_hash: str


class FinalEndStateCertificateSummary(BaseModel):
    """Summary of persisted final end-state certificates."""

    inspect_type: str = "final_end_state_certificate"
    path: str
    exists: bool
    total_certificate_count: int = Field(ge=0)
    latest_certificate_id: str | None
    latest_end_state: str | None
    latest_certificate_status: str | None
    latest_certificate_decision: str | None
    latest_certificate_allowed: bool | None
    latest_safe_to_continue: bool | None
    latest_registry_change_applied: bool | None
    latest_next_action: str | None
    latest_selected_skill: str | None
    latest_certificate_hash: str | None


class FinalEndStateCertificateJsonlStore:
    """Persist final end-state certificates as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[FinalEndStateCertificateRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        FinalEndStateCertificateRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid final end-state certificate at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[FinalEndStateCertificateRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: FinalEndStateCertificateRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_final_end_state_certificate(profile: Path) -> dict[str, object]:
    """Build one final end-state certificate from the latest gate and panel snapshot."""

    gates = ProfileResyncGateJsonlStore(profile / PROFILE_RESYNC_GATE_FILENAME).load()
    panels = ProfilePanelSnapshotJsonlStore(
        profile / PROFILE_PANEL_SNAPSHOT_FILENAME
    ).load()
    record = _certificate_from_sources(
        profile,
        gates[-1] if gates else None,
        panels[-1] if panels else None,
    )
    path = profile / FINAL_END_STATE_CERTIFICATE_FILENAME
    count = FinalEndStateCertificateJsonlStore(path).append(record)
    return {
        "certificate_type": "final_end_state_certificate",
        "profile_path": str(profile),
        "certificate_path": str(path),
        "certificate_count": count,
        "certificate_record": record.model_dump(mode="json"),
    }


def summarize_final_end_state_certificates(path: Path) -> dict[str, object]:
    records = FinalEndStateCertificateJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = FinalEndStateCertificateSummary(
        path=str(path),
        exists=path.exists(),
        total_certificate_count=len(records),
        latest_certificate_id=latest.certificate_id if latest else None,
        latest_end_state=latest.end_state if latest else None,
        latest_certificate_status=latest.certificate_status if latest else None,
        latest_certificate_decision=latest.certificate_decision if latest else None,
        latest_certificate_allowed=latest.certificate_allowed if latest else None,
        latest_safe_to_continue=latest.safe_to_continue if latest else None,
        latest_registry_change_applied=(
            latest.registry_change_applied if latest else None
        ),
        latest_next_action=latest.next_action if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_certificate_hash=latest.certificate_hash if latest else None,
    )
    return summary.model_dump(mode="json")


def _certificate_from_sources(profile: Path, gate, panel) -> FinalEndStateCertificateRecord:
    blockers = _certificate_blockers(gate, panel, registry_change_applied=False)
    allowed = len(blockers) == 0
    selected_skill = _first_string(
        panel.selected_skill if panel else None,
        gate.selected_skill if gate else None,
        "final_end_state_sources_missing",
    )
    safe_to_continue = bool(panel.safe_to_continue) if panel else False
    next_action = PREPARE_FREEZE_STAMP if allowed else _blocked_next_action(gate, panel)
    end_state = READY_AFTER_OPERATOR_ACCEPTANCE if allowed else FINAL_END_STATE_NOT_READY
    status = "certified" if allowed else "blocked"
    decision = (
        "final_end_state_certified" if allowed else "final_end_state_blocked"
    )
    reasons = (
        [
            "operator_acceptance_propagated",
            "profile_resync_ready",
            "resync_gate_ready",
            "panel_safe_to_continue",
            "no_violations",
            "registry_unchanged",
        ]
        if allowed
        else blockers
    )
    hash_payload = {
        "profile_path": str(profile),
        "selected_skill": selected_skill,
        "source_gate_id": gate.gate_id if gate else None,
        "source_gate_hash": gate.gate_hash if gate else None,
        "source_panel_id": panel.panel_id if panel else None,
        "source_resync_decision": panel.resync_decision if panel else None,
        "source_gate_decision": gate.gate_decision if gate else None,
        "source_panel_display_state": panel.display_state if panel else None,
        "manual_choice": panel.manual_choice if panel else None,
        "safe_to_continue": safe_to_continue,
        "registry_change_applied": False,
        "next_action": next_action,
        "end_state": end_state,
        "certificate_status": status,
        "certificate_decision": decision,
        "certificate_allowed": allowed,
        "active_blockers": blockers,
        "reasons": reasons,
    }
    return FinalEndStateCertificateRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        source_gate_id=gate.gate_id if gate else None,
        source_gate_hash=gate.gate_hash if gate else None,
        source_panel_id=panel.panel_id if panel else None,
        source_resync_decision=panel.resync_decision if panel else None,
        source_gate_decision=gate.gate_decision if gate else None,
        source_panel_display_state=panel.display_state if panel else None,
        manual_choice=panel.manual_choice if panel else None,
        safe_to_continue=safe_to_continue,
        registry_change_applied=False,
        next_action=next_action,
        end_state=end_state,
        certificate_status=status,
        certificate_decision=decision,
        certificate_allowed=allowed,
        blocker_count=len(blockers),
        active_blockers=blockers,
        reasons=reasons,
        certificate_hash=_stable_hash(hash_payload),
    )


def _certificate_blockers(gate, panel, registry_change_applied: bool) -> list[str]:
    blockers: list[str] = []
    if gate is None:
        blockers.append("gate_missing")
    else:
        if gate.gate_allowed is not True:
            blockers.append("gate_not_allowed")
        if gate.gate_decision != "gate_ready":
            blockers.append("gate_decision_not_ready")
        if gate.gate_status != "ready":
            blockers.append("gate_status_not_ready")
    if panel is None:
        blockers.append("panel_missing")
    else:
        if panel.display_state != "ready":
            blockers.append("panel_display_state_not_ready")
        if panel.safe_to_continue is not True:
            blockers.append("panel_not_safe_to_continue")
        if panel.violation_count != 0:
            blockers.append("panel_violations_present")
        if panel.manual_choice != "accept":
            blockers.append("manual_choice_not_accept")
        if panel.gate_decision != "gate_ready":
            blockers.append("panel_gate_decision_not_ready")
        if panel.resync_decision != "resync_ready":
            blockers.append("panel_resync_decision_not_ready")
        if panel.next_action != PREPARE_FREEZE_STAMP:
            blockers.append("next_action_not_prepare_freeze_stamp")
    if registry_change_applied is not False:
        blockers.append("registry_change_applied")
    return blockers


def _blocked_next_action(gate, panel) -> str:
    if gate is None:
        return "rerun_profile_resync_gate"
    if panel is None:
        return "rerun_profile_view"
    return "repair_final_end_state_inputs"


def _first_string(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str):
            return value
    return None


def _stable_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
