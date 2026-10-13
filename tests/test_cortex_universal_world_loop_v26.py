"""World cycle: trusted simulated dynamics, observed residual, gated brain."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_local_harness_v2 import Task
from hex_cortex.memory.cortex_universal_sensing_v26 import (
    observe_telemetry, observe_transcript,
)
from hex_cortex.memory.cortex_universal_world_cli_v26 import main
from hex_cortex.memory.cortex_universal_world_loop_v26 import (
    compare_observed_transition, run_universal_world_advisory,
    simulate_world_transition,
)


def _state() -> dict[str, float]:
    return {"x": 0.0, "y": 0.0, "vx": 2.0, "vy": 0.0}


def _action() -> dict[str, float]:
    return {"ax": 0.0, "ay": 0.0}


def _observations() -> list[dict[str, object]]:
    return [
        observe_telemetry(state=_state(), approved=True),
        observe_transcript(text="check the simulation", approved=True),
    ]


def test_idealized_world_predict_and_residual() -> None:
    result = simulate_world_transition(
        state=_state(), action=_action(),
        dt_seconds=2, approved=True,
    )
    assert result["status"] == "simulated"
    assert result["predicted_state"]["x"] == 4.0
    assert result["physical_action_executed"] is False
    residual = compare_observed_transition(
        prediction=result,
        observed_next_state={"x": 3.0, "y": 0.0, "vx": 2.0, "vy": 0.0},
        approved=True,
    )
    assert residual["position_error_m"] == 1.0
    assert residual["unexpected_motion"] is True
    assert residual["model_self_updated"] is False


def test_full_multimodal_world_to_real_harness_brain(tmp_path: Path) -> None:
    prompts: list[str] = []

    def brain(_model: str, task: Task) -> str:
        prompts.append(task.instruction)
        return "Inspect simulated measurement bias; never actuate."

    result = run_universal_world_advisory(
        project_root=tmp_path,
        observations=_observations(),
        state=_state(), action=_action(), dt_seconds=2,
        actual_next_state={"x": 3, "y": 0, "vx": 2, "vy": 0},
        model_id="stub", brain=brain,
        approve_simulation=True, approve_model=True,
    )
    assert result["status"] == "complete"
    assert result["observation_count"] == 2
    assert result["observed_modalities"] == ["telemetry", "transcript"]
    assert result["residual"]["unexpected_motion"] is True
    assert result["model_calls"] == 1
    assert result["harness_replay_verified"] is True
    assert result["spine_integrity_ok"] is True
    assert result["harness_receipt_sha256"]
    assert result["files_written"] is False
    assert result["robot_or_device_handler_called"] is False
    assert "NEVER" not in prompts[0] or "SIMULATION" in prompts[0]
    assert "model" not in result["model_answer"][:5]


def test_world_simulation_can_run_without_model(tmp_path: Path) -> None:
    result = run_universal_world_advisory(
        project_root=tmp_path, observations=_observations(),
        state=_state(), action=_action(), dt_seconds=2,
        approve_simulation=True,
    )
    assert result["status"] == "simulated_advisory"
    assert result["model_calls"] == 0
    assert result["model_answer"] is None
    assert result["spine_integrity_ok"] is True


def test_no_approval_no_world_calculation(tmp_path: Path) -> None:
    report = run_universal_world_advisory(
        project_root=tmp_path, observations=[],
        state=_state(), action=_action(), dt_seconds=2,
    )
    assert report["status"] == "blocked"
    assert report["model_calls"] == 0


def test_bad_physics_and_nonfinite_values_refused() -> None:
    with pytest.raises(ValueError, match="world_acceleration_out_of_scope"):
        simulate_world_transition(
            state=_state(), action={"ax": 99, "ay": 0}, dt_seconds=1,
            approved=True,
        )
    with pytest.raises(ValueError, match="world_dt_out_of_range"):
        simulate_world_transition(
            state=_state(), action=_action(), dt_seconds=float("nan"),
            approved=True,
        )


def test_unverified_sensor_receipt_cannot_enter_world(tmp_path: Path) -> None:
    observation = _observations()
    observation[0]["raw_input_saved"] = True
    with pytest.raises(ValueError, match="world_raw_observation_persistence_denied"):
        run_universal_world_advisory(
            project_root=tmp_path, observations=observation,
            state=_state(), action=_action(), dt_seconds=1,
            approve_simulation=True,
        )


def test_dry_run_cli_never_reads_or_calls_model(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--dry-run", "--model", "qwen2.5:3b", "--transcript", "hello"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "configuration_only"
    assert result["model_calls"] == 0
    assert result["files_read"] is False
    assert result["physical_action_executed"] is False


def test_simulation_cli_requires_both_approvals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    args = ["--project-root", str(tmp_path)]
    assert main([*args, "--approve-observe"]) == 2
    assert json.loads(capsys.readouterr().out)["model_calls"] == 0
    assert main([*args, "--approve-observe", "--approve-simulate"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "simulated_advisory"
    assert result["residual"]["position_error_m"] == 1.0


def test_cli_stub_qwen_cpu_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hex_cortex.memory import cortex_universal_world_cli_v26 as cli

    config: list[dict[str, object]] = []

    class LocalBrain:
        def __init__(self, **kwargs: object) -> None:
            config.append(kwargs)

        def __call__(self, _model: str, _task: Task) -> str:
            return "Read-only diagnostic."

    monkeypatch.setattr(cli, "LocalOllamaBrain", LocalBrain)
    assert cli.main([
        "--project-root", str(tmp_path), "--model", "stub",
        "--approve-observe", "--approve-simulate", "--approve-model",
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "complete"
    assert report["model_calls"] == 1
    assert "model_answer" not in report
    assert report["model_answer_sha256"]
    assert config[0]["num_gpu"] == 0


def test_cli_demo_is_explicitly_illustrative_not_real_sensor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    args = ["--project-root", str(tmp_path), "--approve-observe", "--approve-simulate"]
    assert main(args) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["observed_transition_origin"] == "illustrative_fixture"
    assert receipt["residual"]["position_error_m"] == 1.0


def test_cli_operator_supplied_state_does_not_invent_sensor_measurement(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    args = [
        "--project-root", str(tmp_path), "--approve-observe", "--approve-simulate",
        "--state-x", "10", "--state-vx", "3", "--dt-seconds", "2",
    ]
    assert main(args) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["predicted_state"]["x"] == 16.0
    assert receipt["residual"] is None
    assert receipt["observed_transition_origin"] is None
    assert receipt["physical_action_executed"] is False


def test_cli_explicit_observed_values_create_non_calibrated_residual(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    args = [
        "--project-root", str(tmp_path), "--approve-observe", "--approve-simulate",
        "--state-x", "10", "--state-vx", "3",
        "--observed-x", "15", "--observed-y", "0",
        "--observed-vx", "3", "--observed-vy", "0",
    ]
    assert main(args) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["observed_transition_origin"] == "operator_supplied"
    assert receipt["residual"]["position_error_m"] == 1.0
    assert receipt["residual"]["measurement_calibrated"] is False


def test_cli_partial_measurement_is_refused_before_llm(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    args = [
        "--project-root", str(tmp_path), "--approve-observe", "--approve-simulate",
        "--observed-x", "3",
    ]
    assert main(args) == 2
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["reason"] == "world_observed_state_requires_all_four_coordinates"
