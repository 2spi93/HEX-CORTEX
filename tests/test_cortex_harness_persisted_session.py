"""Historic CanonicalSpine receipts must not block a new verified local session."""
from __future__ import annotations

from pathlib import Path

import pytest

from hex_cortex.memory.cortex_local_cognitive_cycle import run_clocked_local_task
from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget, Capability, LocalHarness, Session, Task, build_readonly_harness,
)
from hex_cortex.memory.cortex_memory_augmented_run import run_memory_augmented_task
from hex_cortex.memory.verified_learning_loop import VerifiedLearningLoop
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


def _save_historic_spine(tmp_path: Path):
    old = build_readonly_harness(tmp_path, session_id="historic-session")
    result = run_clocked_local_task(
        old, Task("historic-task", "repo_read", "Check old files", "repo_manifest"),
        approved=True,
    )
    assert result["status"] == "complete"
    assert old.verify_replay()
    path = Path("history.jsonl")
    old.save_spine(path, approved=True)
    return CanonicalSpineJsonlStore(tmp_path / path).load()


def test_new_session_verifies_historic_spine_and_new_receipt(tmp_path: Path) -> None:
    spine = _save_historic_spine(tmp_path)
    harness = LocalHarness(
        session=Session("new-session", tmp_path),
        grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1),
        spine=spine,
    )
    assert harness.verify_replay()
    calls: list[str] = []

    def fake_brain(_model: str, task: Task) -> str:
        calls.append(task.instruction)
        return "OK"

    result = run_memory_augmented_task(
        harness=harness,
        learning=VerifiedLearningLoop(spine=spine),
        task=Task("new-task", "general", "What happened?"),
        models=["local"], brain=fake_brain,
        approve_model=True,
    )
    assert result["status"] == "complete"
    assert calls == ["What happened?"]
    assert harness.verify_replay()


def test_reusing_historic_session_id_does_not_skip_existing_receipts(
    tmp_path: Path,
) -> None:
    spine = _save_historic_spine(tmp_path)
    fresh = LocalHarness(session=Session("historic-session", tmp_path), spine=spine)
    assert fresh.verify_replay() is False


def test_corrupted_historic_spine_is_still_rejected(tmp_path: Path) -> None:
    spine = _save_historic_spine(tmp_path)
    spine._events[0].payload["modified"] = True
    harness = LocalHarness(session=Session("new-session", tmp_path), spine=spine)
    assert harness.verify_replay() is False
    with pytest.raises(ValueError, match="harness_receipt_integrity_failed"):
        run_memory_augmented_task(
            harness=harness, learning=VerifiedLearningLoop(spine=spine),
            task=Task("new-task", "general", "What happened?"),
            models=["local"], brain=lambda _m, _t: "answer",
            approve_model=True,
        )
