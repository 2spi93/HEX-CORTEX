"""Temporal decay for memory confidence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from hex_cortex.memory.confidence import (
    MemoryConfidenceAuditJsonlStore,
    MemoryConfidenceAuditRecord,
)
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


class MemoryConfidenceDecayCandidate(BaseModel):
    """One memory eligible for temporal confidence decay."""

    memory_id: str
    title: str
    confidence: float = Field(ge=0.0, le=1.0)
    access_count: int = Field(ge=0)
    last_accessed_at: str
    days_since_last_access: float = Field(ge=0.0)
    before_confidence: float = Field(ge=0.0, le=1.0)
    after_confidence: float = Field(ge=0.0, le=1.0)
    decay_amount: float = Field(ge=0.0)
    reason: str


class MemoryConfidenceDecayPlan(BaseModel):
    """Non-mutating plan for temporal confidence decay."""

    total_memory_count: int = Field(ge=0)
    visible_memory_count: int = Field(ge=0)
    stale_memory_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    stale_after_days: int = Field(ge=0)
    decay_amount: float = Field(ge=0.0)
    minimum_confidence: float = Field(ge=0.0, le=1.0)
    candidates: list[MemoryConfidenceDecayCandidate]


class MemoryConfidenceDecayPlanner:
    """Plan confidence decay for stale memories."""

    def __init__(
        self,
        *,
        stale_after_days: int = 30,
        decay_amount: float = 0.05,
        minimum_confidence: float = 0.3,
        now: datetime | None = None,
    ) -> None:
        if stale_after_days < 0:
            raise ValueError("stale_after_days must be non-negative")
        if decay_amount <= 0:
            raise ValueError("decay_amount must be positive")
        if not 0 <= minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be between 0 and 1")
        self.stale_after_days = stale_after_days
        self.decay_amount = decay_amount
        self.minimum_confidence = minimum_confidence
        self.now = now or datetime.now(UTC)

    def plan(self, memories: list[MemoryRecord], *, limit: int = 5) -> MemoryConfidenceDecayPlan:
        """Return stale memory confidence decay candidates."""

        if limit <= 0:
            raise ValueError("memory confidence decay limit must be positive")

        visible_memories = [memory for memory in memories if memory.visible]
        candidates = [
            candidate
            for memory in visible_memories
            if (candidate := self._candidate(memory)) is not None
        ]
        candidates.sort(
            key=lambda candidate: (
                -candidate.days_since_last_access,
                -candidate.confidence,
                candidate.memory_id,
            )
        )
        selected = candidates[:limit]
        return MemoryConfidenceDecayPlan(
            total_memory_count=len(memories),
            visible_memory_count=len(visible_memories),
            stale_memory_count=len(candidates),
            candidate_count=len(selected),
            stale_after_days=self.stale_after_days,
            decay_amount=self.decay_amount,
            minimum_confidence=self.minimum_confidence,
            candidates=selected,
        )

    def _candidate(self, memory: MemoryRecord) -> MemoryConfidenceDecayCandidate | None:
        if memory.last_accessed_at is None:
            return None
        last_accessed = _parse_timestamp(memory.last_accessed_at)
        days_since_last_access = (self.now - last_accessed).total_seconds() / 86_400
        if days_since_last_access < self.stale_after_days:
            return None
        if memory.confidence <= self.minimum_confidence:
            return None
        after_confidence = max(
            self.minimum_confidence,
            round(memory.confidence - self.decay_amount, 4),
        )
        actual_decay = round(memory.confidence - after_confidence, 4)
        if actual_decay <= 0:
            return None
        return MemoryConfidenceDecayCandidate(
            memory_id=memory.memory_id,
            title=memory.title,
            confidence=memory.confidence,
            access_count=memory.access_count,
            last_accessed_at=memory.last_accessed_at,
            days_since_last_access=round(days_since_last_access, 4),
            before_confidence=memory.confidence,
            after_confidence=after_confidence,
            decay_amount=actual_decay,
            reason="stale_memory_confidence_decay",
        )


def run_memory_confidence_decay_profile(
    profile: Path,
    *,
    limit: int = 5,
    stale_after_days: int = 30,
    decay_amount: float = 0.05,
    minimum_confidence: float = 0.3,
    dry_run: bool = True,
) -> dict[str, object]:
    """Run or preview temporal memory confidence decay for one profile."""

    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory_store = LocalMemoryJsonlStore(memory_path)
    memories = memory_store.load()
    planner = MemoryConfidenceDecayPlanner(
        stale_after_days=stale_after_days,
        decay_amount=decay_amount,
        minimum_confidence=minimum_confidence,
    )
    plan = planner.plan(memories, limit=limit)
    updated_memories = _apply_decay_to_memory_records(memories, plan.candidates)
    audit_records = [
        MemoryConfidenceAuditRecord(
            memory_id=candidate.memory_id,
            reason=candidate.reason,
            before_confidence=candidate.before_confidence,
            after_confidence=candidate.after_confidence,
            delta=round(candidate.after_confidence - candidate.before_confidence, 4),
            changed=True,
            before_access_count=candidate.access_count,
            after_access_count=candidate.access_count,
        )
        for candidate in plan.candidates
    ]
    audit_count_before = len(MemoryConfidenceAuditJsonlStore(audit_path).load())
    audit_count_after = audit_count_before
    if not dry_run:
        memory_store.save(updated_memories)
        audit_store = MemoryConfidenceAuditJsonlStore(audit_path)
        for record in audit_records:
            audit_count_after = audit_store.append(record)

    return {
        "decay_type": "memory_confidence_profile",
        "profile_path": str(profile),
        "memory_path": str(memory_path),
        "audit_path": str(audit_path),
        "dry_run": dry_run,
        "applied": not dry_run,
        "limit": limit,
        "stale_after_days": stale_after_days,
        "decay_amount": decay_amount,
        "minimum_confidence": minimum_confidence,
        "stale_memory_count": plan.stale_memory_count,
        "candidate_count": plan.candidate_count,
        "decayed_count": len(plan.candidates),
        "audit_records_written": 0 if dry_run else len(audit_records),
        "audit_record_count_before": audit_count_before,
        "audit_record_count_after": audit_count_after,
        "candidates": [candidate.model_dump(mode="json") for candidate in plan.candidates],
    }


def _apply_decay_to_memory_records(
    memories: list[MemoryRecord],
    candidates: list[MemoryConfidenceDecayCandidate],
) -> list[MemoryRecord]:
    candidate_by_id = {candidate.memory_id: candidate for candidate in candidates}
    return [
        memory.model_copy(update={"confidence": candidate_by_id[memory.memory_id].after_confidence})
        if memory.memory_id in candidate_by_id
        else memory.model_copy(deep=True)
        for memory in memories
    ]


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
