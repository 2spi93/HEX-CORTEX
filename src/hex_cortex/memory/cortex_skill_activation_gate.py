from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_skill_library import (
    CORTEX_SKILL_LIBRARY_FILENAME,
    CortexSkillLibraryJsonlStore,
    CortexSkillLibraryRecord,
)

CORTEX_SKILL_ACTIVATION_GATE_FILENAME = "cortex-skill-activation-gate.jsonl"
_ALLOWED_DOMAINS = {"architecture", "coding", "general", "ops", "product", "research"}


class CortexSkillActivationGateRecord(BaseModel):
    gate_id: str = Field(default_factory=lambda: f"cortex_skill_activation_gate_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    skill_key: str
    domain: str
    source_library_id: str
    source_library_hash: str
    source_candidate_hash: str
    source_learning_ids: list[str]
    source_learning_hashes: list[str]
    evidence_count: int = Field(ge=0)
    average_confidence: float = Field(ge=0.0, le=1.0)
    gate_status: str
    gate_decision: str
    gate_allowed: bool
    activation_authorized: bool
    activation_mode: str
    next_action: str
    blockers: list[str]
    gate_hash: str
    reasons: list[str]


class CortexSkillActivationGateJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexSkillActivationGateRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexSkillActivationGateRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex skill activation gate {line_number}") from exc
        return records

    def save(self, records: list[CortexSkillActivationGateRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_skill_activation_gate(profile: Path) -> dict[str, object]:
    library_records = CortexSkillLibraryJsonlStore(
        profile / CORTEX_SKILL_LIBRARY_FILENAME
    ).load()
    path = profile / CORTEX_SKILL_ACTIVATION_GATE_FILENAME
    store = CortexSkillActivationGateJsonlStore(path)
    current = store.load()
    existing_hashes = {record.source_library_hash for record in current}
    records = [
        _gate_record(profile, library)
        for library in library_records
        if library.library_hash not in existing_hashes
    ]
    count = store.save([*current, *records])
    return {
        "gate_type": "cortex_skill_activation_gate",
        "profile_path": str(profile),
        "gate_path": str(path),
        "gate_count": count,
        "gate_records": [record.model_dump(mode="json") for record in records],
    }


def summarize_cortex_skill_activation_gates(path: Path) -> dict[str, object]:
    records = CortexSkillActivationGateJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.gate_allowed]
    authorized = [record for record in records if record.activation_authorized]
    return {
        "inspect_type": "cortex_skill_activation_gate",
        "path": str(path),
        "exists": path.exists(),
        "total_gate_count": len(records),
        "allowed_gate_count": len(allowed),
        "authorized_activation_count": len(authorized),
        "latest_gate_id": latest.gate_id if latest else None,
        "latest_skill_key": latest.skill_key if latest else None,
        "latest_domain": latest.domain if latest else None,
        "latest_gate_status": latest.gate_status if latest else None,
        "latest_gate_decision": latest.gate_decision if latest else None,
        "latest_gate_allowed": latest.gate_allowed if latest else None,
        "latest_activation_authorized": latest.activation_authorized if latest else None,
        "latest_activation_mode": latest.activation_mode if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_gate_hash": latest.gate_hash if latest else None,
    }


def _gate_record(profile: Path, library: CortexSkillLibraryRecord) -> CortexSkillActivationGateRecord:
    blockers = _gate_blockers(library)
    allowed = not blockers
    decision = "skill_activation_gate_ready" if allowed else "skill_activation_gate_blocked"
    status = "ready" if allowed else "blocked"
    mode = "manual_enablement_required" if allowed else "blocked"
    next_action = "await_manual_skill_activation" if allowed else "repair_skill_library_record"
    reasons = ["library_registered", "activation_requires_manual_gate"] if allowed else blockers
    gate_hash = _hash(
        str(profile),
        library.skill_key,
        library.domain,
        library.library_hash,
        library.source_candidate_hash,
        str(library.average_confidence),
        decision,
        next_action,
        *reasons,
    )
    return CortexSkillActivationGateRecord(
        profile_path=str(profile),
        skill_key=library.skill_key,
        domain=library.domain,
        source_library_id=library.library_id,
        source_library_hash=library.library_hash,
        source_candidate_hash=library.source_candidate_hash,
        source_learning_ids=library.source_learning_ids,
        source_learning_hashes=library.source_learning_hashes,
        evidence_count=library.evidence_count,
        average_confidence=library.average_confidence,
        gate_status=status,
        gate_decision=decision,
        gate_allowed=allowed,
        activation_authorized=allowed,
        activation_mode=mode,
        next_action=next_action,
        blockers=blockers,
        gate_hash=gate_hash,
        reasons=reasons,
    )


def _gate_blockers(library: CortexSkillLibraryRecord) -> list[str]:
    blockers = []
    if library.library_allowed is not True:
        blockers.append("library_not_allowed")
    if library.library_status != "registered":
        blockers.append("library_not_registered")
    if library.library_decision != "skill_library_registered":
        blockers.append("library_decision_not_registered")
    if library.active is not False:
        blockers.append("skill_already_active")
    if library.activation_status != "inactive_pending_gate":
        blockers.append("activation_status_not_pending_gate")
    if library.domain not in _ALLOWED_DOMAINS:
        blockers.append("domain_not_activation_allowed")
    if library.evidence_count < 1:
        blockers.append("missing_skill_evidence")
    if library.average_confidence < 0.75:
        blockers.append("skill_confidence_below_threshold")
    if not library.source_learning_ids or not library.source_learning_hashes:
        blockers.append("missing_learning_lineage")
    if library.next_action != "await_skill_activation_gate":
        blockers.append("library_next_action_not_activation_gate")
    return blockers


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
