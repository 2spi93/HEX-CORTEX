"""Regression tests for provenance fail-closed security fix.

These tests verify that the provenance validation fail-closed behavior is enforced:
1. No spine provided = ALL promotions rejected (fail-closed default)
2. Spine with missing events = rejected
3. Spine with tampered integrity = rejected
4. Spine with wrong task_id = rejected
5. Falsified ReplayReport (spine_integrity_ok=True but spine tampered) = rejected
6. explicit_approval=True CANNOT bypass spine/provenance requirements
7. Custom criteria CANNOT weaken spine requirements
8. Rejected operations leave index and promotion state unchanged
"""

from __future__ import annotations

from uuid import uuid4

from hex_cortex.memory.local_index import LocalKnowledgeIndex
from hex_cortex.memory.memory_promotion import (
    MemoryPromoter,
    PromotionCriteria,
    PromotionStatus,
    RejectionReason,
)
from hex_cortex.memory.schemas import MemoryRecord, MemorySensitivity
from hex_cortex.replay.replay_engine import ReplayEngine
from hex_cortex.replay.schemas import ReplayReport, ReplayStatus
from hex_cortex.spine.canonical_spine import CanonicalSpine


def _build_spine_with_task(task_id: str, event_count: int = 3) -> CanonicalSpine:
    """Build a spine with events for a specific task."""
    spine = CanonicalSpine()
    spine.append(
        event_type="task.received",
        task_id=task_id,
        source="test_harness",
        payload={"goal": "Test goal"},
        confidence=0.9,
    )
    for i in range(event_count - 1):
        spine.append(
            event_type="test.event",
            task_id=task_id,
            source="test",
            payload={"index": i},
            confidence=0.9,
        )
    spine.append(
        event_type="clock.completed",
        task_id=task_id,
        source="clock",
        payload={"completed": True},
        confidence=0.9,
    )
    return spine


def _create_memory_from_spine(spine: CanonicalSpine, task_id: str) -> MemoryRecord:
    """Create a valid memory from a spine."""
    event_ids = [event.event_id for event in spine.events]
    return MemoryRecord(
        title=f"Memory for {task_id}",
        body="Test content",
        tags=["test"],
        source_event_ids=event_ids,
        confidence=0.9,
        sensitivity=MemorySensitivity.LOW,
    )


# =============================================================================
# Test 1: FAIL-CLOSED - No spine provided = ALL rejected
# =============================================================================


def test_fail_closed_no_spine_rejects_all() -> None:
    """Verify that without a spine, ALL promotions are rejected (fail-closed)."""
    index = LocalKnowledgeIndex()

    # Create promoter WITHOUT spine (default require_spine=True)
    promoter = MemoryPromoter(index=index, spine=None)

    # Create a memory with fake event IDs
    memory = MemoryRecord(
        title="Orphan memory",
        body="No spine to verify against",
        tags=["test"],
        source_event_ids=["fake_event_1", "fake_event_2"],
        confidence=0.9,
    )

    result = promoter.promote_memory(memory)

    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.MISSING_PROVENANCE
    assert "spine_required_not_provided" in result.details.get("reason", "")
    assert result.bypassable is False
    assert len(index.entries) == 0  # Index unchanged


# =============================================================================
# Test 2: explicit_approval CANNOT bypass spine requirement
# =============================================================================


def test_explicit_approval_cannot_bypass_spine_requirement() -> None:
    """Verify that explicit_approval=True CANNOT bypass the spine requirement."""
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=None, require_spine=True)

    memory = MemoryRecord(
        title="Orphan memory",
        body="Testing bypass",
        tags=["test"],
        source_event_ids=["fake_event_1"],
        confidence=0.9,
    )

    # WITHOUT explicit_approval
    result1 = promoter.promote_memory(memory, explicit_approval=False)
    assert result1.status == PromotionStatus.REJECTED
    assert result1.rejection_reason == RejectionReason.MISSING_PROVENANCE

    # WITH explicit_approval (should STILL reject)
    result2 = promoter.promote_memory(memory, explicit_approval=True)
    assert result2.status == PromotionStatus.REJECTED
    assert result2.rejection_reason == RejectionReason.MISSING_PROVENANCE
    assert "spine_required_not_provided" in result2.details.get("reason", "")
    assert result2.bypassable is False
    assert len(index.entries) == 0  # Index unchanged


