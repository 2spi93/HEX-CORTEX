"""Regression tests for the local Harness V2 permission and replay boundary."""

from __future__ import annotations

from pathlib import Path

from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget,
    Capability,
    LocalHarness,
    Session,
    Task,
    Tool,
    build_readonly_harness,
    read_repo_manifest,
)


def test_manifest_runs_only_after_explicit_approval(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    harness = build_readonly_harness(tmp_path)
    denied = harness.execute(Task("t1", "coding", "Inventory", "repo_manifest"))
    assert denied["status"] == "blocked"
    assert denied["reason"] == "tool_not_authorized"
    approved = harness.execute(
        Task("t2", "coding", "Inventory", "repo_manifest"), approved=True
    )
    assert approved["tool_result"]["manifest"] == ["pyproject.toml"]
    assert harness.verify_replay()


def test_model_routing_with_explicit_grant_and_budget(tmp_path: Path) -> None:
    harness = LocalHarness(
        Session("s", tmp_path), grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1), priors={"small": 0.7, "large": 0.2},
    )
    observed = []

    def brain(model: str, task: Task) -> str:
        observed.append((model, task.task_id))
        return "validated"

    first = harness.execute(
        Task("t1", "coding", "Explain test"),
        models=["large", "small"], brain=brain, approved=True,
    )
    assert first["output"] == "validated"
    assert first["receipt"]["model_used"] == "small"
    assert observed == [("small", "t1")]
    second = harness.execute(
        Task("t2", "coding", "Explain another test"),
        models=["small"], brain=brain, approved=True,
    )
    assert second["reason"] == "model_call_budget_exhausted"
    assert observed == [("small", "t1")]
    assert harness.verify_replay()


def test_patch_action_is_always_denied(tmp_path: Path) -> None:
    calls = []

    def patch(session: Session, task: Task) -> dict[str, object]:
        calls.append(task.task_id)
        return {"mutated": True}

    harness = LocalHarness(
        Session("s", tmp_path),
        grants=frozenset({Capability.APPLY_PATCH}),
        budget=Budget(max_tool_calls=4),
        tools={"patch": Tool("patch", Capability.APPLY_PATCH, patch, modifies_files=True)},
    )
    result = harness.execute(
        Task("patch1", "coding", "Patch file", "patch"), approved=True
    )
    assert result["reason"] == "mutating_tools_not_supported_in_local_kernel"
    assert calls == []


def test_cross_project_session_rejected(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ValueError, match="identity"):
        Session("cross", tmp_path, project_id="GTIXT")


def test_duplicate_task_ids_blocked_without_reexecution(tmp_path: Path) -> None:
    count = [0]

    def tool(session: Session, task: Task) -> dict[str, object]:
        count[0] += 1
        return dict(read_repo_manifest(session, task))

    harness = LocalHarness(
        Session("s", tmp_path), grants=frozenset({Capability.READ_REPO}),
        budget=Budget(max_tool_calls=2),
        tools={"manifest": Tool("manifest", Capability.READ_REPO, tool)},
    )
    task = Task("id", "read", "Inventory", "manifest")
    assert harness.execute(task, approved=True)["status"] == "complete"
    assert harness.execute(task, approved=True)["reason"] == "duplicate_task_id"
    assert count == [1]
    assert harness.verify_replay()


def test_redacted_receipts_and_tamper_detection(tmp_path: Path) -> None:
    harness = LocalHarness(
        Session("s", tmp_path), grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1),
    )
    result = harness.execute(
        Task("t", "coding", "secret prompt"),
        models=["model"], brain=lambda _model, _task: "private output",
        approved=True,
    )
    assert result["status"] == "complete"
    assert "secret prompt" not in str(harness.receipts)
    assert "private output" not in str(harness.receipts)
    harness.receipts[0]["status"] = "blocked"
    assert harness.verify_replay() is False


def test_unknown_tools_fail_closed(tmp_path: Path) -> None:
    harness = build_readonly_harness(tmp_path)
    result = harness.execute(Task("bad", "read", "unknown", "shell"), approved=True)
    assert result["status"] == "blocked"
    assert result["reason"] == "tool_not_allowlisted"
