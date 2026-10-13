"""Tests of V25 evidence sidecar and manual revocation, never model execution."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_local_harness_v2 import Task
from hex_cortex.memory.cortex_procedural_skill_evidence_cli_v25 import main
from hex_cortex.memory.cortex_procedural_skill_evidence_v25 import (
    EVIDENCE_FILENAME,
    assess_skill_evidence,
    record_skill_trial,
    revoke_skill,
)
from hex_cortex.memory.cortex_procedural_transfer_v25 import evaluate_procedural_transfer


def _report(tmp_path: Path, *, regress: bool = False) -> dict[str, object]:
    def fake_brain(_model: str, task: Task) -> str:
        if regress:
            return "53213" if "127*419" in task.instruction and (
                "Verified mathematical METHOD" not in task.instruction
            ) else "0"
        return "53213" if "127*419" in task.instruction and (
            "Verified mathematical METHOD" in task.instruction
        ) else "0"

    return evaluate_procedural_transfer(
        skill_id="multiply_decomposition",
        training_expressions=("127*413", "23*51"),
        evaluation_expressions=("127*419",),
        model_id="stub",
        brain=fake_brain,
        project_root=tmp_path,
        approve_model_calls=True,
        approve_procedure=True,
    )


def test_no_write_without_separate_operator_approval(tmp_path: Path) -> None:
    report = _report(tmp_path)
    with pytest.raises(PermissionError, match="requires_explicit_approval"):
        record_skill_trial(project_root=tmp_path, report=report)
    assert not (tmp_path / EVIDENCE_FILENAME).exists()


def test_record_is_deduplicated_and_inactive(tmp_path: Path) -> None:
    report = _report(tmp_path)
    first = record_skill_trial(project_root=tmp_path, report=report, approved=True)
    assert first["status"] == "collect_more_evidence"
    assert first["automatically_active"] is False
    assert first["files_written"] is True
    again = record_skill_trial(project_root=tmp_path, report=report, approved=True)
    assert again["status"] == "duplicate"
    assert again["files_written"] is False
    loaded = (tmp_path / EVIDENCE_FILENAME).read_text(encoding="utf-8")
    assert "127*419" not in loaded
    assert "53213" not in loaded
    assert len(loaded.splitlines()) == 1
    state = assess_skill_evidence(
        project_root=tmp_path, skill_id="multiply_decomposition"
    )
    assert state["status"] == "collect_more_evidence"
    assert state["may_activate"] is False


def test_any_regression_causes_quarantine(tmp_path: Path) -> None:
    negative = _report(tmp_path, regress=True)
    assert negative["skill_only_regressions"] == 1
    receipt = record_skill_trial(
        project_root=tmp_path, report=negative, approved=True
    )
    assert receipt["status"] == "quarantined"
    state = assess_skill_evidence(
        project_root=tmp_path, skill_id="multiply_decomposition"
    )
    assert state["status"] == "quarantined"
    assert state["may_activate"] is False


def test_explicit_revocation_dominates_later_trial(tmp_path: Path) -> None:
    positive = _report(tmp_path)
    record_skill_trial(project_root=tmp_path, report=positive, approved=True)
    with pytest.raises(PermissionError):
        revoke_skill(
            project_root=tmp_path, skill_id="multiply_decomposition",
            reason="observed negative transfer",
        )
    revoked = revoke_skill(
        project_root=tmp_path, skill_id="multiply_decomposition",
        reason="observed negative transfer", approved=True,
    )
    assert revoked["status"] == "revoked"
    state = assess_skill_evidence(
        project_root=tmp_path, skill_id="multiply_decomposition"
    )
    assert state["status"] == "revoked"
    assert state["may_activate"] is False
    with pytest.raises(PermissionError, match="skill_revoked_manual_review_required"):
        record_skill_trial(
            project_root=tmp_path, report=positive, approved=True,
        )
    assert revoke_skill(
        project_root=tmp_path, skill_id="multiply_decomposition",
        reason="already revoked", approved=True,
    )["files_written"] is False


def test_revoked_skill_blocks_before_any_future_model_call(
    tmp_path: Path,
) -> None:
    revoke_skill(
        project_root=tmp_path, skill_id="multiply_decomposition",
        reason="known unsafe skill version", approved=True,
    )
    calls: list[bool] = []

    def brain(_model: str, _task: Task) -> str:
        calls.append(True)
        return "0"

    result = evaluate_procedural_transfer(
        skill_id="multiply_decomposition",
        training_expressions=("127*413", "23*51"),
        evaluation_expressions=("127*419",),
        model_id="test",
        brain=brain,
        project_root=tmp_path,
        approve_model_calls=True,
        approve_procedure=True,
    )
    assert result["status"] == "blocked"
    assert result["reason"] == "skill_revoked_or_quarantined"
    assert result["model_calls"] == 0
    assert not calls


def test_quarantined_skill_blocks_future_model_call(
    tmp_path: Path,
) -> None:
    report = _report(tmp_path, regress=True)
    record_skill_trial(project_root=tmp_path, report=report, approved=True)
    calls: list[bool] = []

    def brain(_model: str, _task: Task) -> str:
        calls.append(True)
        return "0"

    result = evaluate_procedural_transfer(
        skill_id="multiply_decomposition",
        training_expressions=("127*413", "23*51"),
        evaluation_expressions=("127*419",),
        model_id="test",
        brain=brain,
        project_root=tmp_path,
        approve_model_calls=True, approve_procedure=True,
    )
    assert result["status"] == "blocked"
    assert result["evidence_status"] == "quarantined"
    assert result["model_calls"] == 0
    assert not calls


def test_does_not_trust_tampered_report_scores(tmp_path: Path) -> None:
    report = _report(tmp_path)
    report["scores"] = {"baseline": 1234, "skill": 9999}
    with pytest.raises(ValueError, match="skill_evidence_inconsistent_scores"):
        record_skill_trial(project_root=tmp_path, report=report, approved=True)
    assert not (tmp_path / EVIDENCE_FILENAME).exists()


def test_inspection_and_revoke_cli_requires_explicit_approval(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    args = [
        "--project-root", str(tmp_path), "--skill", "multiply_decomposition",
    ]
    assert main([*args, "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["files_read"] is False
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "collect_more_evidence"
    with pytest.raises(SystemExit):
        main([*args, "--revoke", "--reason", "failed"])
    assert main([*args, "--revoke", "--reason", "failed", "--approve-revoke"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "revoked"
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["may_activate"] is False
