"""V26 governed multimodal world cycle: see -> predict -> compare -> advise.

Lightweight deterministic kinematic baseline on CPU, not the separately
trained latent world model. Input is operator-supplied simulation telemetry.
Provenance is a Spine hash chain, NOT calibrated sensor authenticity.
No actuator, shell, network or persistence is wired.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from pathlib import Path

from hex_cortex.memory.cortex_local_cognitive_cycle import run_clocked_local_task
from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget, Capability, LocalHarness, Session, Task,
)
from hex_cortex.spine.canonical_spine import CanonicalSpine


def _finite_vector(data: dict[str, object], names: tuple[str, ...]) -> dict[str, float]:
    if not isinstance(data, dict) or set(data) != set(names):
        raise ValueError("world_state_fields_invalid")
    out: dict[str, float] = {}
    for k in names:
        n = data[k]
        if isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n):
            raise ValueError("world_nonfinite_value")
        if abs(n) > 1_000_000:
            raise ValueError("world_state_out_of_bounds")
        out[k] = float(n)
    return out


def simulate_world_transition(
    *, state: dict[str, float], action: dict[str, float],
    dt_seconds: float, approved: bool = False,
) -> dict[str, object]:
    if not approved:
        return {"status": "blocked", "reason": "simulation_approval_required",
                "simulation_performed": False, "physical_action_executed": False}
    old = _finite_vector(state, ("x", "y", "vx", "vy"))
    u = _finite_vector(action, ("ax", "ay"))
    if not isinstance(dt_seconds, (int, float)) or isinstance(dt_seconds, bool) or not math.isfinite(dt_seconds) or not 0 < dt_seconds <= 10:
        raise ValueError("world_dt_out_of_range")
    if any(abs(v) > 5 for v in u.values()):
        raise ValueError("world_acceleration_out_of_scope")
    dt = float(dt_seconds)
    predicted = {
        "x": old["x"] + old["vx"] * dt + .5 * u["ax"] * dt ** 2,
        "y": old["y"] + old["vy"] * dt + .5 * u["ay"] * dt ** 2,
        "vx": old["vx"] + u["ax"] * dt,
        "vy": old["vy"] + u["ay"] * dt,
    }
    if not all(math.isfinite(v) and abs(v) <= 1_000_000 for v in predicted.values()):
        raise ValueError("world_predicted_state_out_of_range")
    proof = hashlib.sha256(json.dumps(
        {"state": old, "action": u, "dt": dt, "predicted": predicted},
        sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    return {
        "status": "simulated",
        "model_type": "idealized_constant_acceleration_2d",
        "predicted_state": predicted,
        "state_prediction_sha256": proof,
        "prediction_verified_by_recomputation": False,
        "real_world_calibration": False,
        "simulation_performed": True,
        "physical_action_executed": False,
        "network_called": False,
    }


def compare_observed_transition(
    *, prediction: dict[str, object], observed_next_state: dict[str, float],
    approved: bool = False,
) -> dict[str, object]:
    if not approved:
        return {"status": "blocked", "reason": "observation_comparison_approval_required"}
    if prediction.get("status") != "simulated":
        raise ValueError("world_prediction_not_simulated")
    actual = _finite_vector(observed_next_state, ("x", "y", "vx", "vy"))
    expected = _finite_vector(prediction["predicted_state"], ("x", "y", "vx", "vy"))
    delta = {k: actual[k] - expected[k] for k in expected}
    position_error_m = math.hypot(delta["x"], delta["y"])
    velocity_error_m_s = math.hypot(delta["vx"], delta["vy"])
    return {
        "status": "residual_measured_against_operator_values",
        "position_error_m": round(position_error_m, 8),
        "velocity_error_m_s": round(velocity_error_m_s, 8),
        "unexpected_motion": bool(position_error_m > 0.5 or velocity_error_m_s > 0.5),
        "measurement_calibrated": False,
        "model_self_updated": False,
        "physical_action_executed": False,
    }


def _observation_receipts(observations: list[dict[str, object]]) -> list[dict[str, object]]:
    if not isinstance(observations, list) or len(observations) > 8:
        raise ValueError("world_observation_count_invalid")
    out: list[dict[str, object]] = []
    for obs in observations:
        if not isinstance(obs, dict) or obs.get("status") != "observed":
            raise ValueError("world_observation_unapproved")
        sha = obs.get("source_sha256")
        modality = obs.get("modality")
        if not isinstance(sha, str) or len(sha) != 64 or modality not in {
            "image", "audio", "code", "transcript", "telemetry"
        }:
            raise ValueError("world_observation_provenance_invalid")
        if obs.get("raw_input_saved") is not False:
            raise ValueError("world_raw_observation_persistence_denied")
        out.append({"modality": modality, "source_sha256": sha})
    return out


def run_universal_world_advisory(
    *,
    project_root: Path,
    observations: list[dict[str, object]],
    state: dict[str, float],
    action: dict[str, float],
    dt_seconds: float,
    model_id: str | None = None,
    brain: Callable[[str, Task], str] | None = None,
    actual_next_state: dict[str, float] | None = None,
    approve_simulation: bool = False,
    approve_model: bool = False,
    task_id: str = "universal-world-v26",
    observation_origin: str = "operator_supplied",
) -> dict[str, object]:
    """Real Spine/Harness integration, with NO real-world actuation path."""
    if not approve_simulation:
        return {"status": "blocked", "reason": "simulation_approval_required",
                "model_calls": 0, "physical_action_executed": False}
    if not isinstance(task_id, str) or not 1 <= len(task_id) <= 128:
        raise ValueError("world_task_id_invalid")
    if observation_origin not in {"operator_supplied", "illustrative_fixture"}:
        raise ValueError("world_observation_origin_invalid")
    receipts = _observation_receipts(observations)
    simulation = simulate_world_transition(
        state=state, action=action, dt_seconds=dt_seconds, approved=True
    )
    residual = (
        compare_observed_transition(
            prediction=simulation, observed_next_state=actual_next_state,
            approved=True,
        )
        if actual_next_state is not None else None
    )
    spine = CanonicalSpine()
    spine.append(
        event_type="world.observations",
        task_id=task_id, source="UniversalSensing",
        payload={"receipts": receipts, "operator_supplied": True},
    )
    spine.append(
        event_type="world.simulation",
        task_id=task_id, source="IdealizedKinematics",
        payload={
            "prediction_sha256": simulation["state_prediction_sha256"],
            "real_world_calibration": False,
            "physical_action_executed": False,
        },
    )
    if residual is not None:
        spine.append(
            event_type="world.residual",
            task_id=task_id, source="OperatorSuppliedMeasurement",
            payload={
                "position_error_m": residual["position_error_m"],
                "velocity_error_m_s": residual["velocity_error_m_s"],
                "unexpected_motion": residual["unexpected_motion"],
                "measurement_calibrated": False,
                "observation_origin": observation_origin,
            },
        )
    report: dict[str, object] = {
        "status": "simulated_advisory",
        "world_model": simulation["model_type"],
        "predicted_state": simulation["predicted_state"],
        "residual": residual,
        "observed_transition_origin": observation_origin if residual is not None else None,
        "observation_count": len(receipts),
        "observed_modalities": sorted({x["modality"] for x in receipts}),
        "observation_receipt_hashes": [x["source_sha256"] for x in receipts],
        "spine_integrity_ok": spine.verify_integrity().ok,
        "model_calls": 0,
        "model_answer": None,
        "model_answer_scientifically_verified": False,
        "trained_latent_model_used": False,
        "real_world_sensor_calibration": False,
        "physical_action_executed": False,
        "robot_or_device_handler_called": False,
        "files_written": False,
    }
    if not approve_model:
        return report
    if brain is None or not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("world_model_brain_missing")
    root = Path(project_root).resolve(strict=True)
    prompt = (
        "You are reviewing a bounded SIMULATION, not controlling hardware. "
        "Never issue actuator/device/shell commands. Explain uncertainty and "
        "do not claim real sensor calibration.\n"
        "Approved observation metadata (hashes, not raw media): "
        + json.dumps(receipts, sort_keys=True) + "\n"
        "Idealized simulation: " + json.dumps(
            simulation["predicted_state"], sort_keys=True
        ) + "\n"
        "Next state provenance: " + observation_origin + ". "
        "When illustrative_fixture, this is an invented DEMONSTRATION, "
        "not a physical sensor measurement. Do not suggest calibrating an "
        "actual sensor based on a fictitious observation.\n"
        "Comparison residual: " + json.dumps(residual, sort_keys=True)
        + "\nReply in at most 70 words with one read-only next diagnostic. " +
          "Do not invent a real sensor or claim experimental evidence."
    )
    harness = LocalHarness(
        session=Session(f"world-{task_id}", root),
        grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1, max_tool_calls=0),
        spine=spine,
    )
    result = run_clocked_local_task(
        harness,
        Task(task_id, "world_model", prompt),
        models=[model_id], brain=brain, approved=True,
    )
    report["status"] = "complete" if result["status"] == "complete" else "blocked"
    report["model_calls"] = harness._model_calls
    report["model_answer"] = result.get("output")
    report["harness_receipt_sha256"] = (
        result["receipt"]["sha256"] if result.get("receipt") else None
    )
    report["spine_integrity_ok"] = bool(result["canonical_spine_verified"])
    report["harness_replay_verified"] = harness.verify_replay()
    return report
