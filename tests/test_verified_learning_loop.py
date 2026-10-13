"""CPU-only end-to-end checks of the governed replay/learning/retrieval loop."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_local_harness_v2 import LocalHarness, Session, Task
from hex_cortex.memory.schemas import RetrievalMethod, RetrievalQuery
from hex_cortex.memory.memory_promotion import PromotionStatus
from hex_cortex.memory.verified_learning_loop import VerifiedLearningLoop
from hex_cortex.replay.schemas import ReplayStatus
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


def _spine(task_id: str = "task_a") -> CanonicalSpine:
    spine = CanonicalSpine()
    spine.append(
        event_type="task.received", task_id=task_id, source="test",
        payload={"goal": "Compute Fibonacci sequence"}, confidence=0.95,
    )
    spine.append(
        event_type="routing.decision", task_id=task_id, source="router",
        payload={"selected_cells": ["logic_cell"]}, confidence=0.9,
    )
    spine.append(
        event_type="clock.completed", task_id=task_id, source="clock",
        payload={"completed": True}, confidence=0.95,
    )
    assert spine.verify_integrity().ok
    return spine


def _query() -> RetrievalQuery:
    return RetrievalQuery(query="Fibonacci sequence")


def test_readonly_default_does_not_mutate_index() -> None:
    loop = VerifiedLearningLoop(spine=_spine())
    result = loop.run(task_id="task_a", query=_query())
    assert result.replay.status == ReplayStatus.CONSOLIDATED
    assert result.promotion is None
    assert result.context.method == RetrievalMethod.EMPTY
    assert not loop.index.entries
    assert not loop.checkpoint_records


def test_approved_promotion_is_retrievable_and_repeat_is_duplicate() -> None:
    loop = VerifiedLearningLoop(spine=_spine())
    first = loop.run(task_id="task_a", query=_query(), approve_promotion=True)
    assert first.promotion is not None
    assert first.promotion.status == PromotionStatus.PROMOTED
    assert first.context.method in {RetrievalMethod.EXACT, RetrievalMethod.LEXICAL}
    assert "Fibonacci" in first.context.context_text
    second = loop.run(task_id="task_a", query=_query(), approve_promotion=True)
    assert second.promotion is not None
    assert second.promotion.status == PromotionStatus.DUPLICATE
    assert len(loop.index.entries) == 1
    assert len(loop.checkpoint_records) == 1


def test_invalid_spine_rejects_without_mutation() -> None:
    spine = _spine()
    spine._events[0].payload["goal"] = "tampered"
    loop = VerifiedLearningLoop(spine=spine)
    result = loop.run(task_id="task_a", query=_query(), approve_promotion=True)
    assert result.replay.status == ReplayStatus.INTEGRITY_FAILED
    assert result.promotion is None
    assert not loop.index.entries


def test_checkpoint_roundtrip_replays_from_persisted_spine(tmp_path: Path) -> None:
    spine = _spine()
    loop = VerifiedLearningLoop(spine=spine)
    loop.run(task_id="task_a", query=_query(), approve_promotion=True)
    CanonicalSpineJsonlStore(tmp_path / "spine.jsonl").save(spine)
    checkpoint = loop.save_checkpoint(
        project_root=tmp_path, relative_path=Path("checkpoints/learning.jsonl"),
        approved=True,
    )
    assert checkpoint.is_file()
    assert "Fibonacci" not in checkpoint.read_text(encoding="utf-8")
    restored_spine = CanonicalSpineJsonlStore(tmp_path / "spine.jsonl").load()
    restored = VerifiedLearningLoop.restore_checkpoint(
        project_root=tmp_path,
        relative_path=Path("checkpoints/learning.jsonl"),
        spine=restored_spine,
    )
    assert len(restored.index.entries) == 1
    assert len(restored.checkpoint_records) == 1
    retrieval = restored.run(task_id="task_unseen", query=_query())
    assert retrieval.context.results


def test_checkpoint_requires_approval_and_refuses_overwrite(tmp_path: Path) -> None:
    loop = VerifiedLearningLoop(spine=_spine())
    loop.run(task_id="task_a", query=_query(), approve_promotion=True)
    relative = Path("checkpoint.jsonl")
    with pytest.raises(PermissionError):
        loop.save_checkpoint(project_root=tmp_path, relative_path=relative)
    assert not (tmp_path / relative).exists()
    loop.save_checkpoint(project_root=tmp_path, relative_path=relative, approved=True)
    with pytest.raises(FileExistsError):
        loop.save_checkpoint(project_root=tmp_path, relative_path=relative, approved=True)


def test_checkpoint_rejects_malformed_or_changed_proofs(tmp_path: Path) -> None:
    spine = _spine()
    loop = VerifiedLearningLoop(spine=spine)
    loop.run(task_id="task_a", query=_query(), approve_promotion=True)
    path = loop.save_checkpoint(
        project_root=tmp_path, relative_path=Path("checkpoint.jsonl"), approved=True
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["records"][0]["promotion_hash"] = "f" * 64
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="checkpoint_content_mismatch"):
        VerifiedLearningLoop.restore_checkpoint(
            project_root=tmp_path, relative_path=Path("checkpoint.jsonl"), spine=spine
        )
    payload["records"][0]["promotion_hash"] = loop.checkpoint_records[0]["promotion_hash"]
    payload["spine_tip"] = "bad"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="checkpoint_spine_or_format_mismatch"):
        VerifiedLearningLoop.restore_checkpoint(
            project_root=tmp_path, relative_path=Path("checkpoint.jsonl"), spine=spine
        )


def test_checkpoint_rejects_path_escape(tmp_path: Path) -> None:
    loop = VerifiedLearningLoop(spine=_spine())
    with pytest.raises(ValueError, match="checkpoint_outside_project_root"):
        loop.save_checkpoint(
            project_root=tmp_path, relative_path=Path("../outside.jsonl"), approved=True
        )


def test_wrong_harness_or_failed_receipt_fails_closed(tmp_path: Path) -> None:
    spine = _spine()
    loop = VerifiedLearningLoop(spine=spine)
    harness = LocalHarness(session=Session("test", tmp_path))
    with pytest.raises(ValueError, match="unverified_or_incomplete_harness_task"):
        loop.run_from_harness(harness=harness, task_id="task_a", query=_query(),
                              approve_promotion=True)
    assert not loop.index.entries


def test_verified_harness_receipt_can_run_without_implicit_promotion(
    tmp_path: Path,
) -> None:
    spine = CanonicalSpine()
    harness = LocalHarness(session=Session("test", tmp_path), spine=spine)
    receipt = harness.execute(Task(task_id="a", domain="math", instruction="Hello"))
    assert receipt["status"] == "complete"
    assert harness.verify_replay()
    loop = VerifiedLearningLoop(spine=spine)
    result = loop.run_from_harness(harness=harness, task_id="a", query=_query())
    assert result.replay.status == ReplayStatus.CONSOLIDATED
    assert result.promotion is None
    assert not loop.index.entries


def test_restore_rejects_duplicate_task_ids_without_partial_index(
    tmp_path: Path,
) -> None:
    spine = _spine()
    loop = VerifiedLearningLoop(spine=spine)
    loop.run(task_id="task_a", query=_query(), approve_promotion=True)
    checkpoint = loop.save_checkpoint(
        project_root=tmp_path, relative_path=Path("checkpoint.jsonl"), approved=True
    )
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    payload["records"].append(dict(payload["records"][0]))
    checkpoint.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid_or_duplicate_checkpoint_task"):
        VerifiedLearningLoop.restore_checkpoint(
            project_root=tmp_path, relative_path=Path("checkpoint.jsonl"), spine=spine
        )
