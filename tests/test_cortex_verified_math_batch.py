"""No-network tests for opt-in paired batch evaluation and evidence limits."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory import cortex_verified_math_batch_cli as cli
from hex_cortex.memory.cortex_local_harness_v2 import Task
from hex_cortex.memory.cortex_verified_math_batch import (
    PUBLIC_MATH_CASES,
    run_verified_math_batch,
)


def test_batch_denied_does_not_run_math_or_model(tmp_path: Path) -> None:
    calls: list[int] = []

    def fake_brain(_model: str, _task: Task) -> str:
        calls.append(1)
        return "123"

    result = run_verified_math_batch(
        project_root=tmp_path, model_id="mock", brain=fake_brain, max_pairs=3,
        approve_math=True,
    )
    assert result["status"] == "blocked"
    assert result["model_calls"] == 0
    assert not calls


def test_three_pairs_alternate_order_and_aggregate(tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_brain(_model: str, task: Task) -> str:
        calls.append(task.instruction)
        # Simulates a weak model that always answers wrong without a calculator.
        if "verified_rational: " in task.instruction:
            return task.instruction.split("verified_rational: ", 1)[1].splitlines()[0]
        return "0"

    result = run_verified_math_batch(
        project_root=tmp_path, model_id="test", brain=fake_brain,
        max_pairs=3, approve_math=True, approve_all_model_calls=True,
    )
    assert result["status"] == "exploratory_pairs_recorded"
    assert result["sample_size"] == 3
    assert result["model_calls_attempted"] == 6
    assert result["correct"] == {"baseline": 0, "cortex": 3}
    assert result["delta_accuracy"] == 1
    assert result["cortex_only_correct"] == 3
    assert result["baseline_only_correct"] == 0
    assert result["arm_orders_balanced"] is False
    assert result["cases"][0]["arm_order"] == ["baseline", "cortex"]
    assert result["cases"][1]["arm_order"] == ["cortex", "baseline"]
    assert result["cases"][2]["arm_order"] == ["baseline", "cortex"]
    assert result["held_out_independently_attested"] is False
    assert result["causal_effect_certified"] is False
    assert all(case["expected_result"] is None for case in result["cases"])
    assert len(calls) == 6


def test_partial_failure_stops_without_claim_of_completed_batch(
    tmp_path: Path,
) -> None:
    calls: list[int] = []

    def fake_brain(_model: str, _task: Task) -> str:
        calls.append(len(calls))
        if len(calls) == 4:
            raise RuntimeError("secret")
        return "1"

    result = run_verified_math_batch(
        project_root=tmp_path, model_id="test", brain=fake_brain,
        max_pairs=3, approve_math=True, approve_all_model_calls=True,
    )
    assert result["status"] == "incomplete"
    assert result["completed_pairs"] == 1
    assert result["model_calls_attempted"] == 4
    assert "secret" not in str(result)
    assert len(calls) == 4


@pytest.mark.parametrize("count", [0, 11, 100, -1])
def test_pair_count_limits(tmp_path: Path, count: int) -> None:
    with pytest.raises(ValueError, match="pair_count_out_of_bounds"):
        run_verified_math_batch(
            project_root=tmp_path, model_id="test",
            brain=lambda _model, _task: "1", max_pairs=count,
        )


def test_public_suite_contains_distinct_expressions() -> None:
    assert len(PUBLIC_MATH_CASES) == 10
    assert len({expression for _domain, expression in PUBLIC_MATH_CASES}) == 10


def test_cli_dry_run_and_no_approval(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["--project-root", str(tmp_path), "--model", "qwen2.5:3b", "--pairs", "3"]
    assert cli.main([*argv, "--dry-run"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["num_gpu"] == 0
    assert output["max_model_calls"] == 6
    assert output["calls_performed"] == 0
    assert cli.main(argv) == 2
    denied = json.loads(capsys.readouterr().out)
    assert denied["status"] == "blocked"
