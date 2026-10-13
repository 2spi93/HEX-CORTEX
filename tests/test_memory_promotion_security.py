"""Security tests for memory promotion - non-bypass guarantees.

These tests verify that:
1. read_only=True ALWAYS prevents index mutation, even with explicit_approval
2. Integrity, provenance, content bans, and sensitivity are NEVER bypassed
3. Only LOW_CONFIDENCE can be bypassed with explicit_approval
4. Rejected operations leave the index unchanged
5. persist=True raises error when persistence is not implemented
6. All source events must exist in spine (not just some)
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from hex_cortex.memory.local_index import LocalKnowledgeIndex
from hex_cortex.memory.memory_promotion import (
    MemoryPromoter,
    PersistenceNotImplementedError,
    PromotionCriteria,
    PromotionSession,
    PromotionStatus,
    RejectionReason,
    _sensitivity_exceeds_limit,
)
from hex_cortex.memory.schemas import (
    MemoryRecord,
    MemorySensitivity,
    MemoryType,
)
from hex_cortex.replay.replay_engine import ReplayEngine
from hex_cortex.replay.schemas import ReplayReport, ReplayStatus
from hex_cortex.spine.canonical_spine import CanonicalSpine


def _build_spine_with_events(task_id: str, event_count: int = 3) -> CanonicalSpine:
    """Build a spine with a known number of events."""
    spine = CanonicalSpine()
    for i in range(event_count):
        spine.append(
            event_type="test.event",
            task_id=task_id,
            source="test",
            payload={"index": i},
            confidence=0.9,
        )
    return spine


def _create_valid_memory(
    task_id: str,
    spine: CanonicalSpine,
    confidence: float = 0.9,
    sensitivity: MemorySensitivity = MemorySensitivity.LOW,
    memory_type: MemoryType = MemoryType.EPISODE,
) -> MemoryRecord:
    """Create a valid memory record from a spine."""
    event_ids = [event.event_id for event in spine.events]
    return MemoryRecord(
        title=f"Test memory for {task_id}",
        body="Test content without sensitive patterns",
        tags=["test"],
        source_event_ids=event_ids,
        confidence=confidence,
        sensitivity=sensitivity,
        memory_type=memory_type,
    )


# =============================================================================
# Test 1: read_only=True ALWAYS prevents mutation (even with explicit_approval)
# =============================================================================


def test_read_only_never_bypassed_by_explicit_approval() -> None:
    """Verify that read_only=True prevents ALL mutations, even with explicit_approval=True."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_spine_with_events(task_id)
    memory = _create_valid_memory(task_id, spine)

    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine, read_only=True)

    initial_count = len(index.entries)

    # Attempt promotion WITHOUT explicit_approval
    result1 = promoter.promote_memory(memory, explicit_approval=False)
    assert result1.status == PromotionStatus.REJECTED
    assert result1.rejection_reason == RejectionReason.READ_ONLY_MODE
    assert result1.bypassable is False
    assert len(index.entries) == initial_count  # Unchanged

    # Attempt promotion WITH explicit_approval (should STILL be rejected)
    result2 = promoter.promote_memory(memory, explicit_approval=True)
    assert result2.status == PromotionStatus.REJECTED
    assert result2.rejection_reason == RejectionReason.READ_ONLY_MODE
    assert result2.bypassable is False
    assert len(index.entries) == initial_count  # Still unchanged


# =============================================================================
# Test 2: Integrity check is NEVER bypassed
# =============================================================================


def test_integrity_check_never_bypassed() -> None:
    """Verify that integrity failures cannot be bypassed with explicit_approval."""
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, read_only=False)

    # Create a replay report with failed status
    replay_report = ReplayReport(
        task_id="test_task",
        status=ReplayStatus.INTEGRITY_FAILED,  # Failed integrity
        event_count=0,
        spine_integrity_ok=False,
        reason="hash_mismatch",
    )

    # Attempt without explicit_approval
    result1 = promoter.promote_from_replay(replay_report, explicit_approval=False)
    assert result1.status == PromotionStatus.REJECTED
    assert result1.rejection_reason == RejectionReason.INTEGRITY_FAILED
    assert result1.bypassable is False

    # Attempt WITH explicit_approval (should STILL be rejected)
    result2 = promoter.promote_from_replay(replay_report, explicit_approval=True)
    assert result2.status == PromotionStatus.REJECTED
    assert result2.rejection_reason == RejectionReason.INTEGRITY_FAILED
    assert result2.bypassable is False


# =============================================================================
# Test 3: Provenance check is NEVER bypassed
# =============================================================================


