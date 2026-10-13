"""A real but extremely bounded CPU world-model update from held-out residuals.

Learns a *constant unmodelled acceleration bias* from independently supplied
2-D transitions; accepts a candidate ONLY if unseen examples improve without
per-case regression. No trained latent vision world model, calibration, device
control, online learning, implicit persistence, or physical safety claim.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence

from hex_cortex.memory.cortex_universal_world_loop_v26 import (
    _finite_vector,
    simulate_world_transition,
)

_MIN_TRAIN, _MIN_TEST = 3, 3


def _row(row: dict[str, object]) -> dict[str, object]:
    if not isinstance(row, dict) or set(row) != {
        "id", "split", "state", "action", "dt_seconds", "observed_next_state"
    }:
        raise ValueError("world_learning_row_schema_invalid")
    sample_id = row["id"]
    split = row["split"]
    if (
        not isinstance(sample_id, str)
        or not 1 <= len(sample_id) <= 80
        or split not in ("train", "test")
    ):
        raise ValueError("world_learning_row_identity_invalid")
    state = _finite_vector(row["state"], ("x", "y", "vx", "vy"))
    action = _finite_vector(row["action"], ("ax", "ay"))
    observed = _finite_vector(row["observed_next_state"], ("x", "y", "vx", "vy"))
    dt = row["dt_seconds"]
    simulation = simulate_world_transition(
        state=state, action=action, dt_seconds=dt, approved=True
    )
    return {
        "id": sample_id, "split": split,
        "state": state, "action": action,
        "dt": float(dt),
        "observed": observed,
        "predicted": simulation["predicted_state"],
        "source_hash": hashlib.sha256(json.dumps(
            {"state": state, "action": action, "dt": float(dt)},
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
        "hash": hashlib.sha256(json.dumps(
            {"id": sample_id, "split": split, "state": state,
             "action": action, "dt": float(dt), "observed": observed},
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
    }


def _metric(actual: dict[str, float], predicted: dict[str, float]) -> float:
    # Positions and velocities have different physical units. These are
    # scaled by explicit reference values to obtain a dimensionless metric.
    return (
        (actual["x"] - predicted["x"]) ** 2 / 1.0**2
        + (actual["y"] - predicted["y"]) ** 2 / 1.0**2
        + (actual["vx"] - predicted["vx"]) ** 2 / 1.0**2
        + (actual["vy"] - predicted["vy"]) ** 2 / 1.0**2
    ) / 4


def fit_bounded_world_residual(
    *,
    transitions: Sequence[dict[str, object]],
    approved: bool = False,
    minimum_improvement_fraction: float = 0.1,
) -> dict[str, object]:
    if not approved:
        return {
            "status": "blocked", "reason": "world_learning_approval_required",
            "learning_performed": False, "files_written": False,
        }
    if isinstance(transitions, (str, bytes)) or not 6 <= len(transitions) <= 100:
        raise ValueError("world_learning_sample_count_invalid")
    if (
        isinstance(minimum_improvement_fraction, bool)
        or not isinstance(minimum_improvement_fraction, (float, int))
        or not math.isfinite(minimum_improvement_fraction)
        or not 0.01 <= minimum_improvement_fraction <= 0.9
    ):
        raise ValueError("world_learning_threshold_invalid")
    rows = [_row(row) for row in transitions]
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("world_learning_duplicate_sample_id")
    if len({row["source_hash"] for row in rows}) != len(rows):
        raise ValueError("world_learning_train_test_source_leakage")
    training = [row for row in rows if row["split"] == "train"]
    heldout = [row for row in rows if row["split"] == "test"]
    if len(training) < _MIN_TRAIN or len(heldout) < _MIN_TEST:
        raise ValueError("world_learning_split_too_small")
    # Velocity residuals divided by duration infer constant acceleration
    # bias. Robust bounded median reduces a single corrupt training point.
    bias = {}
    for axis in ("x", "y"):
        estimates = sorted(
            (row["observed"]["v" + axis] - row["predicted"]["v" + axis]) / row["dt"]
            for row in training
        )
        count = len(estimates)
        value = estimates[count // 2] if count % 2 else (
            estimates[count // 2 - 1] + estimates[count // 2]
        ) / 2
        if not math.isfinite(value) or abs(value) > 5:
            raise ValueError("world_learning_residual_bias_out_of_scope")
        bias["a" + axis] = value

    baseline_losses, corrected_losses = [], []
    details = []
    for row in heldout:
        original = row["predicted"]
        dt = row["dt"]
        updated = dict(original)
        for axis in ("x", "y"):
            a = bias["a" + axis]
            updated[axis] += .5 * a * dt ** 2
            updated["v" + axis] += a * dt
        b_loss = _metric(row["observed"], original)
        c_loss = _metric(row["observed"], updated)
        baseline_losses.append(b_loss)
        corrected_losses.append(c_loss)
        details.append({
            "sample_hash": row["hash"],
            "baseline_normalized_mse": round(b_loss, 10),
            "candidate_normalized_mse": round(c_loss, 10),
            "regressed": c_loss > b_loss + 1e-10,
        })
    before = sum(baseline_losses) / len(baseline_losses)
    after = sum(corrected_losses) / len(corrected_losses)
    gain = (before - after) / before if before > 1e-12 else 0.0
    regressions = sum(bool(r["regressed"]) for r in details)
    good = before > 1e-12 and gain >= minimum_improvement_fraction and regressions == 0
    return {
        "status": "candidate_for_manual_review" if good else "rejected_on_heldout",
        "model_type": "constant_unmodeled_acceleration_bias_v27",
        "bias_estimates_m_s2": bias,
        "training_count": len(training), "heldout_count": len(heldout),
        "baseline_normalized_mse": round(before, 10),
        "candidate_normalized_mse": round(after, 10),
        "heldout_improvement_fraction": round(gain, 8),
        "heldout_regression_count": regressions,
        "heldout_results": details,
        "training_input_hashes": [row["hash"] for row in training],
        "evaluation_input_hashes": [row["hash"] for row in heldout],
        "training_test_source_overlap": False,
        "learned_from_operator_supplied_transitions": True,
        "independent_holdout_attested": False,
        "model_promoted_to_active_world": False,
        "latent_world_model_training_performed": False,
        "real_world_calibrated": False,
        "physical_action_authorized": False,
        "files_written": False,
    }
