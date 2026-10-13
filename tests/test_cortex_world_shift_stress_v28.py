"""Report synthetic world correction failure outside the fitted regime."""
from __future__ import annotations

import json

import pytest

from hex_cortex.memory.cortex_world_shift_stress_cli_v28 import main
from hex_cortex.memory.cortex_world_shift_stress_v28 import stress_world_bias_regimes


def test_stable_world_correction_regresses_on_regime_change() -> None:
    result = stress_world_bias_regimes(approved=True)
    assert result["status"] == "regime_shift_regression_observed"
    regimes = {x["regime"]: x for x in result["regimes"]}
    assert regimes["training_like_bias"]["candidate_worse"] is False
    assert regimes["training_like_bias"]["candidate_normalized_mse"] == pytest.approx(0)
    assert regimes["bias_disappears"]["candidate_worse"] is True
    assert regimes["bias_reverses"]["candidate_worse"] is True
    assert result["regressed_regimes"] == ["bias_disappears", "bias_reverses"]
    assert result["ready_for_real_world"] is False
    assert result["robust_across_evaluated_regimes"] is False
    assert result["generalization_certified"] is False
    assert result["physical_action_executed"] is False
    assert result["model_calls"] == 0


def test_world_shift_stress_denial_and_dry_run_no_actions(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert stress_world_bias_regimes()["status"] == "blocked"
    assert main(["--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["files_read"] is False
    assert main([]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"
    assert main(["--approve-stress"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "regime_shift_regression_observed"
    assert result["files_written"] is False



def test_opt_in_prospective_world_gate_falls_back_after_prior_drift(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--approve-next-prediction"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"
    assert main(["--approve-stress", "--approve-next-prediction"]) == 0
    receipt = json.loads(capsys.readouterr().out)
    regimes = {row["regime"]: row["prospective_next_prediction"]
               for row in receipt["regimes"]}
    assert regimes["training_like_bias"]["correction_proposed"] is True
    assert regimes["bias_disappears"]["fallback_used"] is True
    assert regimes["bias_reverses"]["fallback_used"] is True
    assert all(row["no_future_observation_used"] for row in regimes.values())
    assert all(row["physical_action_executed"] is False for row in regimes.values())
