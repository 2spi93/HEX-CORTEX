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

CORTEX_SKILL_LIBRARY_PROMOTION_GATE_FILENAME = "cortex-skill-library-promotion-gate.jsonl"


class CortexSkillLibraryPromotionGateRecord(BaseModel):
    gate_id: str = Field(default_factory=lambda: f"cortex_skill_library_promotion_gate_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_candidate_id: str | None
    source_candidate_hash: str | None
    skill_key: str | None
    domain: str | None
    evidence_count: int = Field(ge=0)
    average_confidence: float = Field(ge=0.0, le=1.0)
    candidate_verdict: str
    evidence_verdict: str
    confidence_verdict: str
    uniqueness_verdict: str
    gate_status: str
    gate_decision: str
    gate_allowed: bool
    next_action: str
    blockers: list[str]
    gate_hash: str
    reasons: list[str]


class CortexSkillLibraryPromotionGateJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexSkillLibraryPromotionGateRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexSkillLibraryPromotionGateRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex skill library promotion gate {line_number}") from exc
        return records

    def save(self, records: list[CortexSkillLibraryPromotionGateRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_skill_library_promotion_gate(profile: Path) -> dict[str, object]:
    candidate = _latest_promotable_candidate(profile)
    record = _gate_record(profile, candidate)
    path = profile / CORTEX_SKILL_LIBRARY_PROMOTION_GATE_FILENAME
    store = CortexSkillLibraryPromotionGateJsonlStore(path)
    current = store.load()
    if record.source_candidate_hash and any(item.source_candidate_hash == record.source_candidate_hash for item in current):
        records: list[CortexSkillLibraryPromotionGateRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "gate_type": "cortex_skill_library_promotion_gate",
        "profile_path": str(profile),
        "gate_path": str(path),
        "gate_count": count,
        "gate_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_skill_library_promotion_gates(path: Path) -> dict[str, object]:
    records = CortexSkillLibraryPromotionGateJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.gate_allowed]
    return {
        "inspect_type": "cortex_skill_library_promotion_gate",
        "path": str(path),
        "exists": path.exists(),
        "total_gate_count": len(records),
        "allowed_gate_count": len(allowed),
        "latest_gate_id": latest.gate_id if latest else None,
        "latest_gate_status": latest.gate_status if latest else None,
        "latest_gate_decision": latest.gate_decision if latest else None,
        "latest_gate_allowed": latest.gate_allowed if latest else None,
        "latest_skill_key": latest.skill_key if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_gate_hash": latest.gate_hash if latest else None,
    }


def _latest_promotable_candidate(profile: Path) -> CortexSkillCandidateRecord | None:
    records = CortexSkillCandidateJsonlStore(profile / CORTEX_SKILL_CANDIDATE_FILENAME).load()
    promotable = [record for record in records if record.candidate_allowed and record.promote_to_library]
    return promotable[-1] if promotable else None


def _gate_record(profile: Path, candidate: CortexSkillCandidateRecord | None) -> CortexSkillLibraryPromotionGateRecord:
    blockers = _gate_blockers(candidate)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "skill_library_promotion_ready" if allowed else "skill_library_promotion_blocked"
    next_action = "promote_skill_to_library" if allowed else "repair_skill_candidate"
    reasons = ["candidate_promotable", "promotion_gate_ready"] if allowed else blockers
    gate_hash = _hash(
        str(profile),
        candidate.candidate_hash if candidate else "missing_candidate",
        decision,
        next_action,
        *reasons,
    )
    return CortexSkillLibraryPromotionGateRecord(
        profile_path=str(profile),
        source_candidate_id=candidate.candidate_id if candidate else None,
        source_candidate_hash=candidate.candidate_hash if candidate else None,
        skill_key=candidate.skill_key if candidate else None,
        domain=candidate.domain if candidate else None,
        evidence_count=candidate.evidence_count if candidate else 0,
        average_confidence=candidate.average_confidence if candidate else 0.0,
        candidate_verdict=_candidate_verdict(candidate),
        evidence_verdict=_evidence_verdict(candidate),
        confidence_verdict=_confidence_verdict(candidate),
        uniqueness_verdict="not_checked_against_library",
        gate_status=status,
        gate_decision=decision,
        gate_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        gate_hash=gate_hash,
        reasons=reasons,
    )


def _gate_blockers(candidate: CortexSkillCandidateRecord | None) -> list[str]:
    blockers = []
    if candidate is None:
        return ["missing_promotable_skill_candidate"]
    if candidate.candidate_allowed is not True:
        blockers.append("candidate_not_allowed")
    if candidate.promote_to_library is not True:
        blockers.append("candidate_not_marked_for_library")
    if candidate.next_action != "prepare_skill_library_promotion":
        blockers.append("candidate_not_waiting_library_promotion")
    if candidate.evidence_count < 1:
        blockers.append("candidate_missing_evidence")
    if candidate.average_confidence < 0.75:
        blockers.append("candidate_confidence_below_threshold")
    if len(candidate.reusable_rule) < 8:
        blockers.append("reusable_rule_too_short")
    return blockers


def _candidate_verdict(candidate: CortexSkillCandidateRecord | None) -> str:
    if candidate is None:
        return "missing"
    return "candidate_ready" if candidate.candidate_allowed else "candidate_blocked"


def _evidence_verdict(candidate: CortexSkillCandidateRecord | None) -> str:
    if candidate is None:
        return "missing"
    return "evidence_present" if candidate.evidence_count >= 1 else "evidence_missing"


def _confidence_verdict(candidate: CortexSkillCandidateRecord | None) -> str:
    if candidate is None:
        return "missing"
    return "confidence_ready" if candidate.average_confidence >= 0.75 else "confidence_low"


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
