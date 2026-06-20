from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_self_correction import RepairBudget
from hex_cortex.memory.cortex_self_correction import build_self_correction_plan
from hex_cortex.memory.cortex_self_correction import evaluate_repair_candidate
from hex_cortex.memory.cortex_worktree_executor import apply_reviewable_patch
from hex_cortex.memory.cortex_worktree_executor import build_worktree_plan
from hex_cortex.memory.cortex_worktree_executor import create_isolated_worktree
from hex_cortex.memory.cortex_worktree_executor import run_allowlisted_checks

_SOURCE_PATH = Path("src/hex_cortex/memory/cortex_operational_audit.py")
_RUFF_PATH = Path("ruff.toml")
_EXPECTED_CHANGED_PATHS = {_SOURCE_PATH.as_posix(), _RUFF_PATH.as_posix()}
_TYPING_IMPORT = "from pathlib import Path\nfrom typing import Iterable"
_COLLECTIONS_IMPORT = "from collections.abc import Iterable\nfrom pathlib import Path"
_UNUSED_IMPORT = (
    "from hex_cortex.memory.cortex_research_social_credentials import "
    "build_citation_pack\n"
)
_RUFF_IGNORE = (
    '"src/hex_cortex/memory/cortex_operational_audit.py" = ["F401", "UP035"]\n'
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-self-correction-field")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--worktree-root", default=".hex-cortex/worktrees")
    parser.add_argument("--candidate-id", default="operational-audit-lint-cleanup-v1")
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument(
        "--receipt-dir",
        default=".hex-cortex/receipts/self-correction-operational-audit-lint-cleanup-v1",
    )
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_operational_audit_lint_cleanup_cycle(
        repository_root=Path(args.repository_root),
        worktree_root=Path(args.worktree_root),
        candidate_id=args.candidate_id,
        base_ref=args.base_ref,
        receipt_dir=Path(args.receipt_dir),
        operator_approved=args.operator_approved,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0 if payload.get("status") == "field_certified" else 2


def run_operational_audit_lint_cleanup_cycle(
    *,
    repository_root: Path,
    worktree_root: Path,
    candidate_id: str,
    base_ref: str,
    receipt_dir: Path,
    operator_approved: bool = False,
    timeout_seconds: float = 1800.0,
) -> dict[str, object]:
    repo = repository_root.resolve()
    receipts = receipt_dir.resolve()
    receipts.mkdir(parents=True, exist_ok=True)
    if not operator_approved:
        return _write_summary(
            receipts,
            _blocked_summary("operator_approval_required"),
        )
    if timeout_seconds < 30 or timeout_seconds > 7200:
        return _write_summary(
            receipts,
            _blocked_summary("timeout_seconds_out_of_range"),
        )

    budget = RepairBudget(max_attempts=1, max_files_changed=2, max_runtime_seconds=int(timeout_seconds))
    correction_plan = build_self_correction_plan(
        failure_class="lint_suppression_debt",
        hypothesis=(
            "Removing the obsolete operational-audit Ruff suppression and fixing its two "
            "underlying diagnostics reduces lint debt from three facts to zero while the "
            "full deterministic checks remain green."
        ),
        baseline_ref=base_ref,
        evaluator_ref="ruff_plus_full_pytest_v1",
        budget=budget,
    )
    _write_json(receipts / "00-correction-plan.json", correction_plan)
    if correction_plan.get("status") != "ready":
        return _write_summary(receipts, _blocked_summary("correction_plan_not_ready"))

    baseline_debt = count_operational_audit_lint_debt(repo)
    if baseline_debt != 3:
        return _write_summary(
            receipts,
            {
                **_blocked_summary("baseline_lint_debt_not_expected"),
                "baseline_lint_debt": baseline_debt,
            },
        )

    worktree_plan = build_worktree_plan(
        repository_root=repo,
        worktree_root=worktree_root,
        candidate_id=candidate_id,
        base_ref=base_ref,
        check_ids=["ruff", "pytest"],
    )
    _write_json(receipts / "01-worktree-plan.json", worktree_plan)
    if worktree_plan.get("status") != "ready":
        return _write_summary(receipts, _blocked_summary("worktree_plan_not_ready"))

    create_receipt = create_isolated_worktree(
        worktree_plan,
        operator_approved=True,
        timeout_seconds=min(timeout_seconds, 120.0),
    )
    _write_json(receipts / "02-worktree-create.json", create_receipt)
    if create_receipt.get("status") != "created":
        return _write_summary(receipts, _blocked_summary("worktree_create_failed"))

    worktree = Path(str(worktree_plan["worktree_path"])).resolve()
    patch_build = build_reviewable_lint_cleanup_patch(
        worktree_path=worktree,
        output_path=receipts / "operational-audit-lint-cleanup.patch",
    )
    _write_json(receipts / "03-patch-build.json", patch_build)
    if patch_build.get("status") != "built":
        return _write_summary(receipts, _blocked_summary("reviewable_patch_build_failed"))

    patch_receipt = apply_reviewable_patch(
        worktree_path=worktree,
        patch_path=Path(str(patch_build["patch_path"])),
        expected_patch_hash=str(patch_build["patch_hash"]),
        operator_approved=True,
        timeout_seconds=min(timeout_seconds, 120.0),
    )
    _write_json(receipts / "04-patch-apply.json", patch_receipt)
    if patch_receipt.get("status") != "applied":
        return _write_summary(receipts, _blocked_summary("reviewable_patch_apply_failed"))

    post_patch_debt = count_operational_audit_lint_debt(worktree)
    checks_receipt = run_allowlisted_checks(
        worktree_path=worktree,
        check_ids=["ruff", "pytest"],
        operator_approved=True,
        timeout_seconds=timeout_seconds,
    )
    _write_json(receipts / "05-allowlisted-checks.json", checks_receipt)

    checks_passed = checks_receipt.get("status") == "passed"
    metric_improved = baseline_debt == 3 and post_patch_debt == 0
    evaluation = evaluate_repair_candidate(
        plan_hash=str(correction_plan["plan_hash"]),
        candidate_ref=str(worktree),
        deterministic_checks_passed=checks_passed,
        task_metric_improved=metric_improved,
        heldout_gate_passed=checks_passed,
        evaluator_changed=False,
        threshold_lowered=False,
        files_changed=2,
        attempt_index=1,
        budget=budget,
    )
    _write_json(receipts / "06-candidate-evaluation.json", evaluation)

    certified = (
        checks_passed
        and metric_improved
        and evaluation.get("status") == "promotable"
        and evaluation.get("candidate_promotable") is True
    )
    summary = {
        "receipt_type": "self_correction_field_cycle_v1",
        "status": "field_certified" if certified else "blocked",
        "candidate_id": candidate_id,
        "candidate_ref": str(worktree),
        "baseline_lint_debt": baseline_debt,
        "post_patch_lint_debt": post_patch_debt,
        "task_metric_improved": metric_improved,
        "allowlisted_checks_passed": checks_passed,
        "candidate_evaluation_status": evaluation.get("status"),
        "candidate_promotable": evaluation.get("candidate_promotable"),
        "merge_allowed": evaluation.get("merge_allowed"),
        "merge_performed": False,
        "operator_merge_approval_required": True,
        "patch_hash": patch_build.get("patch_hash"),
        "changed_paths": sorted(_EXPECTED_CHANGED_PATHS),
        "raw_patch_persisted": True,
        "raw_output_persisted": False,
        "raw_secret_persisted": False,
        "blockers": [] if certified else ["candidate_evaluation_incomplete"],
        "next_action": "review_candidate_before_merge" if certified else "repair_field_cycle",
    }
    summary["receipt_hash"] = _stable_hash(summary)
    return _write_summary(receipts, summary)


def count_operational_audit_lint_debt(root: Path) -> int:
    source = (root.resolve() / _SOURCE_PATH).read_text(encoding="utf-8")
    ruff = (root.resolve() / _RUFF_PATH).read_text(encoding="utf-8")
    return sum(
        (
            _TYPING_IMPORT in source,
            _UNUSED_IMPORT in source,
            _RUFF_IGNORE in ruff,
        )
    )


def build_reviewable_lint_cleanup_patch(
    *,
    worktree_path: Path,
    output_path: Path,
) -> dict[str, object]:
    worktree = worktree_path.resolve()
    source_path = worktree / _SOURCE_PATH
    ruff_path = worktree / _RUFF_PATH
    try:
        source = source_path.read_text(encoding="utf-8")
        ruff = ruff_path.read_text(encoding="utf-8")
    except OSError:
        return _patch_blocked("candidate_files_missing")
    if _TYPING_IMPORT not in source or _UNUSED_IMPORT not in source or _RUFF_IGNORE not in ruff:
        return _patch_blocked("candidate_baseline_mismatch")

    source_path.write_text(
        source.replace(_TYPING_IMPORT, _COLLECTIONS_IMPORT, 1).replace(_UNUSED_IMPORT, "", 1),
        encoding="utf-8",
    )
    ruff_path.write_text(ruff.replace(_RUFF_IGNORE, "", 1), encoding="utf-8")

    name_result = _run_git(
        ["diff", "--name-only", "--", _SOURCE_PATH.as_posix(), _RUFF_PATH.as_posix()],
        cwd=worktree,
    )
    diff_result = _run_git(
        ["diff", "--binary", "--", _SOURCE_PATH.as_posix(), _RUFF_PATH.as_posix()],
        cwd=worktree,
    )
    restore_result = _run_git(
        ["restore", "--worktree", "--", _SOURCE_PATH.as_posix(), _RUFF_PATH.as_posix()],
        cwd=worktree,
    )
    if name_result["returncode"] != 0 or diff_result["returncode"] != 0:
        return _patch_blocked("git_diff_failed")
    if restore_result["returncode"] != 0:
        return _patch_blocked("candidate_restore_failed")

    changed_paths = {
        line.strip()
        for line in name_result["stdout"].decode("utf-8", errors="replace").splitlines()
        if line.strip()
    }
    patch_bytes = diff_result["stdout"]
    if changed_paths != _EXPECTED_CHANGED_PATHS or not patch_bytes:
        return _patch_blocked("patch_scope_invalid")
    clean_result = _run_git(
        ["diff", "--quiet", "--", _SOURCE_PATH.as_posix(), _RUFF_PATH.as_posix()],
        cwd=worktree,
    )
    if clean_result["returncode"] != 0:
        return _patch_blocked("candidate_not_restored_clean")

    target = output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(patch_bytes)
    patch_hash = hashlib.sha256(patch_bytes).hexdigest()
    payload = {
        "receipt_type": "reviewable_patch_build_v1",
        "status": "built",
        "patch_path": str(target),
        "patch_hash": patch_hash,
        "changed_paths": sorted(changed_paths),
        "files_changed": len(changed_paths),
        "raw_patch_persisted": True,
        "raw_output_persisted": False,
        "blockers": [],
        "next_action": "apply_reviewable_patch",
    }
    payload["receipt_hash"] = _stable_hash(payload)
    return payload


def _run_git(arguments: list[str], *, cwd: Path) -> dict[str, object]:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            check=False,
            capture_output=True,
            shell=False,
            timeout=120.0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "returncode": 124 if isinstance(exc, subprocess.TimeoutExpired) else 127,
            "stdout": b"",
            "stderr_hash": hashlib.sha256(type(exc).__name__.encode("utf-8")).hexdigest(),
        }
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout or b"",
        "stderr_hash": hashlib.sha256(completed.stderr or b"").hexdigest(),
    }


def _patch_blocked(blocker: str) -> dict[str, object]:
    payload = {
        "receipt_type": "reviewable_patch_build_v1",
        "status": "blocked",
        "raw_patch_persisted": False,
        "raw_output_persisted": False,
        "blockers": [blocker],
        "next_action": "repair_reviewable_patch_build",
    }
    payload["receipt_hash"] = _stable_hash(payload)
    return payload


def _blocked_summary(blocker: str) -> dict[str, object]:
    payload = {
        "receipt_type": "self_correction_field_cycle_v1",
        "status": "blocked",
        "merge_performed": False,
        "raw_secret_persisted": False,
        "blockers": [blocker],
        "next_action": "repair_field_cycle",
    }
    payload["receipt_hash"] = _stable_hash(payload)
    return payload


def _write_summary(receipt_dir: Path, payload: dict[str, object]) -> dict[str, object]:
    _write_json(receipt_dir / "07-field-cycle-summary.json", payload)
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
