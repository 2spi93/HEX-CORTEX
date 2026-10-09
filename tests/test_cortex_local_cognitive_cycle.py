"""Clocked local task integration uses legacy CognitiveClock and CanonicalSpine."""

from __future__ import annotations

from pathlib import Path

from hex_cortex.memory.cortex_local_cognitive_cycle import run_clocked_local_task
from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget,
    Capability,
    LocalHarness,
    Session,
    Task,
    build_readonly_harness,
)
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


def test_clocked_read_records_real_spine_events(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("visible", encoding="utf-8")
    harness = build_readonly_harness(tmp_path)
    outcome = run_clocked_local_task(
        harness, Task("clock1", "repo_read", "Inspect", "repo_manifest"), approved=True
    )
    assert outcome["status"] == "complete"
    assert outcome["clock_completed"] is True
    assert outcome["canonical_spine_verified"] is True
    assert [row["name"] for row in outcome["tick_statuses"]] == [
        "intake", "routing", "action", "critic", "spine_verify",
    ]
    assert harness.verify_replay()
    assert harness.spine.latest_by_type("harness.receipt") is not None
    assert "Inspect" not in str([e.model_dump() for e in harness.spine.events])
    assert outcome["canonical_spine_event_count"] >= 10


def test_clocked_denial_stops_before_critic(tmp_path: Path) -> None:
    harness = build_readonly_harness(tmp_path)
    outcome = run_clocked_local_task(
        harness, Task("clock2", "repo_read", "Inspect", "repo_manifest"),
        approved=False,
    )
    assert outcome["status"] == "blocked"
    assert outcome["clock_completed"] is False
    assert outcome["tick_statuses"][-1]["name"] == "action"
    assert harness.verify_replay()


def test_clocked_model_output_never_appears_in_spine(tmp_path: Path) -> None:
    harness = LocalHarness(
        Session("clock-session", tmp_path),
        grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1),
    )
    outcome = run_clocked_local_task(
        harness, Task("clock3", "coding", "private sensitive prompt"),
        models=["local-brain"],
        brain=lambda _model, _task: "private generated response",
        approved=True,
    )
    assert outcome["clock_completed"] is True
    assert outcome["output"] == "private generated response"
    serialized = str([event.model_dump() for event in harness.spine.events])
    assert "private sensitive prompt" not in serialized
    assert "private generated response" not in serialized


def test_persisting_spine_requires_approval_and_new_path(tmp_path: Path) -> None:
    harness = build_readonly_harness(tmp_path)
    run_clocked_local_task(
        harness, Task("clock4", "read", "Inspect", "repo_manifest"), approved=True
    )
    from pytest import raises

    target = Path("receipts/run.jsonl")
    with raises(PermissionError):
        harness.save_spine(target)
    count = harness.save_spine(target, approved=True)
    assert count == len(harness.spine.events)
    assert CanonicalSpineJsonlStore(tmp_path / target).load().verify_integrity().ok
    with raises(ValueError):
        harness.save_spine(target, approved=True)
    with raises(ValueError):
        harness.save_spine(Path("../outside.jsonl"), approved=True)
