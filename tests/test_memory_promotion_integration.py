"""Integration tests for controlled memory promotion - UPDATED for fail-closed spine requirement.

Tests cover:
1. Full flow: execution → event → replay → promotion → index → search
2. Negative tests: invalid integrity, duplicate, missing provenance, inadmissible content
3. Read-only mode enforcement
4. Duplicate prevention on repeated replay
5. Source event reference preservation
6. Comparison: with vs without memory on deterministic task
7. Fail-closed spine requirement
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
from hex_cortex.memory.schemas import MemoryRecord
from hex_cortex.replay.replay_engine import ReplayEngine
from hex_cortex.replay.schemas import ReplayStatus
from hex_cortex.spine.canonical_spine import CanonicalSpine


def _build_successful_episode_spine(task_id: str) -> CanonicalSpine:
    """Build a spine with a successful cognitive episode."""
    spine = CanonicalSpine()
    spine.append(
        event_type="task.received",
        task_id=task_id,
        source="test_harness",
        payload={
            "goal": "Compute Fibonacci sequence up to 10",
            "domain": "math",
        },
        confidence=0.9,
    )
    spine.append(
        event_type="routing.decision",
        task_id=task_id,
        source="router",
        payload={
            "selected_cells": ["logic_cell", "memory_cell"],
            "mode": "working",
        },
        confidence=0.85,
    )
    spine.append(
        event_type="retrieval.packet",
        task_id=task_id,
        source="retrieval_router",
        payload={
            "used_memory_ids": [],
            "method": "empty",
            "result_count": 0,
        },
        confidence=0.8,
    )
    spine.append(
        event_type="tick.completed",
        task_id=task_id,
        source="cognitive_clock",
        payload={
            "tick_name": "intake",
            "status": "success",
            "observations": ["Task parsed successfully"],
        },
        confidence=0.9,
    )
    spine.append(
        event_type="tick.completed",
        task_id=task_id,
        source="cognitive_clock",
        payload={
            "tick_name": "action",
            "status": "success",
            "observations": ["Computation completed"],
        },
        confidence=0.95,
    )
    spine.append(
        event_type="clock.completed",
        task_id=task_id,
        source="cognitive_clock",
        payload={
            "completed": True,
            "elapsed_ms": 150.5,
        },
        confidence=0.92,
    )
    return spine


def _build_failed_episode_spine(task_id: str) -> CanonicalSpine:
    """Build a spine with a failed cognitive episode."""
    spine = CanonicalSpine()
    spine.append(
        event_type="task.received",
        task_id=task_id,
        source="test_harness",
        payload={
            "goal": "Execute unverified external command",
            "domain": "action",
        },
        confidence=0.9,
    )
    spine.append(
        event_type="tick.completed",
        task_id=task_id,
        source="cognitive_clock",
        payload={
            "tick_name": "critic",
            "status": "failed",
            "error": "Action blocked by safety check",
        },
        confidence=0.3,
    )
    spine.append(
        event_type="clock.completed",
        task_id=task_id,
        source="cognitive_clock",
        payload={
            "completed": False,
            "stopped_reason": "critic_rejected",
        },
        confidence=0.2,
    )
    return spine


def _build_tampered_spine(task_id: str) -> CanonicalSpine:
    """Build a spine with tampered events (integrity will fail)."""
    spine = CanonicalSpine()
    spine.append(
        event_type="task.received",
        task_id=task_id,
        source="test",
        payload={"goal": "original goal"},
    )
    # Tamper with the event after creation
    spine._events[0].payload["goal"] = "tampered goal"
    return spine


def _create_memory_from_spine(spine: CanonicalSpine, task_id: str) -> MemoryRecord:
    """Create a memory record from a spine using ReplayEngine."""
    replay_engine = ReplayEngine(spine=spine)
    report = replay_engine.replay_task(task_id)
    assert report.memory is not None, "Replay should produce memory"
    return report.memory


# =============================================================================
# Test 1: Full flow - execution → event → replay → promotion → index → search
# =============================================================================


def test_full_promotion_flow() -> None:
    """Test complete flow from execution to searchable memory."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_successful_episode_spine(task_id)

    # Step 1: Replay
    replay_engine = ReplayEngine(spine=spine)
    report = replay_engine.replay_task(task_id)
    assert report.status == ReplayStatus.CONSOLIDATED
    assert report.memory is not None

    # Step 2: Promote (with spine!)
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine)
    result = promoter.promote_from_replay(report)

    assert result.status == PromotionStatus.PROMOTED
    assert result.memory is not None
    assert result.index_entry is not None
    assert result.rejection_reason is None

    # Step 3: Search in index
    # Exact search for title
    exact_hits = index.exact_search("Compressed cognitive episode")
    assert len(exact_hits) >= 1

    # Lexical search for content
    lexical_hits = index.lexical_scores("Fibonacci computation")
    assert len(lexical_hits) >= 1
    assert lexical_hits[0][1] > 0.5  # Should have good score

    # Verify source event references preserved
    metadata = result.index_entry.metadata
    assert "source_event_ids" in metadata
    assert len(metadata["source_event_ids"]) > 0


