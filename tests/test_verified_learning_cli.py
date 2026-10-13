"""CLI smoke and explicit-approval tests: offline, no model, no network."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.verified_learning_cli import main
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


def _fixture_spine(root: Path) -> None:
    spine = CanonicalSpine()
    spine.append(
        event_type="task.received", task_id="math_task", source="test",
        payload={"goal": "Calculate Fibonacci numbers"}, confidence=0.9,
    )
    spine.append(
        event_type="clock.completed", task_id="math_task", source="test",
        payload={"completed": True}, confidence=0.9,
    )
    CanonicalSpineJsonlStore(root / "events.jsonl").save(spine)


def test_cli_default_read_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _fixture_spine(tmp_path)
    assert main([
        "--project-root", str(tmp_path), "--spine-file", "events.jsonl",
        "--task-id", "math_task", "--query", "Fibonacci",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["promotion_status"] is None
    assert payload["retrieval_count"] == 0
    assert payload["checkpoint_records"] == 0
    assert payload["real_model_amplification_measured"] is False


def test_cli_promote_save_restore(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _fixture_spine(tmp_path)
    assert main([
        "--project-root", str(tmp_path), "--spine-file", "events.jsonl",
        "--task-id", "math_task", "--query", "Fibonacci",
        "--approve-promotion", "--approve-persist",
        "--save-checkpoint", "learning.jsonl",
    ]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["promotion_status"] == "promoted"
    assert first["retrieval_count"] == 1
    assert (tmp_path / "learning.jsonl").is_file()
    assert main([
        "--project-root", str(tmp_path), "--spine-file", "events.jsonl",
        "--restore-checkpoint", "learning.jsonl", "--query", "Fibonacci",
    ]) == 0
    restored = json.loads(capsys.readouterr().out)
    assert restored["promotion_status"] is None
    assert restored["retrieval_count"] == 1
    assert restored["checkpoint_records"] == 1


def test_cli_cannot_save_without_approval(tmp_path: Path) -> None:
    _fixture_spine(tmp_path)
    with pytest.raises(SystemExit):
        main([
            "--project-root", str(tmp_path), "--spine-file", "events.jsonl",
            "--task-id", "math_task", "--query", "Fibonacci",
            "--save-checkpoint", "learning.jsonl",
        ])
    assert not (tmp_path / "learning.jsonl").exists()


def test_cli_requires_real_spine(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="spine_must_be_existing_file_inside_project"):
        main([
            "--project-root", str(tmp_path), "--spine-file", "missing.jsonl",
            "--task-id", "math_task", "--query", "Fibonacci",
        ])


def test_cli_rejects_unsafe_combination(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main([
            "--project-root", str(tmp_path), "--spine-file", "events.jsonl",
            "--restore-checkpoint", "learning.jsonl",
            "--task-id", "math_task", "--query", "Fibonacci",
        ])
