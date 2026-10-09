"""Operator CLI and synthetic local model call integration regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_repo_repair_cli import main, run_local_repair_probe
from hex_cortex.memory.cortex_repo_repair_probe_v3 import CASES


def _initial_responses() -> dict[str, str]:
    return {case.case_id: json.dumps({"files": case.files}) for case in CASES}


def test_local_ollama_calls_require_explicit_operator_grant(
    tmp_path: Path, capsys
) -> None:
    rc = main([
        "--model-id", "local", "--digest", "sha256:abc", "--quantization", "Q4",
        "--project-root", str(tmp_path),
    ])
    assert rc == 2
    assert "approve-model" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_offline_scoring_requires_no_network_or_permission(tmp_path: Path, capsys) -> None:
    path = tmp_path / "responses.json"
    path.write_text(json.dumps(_initial_responses()), encoding="utf-8")
    rc = main([
        "--model-id", "local", "--digest", "sha256:abc", "--quantization", "Q4",
        "--responses", str(path),
    ])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["model_calls_attempted"] == 0
    assert report["localhost_model_requested"] is False
    assert report["overall_score"] == 0.0
    assert report["checkout_modified"] is False
    assert not (tmp_path / "tasks.sqlite").exists()


def test_injected_brain_uses_clock_and_local_budget_without_saving_sources(
    tmp_path: Path,
) -> None:
    observed: list[tuple[str, str]] = []
    originals = _initial_responses()

    def fake_brain(model_id, task) -> str:
        observed.append((model_id, task.task_id))
        return originals[task.task_id]

    report = run_local_repair_probe(
        model_id="local", model_digest="sha256:abc",
        quantization="Q4", hardware_id="test",
        approved=True, project_root=tmp_path, brain=fake_brain,
    )
    assert report["model_calls_attempted"] == 4
    assert report["localhost_model_requested"] is True
    assert report["raw_candidates_persisted"] is False
    assert len(observed) == len(CASES)
    assert {name for _, name in observed} == {row.case_id for row in CASES}
    assert list(tmp_path.iterdir()) == []
    assert "def net_pnl" not in json.dumps(report)


def test_model_exception_blocks_one_task_and_continues(
    tmp_path: Path,
) -> None:
    calls = []

    def broken_brain(model_id, task):
        calls.append(task.task_id)
        raise RuntimeError("mock Ollama unavailable")

    report = run_local_repair_probe(
        model_id="local", model_digest="sha256:abc",
        quantization="Q4", hardware_id="test",
        approved=True, project_root=tmp_path, brain=broken_brain,
    )
    assert report["passed_count"] == 0
    assert report["model_calls_attempted"] == len(CASES)
    assert len(calls) == len(CASES)
    assert "mock Ollama unavailable" not in json.dumps(report)


def test_offline_unknown_case_rejected(tmp_path: Path, capsys) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"unknown":"bad"}', encoding="utf-8")
    rc = main([
        "--model-id", "local", "--digest", "sha256:abc", "--quantization", "Q4",
        "--responses", str(path),
    ])
    assert rc == 2
    assert "unknown benchmark task" in capsys.readouterr().err


def test_show_suite_returns_non_executable_metadata(capsys) -> None:
    rc = main([
        "--model-id", "local", "--digest", "sha256:abc", "--quantization", "Q4",
        "--show-tasks",
    ])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["evaluation_kind"] == "restricted_ast_semantics_no_generated_code_execution"


def test_api_live_unapproved_raises_before_model_call(tmp_path: Path) -> None:
    with pytest.raises(PermissionError):
        run_local_repair_probe(
            model_id="local", model_digest="sha256:abc",
            quantization="Q4", hardware_id="test",
            approved=False, project_root=tmp_path,
        )
