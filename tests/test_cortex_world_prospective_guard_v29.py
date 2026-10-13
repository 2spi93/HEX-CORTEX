"""Future world prediction may only use evidence from completed past steps."""
from __future__ import annotations

from copy import deepcopy

import pytest

from hex_cortex.memory.cortex_universal_world_loop_v26 import simulate_world_transition
from hex_cortex.memory.cortex_world_prospective_guard_v29 import (
    guard_next_simulated_prediction,
)
from hex_cortex.memory.cortex_world_residual_cli_v27 import _public_demo
from hex_cortex.memory.cortex_world_residual_learning_v27 import (
    fit_bounded_world_residual,
)


def _candidate() -> dict[str, object]:
    return fit_bounded_world_residual(transitions=_public_demo(), approved=True)


def _future_kwargs() -> dict:
    return {
        "next_state": {"x": 200., "y": 0., "vx": 1., "vy": 0.},
        "next_action": {"ax": 0., "ay": 0.},
        "next_dt_seconds": 1.,
    }


def _shifted_history(bias: float) -> list[dict[str, object]]:
    rows = deepcopy(_public_demo()[4:])
    for item in rows:
        base = simulate_world_transition(
            state=item["state"], action=item["action"],
            dt_seconds=item["dt_seconds"], approved=True,
        )["predicted_state"]
        dt = item["dt_seconds"]
        item["observed_next_state"] = {
            "x": base["x"] + .5 * bias * dt * dt,
            "y": base["y"],
            "vx": base["vx"] + bias * dt,
            "vy": base["vy"],
        }
    return rows


def test_stable_previous_feedback_permits_simulation_only_bias_trial() -> None:
    output = guard_next_simulated_prediction(
        candidate=_candidate(), completed_history=deepcopy(_public_demo()[:4]),
        approved=True, **_future_kwargs(),
    )
    assert output["status"] == "bias_trial_allowed_for_next_simulation"
    assert output["next_predicted_state"]["x"] == pytest.approx(201.2)
    assert output["correction_proposed"] is True
    assert output["no_future_observation_used"] is True
    assert output["automatic_model_activation_performed"] is False
    assert output["physical_action_executed"] is False


@pytest.mark.parametrize("bias", [0., -0.4])
def test_shifted_regime_falls_back_to_uncorrected_predictor(bias: float) -> None:
    output = guard_next_simulated_prediction(
        candidate=_candidate(), completed_history=_shifted_history(bias),
        approved=True, **_future_kwargs(),
    )
    assert output["status"] == "baseline_fallback_due_to_lagged_regression"
    assert output["fallback_used"] is True
    assert output["next_predicted_state"]["x"] == 201.
    assert output["lagged_candidate_normalized_mse"] > output[
        "lagged_baseline_normalized_mse"
    ]
    assert output["future_actual_outcome_known"] is False


def test_requires_history_and_operator_permission() -> None:
    output = guard_next_simulated_prediction(
        candidate=_candidate(), completed_history=[],
        **_future_kwargs(),
    )
    assert output["status"] == "blocked"
    assert output["prediction_performed"] is False
    with pytest.raises(ValueError, match="world_feedback_history_length_invalid"):
        guard_next_simulated_prediction(
            candidate=_candidate(), completed_history=[],
            approved=True, **_future_kwargs(),
        )


def test_duplicate_historical_samples_fail_closed() -> None:
    records = deepcopy(_public_demo()[:3])
    records[1]["state"] = dict(records[0]["state"])
    with pytest.raises(ValueError, match="world_feedback_duplicate_prior_state"):
        guard_next_simulated_prediction(
            candidate=_candidate(), completed_history=records,
            approved=True, **_future_kwargs(),
        )


def test_no_future_measurement_is_accepted_as_input() -> None:
    with pytest.raises(TypeError):
        guard_next_simulated_prediction(
            candidate=_candidate(), completed_history=deepcopy(_public_demo()[:4]),
            approved=True,
            future_observed_state={"x": 1.},
            **_future_kwargs(),
        )
