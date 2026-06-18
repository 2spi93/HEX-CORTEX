from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_skill_activation_apply import (
    CORTEX_SKILL_ACTIVATION_APPLY_FILENAME,
    CortexSkillActivationApplyJsonlStore,
    CortexSkillActivationApplyRecord,
)

CORTEX_ACTIVE_SKILL_INDEX_FILENAME = "cortex-active-skill-index.jsonl"


class CortexActiveSkillIndexEntry(BaseModel):
    skill_key: str
    domain: str
    reusable_rule: str
    source_apply_id: str
    source_apply_hash: str
    source_library_hash: str
    source_manual_hash: str
    source_learning_ids: list[str]
    evidence_count: int = Field(ge=0)
    average_confidence: float = Field(ge=0.0, le=1.0)


class CortexActiveSkillIndexRecord(BaseModel):
    index_id: str = Field(default_factory=lambda: f"cortex_active_skill_index_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    index_status: str
    index_decision: str
    index_allowed: bool
    active_skill_count: int = Field(ge=0)
    active_domains: list[str]
    active_skill_keys: list[str]
    entries: list[CortexActiveSkillIndexEntry]
    next_action: str
    blockers: list[str]
    index_hash: str
    reasons: list[str]


class CortexActiveSkillIndexJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexActiveSkillIndexRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexActiveSkillIndexRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex active skill index {line_number}") from exc
        return records

    def save(self, records: list[CortexActiveSkillIndexRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: CortexActiveSkillIndexRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_cortex_active_skill_index(profile: Path) -> dict[str, object]:
    applies = CortexSkillActivationApplyJsonlStore(
        profile / CORTEX_SKILL_ACTIVATION_APPLY_FILENAME
    ).load()
    record = _index_record(profile, applies)
    path = profile / CORTEX_ACTIVE_SKILL_INDEX_FILENAME
    count = CortexActiveSkillIndexJsonlStore(path).append(record)
    return {
        "index_type": "cortex_active_skill_index",
        "profile_path": str(profile),
        "index_path": str(path),
        "index_count": count,
        "index_record": record.model_dump(mode="json"),
    }


def summarize_cortex_active_skill_indexes(path: Path) -> dict[str, object]:
    records = CortexActiveSkillIndexJsonlStore(path).load()
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_active_skill_index",
        "path": str(path),
        "exists": path.exists(),
        "total_index_count": len(records),
        "latest_index_id": latest.index_id if latest else None,
        "latest_index_status": latest.index_status if latest else None,
        "latest_index_decision": latest.index_decision if latest else None,
        "latest_index_allowed": latest.index_allowed if latest else None,
        "latest_active_skill_count": latest.active_skill_count if latest else None,
        "latest_active_domains": latest.active_domains if latest else None,
        "latest_active_skill_keys": latest.active_skill_keys if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_index_hash": latest.index_hash if latest else None,
    }


def _index_record(
    profile: Path,
    applies: list[CortexSkillActivationApplyRecord],
) -> CortexActiveSkillIndexRecord:
    active = _latest_active_by_skill(applies)
    entries = [_entry(record) for record in active]
    blockers = _index_blockers(entries)
    allowed = not blockers
    status = "ready" if allowed else "empty"
    decision = "active_skill_index_ready" if allowed else "active_skill_index_empty"
    next_action = "await_controlled_skill_use" if allowed else "collect_active_skill"
    reasons = ["effective_active_skills_indexed"] if allowed else blockers
    active_domains = sorted({entry.domain for entry in entries})
    active_skill_keys = [entry.skill_key for entry in entries]
    index_hash = _hash(
        str(profile),
        *active_skill_keys,
        *[entry.source_apply_hash for entry in entries],
        decision,
        next_action,
        *reasons,
    )
    return CortexActiveSkillIndexRecord(
        profile_path=str(profile),
        index_status=status,
        index_decision=decision,
        index_allowed=allowed,
        active_skill_count=len(entries),
        active_domains=active_domains,
        active_skill_keys=active_skill_keys,
        entries=entries,
        next_action=next_action,
        blockers=blockers,
        index_hash=index_hash,
        reasons=reasons,
    )


def _latest_active_by_skill(
    applies: list[CortexSkillActivationApplyRecord],
) -> list[CortexSkillActivationApplyRecord]:
    latest: dict[str, CortexSkillActivationApplyRecord] = {}
    for record in applies:
        if record.apply_allowed and record.effective_active:
            latest[record.skill_key] = record
    return [latest[key] for key in sorted(latest)]


def _entry(record: CortexSkillActivationApplyRecord) -> CortexActiveSkillIndexEntry:
    return CortexActiveSkillIndexEntry(
        skill_key=record.skill_key,
        domain=record.domain,
        reusable_rule=record.reusable_rule,
        source_apply_id=record.apply_id,
        source_apply_hash=record.apply_hash,
        source_library_hash=record.source_library_hash,
        source_manual_hash=record.source_manual_hash,
        source_learning_ids=record.source_learning_ids,
        evidence_count=record.evidence_count,
        average_confidence=record.average_confidence,
    )


def _index_blockers(entries: list[CortexActiveSkillIndexEntry]) -> list[str]:
    if not entries:
        return ["no_effective_active_skills"]
    return []


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
