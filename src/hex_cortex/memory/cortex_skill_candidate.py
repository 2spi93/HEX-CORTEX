from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_learning_event import (
    CORTEX_LEARNING_EVENT_FILENAME,
    CortexLearningEventJsonlStore,
    CortexLearningEventRecord,
)

CORTEX_SKILL_CANDIDATE_FILENAME = "cortex-skill-candidate.jsonl"


class CortexSkillCandidateRecord(BaseModel):
    candidate_id: str = Field(default_factory=lambda: f"cortex_skill_candidate_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    skill_key: str
    domain: str
    source_learning_ids: list[str]
    source_learning_hashes: list[str]
    reusable_rule: str
    evidence_count: int = Field(ge=0)
    average_confidence: float = Field(ge=0.0, le=1.0)
    candidate_status: str
    candidate_decision: str
    candidate_allowed: bool
    promote_to_library: bool
    blockers: list[str]
    next_action: str
    candidate_hash: str
    reasons: list[str]


class CortexSkillCandidateJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexSkillCandidateRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexSkillCandidateRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex skill candidate {line_number}") from exc
        return records

    def save(self, records: list[CortexSkillCandidateRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append_many(self, records: list[CortexSkillCandidateRecord]) -> int:
        current = self.load()
        current.extend(records)
        return self.save(current)


def build_cortex_skill_candidates(profile: Path) -> dict[str, object]:
    learning_records = CortexLearningEventJsonlStore(
        profile / CORTEX_LEARNING_EVENT_FILENAME
    ).load()
    records = _build_candidates(profile, learning_records)
    path = profile / CORTEX_SKILL_CANDIDATE_FILENAME
    count = CortexSkillCandidateJsonlStore(path).append_many(records)
    return {
        "candidate_type": "cortex_skill_candidate",
        "profile_path": str(profile),
        "candidate_path": str(path),
        "candidate_count": count,
        "candidate_records": [record.model_dump(mode="json") for record in records],
    }


def summarize_cortex_skill_candidates(path: Path) -> dict[str, object]:
    records = CortexSkillCandidateJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.candidate_allowed]
    promotable = [record for record in records if record.promote_to_library]
    return {
        "inspect_type": "cortex_skill_candidate",
        "path": str(path),
        "exists": path.exists(),
        "total_candidate_count": len(records),
        "allowed_candidate_count": len(allowed),
        "promotable_candidate_count": len(promotable),
        "latest_candidate_id": latest.candidate_id if latest else None,
        "latest_skill_key": latest.skill_key if latest else None,
        "latest_domain": latest.domain if latest else None,
        "latest_candidate_status": latest.candidate_status if latest else None,
        "latest_candidate_decision": latest.candidate_decision if latest else None,
        "latest_candidate_allowed": latest.candidate_allowed if latest else None,
        "latest_promote_to_library": latest.promote_to_library if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_candidate_hash": latest.candidate_hash if latest else None,
    }


def _build_candidates(
    profile: Path,
    learning_records: list[CortexLearningEventRecord],
) -> list[CortexSkillCandidateRecord]:
    groups: dict[tuple[str, str], list[CortexLearningEventRecord]] = defaultdict(list)
    for record in learning_records:
        if record.event_allowed and record.promote_to_skill:
            groups[(record.domain, record.reusable_rule)].append(record)
    return [_candidate_from_group(profile, domain, rule, records) for (domain, rule), records in groups.items()]


def _candidate_from_group(
    profile: Path,
    domain: str,
    rule: str,
    records: list[CortexLearningEventRecord],
) -> CortexSkillCandidateRecord:
    confidence = sum(record.confidence for record in records) / len(records)
    blockers = _candidate_blockers(rule, records, confidence)
    allowed = not blockers
    promotable = allowed and len(records) >= 1 and confidence >= 0.75
    decision = "skill_candidate_ready" if allowed else "skill_candidate_blocked"
    status = "ready" if allowed else "blocked"
    next_action = "prepare_skill_library_promotion" if promotable else "collect_more_learning_evidence"
    reasons = ["learning_events_promoted", "reusable_rule_grouped"] if allowed else blockers
    source_ids = [record.learning_id for record in records]
    source_hashes = [record.learning_hash for record in records]
    skill_key = _skill_key(domain, rule)
    candidate_hash = _hash(str(profile), skill_key, domain, rule, str(confidence), *source_hashes, decision, next_action)
    return CortexSkillCandidateRecord(
        profile_path=str(profile),
        skill_key=skill_key,
        domain=domain,
        source_learning_ids=source_ids,
        source_learning_hashes=source_hashes,
        reusable_rule=rule,
        evidence_count=len(records),
        average_confidence=confidence,
        candidate_status=status,
        candidate_decision=decision,
        candidate_allowed=allowed,
        promote_to_library=promotable,
        blockers=blockers,
        next_action=next_action,
        candidate_hash=candidate_hash,
        reasons=reasons,
    )


def _candidate_blockers(rule: str, records: list[CortexLearningEventRecord], confidence: float) -> list[str]:
    blockers = []
    if not records:
        blockers.append("no_promoted_learning_events")
    if len(rule) < 8:
        blockers.append("reusable_rule_too_short")
    if confidence < 0.75:
        blockers.append("confidence_below_skill_threshold")
    return blockers


def _skill_key(domain: str, rule: str) -> str:
    digest = hashlib.sha256(rule.encode("utf-8")).hexdigest()[:12]
    normalized = "-".join(domain.lower().split()) or "general"
    return f"{normalized}:{digest}"


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