def test_provenance_check_never_bypassed() -> None:
    """Verify that missing provenance cannot be bypassed with explicit_approval."""
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, read_only=False)

    # Create memory without source events
    memory = MemoryRecord(
        title="Orphan memory",
        body="No provenance",
        tags=["test"],
        source_event_ids=[],  # Empty!
        confidence=0.9,
    )

    initial_count = len(index.entries)

    # Attempt without explicit_approval
    result1 = promoter.promote_memory(memory, explicit_approval=False)
    assert result1.status == PromotionStatus.REJECTED
    assert result1.rejection_reason == RejectionReason.MISSING_PROVENANCE
    assert result1.bypassable is False
    assert len(index.entries) == initial_count

    # Attempt WITH explicit_approval (should STILL be rejected)
    result2 = promoter.promote_memory(memory, explicit_approval=True)
    assert result2.status == PromotionStatus.REJECTED
    assert result2.rejection_reason == RejectionReason.MISSING_PROVENANCE
    assert result2.bypassable is False
    assert len(index.entries) == initial_count


# =============================================================================
# Test 4: Content bans are NEVER bypassed
# =============================================================================


def test_content_bans_never_bypassed() -> None:
    """Verify that inadmissible content cannot be bypassed with explicit_approval."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_spine_with_events(task_id)
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine, read_only=False)

    # Create memory with sensitive content BUT with valid source_event_ids from spine
    event_ids = [e.event_id for e in spine.events]
    memory = MemoryRecord(
        title="API Configuration",
        body="The password is secret123 and api_key is sk-1234",
        tags=["config"],
        source_event_ids=event_ids,  # Valid events from spine
        confidence=0.9,
    )

    initial_count = len(index.entries)

    # Attempt without explicit_approval
    result1 = promoter.promote_memory(memory, explicit_approval=False)
    assert result1.status == PromotionStatus.REJECTED
    assert result1.rejection_reason == RejectionReason.INADMISSIBLE_CONTENT
    assert result1.bypassable is False
    assert len(index.entries) == initial_count

    # Attempt WITH explicit_approval (should STILL be rejected)
    result2 = promoter.promote_memory(memory, explicit_approval=True)
    assert result2.status == PromotionStatus.REJECTED
    assert result2.rejection_reason == RejectionReason.INADMISSIBLE_CONTENT
    assert result2.bypassable is False
    assert len(index.entries) == initial_count


# =============================================================================
# Test 5: Sensitivity ceiling is NEVER bypassed
# =============================================================================


def test_sensitivity_ceiling_never_bypassed() -> None:
    """Verify that sensitivity violations cannot be bypassed with explicit_approval."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_spine_with_events(task_id)
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(
        index=index,
        spine=spine,  # Need spine for valid provenance
        criteria=PromotionCriteria(max_sensitivity=MemorySensitivity.MEDIUM),
    )

    # Create HIGH sensitivity memory with valid source_event_ids
    event_ids = [e.event_id for e in spine.events]
    memory = MemoryRecord(
        title="Sensitive data",
        body="Contains sensitive information",
        tags=["test"],
        source_event_ids=event_ids,  # Valid events
        confidence=0.9,
        sensitivity=MemorySensitivity.HIGH,  # Above ceiling
    )

    initial_count = len(index.entries)

    # Attempt without explicit_approval
    result1 = promoter.promote_memory(memory, explicit_approval=False)
    assert result1.status == PromotionStatus.REJECTED
    assert result1.rejection_reason == RejectionReason.SENSITIVE_CONTENT
    assert result1.bypassable is False
    assert len(index.entries) == initial_count

    # Attempt WITH explicit_approval (should STILL be rejected)
    result2 = promoter.promote_memory(memory, explicit_approval=True)
    assert result2.status == PromotionStatus.REJECTED
    assert result2.rejection_reason == RejectionReason.SENSITIVE_CONTENT
    assert result2.bypassable is False
    assert len(index.entries) == initial_count


# =============================================================================
# Test 6: Only LOW_CONFIDENCE can be bypassed
# =============================================================================


