"""CPU learning: disjoint heldout improvement, rejection and provenance gates."""
from __future__ import annotations

import json

import pytest

from hex_cortex.memory.cortex_universal_world_loop_v26 import simulate_world_transition
from hex_cortex.memory.cortex_world_residual_cli_v27 import _public_demo, main
from hex_cortex.memory.cortex_world_residual_learning_v27 import (
    fit_bounded_world_residual,
)


def test_toy_residual_fits_known_drift_on_unseen_states() -> None:
    report = fit_bounded_world_residual(
        transitions=_public_demo(), approved=True
    )
    assert report["status"] == "candidate_for_manual_review"
    assert report["bias_estimates_m_s2"]["ax"] == pytest.approx(0.4)
    assert report["bias_estimates_m_s2"]["ay"] == pytest.approx(-0.2)
    assert report["training_count"] == 4
    assert report["heldout_count"] == 4
    assert report["baseline_normalized_mse"] > 0
    assert report["candidate_normalized_mse"] == pytest.approx(0)
    assert report["heldout_improvement_fraction"] == pytest.approx(1)
    assert report["heldout_regression_count"] == 0
    assert report["independent_holdout_attested"] is False
    assert report["model_promoted_to_active_world"] is False
    assert report["real_world_calibrated"] is False
    assert report["files_written"] is False


def test_no_approval_makes_no_training_changes() -> None:
    report = fit_bounded_world_residual(transitions=_public_demo())
    assert report["status"] == "blocked"
    assert report["learning_performed"] is False


def test_cross_split_exact_source_leakage_blocked() -> None:
    items = _public_demo()
    items[4]["state"] = dict(items[0]["state"])
    with pytest.raises(ValueError, match="source_leakage"):
        fit_bounded_world_residual(transitions=items, approved=True)


def test_model_with_wrong_holdout_bias_is_rejected() -> None:
    examples = _public_demo()
    for row in examples[4:]:
        raw = simulate_world_transition(
            state=row["state"], action=row["action"],
            dt_seconds=row["dt_seconds"], approved=True,
        )["predicted_state"]
        row["observed_next_state"] = raw
    report = fit_bounded_world_residual(transitions=examples, approved=True)
    assert report["status"] == "rejected_on_heldout"
    assert report["heldout_regression_count"] == 4
    assert report["model_promoted_to_active_world"] is False


@pytest.mark.parametrize("bad_field", [
    float("nan"), float("inf"), True, 2_000_000.0,
])
def test_invalid_observed_sensor_values_denied(bad_field: float) -> None:
    rows = _public_demo()
    rows[0]["observed_next_state"]["x"] = bad_field
    with pytest.raises(ValueError):
        fit_bounded_world_residual(transitions=rows, approved=True)


def test_insufficient_train_and_eval_rejected() -> None:
    rows = _public_demo()
    rows[2]["split"] = "test"
    rows[3]["split"] = "test"
    with pytest.raises(ValueError, match="split_too_small"):
        fit_bounded_world_residual(transitions=rows, approved=True)


def test_cli_requires_approval_and_only_runs_demo_when_allowed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["training_performed"] is False
    assert main([]) == 2
    assert json.loads(capsys.readouterr().out)["learning_performed"] is False
    assert main(["--approve-fit"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "candidate_for_manual_review"
    assert result["files_written"] is False
