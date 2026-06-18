from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_manual_skill_activation import (
    CORTEX_MANUAL_SKILL_ACTIVATION_FILENAME,
    CortexManualSkillActivationJsonlStore,
    CortexManualSkillActivationRecord,
)
from hex_cortex.memory.cortex_skill_library import (
    CORTEX_SKILL_LIBRARY_FILENAME,
    CortexSkillLibraryJsonlStore,
    CortexSkillLibraryRecord,
)

CORTEX_SKILL_ACTIVATION_APPLY_FILENAME = "cortex-skill-activation-apply.jsonl"


class CortexSkillActivationApplyRecord(BaseModel):
    apply_id: str = Field(default_factory=lambda: f"cortex_skill_activation_apply_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    skill_key: str
    domain: str
    source_manual_id: str
    source_manual_hash: str
    source_gate_hash: str
    source_library_hash: str
    source_candidate_hash: str
    source_learning_ids: list[str]
    source_learning_hashes: list[str]
    reusable_rule: str
    evidence_count: int = Field(ge=0)
    average_confidence: float = Field(ge=0.0, le=1.0)
    apply_status: str
    apply_decision: str
    apply_allowed: bool
    effective_active: bool
    activation_source: str
    next_action: str
    blockers: list[str]
    apply_hash: str
    reasons: list[str]


class CortexSkillActivationApplyJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexSkillActivationApplyRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexSkillActivationApplyRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex skill activation apply {line_number}") from exc
        return records

    def save(self, records: list[CortexSkillActivationApplyRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_skill_activation_apply(profile: Path) -> dict[str, object]:
    manual = _latest_manual(profile)
    library = _matching_library(profile, manual)
    path = profile / CORTEX_SKILL_ACTIVATION_APPLY_FILENAME
    store = CortexSkillActivationApplyJsonlStore(path)
    current = store.load()
    if manual and any(record.source_manual_hash == manual.manual_hash for record in current):
        records: list[CortexSkillActivationApplyRecord] = []
    else:
        records = [_apply_record(profile, manual=manual, library=library)]
    count = store.save([*current, *records])
    return {
        "apply_type": "cortex_skill_activation_apply",
        "profile_path": str(profile),
        "apply_path": str(path),
        "apply_count": count,
        "apply_records": [record.model_dump(mode="json") for record in records],
    }


def summarize_cortex_skill_activation_applies(path: Path) -> dict[str, object]:
    records = CortexSkillActivationApplyJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.apply_allowed]
    active = [record for record in records if record.effective_active]
    return {
        "inspect_type": "cortex_skill_activation_apply",
        "path": str(path),
        "exists": path.exists(),
        "total_apply_count": len(records),
        "allowed_apply_count": len(allowed),
        "effective_active_count": len(active),
        "latest_apply_id": latest.apply_id if latest else None,
        "latest_skill_key": latest.skill_key if latest else None,
        "latest_domain": latest.domain if latest else None,
        "latest_apply_status": latest.apply_status if latest else None,
        "latest_apply_decision": latest.apply_decision if latest else None,
        "latest_apply_allowed": latest.apply_allowed if latest else None,
        "latest_effective_active": latest.effective_active if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_apply_hash": latest.apply_hash if latest else None,
    }


def _latest_manual(profile: Path) -> CortexManualSkillActivationRecord | None:
    records = CortexManualSkillActivationJsonlStore(
        profile / CORTEX_MANUAL_SKILL_ACTIVATION_FILENAME
    ).load()
    return records[-1] if records else None


def _matching_library(
    profile: Path,
    manual: CortexManualSkillActivationRecord | None,
) -> CortexSkillLibraryRecord | None:
    if manual is None or manual.source_library_hash is None:
        return None
    records = CortexSkillLibraryJsonlStore(profile / CORTEX_SKILL_LIBRARY_FILENAME).load()
    for record in reversed(records):
        if record.library_hash == manual.source_library_hash:
            return record
    return None


def _apply_record(
    profile: Path,
    *,
    manual: CortexManualSkillActivationRecord | None,
    library: CortexSkillLibraryRecord | None,
) -> CortexSkillActivationApplyRecord:
    blockers = _apply_blockers(manual, library)
    allowed = not blockers
    status = "applied" if allowed else "blocked"
    decision = "skill_activation_applied" if allowed else "skill_activation_apply_blocked"
    next_action = "skill_available_for_controlled_use" if allowed else "repair_skill_activation_apply"
    reasons = ["manual_activation_accepted", "library_lineage_verified"] if allowed else blockers
    skill_key = _value(manual.skill_key if manual else None, library.skill_key if library else None)
    domain = _value(manual.domain if manual else None, library.domain if library else None)
    source_manual_hash = manual.manual_hash if manual else "missing_manual"
    source_library_hash = manual.source_library_hash if manual else "missing_library"
    apply_hash = _hash(
        str(profile),
        skill_key,
        domain,
        source_manual_hash,
        source_library_hash,
        decision,
        next_action,
        *reasons,
    )
    return CortexSkillActivationApplyRecord(
        profile_path=str(profile),
        skill_key=skill_key,
        domain=domain,
        source_manual_id=manual.manual_id if manual else "missing_manual",
        source_manual_hash=source_manual_hash,
        source_gate_hash=manual.source_gate_hash if manual and manual.source_gate_hash else "missing_gate",
        source_library_hash=source_library_hash,
        source_candidate_hash=manual.source_candidate_hash if manual and manual.source_candidate_hash else "missing_candidate",
        source_learning_ids=manual.source_learning_ids if manual else [],
        source_learning_hashes=manual.source_learning_hashes if manual else [],
        reusable_rule=library.reusable_rule if library else "",
        evidence_count=library.evidence_count if library else 0,
        average_confidence=library.average_confidence if library else 0.0,
        apply_status=status,
        apply_decision=decision,
        apply_allowed=allowed,
        effective_active=allowed,
        activation_source="manual_operator_choice" if allowed else "blocked",
        next_action=next_action,
        blockers=blockers,
        apply_hash=apply_hash,
        reasons=reasons,
    )


def _apply_blockers(
    manual: CortexManualSkillActivationRecord | None,
    library: CortexSkillLibraryRecord | None,
) -> list[str]:
    blockers = []
    if manual is None:
        blockers.append("missing_manual_activation")
        return blockers
    if manual.manual_allowed is not True:
        blockers.append("manual_not_allowed")
    if manual.operator_choice != "activate":
        blockers.append("manual_choice_not_activate")
    if manual.activation_apply_allowed is not True:
        blockers.append("manual_apply_not_allowed")
    if manual.next_action != "prepare_skill_activation_apply":
        blockers.append("manual_next_action_not_apply")
    if library is None:
        blockers.append("missing_library_record")
        return blockers
    if library.library_hash != manual.source_library_hash:
        blockers.append("library_hash_mismatch")
    if library.library_allowed is not True:
        blockers.append("library_not_allowed")
    if library.active is not False:
        blockers.append("library_already_active")
    if library.activation_status != "inactive_pending_gate":
        blockers.append("library_activation_status_not_pending")
    if not manual.source_learning_ids or not manual.source_learning_hashes:
        blockers.append("missing_learning_lineage")
    return blockers


def _value(*values: str | None) -> str:
    for value in values:
        if value:
            return value
    return "unknown"


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
