"""Compact profile panel snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.construction_freeze_stamp import (
    CONSTRUCTION_FREEZE_STAMP_FILENAME,
    summarize_construction_freeze_stamps,
)
from hex_cortex.memory.construction_status_report import (
    CONSTRUCTION_STATUS_REPORT_FILENAME,
    summarize_construction_status_reports,
)
from hex_cortex.memory.invariant_scanner import scan_profile_invariants
from hex_cortex.memory.manual_review_note import (
    MANUAL_REVIEW_NOTE_FILENAME,
    summarize_manual_review_notes,
)
from hex_cortex.memory.profile_resync_gate import (
    PROFILE_RESYNC_GATE_FILENAME,
    summarize_profile_resync_gates,
)
from hex_cortex.memory.profile_resync_report import (
    PROFILE_RESYNC_REPORT_FILENAME,
    summarize_profile_resync_reports,
)
from hex_cortex.memory.review_export_pack import (
    REVIEW_EXPORT_PACK_FILENAME,
    summarize_review_export_packs,
)

PROFILE_PANEL_SNAPSHOT_FILENAME = "profile-panel-snapshot.jsonl"


class ProfilePanelSnapshotRecord(BaseModel):
    """One persisted compact profile panel snapshot."""

    panel_id: str = Field(default_factory=lambda: f"profile_panel_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str | None
    display_state: str
    safe_to_continue: bool
    next_action: str | None
    pack_decision: str | None
    construction_decision: str | None
    freeze_decision: str | None
    manual_choice: str | None
    resync_decision: str | None
    gate_decision: str | None
    invariant_decision: str | None
    violation_count: int


class ProfilePanelSnapshotJsonlStore:
    """Persist compact profile panel snapshots as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ProfilePanelSnapshotRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        ProfilePanelSnapshotRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid profile panel snapshot at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ProfilePanelSnapshotRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ProfilePanelSnapshotRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_profile_panel_snapshot(profile: Path) -> dict[str, object]:
    """Build one compact profile panel snapshot."""

    pack = summarize_review_export_packs(profile / REVIEW_EXPORT_PACK_FILENAME)
    status = summarize_construction_status_reports(
        profile / CONSTRUCTION_STATUS_REPORT_FILENAME
    )
    freeze = summarize_construction_freeze_stamps(
        profile / CONSTRUCTION_FREEZE_STAMP_FILENAME
    )
    manual = summarize_manual_review_notes(profile / MANUAL_REVIEW_NOTE_FILENAME)
    resync = summarize_profile_resync_reports(
        profile / PROFILE_RESYNC_REPORT_FILENAME
    )
    gate = summarize_profile_resync_gates(profile / PROFILE_RESYNC_GATE_FILENAME)
    invariants = scan_profile_invariants(profile)["scan_record"]
    record = _snapshot_from_summaries(
        profile,
        pack,
        status,
        freeze,
        manual,
        resync,
        gate,
        invariants,
    )
    path = profile / PROFILE_PANEL_SNAPSHOT_FILENAME
    count = ProfilePanelSnapshotJsonlStore(path).append(record)
    return {
        "panel_type": "profile_panel_snapshot",
        "profile_path": str(profile),
        "panel_path": str(path),
        "panel_count": count,
        "panel_record": record.model_dump(mode="json"),
    }


def _snapshot_from_summaries(
    profile: Path,
    pack: dict[str, object],
    status: dict[str, object],
    freeze: dict[str, object],
    manual: dict[str, object],
    resync: dict[str, object],
    gate: dict[str, object],
    invariants: dict[str, object],
) -> ProfilePanelSnapshotRecord:
    selected_skill = _first_string(
        pack.get("latest_selected_skill"),
        status.get("latest_selected_skill"),
        freeze.get("latest_selected_skill"),
        manual.get("latest_selected_skill"),
    )
    display_state = _display_state(status, freeze, resync, gate, invariants)
    next_action = _first_string(
        gate.get("latest_next_action"),
        resync.get("latest_next_action"),
        status.get("latest_next_action"),
        freeze.get("latest_next_action"),
        pack.get("latest_next_action"),
    )
    violation_count = int(invariants.get("violation_count", 0))
    return ProfilePanelSnapshotRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        display_state=display_state,
        safe_to_continue=display_state in {"ready", "watch"} and violation_count == 0,
        next_action=next_action,
        pack_decision=_as_string(pack.get("latest_pack_decision")),
        construction_decision=_as_string(status.get("latest_construction_decision")),
        freeze_decision=_as_string(freeze.get("latest_freeze_decision")),
        manual_choice=_as_string(manual.get("latest_operator_choice")),
        resync_decision=_as_string(resync.get("latest_resync_decision")),
        gate_decision=_as_string(gate.get("latest_gate_decision")),
        invariant_decision=_as_string(invariants.get("invariant_decision")),
        violation_count=violation_count,
    )


def _display_state(status, freeze, resync, gate, invariants) -> str:
    if int(invariants.get("violation_count", 0)) > 0:
        return "blocked"
    if gate.get("latest_gate_decision") == "gate_ready":
        return "ready"
    if resync.get("latest_resync_decision") == "resync_ready":
        return "ready"
    if freeze.get("latest_freeze_decision") == "freeze_ready":
        return "ready"
    if status.get("latest_construction_decision") == "construction_blocked":
        return "blocked"
    return "watch"


def _first_string(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str):
            return value
    return None


def _as_string(value: object) -> str | None:
    return value if isinstance(value, str) else None