# =============================================================================
# Test 3: Spine with missing events = rejected
# =============================================================================


def test_spine_missing_events_rejected() -> None:
    """Verify that if source_event_ids reference events not in spine, reject."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_spine_with_task(task_id, event_count=3)
    promoter = MemoryPromoter(index=LocalKnowledgeIndex(), spine=spine)

    # Create memory with extra fake event IDs
    valid_event_ids = [event.event_id for event in spine.events]
    fake_event_ids = ["fake_evt_1", "fake_evt_2"]
    all_event_ids = valid_event_ids + fake_event_ids

    memory = MemoryRecord(
        title="Test memory",
        body="Test content",
        tags=["test"],
        source_event_ids=all_event_ids,  # Mix of valid and fake
        confidence=0.9,
    )

    result = promoter.promote_memory(memory)

    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.MISSING_PROVENANCE
    assert result.details.get("reason") == "source_events_not_in_spine"
    assert result.details.get("total_missing") == 2  # Both fake IDs missing
    assert result.bypassable is False


# =============================================================================
# Test 4: Spine with tampered integrity = rejected
# =============================================================================


def test_spine_tampered_integrity_rejected() -> None:
    """Verify that if spine integrity fails, all promotions are rejected."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_spine_with_task(task_id)

    # Tamper with spine AFTER creation
    if spine.events:
        spine._events[0].payload["tampered"] = True

    promoter = MemoryPromoter(index=LocalKnowledgeIndex(), spine=spine)

    # Even with valid-looking memory
    event_ids = [e.event_id for e in spine.events]
    memory = MemoryRecord(
        title="Test memory",
        body="Test",
        tags=["test"],
        source_event_ids=event_ids,
        confidence=0.9,
    )

    result = promoter.promote_memory(memory)

    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.MISSING_PROVENANCE
    assert result.details.get("reason") == "spine_integrity_verification_failed"
    assert "integrity_reason" in result.details
    assert result.bypassable is False


# =============================================================================
# Test 5: Falsified ReplayReport rejected even with spine_integrity_ok=True
# =============================================================================


