import pytest

from hex_cortex.memory.confidence import (
    MemoryConfidenceAuditJsonlStore,
    MemoryConfidenceAuditRecord,
    MemoryConfidenceUpdater,
)
from hex_cortex.memory.schemas import MemoryRecord


def test_memory_confidence_confirm_increases_confidence_and_access_count() -> None:
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)

    updated, report = MemoryConfidenceUpdater(delta=0.05).confirm(
        [memory],
        memory_id=memory.memory_id,
        reason="retrieval_confirmed",
    )

    assert report.found is True
    assert report.changed is True
    assert report.before_confidence == 0.5
    assert report.after_confidence == 0.55
    assert report.delta == 0.05
    assert updated[0].confidence == 0.55
    assert updated[0].access_count == 1
    assert updated[0].last_accessed_at is not None


def test_memory_confidence_confirm_caps_confidence_at_one() -> None:
    memory = MemoryRecord(title="memory", body="body", confidence=0.99)

    updated, report = MemoryConfidenceUpdater(delta=0.05).confirm(
        [memory],
        memory_id=memory.memory_id,
        reason="retrieval_confirmed",
    )

    assert report.after_confidence == 1.0
    assert report.delta == 0.01
    assert updated[0].confidence == 1.0


def test_memory_confidence_confirm_missing_memory_does_not_mutate() -> None:
    memory = MemoryRecord(title="memory", body="body", confidence=0.5)

    updated, report = MemoryConfidenceUpdater().confirm(
        [memory],
        memory_id="missing",
        reason="retrieval_confirmed",
    )

    assert report.found is False
    assert report.changed is False
    assert updated[0].memory_id == memory.memory_id
    assert updated[0].confidence == memory.confidence


def test_memory_confidence_audit_store_appends_and_loads_records(tmp_path) -> None:
    store = MemoryConfidenceAuditJsonlStore(tmp_path / "memory-confidence-audit.jsonl")
    record = MemoryConfidenceAuditRecord(
        memory_id="mem_1",
        reason="retrieval_confirmed",
        before_confidence=0.5,
        after_confidence=0.55,
        delta=0.05,
        changed=True,
        before_access_count=0,
        after_access_count=1,
    )

    count = store.append(record)
    records = store.load()

    assert count == 1
    assert records[0].audit_id == record.audit_id
    assert records[0].memory_id == "mem_1"


def test_memory_confidence_audit_store_rejects_invalid_json_line(tmp_path) -> None:
    path = tmp_path / "memory-confidence-audit.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    store = MemoryConfidenceAuditJsonlStore(path)

    with pytest.raises(ValueError, match="invalid memory confidence record"):
        store.load()
