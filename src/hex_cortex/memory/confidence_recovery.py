"""Recovery for memories previously affected by confidence decay."""

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

RECOVERY_REASON = "decay_recovered_by_retrieval"
DECAY_REASON = "stale_memory_confidence_decay"


class MemoryConfidenceRecoveryCandidate(BaseModel):
    """One memory eligible for confidence recovery after decay."""

    memory_id: str
    title: str
    confidence: float = Field(ge=0.0, le=1.0)
    access_count: int = Field(ge=0)
    total_decay_delta: float
    total_recovery_delta: float = Field(ge=0.0)
    unrecovered_decay: float = Field(ge=0.0)
    before_confidence: float = Field(ge=0.0, le=1.0)
    after_confidence: float = Field(ge=0.0, le=1.0)
    recovery_amount: float = Field(ge=0.0)
    reason: str = RECOVERY_REASON


class MemoryConfidenceRecoveryPlan(BaseModel):
    """Non-mutating plan for recovering decayed memory confidence."""

    total_memory_count: int = Field(ge=0)
    visible_memory_count: int = Field(ge=0)
    decayed_memory_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    recovery_amount: float = Field(ge=0.0)
    recovery_ceiling: float = Field(ge=0.0, le=1.0)
    candidates: list[MemoryConfidenceRecoveryCandidate]


class MemoryConfidenceRecoveryPlanner:
    """Plan confidence recovery for memories with unrecovered decay."""

    def __init__(
        self,
        *,
        recovery_amount: float = 0.02,
        recovery_ceiling: float = 0.7,
    ) -> None:
        if recovery_amount <= 0:
            raise ValueError("recovery_amount must be positive")
        if not 0 <= recovery_ceiling <= 1:
            raise ValueError("recovery_ceiling must be between 0 and 1")
        self.recovery_amount = recovery_amount
        self.recovery_ceiling = recovery_ceiling

    def plan(
        self,
        memories: list[MemoryRecord],
        audits: list[MemoryConfidenceAuditRecord],
        *,
        limit: int = 5,
    ) -> MemoryConfidenceRecoveryPlan:
        """Return recovery candidates for decayed memories."""

        if limit <= 0:
            raise ValueError("memory confidence recovery limit must be positive")

        visible_memories = [memory for memory in memories if memory.visible]
        recovery_state = _recovery_state_by_memory_id(audits)
        candidates = [
            candidate
            for memory in visible_memories
            if (candidate := self._candidate(memory, recovery_state)) is not None
        ]
        candidates.sort(
            key=lambda candidate: (
                -candidate.unrecovered_decay,
                candidate.confidence,
                candidate.memory_id,
            )
        )
        selected = candidates[:limit]
        return MemoryConfidenceRecoveryPlan(
            total_memory_count=len(memories),
            visible_memory_count=len(visible_memories),
            decayed_memory_count=sum(1 for state in recovery_state.values() if state["decay"] < 0),
            candidate_count=len(selected),
            recovery_amount=self.recovery_amount,
            recovery_ceiling=self.recovery_ceiling,
            candidates=selected,
        )

    def _candidate(
        self,
        memory: MemoryRecord,
        recovery_state: dict[str, dict[str, float]],
    ) -> MemoryConfidenceRecoveryCandidate | None:
        state = recovery_state.get(memory.memory_id)
        if state is None:
            return None
        total_decay_delta = round(state["decay"], 4)
        total_recovery_delta = round(state["recovery"], 4)
        unrecovered_decay = round(abs(total_decay_delta) - total_recovery_delta, 4)
        if unrecovered_decay <= 0:
            return None
        if memory.confidence >= self.recovery_ceiling:
            return None
        actual_recovery = min(
            self.recovery_amount,
            unrecovered_decay,
            round(self.recovery_ceiling - memory.confidence, 4),
        )
        actual_recovery = round(actual_recovery, 4)
        if actual_recovery <= 0:
            return None
        after_confidence = min(1.0, round(memory.confidence + actual_recovery, 4))
        return MemoryConfidenceRecoveryCandidate(
            memory_id=memory.memory_id,
            title=memory.title,
            confidence=memory.confidence,
            access_count=memory.access_count,
            total_decay_delta=total_decay_delta,
            total_recovery_delta=total_recovery_delta,
            unrecovered_decay=unrecovered_decay,
            before_confidence=memory.confidence,
            after_confidence=after_confidence,
            recovery_amount=actual_recovery,
        )


