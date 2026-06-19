from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

_CANDIDATE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_CHECKS = {
    "pytest": [sys.executable, "-m", "pytest"],
    "ruff": [sys.executable, "-m", "ruff", "check", "."],
    "compileall": [sys.executable, "-m", "compileall", "-q", "src"],
}


def build_worktree_plan(
    *,
    repository_root: Path,
    worktree_root: Path,
    candidate_id: str,
    base_ref: str,
    check_ids: list[str] | None = None,
) -> dict[str, object]:
    blockers: list[str] = []
    repo = repository_root.resolve()
    root = worktree_root.resolve()
    if not (repo / ".git").exists():
        blockers.append("repository_root_not_git")
    if not _CANDIDATE_RE.fullmatch(candidate_id):
        blockers.append("candidate_id_invalid")
    if not base_ref.strip() or base_ref.startswith("-"):
        blockers.append("base_ref_invalid")
    target = (root / candidate_id).resolve()
    if not target.is_relative_to(root):
        blockers.append("worktree_path_escape")
    if target.exists():
        blockers.append("worktree_target_exists")
    checks = check_ids or ["pytest", "ruff"]
    invalid_checks = [check for check in checks if check not in _CHECKS]
    if invalid_checks:
        blockers.append("check_not_allowlisted")
    payload = {
        "plan_type": "isolated_worktree_plan_v1",
        "status": "ready" if not blockers else "blocked",
        "repository_root": str(repo),
        "worktree_root": str(root),
        "worktree_path": str(target),
        "candidate_id": candidate_id,
        "base_ref": base_ref,
        "check_ids": checks,
        "shell_allowed": False,
        "arbitrary_command_allowed": False,
        "automatic_merge_allowed": False,
        "operator_approval_required": True,
        "execution_performed": False,
        "blockers": sorted(set(blockers)),
        "next_action": "create_isolated_worktree" if not blockers else "repair_worktree_plan",
    }
    payload["plan_hash"] = _stable_hash(payload)
    return payload


def create_isolated_worktree(
    plan: dict[str, object],
    *,
    operator_approved: bool = False,
    timeout_seconds: float = 120.0,
) -> dict[str, object]:
    if not operator_approved:
        return _blocked("operator_approval_required")
    if plan.get("status") != "ready":
        return _blocked("worktree_plan_not_ready")
    repo = Path(str(plan["repository_root"])).resolve()
    target = Path(str(plan["worktree_path"])).resolve()
    root = Path(str(plan["worktree_root"])).resolve()
    if not target.is_relative_to(root):
        return _blocked("worktree_path_escape")
    if target.exists():
        return _blocked("worktree_target_exists")
    root.mkdir(parents=True, exist_ok=True)
    result = _run(
        ["git", "worktree", "add", "--detach", str(target), str(plan["base_ref"])],
        cwd=repo,
        timeout_seconds=timeout_seconds,
    )
    created = result["returncode"] == 0 and target.exists()
    receipt = {
        "receipt_type": "isolated_worktree_create_v1",
        "status": "created" if created else "failed",
        "plan_hash": plan.get("plan_hash"),
        "candidate_id": plan.get("candidate_id"),
        "worktree_path": str(target),
        "command_id": "git_worktree_add_detached",
        "returncode": result["returncode"],
        "stdout_hash": result["stdout_hash"],
        "stderr_hash": result["stderr_hash"],
        "raw_output_persisted": False,
        "execution_performed": True,
        "merge_performed": False,
        "blockers": [] if created else ["git_worktree_create_failed"],
        "next_action": "apply_reviewable_patch" if created else "repair_worktree_creation",
    }
    receipt["receipt_hash"] = _stable_hash(receipt)
    return receipt


