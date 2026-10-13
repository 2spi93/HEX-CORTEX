"""No-network tests for the real Brain/Harness memory context boundary."""
from __future__ import annotations

from pathlib import Path

import pytest

from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget,
    Capability,
    LocalHarness,
    Session,
    Task,
)
from hex_cortex.memory.cortex_memory_augmented_run import run_memory_augmented_task
from hex_cortex.memory.local_index import LocalKnowledgeIndex
from hex_cortex.memory.schemas import IndexEntry, RetrievalQuery
from hex_cortex.memory.verified_learning_loop import VerifiedLearningLoop
from hex_cortex.spine.canonical_spine import CanonicalSpine


def _training_spine() -> CanonicalSpine:
    spine = CanonicalSpine()
    spine.append(
        event_type="task.received", task_id="training", source="test",
        payload={"goal": "Calculate Fibonacci sequence by recurrence"},
        confidence=0.9,
    )
    spine.append(
        event_type="routing.decision", task_id="training", source="test",
        payload={"selected_cells": ["logic_cell"]},
        confidence=0.9,
    )
    spine.append(
        event_type="clock.completed", task_id="training", source="test",
        payload={"completed": True},
        confidence=0.9,
    )
    return spine


def _harness(path: Path, spine: CanonicalSpine, *, authorized: bool = True) -> LocalHarness:
    return LocalHarness(
        session=Session("local-memory-test", path),
        spine=spine,
        grants=frozenset({Capability.CALL_MODEL}) if authorized else frozenset(),
        budget=Budget(max_model_calls=1, max_tool_calls=0),
    )


def _prepared(path: Path) -> tuple[VerifiedLearningLoop, LocalHarness]:
    spine = _training_spine()
    loop = VerifiedLearningLoop(spine=spine)
    report = loop.run(
        task_id="training", query=RetrievalQuery(query="Fibonacci"),
        approve_promotion=True,
    )
    assert report.promotion is not None and report.promotion.status.value == "promoted"
    return loop, _harness(path, spine)


def test_context_arrives_only_after_both_approvals(tmp_path: Path) -> None:
    loop, harness = _prepared(tmp_path)
    calls: list[str] = []

    def fake_brain(_model: str, task: Task) -> str:
        calls.append(task.instruction)
        return "calculated"

    result = run_memory_augmented_task(
        harness=harness, learning=loop,
        task=Task("next_task", "math", "Calculate Fibonacci"),
        models=["local-test"], brain=fake_brain,
        approve_model=True, approve_memory_use=True,
        query=RetrievalQuery(query="Fibonacci"),
    )
    assert result["status"] == "complete"
    assert result["memory_context"]["retrieved_count"] == 1
    assert "UNTRUSTED retrieved memory data" in calls[0]
    assert "Fibonacci sequence" in calls[0]
    assert "Operator question:\nCalculate Fibonacci" in calls[0]
    assert result["memory_context"]["amplification_measured"] is False
    assert harness.verify_replay()


def test_plain_model_call_does_not_include_memory(tmp_path: Path) -> None:
    loop, harness = _prepared(tmp_path)
    calls: list[str] = []

    def fake_brain(_model: str, task: Task) -> str:
        calls.append(task.instruction)
        return "answer"

    result = run_memory_augmented_task(
        harness=harness, learning=loop,
        task=Task("next_task", "math", "Calculate Fibonacci"),
        models=["local-test"], brain=fake_brain,
        approve_model=True,
    )
    assert calls == ["Calculate Fibonacci"]
    assert result["memory_context"]["retrieved_count"] == 0
    assert result["memory_context"]["enabled"] is False


def test_no_model_approval_never_invokes_brain(tmp_path: Path) -> None:
    loop, harness = _prepared(tmp_path)
    calls: list[str] = []

    def fake_brain(_model: str, _task: Task) -> str:
        calls.append("called")
        return "answer"

    result = run_memory_augmented_task(
        harness=harness, learning=loop, task=Task("next", "math", "question"),
        models=["local-test"], brain=fake_brain,
    )
    assert result["status"] == "blocked"
    assert calls == []
    with pytest.raises(ValueError, match="model_approval_required_for_memory_use"):
        run_memory_augmented_task(
            harness=harness, learning=loop, task=Task("next_2", "math", "question"),
            models=["local-test"], brain=fake_brain, approve_memory_use=True,
        )