def run_memory_confidence_recovery_profile(
    profile: Path,
    *,
    limit: int = 5,
    recovery_amount: float = 0.02,
    recovery_ceiling: float = 0.7,
    dry_run: bool = True,
) -> dict[str, object]:
    """Run or preview memory confidence recovery for one profile."""

    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory_store = LocalMemoryJsonlStore(memory_path)
    audit_store = MemoryConfidenceAuditJsonlStore(audit_path)
    memories = memory_store.load()
    audits = audit_store.load()
    planner = MemoryConfidenceRecoveryPlanner(
        recovery_amount=recovery_amount,
        recovery_ceiling=recovery_ceiling,
    )
    plan = planner.plan(memories, audits, limit=limit)
    updated_memories = _apply_recovery_to_memory_records(memories, plan.candidates)
    audit_records = [
        MemoryConfidenceAuditRecord(
            memory_id=candidate.memory_id,
            reason=candidate.reason,
            before_confidence=candidate.before_confidence,
            after_confidence=candidate.after_confidence,
            delta=candidate.recovery_amount,
            changed=True,
            before_access_count=candidate.access_count,
            after_access_count=candidate.access_count + 1,
        )
        for candidate in plan.candidates
    ]
    audit_count_before = len(audits)
    audit_count_after = audit_count_before
    if not dry_run:
        memory_store.save(updated_memories)
        for record in audit_records:
            audit_count_after = audit_store.append(record)

    return {
        "recovery_type": "memory_confidence_profile",
        "profile_path": str(profile),
        "memory_path": str(memory_path),
        "audit_path": str(audit_path),
        "dry_run": dry_run,
        "applied": not dry_run,
        "limit": limit,
        "recovery_amount": recovery_amount,
        "recovery_ceiling": recovery_ceiling,
        "decayed_memory_count": plan.decayed_memory_count,
        "candidate_count": plan.candidate_count,
        "recovered_count": len(plan.candidates),
        "audit_records_written": 0 if dry_run else len(audit_records),
        "audit_record_count_before": audit_count_before,
        "audit_record_count_after": audit_count_after,
        "candidates": [candidate.model_dump(mode="json") for candidate in plan.candidates],
    }


def _recovery_state_by_memory_id(
    audits: list[MemoryConfidenceAuditRecord],
) -> dict[str, dict[str, float]]:
    state: dict[str, dict[str, float]] = {}
    for audit in audits:
        memory_state = state.setdefault(audit.memory_id, {"decay": 0.0, "recovery": 0.0})
        if audit.reason == DECAY_REASON and audit.delta < 0:
            memory_state["decay"] = round(memory_state["decay"] + audit.delta, 4)
        if audit.reason == RECOVERY_REASON and audit.delta > 0:
            memory_state["recovery"] = round(memory_state["recovery"] + audit.delta, 4)
    return state


def _apply_recovery_to_memory_records(
    memories: list[MemoryRecord],
    candidates: list[MemoryConfidenceRecoveryCandidate],
) -> list[MemoryRecord]:
    candidate_by_id = {candidate.memory_id: candidate for candidate in candidates}
    now = datetime.now(UTC).isoformat()
    updated = []
    for memory in memories:
        candidate = candidate_by_id.get(memory.memory_id)
        if candidate is None:
            updated.append(memory.model_copy(deep=True))
            continue
        updated.append(
            memory.model_copy(
                update={
                    "confidence": candidate.after_confidence,
                    "access_count": memory.access_count + 1,
                    "last_accessed_at": now,
                },
                deep=True,
            )
        )
    return updated