# =============================================================================
# Test 2: Negative test - invalid integrity
# =============================================================================


def test_rejection_invalid_integrity() -> None:
    """Test that tampered spine leads to rejection."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_tampered_spine(task_id)

    replay_engine = ReplayEngine(spine=spine)
    report = replay_engine.replay_task(task_id)

    # Replay should fail integrity check
    assert report.status == ReplayStatus.INTEGRITY_FAILED

    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine)
    result = promoter.promote_from_replay(report)

    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.INTEGRITY_FAILED


# =============================================================================
# Test 3: Negative test - duplicate promotion
# =============================================================================


def test_duplicate_prevention() -> None:
    """Test that repeated replay does not create duplicates."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_successful_episode_spine(task_id)

    replay_engine = ReplayEngine(spine=spine)
    report = replay_engine.replay_task(task_id)
    assert report.memory is not None
    memory_id = report.memory.memory_id

    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine)

    # First promotion
    result1 = promoter.promote_from_replay(report)
    assert result1.status == PromotionStatus.PROMOTED

    # Second promotion attempt (same memory object)
    result2 = promoter.promote_from_replay(report)
    assert result2.status == PromotionStatus.DUPLICATE
    assert result2.rejection_reason == RejectionReason.DUPLICATE

    # Verify only one entry in index
    assert len(index.entries) == 1
    assert promoter.get_promoted_ids() == {memory_id}


# =============================================================================
# Test 4: Negative test - missing provenance
# =============================================================================


def test_rejection_missing_provenance() -> None:
    """Test that memory without source events is rejected."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_successful_episode_spine(task_id)

    # Create memory without source events
    memory = MemoryRecord(
        title="Orphan memory",
        body="This memory has no source events",
        tags=["test"],
        source_event_ids=[],  # Empty!
        confidence=0.9,
    )

    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine)

    result = promoter.promote_memory(memory)

    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.MISSING_PROVENANCE


# =============================================================================
# Test 5: Negative test - inadmissible content (sensitive patterns)
# =============================================================================


def test_rejection_inadmissible_content() -> None:
    """Test that sensitive content is rejected."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_successful_episode_spine(task_id)

    memory = MemoryRecord(
        title="API Configuration",
        body="The API key is sk-1234567890abcdef. Keep this secret.",
        tags=["config"],
        source_event_ids=[e.event_id for e in spine.events],
        confidence=0.9,
    )

    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine)

    result = promoter.promote_memory(memory)

    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.INADMISSIBLE_CONTENT
    assert result.details["issues"]  # Should have issues listed


def test_rejection_blocked_tags() -> None:
    """Test that blocked tags cause rejection."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_successful_episode_spine(task_id)

    memory = MemoryRecord(
        title="Credentials",
        body="Some credentials",
        tags=["password", "config"],  # "password" is blocked
        source_event_ids=[e.event_id for e in spine.events],
        confidence=0.9,
    )

    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine)

    result = promoter.promote_memory(memory)

    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.INADMISSIBLE_CONTENT
    assert "password" in result.details["blocked_tags_found"]


# =============================================================================
# Test 6: Read-only mode enforcement
# =============================================================================


def test_read_only_mode_blocks_promotion() -> None:
    """Test that read-only mode prevents promotion."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_successful_episode_spine(task_id)

    replay_engine = ReplayEngine(spine=spine)
    report = replay_engine.replay_task(task_id)

    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine, read_only=True)

    result = promoter.promote_from_replay(report)

    assert result.status == PromotionStatus.REJECTED
    assert result.rejection_reason == RejectionReason.READ_ONLY_MODE

    # Verify index is unchanged
    assert len(index.entries) == 0


