"""Stress V27 world bias under synthetic stable and shifted motion regimes.

No real sensors, inference, new active model, persistence or actuators.
Returns failure even when in-distribution fit is perfect if zero/reversed
hidden bias makes the candidate worse than the uncorrected model.
"""
from __future__ import annotations

from hex_cortex.memory.cortex_universal_world_loop_v26 import (
    simulate_world_transition,
)
from hex_cortex.memory.cortex_world_residual_learning_v27 import (
    _metric, fit_bounded_world_residual, simulate_with_reviewed_bias,
)
from hex_cortex.memory.cortex_world_residual_cli_v27 import _public_demo
from hex_cortex.memory.cortex_world_prospective_guard_v29 import (
    guard_next_simulated_prediction,
)

_REGIMES = {
    "training_like_bias": (0.4, -0.2),
    "bias_disappears": (0.0, 0.0),
    "bias_reverses": (-0.4, 0.2),
}


def stress_world_bias_regimes(*, approved: bool = False, approve_next_prediction: bool = False) -> dict[str, object]:
    if not approved:
        return {
            "status": "blocked", "reason": "stress_test_approval_required",
            "model_calls": 0, "files_written": False,
        }
    candidate = fit_bounded_world_residual(
        transitions=_public_demo(), approved=True,
    )
    if candidate["status"] != "candidate_for_manual_review":
        raise ValueError("world_stress_training_candidate_unqualified")
    regimes = []
    for name, biases in _REGIMES.items():
        before_losses: list[float] = []
        after_losses: list[float] = []
        historical_transitions: list[dict[str, object]] = []
        for i in range(4):
            state = {
                "x": float(100 + i * 3), "y": float(-10 + i),
                "vx": .5 + .2 * i, "vy": -.3,
            }
            action = {"ax": 0., "ay": 0.}
            dt = 1. + .5 * i
            baseline = simulate_world_transition(
                state=state, action=action, dt_seconds=dt, approved=True,
            )["predicted_state"]
            observed = dict(baseline)
            for axis, bias in zip(("x", "y"), biases, strict=True):
                observed[axis] += .5 * bias * dt ** 2
                observed["v" + axis] += bias * dt
            corrected = simulate_with_reviewed_bias(
                candidate=candidate, state=state, action=action,
                dt_seconds=dt, approved=True,
            )["corrected_predicted_state"]
            historical_transitions.append({
                "id": f"shift-{name}-{i}", "split": "test",
                "state": state, "action": action, "dt_seconds": dt,
                "observed_next_state": observed,
            })
            before_losses.append(_metric(observed, baseline))
            after_losses.append(_metric(observed, corrected))
        base = sum(before_losses) / len(before_losses)
        actual = sum(after_losses) / len(after_losses)
        prospective = (
            guard_next_simulated_prediction(
                candidate=candidate,
                completed_history=historical_transitions,
                next_state={"x": 200., "y": 0., "vx": 1., "vy": 0.},
                next_action={"ax": 0., "ay": 0.},
                next_dt_seconds=1.,
                approved=True,
            )
            if approve_next_prediction else None
        )
        regimes.append({
            "regime": name, "samples": len(before_losses),
            "baseline_normalized_mse": round(base, 10),
            "candidate_normalized_mse": round(actual, 10),
            "candidate_worse": actual > base + 1e-10,
            "prospective_next_prediction": prospective,
        })
    regression_names = [
        row["regime"] for row in regimes if row["candidate_worse"]
    ]
    return {
        "status": "regime_shift_regression_observed" if regression_names
        else "no_regression_observed",
        "training_candidate_status": candidate["status"],
        "model_type": candidate["model_type"],
        "regimes": regimes,
        "regressed_regimes": regression_names,
        "ready_for_real_world": False,
        "generalization_certified": False,
        "robust_across_evaluated_regimes": len(regression_names) == 0,
        "source": "deterministic_synthetic_stress_suite",
        "physical_action_executed": False,
        "model_calls": 0,
        "files_written": False,
    }
