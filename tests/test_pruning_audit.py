import pytest

from hex_cortex.memory.pruning_audit import PruningAuditJsonlStore, PruningAuditRecord


def make_record(operation: str = "preview") -> PruningAuditRecord:
    return PruningAuditRecord(
        operation=operation,
        profile_path=".hex-cortex",
        memory_path=".hex-cortex/memory.jsonl",
        backup_path=None,
        dry_run=True,
        applied=False,
        total_memory_count=2,
        changed_count=1,
        visible_before=2,
        visible_after=2,
        keep_count=1,
        degrade_count=0,
        archive_count=1,
    )


def test_pruning_audit_store_loads_empty_list_when_missing(tmp_path) -> None:
    store = PruningAuditJsonlStore(tmp_path / "audit.jsonl")

    assert store.load() == []


def test_pruning_audit_store_appends_and_loads_records(tmp_path) -> None:
    store = PruningAuditJsonlStore(tmp_path / "audit.jsonl")
    first = make_record("preview")
    second = make_record("apply")

    first_count = store.append(first)
    second_count = store.append(second)
    records = store.load()

    assert first_count == 1
    assert second_count == 2
    assert [record.audit_id for record in records] == [first.audit_id, second.audit_id]
    assert [record.operation for record in records] == ["preview", "apply"]


def test_pruning_audit_store_rejects_invalid_json_line(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    store = PruningAuditJsonlStore(path)

    with pytest.raises(ValueError, match="invalid pruning audit record"):
        store.load()
