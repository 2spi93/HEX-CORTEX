"""Fail-closed Hands checks: original checkout never patched, no untrusted pytest."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from hex_cortex.memory import cortex_worktree_executor as hands


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "original"
    (repo / ".git").mkdir(parents=True)
    return repo


def _worktree(tmp_path: Path) -> Path:
    worktree = tmp_path / "linked-worktree"
    worktree.mkdir()
    (worktree / ".git").write_text(
        "gitdir: C:/example/original/.git/worktrees/isolated\n", encoding="utf-8"
    )
    return worktree


def test_forged_plan_target_does_not_launch_git(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    plan = hands.build_worktree_plan(
        repository_root=repo, worktree_root=tmp_path / "worktrees",
        candidate_id="candidate-a", base_ref="main",
    )
    assert plan["status"] == "ready"
    plan["worktree_path"] = str(repo)
    calls = []
    monkeypatch.setattr(hands, "_run", lambda *a, **k: calls.append(a))
    report = hands.create_isolated_worktree(plan, operator_approved=True)
    assert report["status"] == "blocked"
    assert "worktree_plan_tampered_or_stale" in report["blockers"]
    assert calls == []


def test_forged_plan_hash_is_not_authorization(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    plan = hands.build_worktree_plan(
        repository_root=repo, worktree_root=tmp_path / "worktrees",
        candidate_id="candidate-a", base_ref="main",
    )
    plan["plan_hash"] = "f" * 64
    calls = []
    monkeypatch.setattr(hands, "_run", lambda *a, **k: calls.append(a))
    report = hands.create_isolated_worktree(plan, operator_approved=True)
    assert "worktree_plan_tampered_or_stale" in report["blockers"]
    assert not calls


def test_valid_plan_runs_only_approved_git_worktree(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    root = tmp_path / "worktrees"
    plan = hands.build_worktree_plan(
        repository_root=repo, worktree_root=root,
        candidate_id="candidate-a", base_ref="main",
        check_ids=["ruff"],
    )
    calls = []
    def fake_run(args, *, cwd, timeout_seconds):
        calls.append((args, cwd))
        Path(args[4]).mkdir(parents=True)
        return {"returncode": 0, "stdout_hash": "a" * 64, "stderr_hash": "b" * 64}
    monkeypatch.setattr(hands, "_run", fake_run)
    receipt = hands.create_isolated_worktree(plan, operator_approved=True)
    assert receipt["status"] == "created"
    assert receipt["merge_performed"] is False
    assert calls[0][0][:4] == ["git", "worktree", "add", "--detach"]
    assert calls[0][1] == repo


def test_original_checkout_never_receives_reviewable_patch(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    patch = tmp_path / "safe.patch"
    patch.write_text("fake patch", encoding="utf-8")
    calls = []
    monkeypatch.setattr(hands, "_run", lambda *a, **k: calls.append(a))
    result = hands.apply_reviewable_patch(
        worktree_path=repo, patch_path=patch,
        expected_patch_hash=hashlib.sha256(patch.read_bytes()).hexdigest(),
        operator_approved=True,
    )
    assert result["status"] == "blocked"
    assert "isolated_linked_worktree_required" in result["blockers"]
    assert calls == []
    assert patch.read_text(encoding="utf-8") == "fake patch"


def test_original_checkout_never_receives_automated_checks(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    calls = []
    monkeypatch.setattr(hands, "_run", lambda *a, **k: calls.append(a))
    result = hands.run_allowlisted_checks(
        worktree_path=repo, check_ids=["ruff"], operator_approved=True
    )
    assert result["status"] == "blocked"
    assert "isolated_linked_worktree_required" in result["blockers"]
    assert calls == []


def test_unsandboxed_pytest_blocked_even_if_operator_approved(
    tmp_path: Path, monkeypatch
) -> None:
    worktree = _worktree(tmp_path)
    calls = []
    monkeypatch.setattr(hands, "_run", lambda *a, **k: calls.append(a))
    result = hands.run_allowlisted_checks(
        worktree_path=worktree,
        check_ids=["ruff", "pytest"],
        operator_approved=True,
    )
    assert result["status"] == "blocked"
    assert "untrusted_pytest_requires_os_sandbox" in result["blockers"]
    assert calls == []


def test_ruff_safe_static_check_still_works_with_approval(
    tmp_path: Path, monkeypatch
) -> None:
    worktree = _worktree(tmp_path)
    calls = []
    def fake_run(cmd, *, cwd, timeout_seconds):
        calls.append(cmd)
        return {"returncode": 0, "stdout_hash": "a" * 64, "stderr_hash": "b" * 64}
    monkeypatch.setattr(hands, "_run", fake_run)
    report = hands.run_allowlisted_checks(
        worktree_path=worktree, check_ids=["ruff"], operator_approved=True
    )
    assert report["status"] == "passed"
    assert report["merge_allowed"] is False
    assert len(calls) == 1
    assert calls[0][-3:] == ["ruff", "check", "."]


def test_git_marker_symlink_is_rejected_when_supported(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    elsewhere = tmp_path / "fake-gitdir"
    elsewhere.write_text("gitdir: /path/to/worktree", encoding="utf-8")
    try:
        (worktree / ".git").symlink_to(elsewhere)
    except (OSError, NotImplementedError):
        pytest.skip("host symlinks not permitted")
    assert hands._is_linked_worktree(worktree) is False

def test_untrusted_compileall_is_also_blocked(tmp_path: Path, monkeypatch) -> None:
    worktree = _worktree(tmp_path)
    calls = []
    monkeypatch.setattr(hands, "_run", lambda *a, **k: calls.append(a))
    report = hands.run_allowlisted_checks(
        worktree_path=worktree, check_ids=["compileall"], operator_approved=True,
    )
    assert report["status"] == "blocked"
    assert "untrusted_python_requires_os_sandbox" in report["blockers"]
    assert calls == []


def test_new_default_plan_contains_only_static_ruff(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    plan = hands.build_worktree_plan(
        repository_root=repo, worktree_root=tmp_path / "worktrees",
        candidate_id="safe-candidate", base_ref="main",
    )
    assert plan["status"] == "ready"
    assert plan["check_ids"] == ["ruff"]
