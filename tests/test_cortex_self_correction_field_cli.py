import subprocess
from pathlib import Path

from hex_cortex.memory.cortex_self_correction_field_cli import (
    build_parser,
    build_reviewable_lint_cleanup_patch,
    count_operational_audit_lint_debt,
    run_operational_audit_lint_cleanup_cycle,
)


def test_field_cli_requires_operator_approval(tmp_path: Path) -> None:
    payload = run_operational_audit_lint_cleanup_cycle(
        repository_root=tmp_path / "repo",
        worktree_root=tmp_path / "worktrees",
        candidate_id="candidate-001",
        base_ref="HEAD",
        receipt_dir=tmp_path / "receipts",
        operator_approved=False,
    )

    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["operator_approval_required"]
    assert payload["merge_performed"] is False
    assert (tmp_path / "receipts" / "07-field-cycle-summary.json").is_file()


def test_field_cli_defaults_are_bounded() -> None:
    args = build_parser().parse_args([])

    assert args.candidate_id == "operational-audit-lint-cleanup-v1"
    assert args.base_ref == "HEAD"
    assert args.operator_approved is False
    assert args.timeout_seconds == 1800.0


def test_reviewable_patch_removes_three_lint_debt_facts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source_path = repo / "src/hex_cortex/memory/cortex_operational_audit.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "from pathlib import Path\n"
        "from typing import Iterable\n"
        "\n"
        "from hex_cortex.memory.cortex_research_social_credentials import "
        "build_citation_pack\n"
        "\n"
        "def use(value: Iterable[Path]) -> int:\n"
        "    return len(list(value))\n",
        encoding="utf-8",
    )
    (repo / "ruff.toml").write_text(
        'extend = "pyproject.toml"\n\n'
        "[lint.per-file-ignores]\n"
        '"src/hex_cortex/memory/cortex_operational_audit.py" = ["F401", "UP035"]\n',
        encoding="utf-8",
    )
    _run(["git", "init"], cwd=repo)
    _run(["git", "config", "user.email", "test@example.invalid"], cwd=repo)
    _run(["git", "config", "user.name", "HEX-CORTEX Test"], cwd=repo)
    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", "baseline"], cwd=repo)

    assert count_operational_audit_lint_debt(repo) == 3
    patch_path = tmp_path / "receipts" / "candidate.patch"
    payload = build_reviewable_lint_cleanup_patch(
        worktree_path=repo,
        output_path=patch_path,
    )

    assert payload["status"] == "built"
    assert payload["files_changed"] == 2
    assert payload["changed_paths"] == [
        "ruff.toml",
        "src/hex_cortex/memory/cortex_operational_audit.py",
    ]
    assert patch_path.is_file()
    assert count_operational_audit_lint_debt(repo) == 3

    _run(["git", "apply", str(patch_path)], cwd=repo)
    assert count_operational_audit_lint_debt(repo) == 0


def _run(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )
    assert completed.returncode == 0, completed.stderr