# =============================================================================
# Test 7: Low confidence deferral
# =============================================================================


def test_low_confidence_deferred() -> None:
    """Test that low confidence memories are deferred, not rejected."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_successful_episode_spine(task_id)

    memory = MemoryRecord(
        title="Uncertain observation",
        body="This might be useful but confidence is low",
        tags=["hypothesis"],
        source_event_ids=[e.event_id for e in spine.events],
        confidence=0.3,  # Below default threshold of 0.5
    )

    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine)

    result = promoter.promote_memory(memory)

    assert result.status == PromotionStatus.DEFERRED
    assert result.rejection_reason == RejectionReason.LOW_CONFIDENCE
    assert result.details["confidence"] == 0.3
    assert result.details["threshold"] == 0.5

    # Verify not added to index
    assert len(index.entries) == 0


# =============================================================================
# Test 8: Explicit approval bypass
# =============================================================================


def test_explicit_approval_bypasses_checks() -> None:
    """Test that explicit approval can bypass low confidence check."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_successful_episode_spine(task_id)

    memory = MemoryRecord(
        title="Low confidence but approved",
        body="Operator verified this is useful",
        tags=["verified"],
        source_event_ids=[e.event_id for e in spine.events],
        confidence=0.3,  # Below threshold
    )

    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine)

    # Without approval: deferred
    result1 = promoter.promote_memory(memory, explicit_approval=False)
    assert result1.status == PromotionStatus.DEFERRED

    # With approval: promoted
    result2 = promoter.promote_memory(memory, explicit_approval=True)
    assert result2.status == PromotionStatus.PROMOTED
    assert len(index.entries) == 1


# =============================================================================
# Test 9: Comparison - with vs without memory on deterministic task
# =============================================================================


def test_memory_retrieval_comparison() -> None:
    """Test that retrieved memory affects context packet."""
    # Setup: Create and promote a memory
    task_id_1 = f"task_{uuid4().hex[:8]}"
    spine_1 = _build_successful_episode_spine(task_id_1)

    replay_engine = ReplayEngine(spine=spine_1)
    report_1 = replay_engine.replay_task(task_id_1)
    assert report_1.memory is not None

    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine_1)
    promoter.promote_from_replay(report_1)

    # Scenario A: Search WITHOUT promoted memory (fresh index)
    fresh_index = LocalKnowledgeIndex()
    from hex_cortex.memory.schemas import RetrievalQuery
    from hex_cortex.memory.retrieval_router import RetrievalRouter

    router_fresh = RetrievalRouter(fresh_index)
    query = RetrievalQuery(query="Fibonacci computation", top_k=5)
    packet_fresh = router_fresh.retrieve(query)

    assert packet_fresh.method.value == "empty"
    assert len(packet_fresh.results) == 0
    assert packet_fresh.total_chars == 0

    # Scenario B: Search WITH promoted memory
    router_with_memory = RetrievalRouter(index)
    packet_with_memory = router_with_memory.retrieve(query)

    assert packet_with_memory.method.value in ("exact", "lexical")
    assert len(packet_with_memory.results) >= 1
    assert packet_with_memory.total_chars > 0

    # Verify the difference
    assert packet_with_memory.total_chars > packet_fresh.total_chars
    assert "Fibonacci" in packet_with_memory.context_text


# =============================================================================
# Test 10: Source event reference preservation
# =============================================================================


