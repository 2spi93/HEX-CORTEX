from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_skill_activation_gate import (
    CORTEX_SKILL_ACTIVATION_GATE_FILENAME,
    CortexSkillActivationGateJsonlStore,
    CortexSkillActivationGateRecord,
)

CORTEX_MANUAL_SKILL_ACTIVATION_FILENAME = "cortex-manual-skill-activation.jsonl"
_VALID_CHOICES = {"activate", "hold", "reject"}


class CortexManualSkillActivationRecord(BaseModel):
    manual_id: str = Field(default_factory=lambda: f"cortex_manual_skill_activation_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    skill_key: str | None
    domain: str | None
    operator_choice: str
    operator_note: str
    source_gate_id: str | None
    source_gate_hash: str | None
    source_library_hash: str | None
    source_candidate_hash: str | None
    source_learning_ids: list[str]
    source_learning_hashes: list[str]
    manual_status: str
    manual_decision: str
    manual_allowed: bool
    activation_apply_allowed: bool
    next_action: str
    blockers: list[str]
    manual_hash: str
    reasons: list[str]


class CortexManualSkillActivationJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexManualSkillActivationRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexManualSkillActivationRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex manual skill activation {line_number}") from exc
        return records

    def save(self, records: list[CortexManualSkillActivationRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: CortexManualSkillActivationRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def record_cortex_manual_skill_activation(
    profile: Path,
    *,
    choice: str,
    note: str,
) -> dict[str, object]:
    gate = _latest_gate(profile)
    record = _manual_record(profile, gate=gate, choice=choice, note=note)
    path = profile / CORTEX_MANUAL_SKILL_ACTIVATION_FILENAME
    count = CortexManualSkillActivationJsonlStore(path).append(record)
    return {
        "manual_type": "cortex_manual_skill_activation",
        "profile_path": str(profile),
        "manual_path": str(path),
        "manual_count": count,
        "manual_record": record.model_dump(mode="json"),
    }


def summarize_cortex_manual_skill_activations(path: Path) -> dict[str, object]:
    records = CortexManualSkillActivationJsonlStore(path).load()
    latest = records[-1] if records else None
    accepted = [record for record in records if record.manual_allowed]
    apply_ready = [record for record in records if record.activation_apply_allowed]
    return {
        "inspect_type": "cortex_manual_skill_activation",
        "path": str(path),
        "exists": path.exists(),
        "total_manual_count": len(records),
        "allowed_manual_count": len(accepted),
        "apply_ready_count": len(apply_ready),
        "latest_manual_id": latest.manual_id if latest else None,
        "latest_skill_key": latest.skill_key if latest else None,
        "latest_domain": latest.domain if latest else None,
        "latest_operator_choice": latest.operator_choice if latest else None,
        "latest_manual_status": latest.manual_status if latest else None,
        "latest_manual_decision": latest.manual_decision if latest else None,
        "latest_manual_allowed": latest.manual_allowed if latest else None,
        "latest_activation_apply_allowed": latest.activation_apply_allowed if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_manual_hash": latest.manual_hash if latest else None,
    }


def _latest_gate(profile: Path) -> CortexSkillActivationGateRecord | None:
    records = CortexSkillActivationGateJsonlStore(
        profile / CORTEX_SKILL_ACTIVATION_GATE_FILENAME
    ).load()
    return records[-1] if records else None


def _manual_record(
    profile: Path,
    *,
    gate: CortexSkillActivationGateRecord | None,
    choice: str,
    note: str,
) -> CortexManualSkillActivationRecord:
    clean_choice = choice.strip().lower()
    clean_note = " ".join(note.strip().split())
    blockers = _manual_blockers(gate, clean_choice, clean_note)
    allowed = not blockers
    apply_allowed = allowed and clean_choice == "activate"
    decision = _decision(clean_choice, allowed)
    next_action = _next_action(clean_choice, allowed, apply_allowed)
    reasons = ["manual_choice_recorded", f"operator_choice_{clean_choice}"] if allowed else blockers
    manual_hash = _hash(
        str(profile),
        clean_choice,
        clean_note,
        gate.gate_hash if gate else "missing_gate",
        decision,
        next_action,
        *reasons,
    )
    return CortexManualSkillActivationRecord(
        profile_path=str(profile),
        skill_key=gate.skill_key if gate else None,
        domain=gate.domain if gate else None,
        operator_choice=clean_choice,
        operator_note=clean_note,
        source_gate_id=gate.gate_id if gate else None,
        source_gate_hash=gate.gate_hash if gate else None,
        source_library_hash=gate.source_library_hash if gate else None,
        source_candidate_hash=gate.source_candidate_hash if gate else None,
        source_learning_ids=gate.source_learning_ids if gate else [],
        source_learning_hashes=gate.source_learning_hashes if gate else [],
        manual_status="accepted" if allowed else "blocked",
        manual_decision=decision,
        manual_allowed=allowed,
        activation_apply_allowed=apply_allowed,
        next_action=next_action,
        blockers=blockers,
        manual_hash=manual_hash,
        reasons=reasons,
    )


def _manual_blockers(
    gate: CortexSkillActivationGateRecord | None,
    choice: str,
    note: str,
) -> list[str]:
    blockers = []
    if choice not in _VALID_CHOICES:
        blockers.append("invalid_operator_choice")
    if len(note) < 8:
        blockers.append("operator_note_too_short")
    if gate is None:
        blockers.append("missing_activation_gate")
        return blockers
    if gate.gate_allowed is not True:
        blockers.append("gate_not_allowed")
    if gate.activation_authorized is not True:
        blockers.append("activation_not_authorized")
    if gate.next_action != "await_manual_skill_activation":
        blockers.append("gate_not_waiting_manual_activation")
    if not gate.source_learning_ids or not gate.source_learning_hashes:
        blockers.append("missing_learning_lineage")
    return blockers


def _decision(choice: str, allowed: bool) -> str:
    if not allowed:
        return "manual_skill_activation_blocked"
    if choice == "activate":
        return "manual_skill_activation_accepted"
    if choice == "hold":
        return "manual_skill_activation_held"
    if choice == "reject":
        return "manual_skill_activation_rejected"
    return "manual_skill_activation_blocked"


def _next_action(choice: str, allowed: bool, apply_allowed: bool) -> str:
    if not allowed:
        return "repair_manual_skill_activation"
    if apply_allowed:
        return "prepare_skill_activation_apply"
    if choice == "hold":
        return "await_manual_skill_activation"
    return "skill_activation_rejected"


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
