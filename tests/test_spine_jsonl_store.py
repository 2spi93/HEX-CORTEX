import json

import pytest

from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


def make_spine() -> CanonicalSpine:
    spine = CanonicalSpine()
    spine.append(
        event_type="task.received",
        task_id="task_1",
        source="test",
        payload={"content": "persist me"},
    )
    spine.append(
        event_type="clock.completed",
        task_id="task_1",
        source="clock",
        payload={"completed": True},
        confidence=0.9,
    )
    return spine


def test_jsonl_store_saves_and_loads_verified_spine(tmp_path) -> None:
    path = tmp_path / "spine.jsonl"
    spine = make_spine()
    store = CanonicalSpineJsonlStore(path)

    written = store.save(spine)
    loaded = store.load()

    assert written == 2
    assert loaded.verify_integrity().ok is True
    assert loaded.project().total_events == 2
    assert loaded.project().latest_event_hash == spine.project().latest_event_hash


def test_jsonl_store_loads_empty_spine_when_file_is_missing(tmp_path) -> None:
    store = CanonicalSpineJsonlStore(tmp_path / "missing.jsonl")

    loaded = store.load()

    assert loaded.project().total_events == 0
    assert loaded.verify_integrity().ok is True


def test_jsonl_store_appends_single_event(tmp_path) -> None:
    path = tmp_path / "spine.jsonl"
    spine = make_spine()
    store = CanonicalSpineJsonlStore(path)

    store.append_event(spine.events[0])

    loaded = store.load()

    assert loaded.project().total_events == 1
    assert loaded.events[0].event_type == "task.received"


def test_jsonl_store_rejects_invalid_json_line(tmp_path) -> None:
    path = tmp_path / "spine.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    store = CanonicalSpineJsonlStore(path)

    with pytest.raises(ValueError, match="invalid JSONL spine event"):
        store.load()


def test_jsonl_store_rejects_tampered_hash_chain(tmp_path) -> None:
    path = tmp_path / "spine.jsonl"
    spine = make_spine()
    CanonicalSpineJsonlStore(path).save(spine)

    lines = path.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[0])
    event["payload"]["content"] = "tampered"
    lines[0] = json.dumps(event)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="event_hash_mismatch"):
        CanonicalSpineJsonlStore(path).load()