def test_falsified_replay_report_rejected() -> None:
    """Verify that a ReplayReport claiming spine_integrity_ok=True when spine is tampered is rejected."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_spine_with_task(task_id)

    # Tamper with spine
    if spine.events:
        spine._events[0].payload["tampered"] = True

    promoter = MemoryPromoter(index=LocalKnowledgeIndex(), spine=spine)

    # Create a FALSIFIED report claiming integrity is OK
    memory = MemoryRecord(
        title="Test",
        body="Test",
        tags=[],
        source_event_ids=[e.event_id for e in spine.events],
        confidence=0.9,
    )

    falsified_report = ReplayReport(
        task_id=task_id,
        status=ReplayStatus.CONSOLIDATED,
        event_count=len(spine.events),
        spine_integrity_ok=True,  # FALSIFIED - claims OK but spine is tampered
        memory=memory,
    )

    result = promoter.promote_from_replay(falsified_report)

    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.INTEGRITY_FAILED
    assert result.details.get("reason") == "report_claims_integrity_but_spine_tampered"
    assert "actual_integrity_reason" in result.details
    assert result.bypassable is False


# =============================================================================
# Test 6: Custom criteria CANNOT weaken spine requirement
# =============================================================================


def test_custom_criteria_cannot_weaken_spine_requirement() -> None:
    """Verify that custom PromotionCriteria cannot weaken the spine requirement."""
    index = LocalKnowledgeIndex()

    # Create custom criteria that tries to disable source event requirement
    weak_criteria = PromotionCriteria(
        require_source_events=False,  # Try to disable
        min_confidence=0.0,
    )

    # But require_spine=True takes precedence
    promoter = MemoryPromoter(
        index=index,
        spine=None,  # No spine provided
        criteria=weak_criteria,
        require_spine=True,  # This takes precedence
    )

    memory = MemoryRecord(
        title="Test",
        body="Test",
        tags=[],
        source_event_ids=[],  # Empty
        confidence=0.9,
    )

    result = promoter.promote_memory(memory)

    # Should still reject because require_spine=True
    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.MISSING_PROVENANCE
    assert "spine_required" in result.details.get("reason", "")
    assert result.bypassable is False


# =============================================================================
# Test 7: Empty spine = rejected
# =============================================================================


def test_empty_spine_rejected() -> None:
    """Verify that an empty spine (no events) rejects all promotions."""
    spine = CanonicalSpine()  # Empty spine
    promoter = MemoryPromoter(index=LocalKnowledgeIndex(), spine=spine)

    memory = MemoryRecord(
        title="Test",
        body="Test",
        tags=[],
        source_event_ids=["evt_123"],  # References non-existent event
        confidence=0.9,
    )

    result = promoter.promote_memory(memory)

    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.MISSING_PROVENANCE
    assert result.details.get("reason") == "source_events_not_in_spine"
    assert result.bypassable is False


# =============================================================================
# Test 8: Wrong task_id in events = rejected (task coherence check)
# =============================================================================


def test_wrong_task_id_in_events() -> None:
    """Verify that modifying spine after creation breaks integrity (hash chain).

    This test demonstrates that the hash chain integrity check catches
    unauthorized modifications to the spine. When we append events from
    another spine, the hash chain is broken and promotion is rejected.
    """
    # Create spine for task A
    task_a = f"task_a_{uuid4().hex[:8]}"
    task_b = f"task_b_{uuid4().hex[:8]}"

    spine_a = _build_spine_with_task(task_a)
    spine_b = _build_spine_with_task(task_b)

    # Attempt to merge spines - this BREAKS the hash chain integrity
    for event in spine_b.events:
        spine_a._events.append(event)

    promoter = MemoryPromoter(index=LocalKnowledgeIndex(), spine=spine_a)

    # Get events from task A
    task_a_event_ids = [e.event_id for e in spine_a.events if e.task_id == task_a]

    memory = MemoryRecord(
        title="Test",
        body="Test",
        tags=[],
        source_event_ids=task_a_event_ids,
        confidence=0.9,
    )

    # Should FAIL because spine integrity is broken (hash chain mismatch)
    result = promoter.promote_memory(memory)

    # The hash chain integrity check catches the unauthorized modification
    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.MISSING_PROVENANCE
    assert "spine_integrity" in result.details.get("reason", "")
    assert result.bypassable is False
    assert len(promoter.index.entries) == 0  # Index unchanged


# =============================================================================
# Test 9: Rejected operations leave index unchanged
# =============================================================================


def test_rejected_operations_leave_index_unchanged() -> None:
    """Verify that all rejection scenarios leave the index unchanged."""
    index = LocalKnowledgeIndex()
    initial_count = len(index.entries)

    # Test 1: No spine
    promoter_no_spine = MemoryPromoter(index=index, spine=None)
    memory1 = MemoryRecord(
        title="Test", body="Test", tags=[], source_event_ids=["evt"], confidence=0.9
    )
    promoter_no_spine.promote_memory(memory1)
    assert len(index.entries) == initial_count

    # Test 2: Missing events
    spine = _build_spine_with_task("task_test")
    promoter_missing = MemoryPromoter(index=index, spine=spine)
    memory2 = MemoryRecord(
        title="Test", body="Test", tags=[], source_event_ids=["fake"], confidence=0.9
    )
    promoter_missing.promote_memory(memory2)
    assert len(index.entries) == initial_count

    # Test 3: Tampered spine
    spine_tampered = _build_spine_with_task("task_test2")
    if spine_tampered.events:
        spine_tampered._events[0].payload["tampered"] = True
    promoter_tampered = MemoryPromoter(index=index, spine=spine_tampered)
    memory3 = MemoryRecord(
        title="Test",
        body="Test",
        tags=[],
        source_event_ids=[e.event_id for e in spine_tampered.events],
        confidence=0.9,
    )
    promoter_tampered.promote_memory(memory3)
    assert len(index.entries) == initial_count


# =============================================================================
# Test 10: Valid promotion with spine succeeds
# =============================================================================


def test_valid_promotion_with_spine_succeeds() -> None:
    """Verify that valid memories with proper spine succeed."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_spine_with_task(task_id)
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine)

    memory = _create_memory_from_spine(spine, task_id)

    result = promoter.promote_memory(memory)

    assert result.status == PromotionStatus.PROMOTED
    assert result.bypassable is False
    assert len(index.entries) == 1
    # Spine integrity was verified during _validate_provenance (otherwise would reject)
    # Details may not include explicit integrity flag on success path


