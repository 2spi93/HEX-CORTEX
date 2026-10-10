"""CanonicalSpine durable recovery and chain preservation, no LLM or I/O outside tmp."""
from __future__ import annotations

import json

import pytest

from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore
from hex_cortex.memory import cortex_durable_jsonl_v7 as durable


def _chain() -> CanonicalSpine:
    spine = CanonicalSpine()
    spine.append(event_type="task.received", task_id="one", source="trusted")
    spine.append(event_type="task.completed", task_id="one", source="trusted")
    return spine


def test_spine_append_idempotent_only_for_same_event(tmp_path) -> None:
    path = tmp_path / "spine.jsonl"
    store = CanonicalSpineJsonlStore(path)
    chain = _chain()
    store.append_event(chain.events[0])
    before = path.read_bytes()
    store.append_event(chain.events[0])
    assert path.read_bytes() == before
    store.append_event(chain.events[1])
    assert store.load().project().total_events == 2
    assert store.load().verify_integrity().ok
    assert not (tmp_path / "spine.jsonl.write-lock").exists()


def test_spine_rejects_wrong_previous_hash_without_destroying_file(tmp_path) -> None:
    path = tmp_path / "spine.jsonl"
    store = CanonicalSpineJsonlStore(path)
    first = _chain()
    store.append_event(first.events[0])
    previous = path.read_bytes()
    forged = first.events[1].model_copy(update={"prev_event_hash": "f" * 64})
    with pytest.raises(ValueError, match="invalid canonical spine"):
        store.append_event(forged)
    assert path.read_bytes() == previous
    assert store.load().verify_integrity().ok


def test_spine_save_rejects_stale_or_modified_history(tmp_path) -> None:
    store = CanonicalSpineJsonlStore(tmp_path / "spine.jsonl")
    good = _chain()
    store.save(good)
    before = store.path.read_bytes()
    other = CanonicalSpine()
    other.append(event_type="different.event", task_id="other", source="trusted")
    with pytest.raises(ValueError, match="spine_snapshot_would_rewrite_history"):
        store.save(other)
    assert store.path.read_bytes() == before


def test_spine_atomic_replace_failure_preserves_original_bytes(
    tmp_path, monkeypatch,
) -> None:
    path = tmp_path / "spine.jsonl"
    store = CanonicalSpineJsonlStore(path)
    chain = _chain()
    store.append_event(chain.events[0])
    previous = path.read_bytes()
    def explode(*args):
        raise OSError("replace interrupted")
    monkeypatch.setattr(durable.os, "replace", explode)
    with pytest.raises(OSError, match="replace interrupted"):
        store.append_event(chain.events[1])
    assert path.read_bytes() == previous
    assert store.load().project().total_events == 1
    assert not (tmp_path / "spine.jsonl.write-lock").exists()


def test_spine_invalid_on_disk_prohibits_replacement(tmp_path) -> None:
    path = tmp_path / "spine.jsonl"
    path.write_text('{"not":"a spine"}\n', encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError):
        CanonicalSpineJsonlStore(path).save(_chain())
    assert path.read_bytes() == before


def test_spine_event_identity_collision_rejected(tmp_path) -> None:
    path = tmp_path / "spine.jsonl"
    store = CanonicalSpineJsonlStore(path)
    chain = _chain()
    store.append_event(chain.events[0])
    changed = chain.events[0].model_copy(update={"event_type": "bad.event"})
    before = path.read_bytes()
    with pytest.raises(ValueError, match="spine_event_id_collision"):
        store.append_event(changed)
    assert path.read_bytes() == before


def test_disk_payload_tampering_stops_append(tmp_path) -> None:
    path = tmp_path / "spine.jsonl"
    store = CanonicalSpineJsonlStore(path)
    chain = _chain()
    store.append_event(chain.events[0])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["payload"]["fake"] = "bad"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="event_hash_mismatch"):
        store.append_event(chain.events[1])
