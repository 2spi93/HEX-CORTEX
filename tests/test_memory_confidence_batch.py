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
    assert payload["candidate_count"] == 1
    assert payload["confirmed_count"] == 1
    assert payload["changed_count"] == 1
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
    assert payload["confirmed_count"] == 2
    assert payload["changed_count"] == 2
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
