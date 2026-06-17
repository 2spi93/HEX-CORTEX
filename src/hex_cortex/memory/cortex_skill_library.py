from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_skill_candidate import (
    CORTEX_SKILL_CANDIDATE_FILENAME,
    CortexSkillCandidateJsonlStore,
    CortexSkillCandidateRecord,
)

CORTEX_SKILL_LIBRARY_FILENAME = "cortex-skill-library.jsonl"


class CortexSkillLibraryRecord(BaseModel):
    library_id: str = Field(default_factory=lambda: f"cortex_skill_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    skill_key: str
    domain: str
    reusable_rule: str
    source_candidate_id: str
    source_candidate_hash: str
    source_learning_ids: list[str]
    source_learning_hashes: list[str]
    evidence_count: int = Field(ge=0)
    average_confidence: float = Field(ge=0.0, le=1.0)
    library_status: str
    library_decision: str
    library_allowed: bool
    active: bool
    activation_status: str
    next_action: str
    blockers: list[str]
    library_hash: str
    reasons: list[str]


class CortexSkillLibraryJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexSkillLibraryRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexSkillLibraryRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex skill library record {line_number}") from exc
        return records

    def save(self, records: list[CortexSkillLibraryRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_skill_library(profile: Path) -> dict[str, object]:
    candidates = CortexSkillCandidateJsonlStore(
        profile / CORTEX_SKILL_CANDIDATE_FILENAME
    ).load()
    path = profile / CORTEX_SKILL_LIBRARY_FILENAME
    store = CortexSkillLibraryJsonlStore(path)
    current = store.load()
    existing_hashes = {record.source_candidate_hash for record in current}
    records = [
        _library_record(profile, candidate)
        for candidate in candidates
        if _is_promotable(candidate) and candidate.candidate_hash not in existing_hashes
    ]
    count = store.save([*current, *records])
    return {
        "library_type": "cortex_skill_library",
        "profile_path": str(profile),
        "library_path": str(path),
        "library_count": count,
        "library_records": [record.model_dump(mode="json") for record in records],
    }


def summarize_cortex_skill_library(path: Path) -> dict[str, object]:
    records = CortexSkillLibraryJsonlStore(path).load()
    latest = records[-1] if records else None
    registered = [record for record in records if record.library_allowed]
    active = [record for record in records if record.active]
    return {
        "inspect_type": "cortex_skill_library",
        "path": str(path),
        "exists": path.exists(),
        "total_skill_count": len(records),
        "registered_skill_count": len(registered),
        "active_skill_count": len(active),
        "latest_library_id": latest.library_id if latest else None,
        "latest_skill_key": latest.skill_key if latest else None,
        "latest_domain": latest.domain if latest else None,
        "latest_library_status": latest.library_status if latest else None,
        "latest_library_decision": latest.library_decision if latest else None,
        "latest_library_allowed": latest.library_allowed if latest else None,
        "latest_active": latest.active if latest else None,
        "latest_activation_status": latest.activation_status if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_library_hash": latest.library_hash if latest else None,
    }


def _is_promotable(candidate: CortexSkillCandidateRecord) -> bool:
    return candidate.candidate_allowed is True and candidate.promote_to_library is True


def _library_record(profile: Path, candidate: CortexSkillCandidateRecord) -> CortexSkillLibraryRecord:
    blockers = _library_blockers(candidate)
    allowed = not blockers
    decision = "skill_library_registered" if allowed else "skill_library_blocked"
    status = "registered" if allowed else "blocked"
    next_action = "await_skill_activation_gate" if allowed else "repair_skill_candidate"
    reasons = ["skill_candidate_promotable", "skill_registered_inactive"] if allowed else blockers
    library_hash = _hash(
        str(profile),
        candidate.skill_key,
        candidate.domain,
        candidate.candidate_hash,
        candidate.reusable_rule,
        str(candidate.average_confidence),
        decision,
        next_action,
        *reasons,
    )
    return CortexSkillLibraryRecord(
        profile_path=str(profile),
        skill_key=candidate.skill_key,
        domain=candidate.domain,
        reusable_rule=candidate.reusable_rule,
        source_candidate_id=candidate.candidate_id,
        source_candidate_hash=candidate.candidate_hash,
        source_learning_ids=candidate.source_learning_ids,
        source_learning_hashes=candidate.source_learning_hashes,
        evidence_count=candidate.evidence_count,
        average_confidence=candidate.average_confidence,
        library_status=status,
        library_decision=decision,
        library_allowed=allowed,
        active=False,
        activation_status="inactive_pending_gate" if allowed else "blocked",
        next_action=next_action,
        blockers=blockers,
        library_hash=library_hash,
        reasons=reasons,
    )


def _library_blockers(candidate: CortexSkillCandidateRecord) -> list[str]:
    blockers = []
    if candidate.candidate_allowed is not True:
        blockers.append("candidate_not_allowed")
    if candidate.promote_to_library is not True:
        blockers.append("candidate_not_promotable")
    if candidate.evidence_count < 1:
        blockers.append("missing_skill_evidence")
    if candidate.average_confidence < 0.75:
        blockers.append("candidate_confidence_below_threshold")
    if len(candidate.reusable_rule) < 8:
        blockers.append("reusable_rule_too_short")
    return blockers


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
