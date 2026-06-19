import hashlib
from pathlib import Path

from hex_cortex.memory.cortex_worktree_executor import build_worktree_plan
from hex_cortex.memory.cortex_worktree_executor import run_allowlisted_checks


def test_worktree_plan_is_isolated_and_non_merging(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    payload = build_worktree_plan(
        repository_root=repo,
        worktree_root=tmp_path / "worktrees",
        candidate_id="candidate-001",
        base_ref="main",
        check_ids=["pytest", "ruff"],
    )

    assert payload["status"] == "ready"
    assert payload["shell_allowed"] is False
    assert payload["arbitrary_command_allowed"] is False
    assert payload["automatic_merge_allowed"] is False
    assert payload["operator_approval_required"] is True
    assert payload["execution_performed"] is False


def test_worktree_plan_rejects_path_like_candidate_id(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    payload = build_worktree_plan(
        repository_root=repo,
        worktree_root=tmp_path / "worktrees",
        candidate_id="../escape",
        base_ref="main",
    )

    assert payload["status"] == "blocked"
    assert "candidate_id_invalid" in payload["blockers"]


def test_worktree_plan_rejects_non_allowlisted_check(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    payload = build_worktree_plan(
        repository_root=repo,
        worktree_root=tmp_path / "worktrees",
        candidate_id="candidate-002",
        base_ref="main",
        check_ids=["powershell-anything"],
    )

    assert payload["status"] == "blocked"
    assert "check_not_allowlisted" in payload["blockers"]


def test_allowlisted_checks_require_operator_approval(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    (worktree / ".git").mkdir(parents=True)

    payload = run_allowlisted_checks(
        worktree_path=worktree,
        check_ids=["compileall"],
        operator_approved=False,
    )

    assert payload["status"] == "blocked"
    assert payload["execution_performed"] is False
    assert payload["blockers"] == ["operator_approval_required"]
    assert len(payload["receipt_hash"]) == len(hashlib.sha256().hexdigest())
