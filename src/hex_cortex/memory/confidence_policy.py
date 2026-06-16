"""Unified policy for memory confidence maintenance."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from hex_cortex.memory.confidence import (
    MemoryConfidenceAuditJsonlStore,
    MemoryConfidenceAuditRecord,
    MemoryConfidencePlanner,
)
from hex_cortex.memory.confidence_decay import MemoryConfidenceDecayPlanner
from hex_cortex.memory.confidence_recovery import MemoryConfidenceRecoveryPlanner
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord

CONFIRMATION_REASON = "policy_retrieval_confirmed"


class MemoryConfidencePolicyActionType(StrEnum):
    """Supported confidence policy action types."""

    RECOVERY = "recovery"
    CONFIRMATION = "confirmation"
    DECAY = "decay"


class MemoryConfidencePolicyAction(BaseModel):
    """One selected confidence policy action."""

    action_type: MemoryConfidencePolicyActionType
    memory_id: str
    title: str
    reason: str
    before_confidence: float = Field(ge=0.0, le=1.0)
    after_confidence: float = Field(ge=0.0, le=1.0)
    delta: float
    before_access_count: int = Field(ge=0)
    after_access_count: int = Field(ge=0)


class MemoryConfidencePolicyReport(BaseModel):
    """Report for a unified confidence policy run."""

    policy_type: str = "memory_confidence_profile"
    profile_path: str
    memory_path: str
    audit_path: str
    dry_run: bool
    applied: bool
    limit: int = Field(ge=1)
    max_total_positive_delta: float = Field(ge=0.0)
    max_total_negative_delta: float = Field(ge=0.0)
    max_total_operations: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    selected_action_count: int = Field(ge=0)
    skipped_action_count: int = Field(ge=0)
    total_positive_delta: float
    total_negative_delta: float
    net_delta: float
    audit_records_written: int = Field(ge=0)
    audit_record_count_before: int = Field(ge=0)
    audit_record_count_after: int = Field(ge=0)
    actions: list[MemoryConfidencePolicyAction]
    skipped_actions: list[MemoryConfidencePolicyAction]


def run_memory_confidence_policy_profile(
    profile: Path,
    *,
    limit: int = 5,
    max_total_positive_delta: float = 0.1,
    max_total_negative_delta: float = 0.05,
    max_total_operations: int = 5,
    confirmation_delta: float = 0.05,
    saturation_threshold: float = 0.7,
    min_priority_score: float = 0.0,
    recovery_amount: float = 0.02,
    recovery_ceiling: float = 0.7,
    stale_after_days: int = 30,
    decay_amount: float = 0.05,
    minimum_confidence: float = 0.3,
    dry_run: bool = True,
) -> dict[str, object]:
    """Run or preview a unified confidence maintenance policy."""

    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory_store = LocalMemoryJsonlStore(memory_path)
    audit_store = MemoryConfidenceAuditJsonlStore(audit_path)
    memories = memory_store.load()
    audits = audit_store.load()
    candidates = _policy_candidates(
        memories,
        audits,
        limit=limit,
        confirmation_delta=confirmation_delta,
        saturation_threshold=saturation_threshold,
        min_priority_score=min_priority_score,
        recovery_amount=recovery_amount,
        recovery_ceiling=recovery_ceiling,
        stale_after_days=stale_after_days,
        decay_amount=decay_amount,
        minimum_confidence=minimum_confidence,
    )
    actions, skipped_actions = _select_actions(
        candidates,
        max_total_positive_delta=max_total_positive_delta,
        max_total_negative_delta=max_total_negative_delta,
        max_total_operations=max_total_operations,
    )
    audit_count_before = len(audits)
    audit_count_after = audit_count_before
    if not dry_run:
        memory_store.save(_apply_policy_actions(memories, actions))
        for action in actions:
            audit_count_after = audit_store.append(_audit_record_from_action(action))

    total_positive_delta = round(sum(action.delta for action in actions if action.delta > 0), 4)
    total_negative_delta = round(sum(action.delta for action in actions if action.delta < 0), 4)
    report = MemoryConfidencePolicyReport(
        profile_path=str(profile),
        memory_path=str(memory_path),
        audit_path=str(audit_path),
        dry_run=dry_run,
        applied=not dry_run,
        limit=limit,
        max_total_positive_delta=max_total_positive_delta,
        max_total_negative_delta=max_total_negative_delta,
        max_total_operations=max_total_operations,
        candidate_count=len(candidates),
        selected_action_count=len(actions),
        skipped_action_count=len(skipped_actions),
        total_positive_delta=total_positive_delta,
        total_negative_delta=total_negative_delta,
        net_delta=round(total_positive_delta + total_negative_delta, 4),
        audit_records_written=0 if dry_run else len(actions),
        audit_record_count_before=audit_count_before,
        audit_record_count_after=audit_count_after,
        actions=actions,
        skipped_actions=skipped_actions,
    )
    return report.model_dump(mode="json")


def _policy_candidates(
    memories: list[MemoryRecord],
    audits: list[MemoryConfidenceAuditRecord],
    *,
    limit: int,
    confirmation_delta: float,
    saturation_threshold: float,
    min_priority_score: float,
    recovery_amount: float,
    recovery_ceiling: float,
    stale_after_days: int,
    decay_amount: float,
    minimum_confidence: float,
) -> list[MemoryConfidencePolicyAction]:
    memory_by_id = {memory.memory_id: memory for memory in memories}
    selected_memory_ids: set[str] = set()
    actions: list[MemoryConfidencePolicyAction] = []

    recovery_plan = MemoryConfidenceRecoveryPlanner(
        recovery_amount=recovery_amount,
        recovery_ceiling=recovery_ceiling,
    ).plan(memories, audits, limit=limit)
    for candidate in recovery_plan.candidates:
        memory = memory_by_id[candidate.memory_id]
        actions.append(
            MemoryConfidencePolicyAction(
                action_type=MemoryConfidencePolicyActionType.RECOVERY,
                memory_id=candidate.memory_id,
                title=candidate.title,
                reason=candidate.reason,
                before_confidence=candidate.before_confidence,
                after_confidence=candidate.after_confidence,
                delta=candidate.recovery_amount,
                before_access_count=memory.access_count,
                after_access_count=memory.access_count + 1,
            )
        )
        selected_memory_ids.add(candidate.memory_id)

    confirmation_plan = MemoryConfidencePlanner(
        confidence_floor=saturation_threshold,
    ).plan(memories, limit=limit)
    for candidate in confirmation_plan.candidates:
        if candidate.memory_id in selected_memory_ids:
            continue
        if candidate.priority_score < min_priority_score:
            continue
        memory = memory_by_id[candidate.memory_id]
        after_confidence = min(1.0, round(memory.confidence + confirmation_delta, 4))
        delta = round(after_confidence - memory.confidence, 4)
        if delta <= 0:
            continue
        actions.append(
            MemoryConfidencePolicyAction(
                action_type=MemoryConfidencePolicyActionType.CONFIRMATION,
                memory_id=candidate.memory_id,
                title=candidate.title,
                reason=CONFIRMATION_REASON,
                before_confidence=memory.confidence,
                after_confidence=after_confidence,
                delta=delta,
                before_access_count=memory.access_count,
                after_access_count=memory.access_count + 1,
            )
        )
        selected_memory_ids.add(candidate.memory_id)

    decay_plan = MemoryConfidenceDecayPlanner(
        stale_after_days=stale_after_days,
        decay_amount=decay_amount,
        minimum_confidence=minimum_confidence,
    ).plan(memories, limit=limit)
    for candidate in decay_plan.candidates:
        if candidate.memory_id in selected_memory_ids:
            continue
        memory = memory_by_id[candidate.memory_id]
        actions.append(
            MemoryConfidencePolicyAction(
                action_type=MemoryConfidencePolicyActionType.DECAY,
                memory_id=candidate.memory_id,
                title=candidate.title,
                reason=candidate.reason,
                before_confidence=candidate.before_confidence,
                after_confidence=candidate.after_confidence,
                delta=round(candidate.after_confidence - candidate.before_confidence, 4),
                before_access_count=memory.access_count,
                after_access_count=memory.access_count,
            )
        )
        selected_memory_ids.add(candidate.memory_id)

    return actions


def _select_actions(
    candidates: list[MemoryConfidencePolicyAction],
    *,
    max_total_positive_delta: float,
    max_total_negative_delta: float,
    max_total_operations: int,
) -> tuple[list[MemoryConfidencePolicyAction], list[MemoryConfidencePolicyAction]]:
    selected: list[MemoryConfidencePolicyAction] = []
    skipped: list[MemoryConfidencePolicyAction] = []
    positive_delta = 0.0
    negative_delta = 0.0
    for action in candidates:
        if len(selected) >= max_total_operations:
            skipped.append(action)
            continue
        if action.delta > 0:
            next_positive = round(positive_delta + action.delta, 4)
            if next_positive > max_total_positive_delta:
                skipped.append(action)
                continue
            positive_delta = next_positive
        if action.delta < 0:
            next_negative = round(negative_delta + abs(action.delta), 4)
            if next_negative > max_total_negative_delta:
                skipped.append(action)
                continue
            negative_delta = next_negative
        selected.append(action)
    return selected, skipped


def _apply_policy_actions(
    memories: list[MemoryRecord],
    actions: list[MemoryConfidencePolicyAction],
) -> list[MemoryRecord]:
    action_by_id = {action.memory_id: action for action in actions}
    now = datetime.now(UTC).isoformat()
    updated = []
    for memory in memories:
        action = action_by_id.get(memory.memory_id)
        if action is None:
            updated.append(memory.model_copy(deep=True))
            continue
        update = {"confidence": action.after_confidence}
        if action.action_type in {
            MemoryConfidencePolicyActionType.RECOVERY,
            MemoryConfidencePolicyActionType.CONFIRMATION,
        }:
            update["access_count"] = action.after_access_count
            update["last_accessed_at"] = now
        updated.append(memory.model_copy(update=update, deep=True))
    return updated


def _audit_record_from_action(action: MemoryConfidencePolicyAction) -> MemoryConfidenceAuditRecord:
    return MemoryConfidenceAuditRecord(
        memory_id=action.memory_id,
        reason=action.reason,
        before_confidence=action.before_confidence,
        after_confidence=action.after_confidence,
        delta=action.delta,
        changed=True,
        before_access_count=action.before_access_count,
        after_access_count=action.after_access_count,
    )
