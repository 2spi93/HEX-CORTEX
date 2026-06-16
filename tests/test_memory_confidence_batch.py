from hex_cortex.memory.confidence import MemoryConfidenceAuditJsonlStore
from hex_cortex.memory.confidence_batch import run_memory_confidence_batch_profile
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_memory_confidence_batch_dry_run_does_not_mutate_or_audit(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([memory])

    payload = run_memory_confidence_batch_profile(profile, limit=1, dry_run=True)
    persisted = LocalMemoryJsonlStore(memory_path).load()[0]

    assert payload["dry_run"] is True
    assert payload["applied"] is False
    assert payload["apply_blocked_reason"] is None
    assert payload["candidate_count"] == 1
    assert payload["eligible_candidate_count"] == 1
    assert payload["confirmed_count"] == 1
    assert payload["changed_count"] == 1
    assert payload["saturation_threshold"] == 0.7
    assert payload["saturated_memory_count"] == 0
    assert payload["unsaturated_memory_count"] == 1
    assert payload["audit_records_written"] == 0
    assert persisted.confidence == 0.5
    assert persisted.access_count == 0
    assert not audit_path.exists()


def test_memory_confidence_batch_apply_updates_memories_and_audits(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    first = MemoryRecord(title="first", body="body", confidence=0.5)
    second = MemoryRecord(title="second", body="body", confidence=0.5)
    third = MemoryRecord(title="third", body="body", confidence=0.9, access_count=1)
    LocalMemoryJsonlStore(memory_path).save([first, second, third])

    payload = run_memory_confidence_batch_profile(
        profile,
        limit=2,
        reason="retrieval_confirmed",
        dry_run=False,
    )
    persisted = LocalMemoryJsonlStore(memory_path).load()
    audits = MemoryConfidenceAuditJsonlStore(audit_path).load()

    assert payload["dry_run"] is False
    assert payload["applied"] is True
    assert payload["apply_blocked_reason"] is None
    assert payload["confirmed_count"] == 2
    assert payload["changed_count"] == 2
    assert payload["saturated_memory_count"] == 1
    assert payload["unsaturated_memory_count"] == 2
    assert payload["audit_records_written"] == 2
    assert payload["audit_record_count_after"] == 2
    assert len(audits) == 2
    updated_by_id = {memory.memory_id: memory for memory in persisted}
    assert updated_by_id[first.memory_id].confidence == 0.55
    assert updated_by_id[first.memory_id].access_count == 1
    assert updated_by_id[second.memory_id].confidence == 0.55
    assert updated_by_id[second.memory_id].access_count == 1
    assert updated_by_id[third.memory_id].confidence == 0.9
    assert audits[0].reason == "retrieval_confirmed"


def test_memory_confidence_batch_blocks_apply_when_total_delta_exceeds_limit(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    audit_path = profile / "memory-confidence-audit.jsonl"
    first = MemoryRecord(title="first", body="body", confidence=0.5)
    second = MemoryRecord(title="second", body="body", confidence=0.5)
    LocalMemoryJsonlStore(memory_path).save([first, second])

    payload = run_memory_confidence_batch_profile(
        profile,
        limit=2,
        dry_run=False,
        max_total_delta=0.05,
    )
    persisted = LocalMemoryJsonlStore(memory_path).load()

    assert payload["applied"] is False
    assert payload["apply_blocked_reason"] == "max_total_delta_exceeded"
    assert payload["total_delta"] == 0.1
    assert payload["audit_records_written"] == 0
    assert [memory.confidence for memory in persisted] == [0.5, 0.5]
    assert not audit_path.exists()


def test_memory_confidence_batch_filters_by_min_priority_score(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    low = MemoryRecord(title="low", body="body", confidence=0.5)
    medium = MemoryRecord(title="medium", body="body", confidence=0.55, access_count=1)
    LocalMemoryJsonlStore(memory_path).save([low, medium])

    payload = run_memory_confidence_batch_profile(
        profile,
        limit=2,
        dry_run=True,
        min_priority_score=0.4,
    )

    assert payload["candidate_count"] == 2
    assert payload["eligible_candidate_count"] == 1
    assert payload["confirmed_count"] == 1
    assert payload["candidates"][0]["memory_id"] == low.memory_id


def test_memory_confidence_batch_blocks_apply_without_eligible_candidates(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    memory = MemoryRecord(title="memory", body="body", confidence=0.55, access_count=1)
    LocalMemoryJsonlStore(memory_path).save([memory])

    payload = run_memory_confidence_batch_profile(
        profile,
        limit=1,
        dry_run=False,
        min_priority_score=0.9,
    )

    assert payload["applied"] is False
    assert payload["apply_blocked_reason"] == "no_eligible_candidates"
    assert payload["eligible_candidate_count"] == 0


def test_memory_confidence_batch_excludes_saturated_memories(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    saturated = MemoryRecord(
        title="saturated",
        body="body",
        confidence=0.7,
        access_count=1,
    )
    candidate = MemoryRecord(title="candidate", body="body", confidence=0.6)
    LocalMemoryJsonlStore(memory_path).save([saturated, candidate])

    payload = run_memory_confidence_batch_profile(profile, limit=2, dry_run=True)

    assert payload["saturated_memory_count"] == 1
    assert payload["unsaturated_memory_count"] == 1
    assert payload["candidate_count"] == 1
    assert payload["candidates"][0]["memory_id"] == candidate.memory_id
    assert payload["candidates"][0]["saturation_state"] == "needs_confirmation"


def test_memory_confidence_batch_uses_configurable_saturation_threshold(tmp_path) -> None:
    profile = tmp_path / "profile"
    memory_path = profile / "memory.jsonl"
    memory = MemoryRecord(
        title="memory",
        body="body",
        confidence=0.65,
        access_count=1,
    )
    LocalMemoryJsonlStore(memory_path).save([memory])

    payload = run_memory_confidence_batch_profile(
        profile,
        limit=1,
        dry_run=False,
        saturation_threshold=0.6,
    )

    assert payload["applied"] is False
    assert payload["apply_blocked_reason"] == "no_eligible_candidates"
    assert payload["saturation_threshold"] == 0.6
    assert payload["saturated_memory_count"] == 1
    assert payload["unsaturated_memory_count"] == 0