def test_source_event_references_preserved() -> None:
    """Test that source event IDs are preserved through promotion."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_successful_episode_spine(task_id)

    # Get all event IDs before replay
    original_event_ids = {event.event_id for event in spine.events}
    assert len(original_event_ids) >= 3

    replay_engine = ReplayEngine(spine=spine)
    report = replay_engine.replay_task(task_id)
    assert report.memory is not None

    # Verify memory has source event IDs
    memory = report.memory
    assert len(memory.source_event_ids) > 0

    # Promote
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine)
    result = promoter.promote_from_replay(report)

    assert result.index_entry is not None

    # Verify metadata contains source event references
    metadata = result.index_entry.metadata
    assert "source_event_ids" in metadata
    assert len(metadata["source_event_ids"]) > 0

    # Verify at least some original events are referenced
    referenced = set(metadata["source_event_ids"])
    assert len(referenced & original_event_ids) > 0


# =============================================================================
# Test 11: Failed episode promotion (error pattern learning)
# =============================================================================


def test_failed_episode_promotion() -> None:
    """Test that failed episodes can be promoted for error pattern learning."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_failed_episode_spine(task_id)

    replay_engine = ReplayEngine(spine=spine)
    report = replay_engine.replay_task(task_id)

    assert report.status == ReplayStatus.CONSOLIDATED
    assert report.memory is not None

    # Verify memory captures failure (as episode with error-related rules)
    memory = report.memory
    # Failed episodes are stored as EPISODE type with tacit rules about errors
    assert "tacit-rule" in memory.tags
    assert "CriticCell" in memory.body or "errors" in memory.body.lower()

    # Promote with explicit approval (failed episodes may have lower confidence)
    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine)
    result = promoter.promote_from_replay(report, explicit_approval=True)

    assert result.status == PromotionStatus.PROMOTED
    assert result.index_entry is not None

    # Verify error content is searchable
    lexical_hits = index.lexical_scores("safety check blocked")
    assert len(lexical_hits) > 0


# =============================================================================
# Test 12: Promotion with custom criteria
# =============================================================================


def test_custom_promotion_criteria() -> None:
    """Test promotion with custom criteria."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_successful_episode_spine(task_id)

    memory = MemoryRecord(
        title="Medium confidence memory",
        body="Useful pattern",
        tags=["pattern"],
        source_event_ids=[e.event_id for e in spine.events],
        confidence=0.6,
    )

    index = LocalKnowledgeIndex()

    # Default criteria (threshold 0.5): should promote
    promoter_default = MemoryPromoter(index=index, spine=spine)
    result1 = promoter_default.promote_memory(memory)
    assert result1.status == PromotionStatus.PROMOTED

    # Stricter criteria (threshold 0.8): should defer
    memory2 = MemoryRecord(
        title="Another memory",
        body="Also useful",
        tags=["pattern"],
        source_event_ids=[e.event_id for e in spine.events],
        confidence=0.6,
    )
    promoter_strict = MemoryPromoter(
        index=LocalKnowledgeIndex(),
        spine=spine,  # Still need spine!
        criteria=PromotionCriteria(min_confidence=0.8),
    )
    result2 = promoter_strict.promote_memory(memory2)
    assert result2.status == PromotionStatus.DEFERRED
    assert result2.rejection_reason == RejectionReason.LOW_CONFIDENCE


# =============================================================================
# Test 13: Promotion history tracking
# =============================================================================


def test_promotion_history() -> None:
    """Test that promotion history is tracked."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_successful_episode_spine(task_id)

    index = LocalKnowledgeIndex()
    promoter = MemoryPromoter(index=index, spine=spine)

    # Promote multiple memories
    for i in range(3):
        memory = MemoryRecord(
            title=f"Memory {i}",
            body=f"Content {i}",
            tags=["test"],
            source_event_ids=[e.event_id for e in spine.events],
            confidence=0.9,
        )
        promoter.promote_memory(memory)

    history = promoter.get_promotion_history()
    assert len(history) == 3
    assert all(h.status == PromotionStatus.PROMOTED for h in history)


# =============================================================================
# Test 14: Hash-based duplicate detection
# =============================================================================


def test_content_hash_duplicate_detection() -> None:
    """Test that content hash can detect duplicates across sessions."""
    task_id = f"task_{uuid4().hex[:8]}"
    spine = _build_successful_episode_spine(task_id)

    memory1 = MemoryRecord(
        title="Same content",
        body="Identical body",
        tags=["test"],
        source_event_ids=[e.event_id for e in spine.events],
        confidence=0.9,
    )

    memory2 = MemoryRecord(
        title="Same content",
        body="Identical body",
        tags=["test"],
        source_event_ids=[e.event_id for e in spine.events],  # Same events
        confidence=0.9,
    )

    promoter = MemoryPromoter(index=LocalKnowledgeIndex(), spine=spine)

    hash1 = promoter.compute_promotion_hash(memory1)
    hash2 = promoter.compute_promotion_hash(memory2)

    assert hash1 == hash2  # Same content = same hash

    # Different content = different hash
    memory3 = MemoryRecord(
        title="Different content",
        body="Different body",
        tags=["test"],
        source_event_ids=[e.event_id for e in spine.events],
        confidence=0.9,
    )
    hash3 = promoter.compute_promotion_hash(memory3)
    assert hash3 != hash1