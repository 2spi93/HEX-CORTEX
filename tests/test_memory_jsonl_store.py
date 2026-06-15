import pytest

from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def make_memory(title: str = "Memory") -> MemoryRecord:
    return MemoryRecord(
        title=title,
        body=f"Compressed body for {title}.",
        tags=["memory"],
        source_event_ids=["evt_1"],
        confidence=0.8,
    )


def test_memory_jsonl_store_loads_empty_list_when_missing(tmp_path) -> None:
    store = LocalMemoryJsonlStore(tmp_path / "missing.jsonl")

    assert store.load() == []
    assert store.visible() == []


def test_memory_jsonl_store_saves_and_loads_records(tmp_path) -> None:
    path = tmp_path / "memory.jsonl"
    records = [make_memory("A"), make_memory("B")]
    store = LocalMemoryJsonlStore(path)

    written = store.save(records)
    loaded = store.load()

    assert written == 2
    assert [record.memory_id for record in loaded] == [
        records[0].memory_id,
        records[1].memory_id,
    ]


def test_memory_jsonl_store_appends_record_and_returns_count(tmp_path) -> None:
    path = tmp_path / "memory.jsonl"
    store = LocalMemoryJsonlStore(path)

    first_count = store.append(make_memory("A"))
    second_count = store.append(make_memory("B"))

    assert first_count == 1
    assert second_count == 2
    assert len(store.load()) == 2


def test_memory_jsonl_store_filters_visible_records(tmp_path) -> None:
    visible = make_memory("Visible")
    hidden = make_memory("Hidden").model_copy(update={"visible": False})
    store = LocalMemoryJsonlStore(tmp_path / "memory.jsonl")

    store.save([visible, hidden])

    assert [record.memory_id for record in store.visible()] == [visible.memory_id]


def test_memory_jsonl_store_rejects_invalid_json_line(tmp_path) -> None:
    path = tmp_path / "memory.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    store = LocalMemoryJsonlStore(path)

    with pytest.raises(ValueError, match="invalid JSONL memory record"):
        store.load()
