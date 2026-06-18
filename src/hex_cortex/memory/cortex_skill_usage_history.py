from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_controlled_skill_use import (
    CORTEX_CONTROLLED_SKILL_USE_FILENAME,
    CortexControlledSkillUseJsonlStore,
)
from hex_cortex.memory.cortex_multi_skill_feedback_score import (
    CORTEX_MULTI_SKILL_FEEDBACK_SCORE_FILENAME,
    CortexMultiSkillFeedbackScoreJsonlStore,
    CortexMultiSkillFeedbackScoreRecord,
)
from hex_cortex.memory.cortex_multi_skill_router import (
    CORTEX_MULTI_SKILL_ROUTER_FILENAME,
    CortexMultiSkillRouterJsonlStore,
)

CORTEX_SKILL_USAGE_HISTORY_FILENAME = "cortex-skill-usage-history.jsonl"


class CortexSkillUsageHistoryEntry(BaseModel):
    skill_key: str
    domain: str | None
    usage_count: int = Field(ge=0)
    success_count: int = Field(ge=0)
    average_feedback_score: float = Field(ge=0.0, le=1.0)
    last_feedback_score: float = Field(ge=0.0, le=1.0)
    last_router_hash: str | None
    last_use_hash: str | None
    last_feedback_hash: str | None
    last_seen_at: str | None


class CortexSkillUsageHistoryRecord(BaseModel):
    history_id: str = Field(default_factory=lambda: f"cortex_skill_usage_history_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_feedback_hashes: list[str]
    skill_count: int = Field(ge=0)
    total_usage_count: int = Field(ge=0)
    successful_usage_count: int = Field(ge=0)
    best_skill_key: str | None
    best_feedback_score: float = Field(ge=0.0, le=1.0)
    history_entries: list[CortexSkillUsageHistoryEntry]
    history_status: str
    history_decision: str
    history_allowed: bool
    next_action: str
    blockers: list[str]
    history_hash: str
    reasons: list[str]


class CortexSkillUsageHistoryJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexSkillUsageHistoryRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexSkillUsageHistoryRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex skill usage history {line_number}") from exc
        return records

    def save(self, records: list[CortexSkillUsageHistoryRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_skill_usage_history(profile: Path) -> dict[str, object]:
    feedback_records = CortexMultiSkillFeedbackScoreJsonlStore(profile / CORTEX_MULTI_SKILL_FEEDBACK_SCORE_FILENAME).load()
    router_records = CortexMultiSkillRouterJsonlStore(profile / CORTEX_MULTI_SKILL_ROUTER_FILENAME).load()
    use_records = CortexControlledSkillUseJsonlStore(profile / CORTEX_CONTROLLED_SKILL_USE_FILENAME).load()
    record = _history_record(profile, feedback_records, router_records, use_records)
    path = profile / CORTEX_SKILL_USAGE_HISTORY_FILENAME
    store = CortexSkillUsageHistoryJsonlStore(path)
    current = store.load()
    current_hashes = {item.history_hash for item in current}
    records = [] if record.history_hash in current_hashes else [record]
    count = store.save([*current, *records])
    return {
        "history_type": "cortex_skill_usage_history",
        "profile_path": str(profile),
        "history_path": str(path),
        "history_count": count,
        "history_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_skill_usage_histories(path: Path) -> dict[str, object]:
    records = CortexSkillUsageHistoryJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.history_allowed]
    return {
        "inspect_type": "cortex_skill_usage_history",
        "path": str(path),
        "exists": path.exists(),
        "total_history_count": len(records),
        "allowed_history_count": len(allowed),
        "latest_history_id": latest.history_id if latest else None,
        "latest_history_status": latest.history_status if latest else None,
        "latest_history_decision": latest.history_decision if latest else None,
        "latest_history_allowed": latest.history_allowed if latest else None,
        "latest_skill_count": latest.skill_count if latest else None,
        "latest_total_usage_count": latest.total_usage_count if latest else None,
        "latest_successful_usage_count": latest.successful_usage_count if latest else None,
        "latest_best_skill_key": latest.best_skill_key if latest else None,
        "latest_best_feedback_score": latest.best_feedback_score if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_history_hash": latest.history_hash if latest else None,
    }


def _history_record(
    profile: Path,
    feedback_records: list[CortexMultiSkillFeedbackScoreRecord],
    router_records,
    use_records,
) -> CortexSkillUsageHistoryRecord:
    blockers = []
    if not feedback_records:
        blockers.append("missing_multi_skill_feedback_records")
    valid_feedback = [record for record in feedback_records if record.feedback_allowed]
    if feedback_records and not valid_feedback:
        blockers.append("no_allowed_multi_skill_feedback_records")
    entries = _entries(valid_feedback)
    if valid_feedback and not entries:
        blockers.append("missing_skill_usage_entries")
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "skill_usage_history_ready" if allowed else "skill_usage_history_blocked"
    next_action = "build_cockpit_data_api" if allowed else "repair_skill_usage_history"
    reasons = ["feedback_records_loaded", "usage_history_built", "best_skill_selected"] if allowed else blockers
    source_hashes = [record.feedback_hash for record in valid_feedback]
    best_entry = max(entries, key=lambda item: (item.average_feedback_score, item.success_count, item.usage_count, item.skill_key), default=None)
    total_usage_count = sum(entry.usage_count for entry in entries)
    successful_usage_count = sum(entry.success_count for entry in entries)
    history_hash = _hash(
        str(profile),
        *source_hashes,
        str(len(router_records)),
        str(len(use_records)),
        best_entry.skill_key if best_entry else "missing_best_skill",
        decision,
        next_action,
        *reasons,
    )
    return CortexSkillUsageHistoryRecord(
        profile_path=str(profile),
        source_feedback_hashes=source_hashes,
        skill_count=len(entries),
        total_usage_count=total_usage_count,
        successful_usage_count=successful_usage_count,
        best_skill_key=best_entry.skill_key if best_entry else None,
        best_feedback_score=best_entry.average_feedback_score if best_entry else 0.0,
        history_entries=entries,
        history_status=status,
        history_decision=decision,
        history_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        history_hash=history_hash,
        reasons=reasons,
    )


def _entries(feedback_records: list[CortexMultiSkillFeedbackScoreRecord]) -> list[CortexSkillUsageHistoryEntry]:
    buckets: dict[str, list[CortexMultiSkillFeedbackScoreRecord]] = {}
    for record in feedback_records:
        if not record.selected_skill_key:
            continue
        buckets.setdefault(record.selected_skill_key, []).append(record)
    entries = []
    for skill_key, records in buckets.items():
        ordered = sorted(records, key=lambda item: item.created_at)
        last = ordered[-1]
        success_count = sum(1 for item in ordered if item.feedback_allowed and item.feedback_score >= 0.8)
        average_feedback_score = round(sum(item.feedback_score for item in ordered) / len(ordered), 4)
        entries.append(
            CortexSkillUsageHistoryEntry(
                skill_key=skill_key,
                domain=last.selected_domain,
                usage_count=len(ordered),
                success_count=success_count,
                average_feedback_score=average_feedback_score,
                last_feedback_score=last.feedback_score,
                last_router_hash=last.source_router_hash,
                last_use_hash=last.source_use_hash,
                last_feedback_hash=last.feedback_hash,
                last_seen_at=last.created_at,
            )
        )
    entries.sort(key=lambda item: (item.average_feedback_score, item.success_count, item.usage_count, item.skill_key), reverse=True)
    return entries


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
