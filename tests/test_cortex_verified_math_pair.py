"""Network-free smoke, arithmetic proof, gating and paired Harness comparison."""
from __future__ import annotations

from pathlib import Path

import pytest

from hex_cortex.memory.cortex_local_harness_v2 import Task
from hex_cortex.memory.cortex_verified_math_pair import run_verified_math_pair


def test_denial_does_not_call_brain_or_math(tmp_path: Path) -> None:
    calls: list[str] = []

    def brain(_model: str, _task: Task) -> str:
        calls.append("called")
        return "0"

    report = run_verified_math_pair(
        project_root=tmp_path,
        expression="17*23",
        model_id="local-test",
        brain=brain,
        approve_math=True,
    )
    assert report["status"] == "blocked"
    assert report["model_calls"] == 0
    assert report["math_cell_executed"] is False
    assert calls == []


def test_actual_harness_two_arms_and_verified_math(tmp_path: Path) -> None:
    calls: list[str] = []

    def brain(_model: str, task: Task) -> str:
        calls.append(task.instruction)
        return "391" if "verified_rational: 391" in task.instruction else "392"

    report = run_verified_math_pair(
        project_root=tmp_path,
        expression="17 * 23",
        model_id="local-test",
        brain=brain,
        approve_math=True,
        approve_two_model_calls=True,
        reveal_outputs=True,
    )
    assert report["status"] == "paired_observations_recorded"
    assert report["model_calls"] == 2
    assert report["math_cell_verified"] is True
    assert report["verified_result"] == "391"
    assert report["baseline"]["correct"] is False
    assert report["cortex"]["correct"] is True
    assert report["delta_correct"] == 1
    assert "verified_rational" not in calls[0]
    assert "verified_rational: 391" in calls[1]
    assert report["baseline"]["answer"] == "392"
    assert report["cortex"]["answer"] == "391"
    assert report["causal_effect_certified"] is False


def test_order_reversed_but_original_question_same(tmp_path: Path) -> None:
    calls: list[str] = []

    def brain(_model: str, task: Task) -> str:
        calls.append(task.instruction)
        return "7/2"

    report = run_verified_math_pair(
        project_root=tmp_path,
        expression="7 / 2",
        model_id="same-model",
        brain=brain,
        approve_math=True,
        approve_two_model_calls=True,
        order="cortex-first",
    )
    assert report["status"] == "paired_observations_recorded"
    assert report["arm_order"] == ["cortex", "baseline"]
    assert report["baseline"]["correct"] is True
    assert report["cortex"]["correct"] is True
    assert report["delta_correct"] == 0
    assert "7 / 2" in calls[0] and "7 / 2" in calls[1]
    assert "verified_rational" in calls[0]
    assert "verified_rational" not in calls[1]
    assert report["baseline"]["answer"] is None
    assert report["cortex"]["answer"] is None


@pytest.mark.parametrize("expression", [
    "17*0/0",
    "__import__('os')",
    "10 ** 999999",
    "1.5 + 3",
])
def test_invalid_expression_never_calls_brain(tmp_path: Path, expression: str) -> None:
    calls: list[bool] = []

    def brain(_model: str, _task: Task) -> str:
        calls.append(True)
        return "42"

    result = run_verified_math_pair(
        project_root=tmp_path,
        expression=expression,
        model_id="test",
        brain=brain,
        approve_math=True,
        approve_two_model_calls=True,
    )
    assert result["status"] == "blocked"
    assert result["model_calls"] == 0
    assert calls == []


def test_rejects_non_rational_model_answer(tmp_path: Path) -> None:
    report = run_verified_math_pair(
        project_root=tmp_path, expression="17*23", model_id="test",
        brain=lambda _model, _task: "The answer is 391",
        approve_math=True, approve_two_model_calls=True,
    )
    assert report["status"] == "paired_observations_recorded"
    assert report["baseline"]["correct"] is False
    assert report["cortex"]["correct"] is False


def test_partial_failure_not_claimed_as_pair(tmp_path: Path) -> None:
    counter = [0]

    def brain(_model: str, _task: Task) -> str:
        counter[0] += 1
        if counter[0] == 2:
            raise RuntimeError("secret_private_provider_error")
        return "391"

    report = run_verified_math_pair(
        project_root=tmp_path, expression="17*23", model_id="test",
        brain=brain, approve_math=True, approve_two_model_calls=True,
    )
    assert report["status"] == "incomplete"
    assert report["completed_arms"] == 1
    assert report["model_calls"] == 2
    assert "secret_private_provider_error" not in str(report)
