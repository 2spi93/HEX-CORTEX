"""Batch runner for memory confidence confirmations."""

from __future__ import annotations

from pathlib import Path

from hex_cortex.memory.confidence import (
    MemoryConfidenceAuditJsonlStore,
    MemoryConfidenceAuditRecord,
    MemoryConfidencePlanner,
    MemoryConfidenceUpdater,
)
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore


def run_memory_confidence_batch_profile(
    profile: Path,
    *,
    limit: int = 3,
    reason: str = "batch_confirmed",
    delta: float = 0.05,
    dry_run: bool = True,
    max_total_delta: float = 0.15,
    min_priority_score: float = 0.0,
) -> dict[str, object]:
    """Run or preview a batch of memory confidence confirmations."""

    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory_store = LocalMemoryJsonlStore(memory_path)
    memories = memory_store.load()
    plan = MemoryConfidencePlanner().plan(memories, limit=limit)
    candidates = [
        candidate
        for candidate in plan.candidates
        if candidate.priority_score >= min_priority_score
    ]
    working_memories = memories
    reports = []
    audit_records = []
    updater = MemoryConfidenceUpdater(delta=delta)

    for candidate in candidates:
        working_memories, report = updater.confirm(
            working_memories,
            memory_id=candidate.memory_id,
            reason=reason,
        )
        reports.append(report)
        if report.found:
            audit_records.append(
                MemoryConfidenceAuditRecord(
                    memory_id=candidate.memory_id,
                    reason=reason,
                    before_confidence=report.before_confidence or 0.0,
                    after_confidence=report.after_confidence or 0.0,
                    delta=report.delta,
                    changed=report.changed,
                    before_access_count=report.before_access_count or 0,
                    after_access_count=report.after_access_count or 0,
                )
            )

    total_delta = round(sum(report.delta for report in reports), 4)
    apply_blocked_reason = _apply_blocked_reason(
        total_delta=total_delta,
        max_total_delta=max_total_delta,
        candidate_count=len(candidates),
    )
    can_apply = not dry_run and apply_blocked_reason is None
    audit_count_before = len(MemoryConfidenceAuditJsonlStore(audit_path).load())
    audit_count_after = audit_count_before
    if can_apply:
        memory_store.save(working_memories)
        audit_store = MemoryConfidenceAuditJsonlStore(audit_path)
        for record in audit_records:
            audit_count_after = audit_store.append(record)

    return {
        "batch_type": "memory_confidence_profile",
        "profile_path": str(profile),
        "memory_path": str(memory_path),
        "audit_path": str(audit_path),
        "dry_run": dry_run,
        "applied": can_apply,
        "apply_blocked_reason": apply_blocked_reason,
        "limit": limit,
        "reason": reason,
        "delta": delta,
        "max_total_delta": max_total_delta,
        "min_priority_score": min_priority_score,
        "total_delta": total_delta,
        "candidate_count": plan.candidate_count,
        "eligible_candidate_count": len(candidates),
        "confirmed_count": sum(1 for report in reports if report.found),
        "changed_count": sum(1 for report in reports if report.changed),
        "audit_records_written": len(audit_records) if can_apply else 0,
        "audit_record_count_before": audit_count_before,
        "audit_record_count_after": audit_count_after,
        "reports": [report.model_dump(mode="json") for report in reports],
        "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
    }


def _apply_blocked_reason(
    *,
    total_delta: float,
    max_total_delta: float,
    candidate_count: int,
) -> str | None:
    if candidate_count == 0:
        return "no_eligible_candidates"
    if total_delta > max_total_delta:
        return "max_total_delta_exceeded"
    return None
