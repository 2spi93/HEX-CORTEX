"""CPU/no-network regression coverage of real four-arm Harness ablation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory import cortex_four_arm_math_eval_cli_v23 as cli
from hex_cortex.memory.cortex_four_arm_math_eval_v23 import run_four_arm_math_eval
from hex_cortex.memory.cortex_local_harness_v2 import Task


def _arguments(tmp_path: Path) -> dict[str, object]:
    return {
        "project_root": tmp_path,
        "training_expression": "127*413",
        "evaluation_expression": "127*419",
        "model_id": "same-stub-model",
    }


def test_four_isolated_harness_arms_are_graded_separately(tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_brain(_model: str, task: Task) -> str:
        calls.append(task.instruction)
        if "verified_rational: 53213" in task.instruction:
            return "53213"
        return "0"

    result = run_four_arm_math_eval(
        **_arguments(tmp_path), brain=fake_brain,
        approve_model_calls=True, approve_memory=True, approve_calculator=True,
        show_answers=True,
    )
    assert result["status"] == "four_arm_observations_recorded"
    assert result["model_calls"] == 4
    assert result["training_fact_independently_verified"] is True
    assert result["memory_source_event_count"] == 2
    assert result["memory_exact_evaluation_answer_detected"] is False
    assert result["arms"]["baseline"]["correct"] is False
    assert result["arms"]["memory"]["correct"] is False
    assert result["arms"]["calculator"]["correct"] is True
    assert result["arms"]["combined"]["correct"] is True
    assert result["arms"]["memory"]["memory_provided"] is True
    assert result["arms"]["calculator"]["calculator_answer_provided"] is True
    assert result["arms"]["baseline"]["answer"] == "0"
    assert result["arms"]["combined"]["answer"] == "53213"
    assert all(result["arms"][arm]["receipt_sha256"] for arm in result["arms"])
    assert all(result["arms"][arm]["latency_ms"] >= 0 for arm in result["arms"])
    assert "127*413" in calls[1]
    assert "verified_rational: 53213" not in calls[1]
    assert "verified_rational: 53213" in calls[2]
    assert result["causal_effect_certified"] is False
    assert result["memory_generalization_certified"] is False
    assert result["files_written"] is False


def test_detects_observed_training_answer_copy_as_negative_transfer(
    tmp_path: Path,
) -> None:
    def brain(_model: str, task: Task) -> str:
        if "verified_rational: 53213" in task.instruction:
            return "53213"
        if "Verified exact arithmetic: 127*413 = 52451" in task.instruction:
            return "52451"
        return "53813"

    report = run_four_arm_math_eval(
        **_arguments(tmp_path), brain=brain,
        approve_model_calls=True, approve_memory=True,
        approve_calculator=True, show_answers=True,
    )
    assert report["status"] == "four_arm_observations_recorded"
    assert report["negative_transfer_training_answer_copy_observed"] is True
    assert report["memory_only_accurate"] is False
    assert report["cross_expression_prior_scalar_diagnostic_mode"] is True
    assert report["arms"]["memory"]["answer_copied_from_training_fact"] is True
    assert report["arms"]["calculator"]["correct"] is True


def test_operator_denial_runs_no_model_or_math(tmp_path: Path) -> None:
    calls: list[str] = []

    def brain(_model: str, _task: Task) -> str:
        calls.append("called")
        return "0"

    report = run_four_arm_math_eval(
        **_arguments(tmp_path), brain=brain,
        approve_model_calls=True, approve_memory=True,
    )
    assert report["status"] == "blocked"
    assert report["model_calls"] == 0
    assert not report["fact_recorded"]
    assert calls == []


@pytest.mark.parametrize(("training", "evaluation"), [
    ("127*413", "127*413"),  # exact task reuse
    ("17*23", "391"),  # same answer, different expression
])
def test_identical_training_task_or_result_refused(
    tmp_path: Path, training: str, evaluation: str,
) -> None:
    with pytest.raises(ValueError, match="evaluation_"):
        run_four_arm_math_eval(
            project_root=tmp_path, model_id="test",
            training_expression=training, evaluation_expression=evaluation,
            brain=lambda _model, _task: "0",
            approve_model_calls=True, approve_memory=True,
            approve_calculator=True,
        )


def test_partial_provider_failure_not_certified(tmp_path: Path) -> None:
    calls: list[int] = []

    def fake_brain(_model: str, _task: Task) -> str:
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("private_provider_detail")
        return "42"

    report = run_four_arm_math_eval(
        **_arguments(tmp_path), brain=fake_brain,
        approve_model_calls=True, approve_memory=True, approve_calculator=True,
    )
    assert report["status"] == "incomplete"
    assert report["completed_arms"] == 1
    assert report["attempted_model_calls"] == 2
    assert len(calls) == 2
    assert "private_provider_detail" not in str(report)


def test_alternate_four_arm_order_preserved(tmp_path: Path) -> None:
    selected = ("combined", "baseline", "memory", "calculator")
    calls: list[str] = []

    def fake_brain(_model: str, task: Task) -> str:
        calls.append(task.instruction)
        return "53213"

    report = run_four_arm_math_eval(
        **_arguments(tmp_path), brain=fake_brain,
        approve_model_calls=True, approve_memory=True, approve_calculator=True,
        arm_order=selected,
    )
    assert report["status"] == "four_arm_observations_recorded"
    assert report["arm_order"] == list(selected)
    assert report["all_four_arms_correct"] is True
    assert report["arms"]["combined"]["answer"] is None
    assert "verified_rational: 53213" in calls[0]
    assert "verified_rational: 53213" not in calls[1]


def test_cli_dry_run_and_gate_without_network(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    args = [
        "--project-root", str(tmp_path), "--model", "qwen2.5:3b",
        "--training-expression", "127*413",
        "--evaluation-expression", "127*419",
        "--order-index", "1",
    ]
    assert cli.main([*args, "--dry-run"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "configuration_only"
    assert output["max_model_calls"] == 4
    assert output["model_calls_performed"] == 0
    assert output["num_gpu"] == 0
    assert output["arms"] == ["combined", "calculator", "memory", "baseline"]
    assert cli.main(args) == 2
    denied = json.loads(capsys.readouterr().out)
    assert denied["model_calls"] == 0


def test_cli_approved_uses_cpu_only_with_stub(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = [
        "--project-root", str(tmp_path), "--model", "test",
        "--training-expression", "127*413",
        "--evaluation-expression", "127*419",
        "--approve-model-calls", "--approve-memory", "--approve-calculator",
    ]
    constructor_options: list[dict[str, object]] = []

    class FakeOllama:
        def __init__(self, **options: object) -> None:
            constructor_options.append(options)

        def __call__(self, _model: str, _task: Task) -> str:
            return "53213"

    monkeypatch.setattr(cli, "LocalOllamaBrain", FakeOllama)
    assert cli.main(args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["model_calls"] == 4
    assert output["arms"]["baseline"]["correct"] is True
    assert output["memory_context_chars"] > 0
    assert output["files_written"] is False
    assert constructor_options[0]["num_gpu"] == 0
