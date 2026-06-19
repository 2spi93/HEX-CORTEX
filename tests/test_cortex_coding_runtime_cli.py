import json
from pathlib import Path

from hex_cortex.memory.cortex_coding_runtime_cli import build_parser
from hex_cortex.memory.cortex_coding_runtime_cli import main


def test_coding_runtime_cli_parses_local_execution() -> None:
    args = build_parser().parse_args(
        [
            "execute",
            "local_open_weight",
            "prompt.txt",
            "--instruction-file",
            "instruction.txt",
            "--model",
            "local-coder",
            "--operator-approved",
        ]
    )

    assert args.command == "execute"
    assert args.provider_id == "local_open_weight"
    assert args.operator_approved is True


def test_worktree_plan_command_writes_reviewable_plan(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    output = tmp_path / "plan.json"

    code = main(
        [
            "worktree-plan",
            str(repo),
            str(tmp_path / "worktrees"),
            "candidate-001",
            "main",
            "--check",
            "pytest",
            "--check",
            "ruff",
            "--output",
            str(output),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "ready"
    assert output.exists()
    assert payload["automatic_merge_allowed"] is False


def test_hypothesis_frontier_command_handles_empty_ledger(tmp_path: Path, capsys) -> None:
    ledger = tmp_path / "hypotheses.jsonl"

    code = main(["hypothesis-frontier", str(ledger)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["projection_type"] == "research_hypothesis_frontier_v1"
    assert payload["frontier_count"] == 0


def test_execute_rejects_missing_prompt_file(tmp_path: Path, capsys) -> None:
    instruction = tmp_path / "instruction.txt"
    instruction.write_text("Plan safely.", encoding="utf-8")

    code = main(
        [
            "execute",
            "local_open_weight",
            str(tmp_path / "missing-prompt.txt"),
            "--instruction-file",
            str(instruction),
            "--model",
            "local-coder",
            "--operator-approved",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["blockers"] == ["prompt_file_invalid"]
