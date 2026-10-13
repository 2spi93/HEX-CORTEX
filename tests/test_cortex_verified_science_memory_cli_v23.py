"""No-network CLI smoke tests for science-fact memory and checkpoint gates."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_verified_science_memory_cli_v23 import main
from hex_cortex.memory.cortex_verified_science_memory_v23 import verify_science_fact_task
from hex_cortex.memory.verified_learning_loop import VerifiedLearningLoop
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


@pytest.mark.parametrize("domain", ["physics", "chemistry"])
def test_source_fact_cli_persist_and_restore(
    tmp_path: Path, domain: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = [
        "--project-root", str(tmp_path), "--domain", domain, "--example",
        "--task-id", "science-proof", "--approve-record",
        "--approve-promote", "--approve-persist",
        "--spine-output", "proof.jsonl",
        "--checkpoint-output", "memory.jsonl",
    ]
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["model_called"] is False
    assert report["spine_verified"] is True
    assert report["promotion_status"] == "promoted"
    assert report["retrieval_count"] == 1
    assert report["files_saved"] is True
    spine = CanonicalSpineJsonlStore(tmp_path / "proof.jsonl").load()
    assert verify_science_fact_task(spine, "science-proof")
    restored = VerifiedLearningLoop.restore_checkpoint(
        project_root=tmp_path,
        relative_path=Path("memory.jsonl"),
        spine=spine,
    )
    assert len(restored.checkpoint_records) == 1


def test_cli_dry_run_is_fully_read_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([
        "--project-root", str(tmp_path), "--domain", "physics", "--example",
        "--task-id", "science-proof", "--dry-run",
    ]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["status"] == "configuration_only"
    assert info["files_read"] is False
    assert info["files_written"] is False


def test_cli_persistence_requires_separate_approvals(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main([
            "--project-root", str(tmp_path), "--domain", "physics", "--example",
            "--task-id", "science-proof",
            "--approve-record", "--spine-output", "proof.jsonl",
        ])
    assert not (tmp_path / "proof.jsonl").exists()
