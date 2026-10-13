"""Conservative lagged feedback gate for a synthetic world-model bias.

Unlike a hindsight oracle, this decides whether to use a correction for
the *next* virtual prediction from ONLY already-completed transitions.
It is a rolling comparative-error safety heuristic, not ADWIN, a calibrated
statistical drift detector, real-world safety or autonomous model control.
"""
from __future__ import annotations

import math

from hex_cortex.memory.cortex_universal_world_loop_v26 import (
    simulate_world_transition,
)
from hex_cortex.memory.cortex_world_residual_learning_v27 import (
    _metric,
    _row,
    simulate_with_reviewed_bias,
)


def guard_next_simulated_prediction(
    *,
    candidate: dict[str, object],
    completed_history: list[dict[str, object]],
    next_state: dict[str, float],
    next_action: dict[str, float],
    next_dt_seconds: float,
    approved: bool = False,
    window: int = 3,
) -> dict[str, object]:
    if not approved:
        return {
            "status": "blocked", "reason": "world_feedback_gate_approval_required",
            "prediction_performed": False, "physical_action_executed": False,
        }
    if not isinstance(window, int) or isinstance(window, bool) or not 3 <= window <= 16:
        raise ValueError("world_feedback_window_invalid")
    if not isinstance(completed_history, list) or not 3 <= len(completed_history) <= 128:
        raise ValueError("world_feedback_history_length_invalid")
    rows = [_row(entry) for entry in completed_history]
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("world_feedback_duplicate_id")
    if len({row["source_hash"] for row in rows}) != len(rows):
        raise ValueError("world_feedback_duplicate_prior_state")
    # Baseline and corrected predictions are evaluated ONLY against
    # historical outcomes from previous completed transitions.
    recent = rows[-window:]
    before, after = [], []
    for entry in recent:
        checked = simulate_with_reviewed_bias(
            candidate=candidate,
            state=entry["state"], action=entry["action"],
            dt_seconds=entry["dt"], approved=True,
        )
        before.append(_metric(
            entry["observed"], checked["baseline_predicted_state"],
        ))
        after.append(_metric(
            entry["observed"], checked["corrected_predicted_state"],
        ))
    mean_before = sum(before) / len(before)
    mean_after = sum(after) / len(after)
    # Fail closed on repeated degradation, or loss of all positive evidence.
    if (
        any(not math.isfinite(value) for value in [mean_before, mean_after])
        or (mean_after > mean_before + 1e-10)
        or (mean_before <= 1e-12 and mean_after > 1e-12)
    ):
        status = "baseline_fallback_due_to_lagged_regression"
        use_bias = False
    else:
        status = "bias_trial_allowed_for_next_simulation"
        use_bias = True
    baseline_next = simulate_world_transition(
        state=next_state, action=next_action,
        dt_seconds=next_dt_seconds, approved=True,
    )["predicted_state"]
    corrected_next = (
        simulate_with_reviewed_bias(
            candidate=candidate, state=next_state, action=next_action,
            dt_seconds=next_dt_seconds, approved=True,
        )["corrected_predicted_state"]
        if use_bias else None
    )
    return {
        "status": status,
        "next_predicted_state": corrected_next if use_bias else baseline_next,
        "correction_proposed": use_bias,
        "fallback_used": not use_bias,
        "lagged_window_count": len(recent),
        "lagged_baseline_normalized_mse": round(mean_before, 10),
        "lagged_candidate_normalized_mse": round(mean_after, 10),
        "no_future_observation_used": True,
        "future_actual_outcome_known": False,
        "history_origin_independently_attested": False,
        "real_world_robustness_certified": False,
        "physical_action_executed": False,
        "automatic_model_activation_performed": False,
        "files_written": False,
    }