def test_unverified_index_entry_never_enters_context(tmp_path: Path) -> None:
    loop, harness = _prepared(tmp_path)
    loop.index.add_entry(IndexEntry(
        path="memory://untrusted/1", title="Fibonacci",
        text="SPOOFED CONTEXT DO NOT TRUST",
        tags=["promoted"],
    ))
    captured: list[str] = []

    def fake_brain(_model: str, task: Task) -> str:
        captured.append(task.instruction)
        return "answer"

    result = run_memory_augmented_task(
        harness=harness, learning=loop,
        task=Task("next", "math", "Fibonacci"),
        models=["local-test"], brain=fake_brain,
        approve_model=True, approve_memory_use=True,
    )
    assert result["status"] == "complete"
    assert "SPOOFED" not in captured[0]
    assert result["memory_context"]["retrieved_count"] == 1


def test_current_task_source_is_not_retrieved(tmp_path: Path) -> None:
    loop, harness = _prepared(tmp_path)
    captured: list[str] = []

    def fake_brain(_model: str, task: Task) -> str:
        captured.append(task.instruction)
        return "answer"

    result = run_memory_augmented_task(
        harness=harness, learning=loop,
        task=Task("training", "math", "Fibonacci"),
        models=["local-test"], brain=fake_brain,
        approve_model=True, approve_memory_use=True,
    )
    assert result["status"] == "complete"
    assert result["memory_context"]["retrieved_count"] == 0
    assert captured == ["Fibonacci"]


def test_tampered_spine_fails_before_brain(tmp_path: Path) -> None:
    loop, harness = _prepared(tmp_path)
    loop.spine._events[0].payload["goal"] = "tampered"
    called: list[bool] = []

    def fake_brain(_model: str, _task: Task) -> str:
        called.append(True)
        return "answer"

    with pytest.raises(ValueError, match="harness_receipt_integrity_failed"):
        run_memory_augmented_task(
            harness=harness, learning=loop,
            task=Task("next", "math", "Fibonacci"),
            models=["test"], brain=fake_brain,
            approve_model=True, approve_memory_use=True,
        )
    assert called == []


def test_mismatched_spine_and_deny_list_fail_closed(tmp_path: Path) -> None:
    loop, _h = _prepared(tmp_path)
    different = _harness(tmp_path, CanonicalSpine())
    with pytest.raises(ValueError, match="harness_learning_spine_mismatch"):
        run_memory_augmented_task(
            harness=different, learning=loop,
            task=Task("next", "math", "Fibonacci"), models=["test"],
            brain=lambda _model, _task: "answer", approve_model=True,
        )
    denied = _harness(tmp_path, loop.spine, authorized=False)
    called: list[bool] = []

    def fake_brain(_model: str, _task: Task) -> str:
        called.append(True)
        return "answer"

    result = run_memory_augmented_task(
        harness=denied, learning=loop,
        task=Task("next", "math", "Fibonacci"),
        models=["test"], brain=fake_brain,
        approve_model=True, approve_memory_use=True,
    )
    assert result["status"] == "blocked"
    assert not called


def test_context_is_capped(tmp_path: Path) -> None:
    loop, harness = _prepared(tmp_path)
    result = run_memory_augmented_task(
        harness=harness, learning=loop,
        task=Task("next", "math", "Fibonacci"),
        models=["test"], brain=lambda _model, _task: "answer",
        approve_model=True, approve_memory_use=True,
        query=RetrievalQuery(query="Fibonacci", max_context_chars=8_000),
    )
    assert result["status"] == "complete"
    assert 0 < result["memory_context"]["used_context_chars"] <= 3_000


def test_no_unnecessary_memory_index_side_effects(tmp_path: Path) -> None:
    loop, harness = _prepared(tmp_path)
    before = len(loop.index.entries)
    assert isinstance(loop.index, LocalKnowledgeIndex)
    run_memory_augmented_task(
        harness=harness, learning=loop,
        task=Task("next", "math", "Fibonacci"),
        models=["test"], brain=lambda _model, _task: "answer",
        approve_model=True, approve_memory_use=True,
    )
    assert len(loop.index.entries) == before
    assert len(loop.checkpoint_records) == 1