def apply_reviewable_patch(
    *,
    worktree_path: Path,
    patch_path: Path,
    expected_patch_hash: str,
    operator_approved: bool = False,
    timeout_seconds: float = 120.0,
) -> dict[str, object]:
    if not operator_approved:
        return _blocked("operator_approval_required")
    worktree = worktree_path.resolve()
    patch = patch_path.resolve()
    if not (worktree / ".git").exists():
        return _blocked("worktree_not_git")
    if not patch.is_file():
        return _blocked("patch_file_missing")
    observed_hash = _file_hash(patch)
    if observed_hash != expected_patch_hash:
        return _blocked("patch_hash_mismatch")
    check = _run(
        ["git", "apply", "--check", str(patch)],
        cwd=worktree,
        timeout_seconds=timeout_seconds,
    )
    if check["returncode"] != 0:
        return {
            **_blocked("patch_check_failed"),
            "patch_hash": observed_hash,
            "check_stderr_hash": check["stderr_hash"],
        }
    applied = _run(
        ["git", "apply", str(patch)],
        cwd=worktree,
        timeout_seconds=timeout_seconds,
    )
    success = applied["returncode"] == 0
    receipt = {
        "receipt_type": "reviewable_patch_apply_v1",
        "status": "applied" if success else "failed",
        "patch_hash": observed_hash,
        "worktree_path": str(worktree),
        "returncode": applied["returncode"],
        "stdout_hash": applied["stdout_hash"],
        "stderr_hash": applied["stderr_hash"],
        "raw_patch_persisted": False,
        "raw_output_persisted": False,
        "execution_performed": True,
        "merge_performed": False,
        "blockers": [] if success else ["patch_apply_failed"],
        "next_action": "run_allowlisted_checks" if success else "repair_patch",
    }
    receipt["receipt_hash"] = _stable_hash(receipt)
    return receipt


def run_allowlisted_checks(
    *,
    worktree_path: Path,
    check_ids: list[str],
    operator_approved: bool = False,
    timeout_seconds: float = 1800.0,
) -> dict[str, object]:
    if not operator_approved:
        return _blocked("operator_approval_required")
    worktree = worktree_path.resolve()
    if not (worktree / ".git").exists():
        return _blocked("worktree_not_git")
    if not check_ids or any(check_id not in _CHECKS for check_id in check_ids):
        return _blocked("check_not_allowlisted")
    rows = []
    for check_id in check_ids:
        result = _run(_CHECKS[check_id], cwd=worktree, timeout_seconds=timeout_seconds)
        rows.append(
            {
                "check_id": check_id,
                "returncode": result["returncode"],
                "passed": result["returncode"] == 0,
                "stdout_hash": result["stdout_hash"],
                "stderr_hash": result["stderr_hash"],
            }
        )
        if result["returncode"] != 0:
            break
    passed = len(rows) == len(check_ids) and all(row["passed"] for row in rows)
    receipt = {
        "receipt_type": "allowlisted_check_run_v1",
        "status": "passed" if passed else "failed",
        "worktree_path": str(worktree),
        "checks": rows,
        "raw_output_persisted": False,
        "arbitrary_command_executed": False,
        "execution_performed": True,
        "merge_allowed": False,
        "merge_performed": False,
        "blockers": [] if passed else ["allowlisted_checks_failed"],
        "next_action": "evaluate_repair_candidate" if passed else "repair_candidate_within_budget",
    }
    receipt["receipt_hash"] = _stable_hash(receipt)
    return receipt


def _run(command: list[str], *, cwd: Path, timeout_seconds: float) -> dict[str, object]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=False,
            shell=False,
            timeout=timeout_seconds,
        )
        stdout = completed.stdout or b""
        stderr = completed.stderr or b""
        return {
            "returncode": completed.returncode,
            "stdout_hash": hashlib.sha256(stdout).hexdigest(),
            "stderr_hash": hashlib.sha256(stderr).hexdigest(),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "returncode": 124 if isinstance(exc, subprocess.TimeoutExpired) else 127,
            "stdout_hash": hashlib.sha256(b"").hexdigest(),
            "stderr_hash": hashlib.sha256(type(exc).__name__.encode("utf-8")).hexdigest(),
        }


def _blocked(blocker: str) -> dict[str, object]:
    payload = {
        "status": "blocked",
        "execution_performed": False,
        "merge_performed": False,
        "blockers": [blocker],
        "next_action": "repair_worktree_executor_inputs",
    }
    payload["receipt_hash"] = _stable_hash(payload)
    return payload


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
