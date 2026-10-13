"""Tests: procedural skills teach methods, never supply cached test answers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory import cortex_procedural_transfer_cli_v25 as cli
from hex_cortex.memory.cortex_local_harness_v2 import Task
from hex_cortex.memory.cortex_procedural_transfer_v25 import (
    evaluate_procedural_transfer,
    verify_procedural_skill,
)


@pytest.mark.parametrize(("skill", "expression", "answer"), [
    ("multiply_decomposition", "127*419", "53213"),
    ("multiply_decomposition", "-37*84", "-3108"),
    ("fraction_reduction", "-77/44", "-7/4"),
    ("fraction_reduction", "49/14", "7/2"),
    ("addition_compensation", "-517+728", "211"),
    ("addition_compensation", "1379+2843", "4222"),
])
def test_method_checked_against_independent_exact_math_cell(
    skill: str, expression: str, answer: str,
) -> None:
    record = verify_procedural_skill(skill_id=skill, expression=expression)
    assert record["method_verified_against_exact_cell"] is True
    assert record["verified_expected"] == answer
    assert record["verified_cell_ref"].startswith("math:exact:")
    assert "53213" not in record["method"]


@pytest.mark.parametrize(("skill", "expression"), [
    ("multiply_decomposition", "127+419"),
    ("fraction_reduction", "127*419"),
    ("addition_compensation", "127/419"),
    ("multiply_decomposition", "unknown*3"),
    ("multiply_decomposition", "1**2"),
    ("multiply_decomposition", "__import__('os')"),
    ("fraction_reduction", "7/0"),
    ("multiply_decomposition", "99999999999999*2"),
])
def test_non_applicable_skills_are_blocked(skill: str, expression: str) -> None:
    with pytest.raises(ValueError, match="procedural_skill_"):
        verify_procedural_skill(skill_id=skill, expression=expression)


def _args(tmp_path: Path) -> dict:
    return {
        "project_root": tmp_path,
        "skill_id": "multiply_decomposition",
        "training_expressions": ("127*413", "23*51", "-37*84"),
        "evaluation_expressions": ("127*419", "1379*2843", "6173*7919", "-429*317"),
        "model_id": "fake-qwen",
    }


def test_unseen_procedural_trial_uses_true_harness_and_no_test_answer(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def brain(_model: str, task: Task) -> str:
        calls.append(task.instruction)
        if "Verified mathematical METHOD" in task.instruction:
            return "53213" if "127*419" in task.instruction else "0"
        return "0"

    report = evaluate_procedural_transfer(
        **_args(tmp_path), brain=brain,
        approve_model_calls=True, approve_procedure=True,
        show_answers=True,
    )
    assert report["status"] == "procedural_transfer_observations_recorded"
    assert report["evaluated_unseen_expressions"] == 4
    assert report["model_calls"] == 8
    assert report["oracle_answer_given_to_brain"] is False
    assert report["scores"]["baseline"] == 0
    assert report["scores"]["skill"] == 1
    assert report["skill_only_improvements"] == 1
    assert report["skill_only_regressions"] == 0
    assert report["candidate_for_manual_review"] is False
    assert report["legacy_skill_activation_performed"] is False
    assert report["skill_persisted"] is False
    assert all(row["arms"]["skill"]["receipt_sha256"] for row in report["cases"])
    assert all(row["arms"]["skill"]["evaluation_answer_disclosed"] is False
               for row in report["cases"])
    assert "verified_rational" not in " ".join(calls)
    assert "53213" not in calls[1]


def test_proposal_only_after_positive_multi_task_outcomes(tmp_path: Path) -> None:
    results = {
        "127*419": "53213",
        "1379*2843": "3920797",
        "6173*7919": "48880387",
        "-429*317": "-135993",
    }

    def brain(_model: str, task: Task) -> str:
        for expr, expected in results.items():
            if expr in task.instruction:
                return expected if "Verified mathematical METHOD" in task.instruction else "0"
        return "0"

    report = evaluate_procedural_transfer(
        **_args(tmp_path), brain=brain,
        approve_model_calls=True, approve_procedure=True,
    )
    assert report["status"] == "procedural_transfer_observations_recorded"
    assert report["candidate_for_manual_review"] is True
    assert report["scores"] == {"baseline": 0, "skill": 4}
    assert report["legacy_skill_activation_performed"] is False


def test_regression_prevents_promotion_to_review(tmp_path: Path) -> None:
    def brain(_model: str, task: Task) -> str:
        return "53213" if "127*419" in task.instruction and (
            "Verified mathematical METHOD" not in task.instruction
        ) else "0"

    report = evaluate_procedural_transfer(
        **_args(tmp_path), brain=brain,
        approve_model_calls=True, approve_procedure=True,
    )
    assert report["skill_only_regressions"] == 1
    assert report["candidate_for_manual_review"] is False


def test_approvals_and_seen_examples_fail_closed(tmp_path: Path) -> None:
    called: list[str] = []

    def brain(_model: str, _task: Task) -> str:
        called.append("called")
        return "0"

    denied = evaluate_procedural_transfer(**_args(tmp_path), brain=brain)
    assert denied["status"] == "blocked"
    assert denied["model_calls"] == 0
    assert not called
    duplicated = {**_args(tmp_path), "evaluation_expressions": ("127*413",)}
    with pytest.raises(ValueError, match="seen_in_training"):
        evaluate_procedural_transfer(
            **duplicated, brain=brain,
            approve_model_calls=True, approve_procedure=True,
        )
    assert not called


def test_cli_dry_run_uses_no_gpu_or_model(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main([
        "--skill", "fraction_reduction", "--model", "qwen2.5:3b",
        "--cases", "4", "--dry-run",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["num_gpu"] == 0
    assert payload["max_model_calls"] == 8
    assert payload["model_calls_performed"] == 0


def test_cli_approved_with_fake_ollama(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen_options: list[dict] = []

    class StubBrain:
        def __init__(self, **options: object) -> None:
            seen_options.append(options)

        def __call__(self, _model: str, _task: Task) -> str:
            return "53213"

    monkeypatch.setattr(cli, "LocalOllamaBrain", StubBrain)
    assert cli.main([
        "--project-root", str(tmp_path), "--skill", "multiply_decomposition",
        "--model", "test", "--cases", "1",
        "--approve-model-calls", "--approve-procedure",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["model_calls"] == 2
    assert payload["scores"] == {"baseline": 1, "skill": 1}
    assert seen_options[0]["num_gpu"] == 0