def test_only_low_confidence_bypassable() -> None:
    """Verify that LOW_CONFIDENCE is the ONLY bypassable check."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_spine_with_events(task_id)
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine, read_only=False)

    # Create low confidence memory with valid source_event_ids
    event_ids = [e.event_id for e in spine.events]
    memory = MemoryRecord(
        title="Uncertain memory",
        body="Might be useful",
        tags=["test"],
        source_event_ids=event_ids,  # Valid events
        confidence=0.3,  # Below threshold
        sensitivity=MemorySensitivity.LOW,
    )

    # Without explicit_approval: DEFERRED
    result1 = promoter.promote_memory(memory, explicit_approval=False)
    assert result1.status == PromotionStatus.DEFERRED
    assert result1.rejection_reason == RejectionReason.LOW_CONFIDENCE
    assert result1.bypassable is True

    # With explicit_approval: PROMOTED
    result2 = promoter.promote_memory(memory, explicit_approval=True)
    assert result2.status == PromotionStatus.PROMOTED
    assert result2.bypassable is False  # Promotion succeeded
    assert len(index.entries) == 1


# =============================================================================
# Test 7: Rejected operations leave index unchanged
# =============================================================================


def test_rejected_operations_leave_index_unchanged() -> None:
    """Verify that all rejection paths leave the index unchanged."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_spine_with_events(task_id)
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine, read_only=False)

    initial_count = len(index.entries)
    event_ids = [e.event_id for e in spine.events]

    # Test each rejection reason (all with valid source_event_ids from spine)
    rejection_tests = [
        # Inadmissible content
        MemoryRecord(
            title="Test",
            body="password: secret123",
            tags=[],
            source_event_ids=event_ids,
            confidence=0.9,
        ),
        # Sensitivity violation
        MemoryRecord(
            title="Test",
            body="Test",
            tags=[],
            source_event_ids=event_ids,
            confidence=0.9,
            sensitivity=MemorySensitivity.HIGH,
        ),
    ]

    for i, memory in enumerate(rejection_tests):
        before_count = len(index.entries)
        result = promoter.promote_memory(memory)
        after_count = len(index.entries)

        assert result.status in (PromotionStatus.REJECTED, PromotionStatus.DEFERRED), (
            f"Test {i}: Expected REJECTED or DEFERRED, got {result.status}"
        )
        assert after_count == before_count, f"Test {i}: Index was modified on rejection"
        assert after_count == initial_count, f"Test {i}: Index drifted from initial count"

    # Also test missing provenance (separate because it needs empty source_event_ids)
    memory_no_provenance = MemoryRecord(
        title="No provenance",
        body="Test",
        tags=[],
        source_event_ids=[],  # Empty
        confidence=0.9,
    )
    before = len(index.entries)
    result = promoter.promote_memory(memory_no_provenance)
    after = len(index.entries)
    assert result.status == PromotionStatus.REJECTED
    assert after == before == initial_count


# =============================================================================
# Test 8: persist=True raises error when not implemented
# =============================================================================


def test_persist_true_raises_when_not_implemented() -> None:
    """Verify that persist=True raises PersistenceNotImplementedError."""
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, read_only=False)

    session = PromotionSession(
        promoter=promoter,
        spine_store=None,
        promotion_log_path=None,
        _persistence_implemented=False,
    )

    # Create a valid replay report
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_spine_with_events(task_id)
    replay_engine = ReplayEngine(spine=spine)
    report = replay_engine.replay_task(task_id)

    # Attempt with persist=True (should raise)
    with pytest.raises(PersistenceNotImplementedError) as exc_info:
        session.promote_and_log(report, persist=True)

    assert "persist=True requested but persistence is not implemented" in str(exc_info.value)


# =============================================================================
# Test 9: All source events must exist in spine
# =============================================================================


def test_all_source_events_must_exist_in_spine() -> None:
    """Verify that ALL source events must exist in spine, not just some."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_spine_with_events(task_id, event_count=3)

    # Create memory with extra event IDs not in spine
    valid_event_ids = [event.event_id for event in spine.events]
    fake_event_ids = ["fake_evt_1", "fake_evt_2", "fake_evt_3"]
    all_event_ids = valid_event_ids + fake_event_ids

    memory = MemoryRecord(
        title="Test memory",
        body="Test content",
        tags=["test"],
        source_event_ids=all_event_ids,  # Mix of valid and fake
        confidence=0.9,
    )

    promoter = MemoryPromoter(index=LocalKnowledgeIndex(), spine=spine, read_only=False)

    result = promoter.promote_memory(memory)

    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.MISSING_PROVENANCE
    assert "source_events_not_in_spine" in result.details.get("reason", "")
    assert "missing_event_ids" in result.details
    assert result.details["total_missing"] == 3  # All fake IDs missing


# =============================================================================
# Test 10: verify_index_unchanged tracks modifications
# =============================================================================


def test_verify_index_unchanged_tracks_modifications() -> None:
    """Verify that verify_index_unchanged correctly tracks modifications."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_spine_with_events(task_id)
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine, read_only=False)

    # Before any operation
    assert promoter.verify_index_unchanged() is True

    # Create and promote valid memory
    memory = _create_valid_memory(task_id, spine)

    result = promoter.promote_memory(memory)
    assert result.status == PromotionStatus.PROMOTED

    # After successful promotion, index should have changed
    # (snapshot was taken before, so verify should return False)
    assert promoter.verify_index_unchanged() is False
    assert result.status == PromotionStatus.PROMOTED

    # After successful promotion, index should be changed
    # (snapshot was taken before, so verify should return False)
    # Note: This depends on implementation - if snapshot is updated after success,
    # this might return True. Adjust test based on actual behavior.