# =============================================================================
# Test 11: Partial provenance (some events exist) = rejected
# =============================================================================


def test_partial_provenance_rejected() -> None:
    """Verify that if only SOME source events exist in spine, reject."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_spine_with_task(task_id, event_count=3)
    promoter = MemoryPromoter(index=LocalKnowledgeIndex(), spine=spine)

    # Get some valid events and add fake ones
    valid_events = [e.event_id for e in spine.events][:2]  # Only first 2
    fake_events = ["fake_1", "fake_2"]

    memory = MemoryRecord(
        title="Test",
        body="Test",
        tags=[],
        source_event_ids=valid_events + fake_events,  # Mix
        confidence=0.9,
    )

    result = promoter.promote_memory(memory)

    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.MISSING_PROVENANCE
    assert result.details.get("reason") == "source_events_not_in_spine"
    assert result.details.get("total_missing") == 2  # Both fake events missing
    assert result.bypassable is False


# =============================================================================
# Test 12: promote_from_replay with None spine = rejected
# =============================================================================


def test_promote_from_replay_no_spine_rejected() -> None:
    """Verify that promote_from_replay rejects when spine is None."""
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=None, require_spine=True)

    # Create a valid-looking report
    memory = MemoryRecord(
        title="Test",
        body="Test",
        tags=[],
        source_event_ids=["evt_123"],
        confidence=0.9,
    )

    report = ReplayReport(
        task_id="test",
        status=ReplayStatus.CONSOLIDATED,
        event_count=1,
        spine_integrity_ok=True,
        memory=memory,
    )

    result = promoter.promote_from_replay(report)

    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.INTEGRITY_FAILED
    assert result.details.get("reason") == "spine_required_fail_closed"
    assert result.bypassable is False
# Review regressions: these cases were not covered by the original 1,690 tests.

def test_two_real_tasks_in_valid_spine_are_rejected() -> None:
    spine = CanonicalSpine()
    a = spine.append(event_type="task.received", task_id="task_A", source="test")
    b = spine.append(event_type="task.received", task_id="task_B", source="test")
    assert spine.verify_integrity().ok
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine)
    memory = MemoryRecord(title="Diagnostic technique", body="Observation de test", source_event_ids=[a.event_id, b.event_id], confidence=0.9)
    for approved in (False, True):
        result = promoter.promote_memory(memory, explicit_approval=approved)
        assert result.status == PromotionStatus.REJECTED
        assert result.rejection_reason == RejectionReason.MISSING_PROVENANCE
        assert result.details["reason"] == "source_events_mixed_tasks"
        assert result.bypassable is False
        assert index.entries == []
        assert promoter.get_promoted_ids() == set()


def test_single_task_sources_in_multitask_spine_are_permitted() -> None:
    spine = CanonicalSpine()
    a1 = spine.append(event_type="task.received", task_id="task_A", source="test")
    a2 = spine.append(event_type="clock.completed", task_id="task_A", source="test", payload={"completed": True})
    spine.append(event_type="task.received", task_id="task_B", source="test")
    memory = MemoryRecord(title="Diagnostic technique", body="Observation de test", source_event_ids=[a1.event_id, a2.event_id], confidence=0.9)
    index = LocalKnowledgeIndex()
    result = MemoryPromoter(index=index, spine=spine).promote_memory(memory)
    assert result.status == PromotionStatus.PROMOTED
    assert len(index.entries) == 1


def test_report_cannot_claim_other_task_or_episode() -> None:
    spine = _build_spine_with_task("task_A")
    report = ReplayEngine(spine=spine).replay_task("task_A")
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine)
    forged_task = report.model_copy(update={"task_id": "task_B"})
    forged_episode = report.model_copy(update={"episode": report.episode.model_copy(update={"task_id": "task_B"})})
    for forged in (forged_task, forged_episode):
        result = promoter.promote_from_replay(forged, explicit_approval=True)
        assert result.status == PromotionStatus.REJECTED
        assert result.rejection_reason == RejectionReason.MISSING_PROVENANCE
        assert not index.entries


def test_report_cannot_inject_fabricated_memory_text() -> None:
    spine = _build_spine_with_task("task_A")
    report = ReplayEngine(spine=spine).replay_task("task_A")
    fabricated_memory = report.memory.model_copy(update={"body": "Fabricated but innocent-looking content"})
    fabricated = report.model_copy(update={"memory": fabricated_memory})
    index = LocalKnowledgeIndex()
    result = MemoryPromoter(index=index, spine=spine).promote_from_replay(fabricated)
    assert result.status == PromotionStatus.REJECTED
    assert result.details["reason"] == "replay_report_content_mismatch"
    assert not index.entries


def test_report_cannot_attach_other_task_sources() -> None:
    spine = _build_spine_with_task("task_A")
    foreign = spine.append(event_type="task.received", task_id="task_B", source="test")
    report = ReplayEngine(spine=spine).replay_task("task_A")
    fabricated_memory = report.memory.model_copy(update={"source_event_ids": [*report.memory.source_event_ids, foreign.event_id]})
    fabricated = report.model_copy(update={"memory": fabricated_memory})
    index = LocalKnowledgeIndex()
    assert MemoryPromoter(index=index, spine=spine).promote_from_replay(fabricated).status == PromotionStatus.REJECTED
    assert not index.entries


def test_custom_flags_cannot_disable_mandatory_provenance() -> None:
    memory = MemoryRecord(title="Test memory", body="Safe observation", source_event_ids=[], confidence=0.9)
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=None, require_spine=False, criteria=PromotionCriteria(require_source_events=False))
    assert promoter.promote_memory(memory, explicit_approval=True).status == PromotionStatus.REJECTED
    spine = CanonicalSpine()
    promoter2 = MemoryPromoter(index=index, spine=spine, require_spine=False, criteria=PromotionCriteria(require_source_events=False))
    assert promoter2.promote_memory(memory, explicit_approval=True).status == PromotionStatus.REJECTED
    assert not index.entries


def test_replayed_memory_is_duplicate_in_new_promoter_on_same_index() -> None:
    spine = _build_spine_with_task("task_A")
    report_a = ReplayEngine(spine=spine).replay_task("task_A")
    report_b = ReplayEngine(spine=spine).replay_task("task_A")
    assert report_a.memory.memory_id != report_b.memory.memory_id
    index = LocalKnowledgeIndex()
    assert MemoryPromoter(index=index, spine=spine).promote_from_replay(report_a).status == PromotionStatus.PROMOTED
    result = MemoryPromoter(index=index, spine=spine).promote_from_replay(report_b)
    assert result.status == PromotionStatus.DUPLICATE
    assert len(index.entries) == 1


def test_index_metadata_preserves_sensitivity_and_complete_lineage() -> None:
    spine = _build_spine_with_task("task_A", event_count=12)
    memory = _create_memory_from_spine(spine, "task_A")
    index = LocalKnowledgeIndex()
    result = MemoryPromoter(index=index, spine=spine).promote_memory(memory)
    assert result.status == PromotionStatus.PROMOTED
    assert result.index_entry.metadata["sensitivity"] == "low"
    assert result.index_entry.metadata["source_event_ids"] == memory.source_event_ids
    assert "promotion_hash" in result.index_entry.metadata


def test_persistence_flag_cannot_cause_mutation_before_unimplemented_write() -> None:
    from hex_cortex.memory.memory_promotion import PersistenceNotImplementedError, PromotionSession
    import pytest

    spine = _build_spine_with_task("task_A")
    report = ReplayEngine(spine=spine).replay_task("task_A")
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine)
    session = PromotionSession(promoter=promoter, spine_store=None, promotion_log_path=None, _persistence_implemented=True)
    with pytest.raises(PersistenceNotImplementedError):
        session.promote_and_log(report, persist=True)
    assert index.entries == []
    assert promoter.get_promoted_ids() == set()
