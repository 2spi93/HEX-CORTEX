from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_active_skill_index import (
    CORTEX_ACTIVE_SKILL_INDEX_FILENAME,
    CortexActiveSkillIndexEntry,
    CortexActiveSkillIndexJsonlStore,
    CortexActiveSkillIndexRecord,
)

CORTEX_CONTROLLED_SKILL_USE_FILENAME = "cortex-controlled-skill-use.jsonl"
_ALLOWED_INTENTS = {"inspect", "plan", "apply_rule", "explain"}
_BLOCKED_WORDS = {"execute", "deploy", "live", "trade", "order", "buy", "sell", "delete", "destroy"}


class CortexControlledSkillUseRecord(BaseModel):
    use_id: str = Field(default_factory=lambda: f"cortex_controlled_skill_use_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    requested_skill_key: str | None
    requested_domain: str | None
    intent: str
    task_text: str
    selected_skill_key: str | None
    selected_domain: str | None
    selected_reusable_rule: str | None
    source_index_id: str | None
    source_index_hash: str | None
    source_apply_hash: str | None
    source_library_hash: str | None
    source_learning_ids: list[str]
    use_status: str
    use_decision: str
    use_allowed: bool
    next_action: str
    blockers: list[str]
    use_hash: str
    reasons: list[str]


class CortexControlledSkillUseJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexControlledSkillUseRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexControlledSkillUseRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex controlled skill use {line_number}") from exc
        return records

    def save(self, records: list[CortexControlledSkillUseRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: CortexControlledSkillUseRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def record_cortex_controlled_skill_use(
    profile: Path,
    *,
    intent: str,
    task_text: str,
    skill_key: str | None = None,
    domain: str | None = None,
) -> dict[str, object]:
    index = _latest_index(profile)
    entry = _select_entry(index, skill_key=skill_key, domain=domain)
    record = _use_record(
        profile,
        index=index,
        entry=entry,
        intent=intent,
        task_text=task_text,
        requested_skill_key=skill_key,
        requested_domain=domain,
    )
    path = profile / CORTEX_CONTROLLED_SKILL_USE_FILENAME
    count = CortexControlledSkillUseJsonlStore(path).append(record)
    return {
        "use_type": "cortex_controlled_skill_use",
        "profile_path": str(profile),
        "use_path": str(path),
        "use_count": count,
        "use_record": record.model_dump(mode="json"),
    }


def summarize_cortex_controlled_skill_uses(path: Path) -> dict[str, object]:
    records = CortexControlledSkillUseJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.use_allowed]
    return {
        "inspect_type": "cortex_controlled_skill_use",
        "path": str(path),
        "exists": path.exists(),
        "total_use_count": len(records),
        "allowed_use_count": len(allowed),
        "latest_use_id": latest.use_id if latest else None,
        "latest_intent": latest.intent if latest else None,
        "latest_selected_skill_key": latest.selected_skill_key if latest else None,
        "latest_selected_domain": latest.selected_domain if latest else None,
        "latest_use_status": latest.use_status if latest else None,
        "latest_use_decision": latest.use_decision if latest else None,
        "latest_use_allowed": latest.use_allowed if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_use_hash": latest.use_hash if latest else None,
    }


def _latest_index(profile: Path) -> CortexActiveSkillIndexRecord | None:
    records = CortexActiveSkillIndexJsonlStore(profile / CORTEX_ACTIVE_SKILL_INDEX_FILENAME).load()
    return records[-1] if records else None


def _select_entry(
    index: CortexActiveSkillIndexRecord | None,
    *,
    skill_key: str | None,
    domain: str | None,
) -> CortexActiveSkillIndexEntry | None:
    if index is None:
        return None
    entries = index.entries
    if skill_key:
        for entry in entries:
            if entry.skill_key == skill_key:
                return entry
        return None
    if domain:
        matches = [entry for entry in entries if entry.domain == domain]
        return matches[0] if len(matches) == 1 else None
    return entries[0] if len(entries) == 1 else None


def _use_record(
    profile: Path,
    *,
    index: CortexActiveSkillIndexRecord | None,
    entry: CortexActiveSkillIndexEntry | None,
    intent: str,
    task_text: str,
    requested_skill_key: str | None,
    requested_domain: str | None,
) -> CortexControlledSkillUseRecord:
    clean_intent = intent.strip().lower()
    clean_task = " ".join(task_text.strip().split())
    blockers = _use_blockers(index, entry, clean_intent, clean_task, requested_skill_key, requested_domain)
    allowed = not blockers
    decision = "controlled_skill_use_allowed" if allowed else "controlled_skill_use_blocked"
    status = "allowed" if allowed else "blocked"
    next_action = "render_controlled_skill_guidance" if allowed else "revise_controlled_skill_use"
    reasons = ["active_skill_selected", f"intent_{clean_intent}"] if allowed else blockers
    use_hash = _hash(
        str(profile),
        requested_skill_key or "none",
        requested_domain or "none",
        clean_intent,
        clean_task,
        entry.skill_key if entry else "missing_skill",
        index.index_hash if index else "missing_index",
        decision,
        next_action,
        *reasons,
    )
    return CortexControlledSkillUseRecord(
        profile_path=str(profile),
        requested_skill_key=requested_skill_key,
        requested_domain=requested_domain,
        intent=clean_intent,
        task_text=clean_task,
        selected_skill_key=entry.skill_key if entry else None,
        selected_domain=entry.domain if entry else None,
        selected_reusable_rule=entry.reusable_rule if entry else None,
        source_index_id=index.index_id if index else None,
        source_index_hash=index.index_hash if index else None,
        source_apply_hash=entry.source_apply_hash if entry else None,
        source_library_hash=entry.source_library_hash if entry else None,
        source_learning_ids=entry.source_learning_ids if entry else [],
        use_status=status,
        use_decision=decision,
        use_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        use_hash=use_hash,
        reasons=reasons,
    )


def _use_blockers(
    index: CortexActiveSkillIndexRecord | None,
    entry: CortexActiveSkillIndexEntry | None,
    intent: str,
    task_text: str,
    requested_skill_key: str | None,
    requested_domain: str | None,
) -> list[str]:
    blockers = []
    if index is None:
        blockers.append("missing_active_skill_index")
        return blockers
    if index.index_allowed is not True:
        blockers.append("active_skill_index_not_allowed")
    if index.next_action != "await_controlled_skill_use":
        blockers.append("index_not_waiting_controlled_use")
    if entry is None:
        blockers.append("no_matching_active_skill")
    if intent not in _ALLOWED_INTENTS:
        blockers.append("intent_not_allowed")
    if len(task_text) < 8:
        blockers.append("task_text_too_short")
    words = {part.strip(".,:;!?()[]{}\"'").lower() for part in task_text.split()}
    if words & _BLOCKED_WORDS:
        blockers.append("task_contains_blocked_action")
    if requested_skill_key and requested_domain and entry is not None and entry.domain != requested_domain:
        blockers.append("requested_domain_mismatch")
    return blockers


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