# =============================================================================
# Test 11: Sensitivity ordering is strict (LOW < MEDIUM < HIGH)
# =============================================================================


def test_sensitivity_ordering_is_strict() -> None:
    """Verify that sensitivity ordering uses strict LOW < MEDIUM < HIGH."""
    # LOW does not exceed MEDIUM
    assert _sensitivity_exceeds_limit(MemorySensitivity.LOW, MemorySensitivity.MEDIUM) is False
    # LOW does not exceed LOW
    assert _sensitivity_exceeds_limit(MemorySensitivity.LOW, MemorySensitivity.LOW) is False
    # MEDIUM exceeds LOW
    assert _sensitivity_exceeds_limit(MemorySensitivity.MEDIUM, MemorySensitivity.LOW) is True
    # MEDIUM does not exceed MEDIUM
    assert _sensitivity_exceeds_limit(MemorySensitivity.MEDIUM, MemorySensitivity.MEDIUM) is False
    # HIGH exceeds LOW
    assert _sensitivity_exceeds_limit(MemorySensitivity.HIGH, MemorySensitivity.LOW) is True
    # HIGH exceeds MEDIUM
    assert _sensitivity_exceeds_limit(MemorySensitivity.HIGH, MemorySensitivity.MEDIUM) is True
    # HIGH does not exceed HIGH
    assert _sensitivity_exceeds_limit(MemorySensitivity.HIGH, MemorySensitivity.HIGH) is False


# =============================================================================
# Test 12: promote_from_replay validates spine integrity from report
# =============================================================================


def test_promote_from_replay_validates_spine_integrity() -> None:
    """Verify that promote_from_replay checks spine_integrity_ok from report."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_spine_with_events(task_id)
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine, read_only=False)

    # Create report with spine_integrity_ok=False
    replay_report = ReplayReport(
        task_id="test",
        status=ReplayStatus.CONSOLIDATED,  # Status says OK
        event_count=5,
        spine_integrity_ok=False,  # But integrity check failed
        memory=MemoryRecord(
            title="Test",
            body="Test",
            tags=[],
            source_event_ids=[e.event_id for e in spine.events],  # Valid events
            confidence=0.9,
        ),
    )

    # Should be rejected due to integrity failure
    result = promoter.promote_from_replay(replay_report, explicit_approval=False)
    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.INTEGRITY_FAILED
    assert result.bypassable is False

    # Even with explicit_approval
    result2 = promoter.promote_from_replay(replay_report, explicit_approval=True)
    assert result2.status == PromotionStatus.REJECTED
    assert result2.rejection_reason == RejectionReason.INTEGRITY_FAILED
    assert result2.bypassable is False


# =============================================================================
# Test 13: Bypassable flag is correctly set
# =============================================================================


def test_bypassable_flag_correctly_set() -> None:
    """Verify that bypassable flag correctly indicates if rejection can be bypassed."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_spine_with_events(task_id)
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine, read_only=False)
    event_ids = [e.event_id for e in spine.events]

    # Non-bypassable rejections
    non_bypassable_tests = [
        # Inadmissible content
        (
            MemoryRecord(
                title="T", body="password: secret", tags=[], source_event_ids=event_ids, confidence=0.9
            ),
            RejectionReason.INADMISSIBLE_CONTENT,
        ),
        # Sensitivity violation
        (
            MemoryRecord(
                title="T", body="Test", tags=[], source_event_ids=event_ids, confidence=0.9,
                sensitivity=MemorySensitivity.HIGH,
            ),
            RejectionReason.SENSITIVE_CONTENT,
        ),
    ]

    for memory, expected_reason in non_bypassable_tests:
        result = promoter.promote_memory(memory)
        assert result.status == PromotionStatus.REJECTED
        assert result.rejection_reason == expected_reason
        assert result.bypassable is False, f"{expected_reason} should not be bypassable"

    # Bypassable rejection (low confidence)
    low_conf_memory = MemoryRecord(
        title="Test",
        body="Test",
        tags=[],
        source_event_ids=event_ids,  # Valid events
        confidence=0.3,  # Low
        sensitivity=MemorySensitivity.LOW,
    )
    result = promoter.promote_memory(low_conf_memory)
    assert result.status == PromotionStatus.DEFERRED
    assert result.rejection_reason == RejectionReason.LOW_CONFIDENCE
    assert result.bypassable is True, "LOW_CONFIDENCE should be bypassable"