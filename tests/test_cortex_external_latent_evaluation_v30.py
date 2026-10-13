"""External latent audit: group-heldout, leakage checks, score separation."""
from __future__ import annotations

from copy import deepcopy

import pytest

from hex_cortex.memory.cortex_external_latent_cli_v30 import _synthetic_example
from hex_cortex.memory.cortex_external_latent_evaluation_v30 import (
    audit_external_latent_trajectories,
    evaluate_external_latent_predictions,
)


def _records() -> list[dict]:
    return deepcopy(_synthetic_example())


def test_external_latent_audit_reuses_existing_world_manifest() -> None:
    receipt = audit_external_latent_trajectories(_records())
    assert receipt["status"] == "external_latent_audit_pass"
    assert receipt["audit_allowed"] is True
    assert receipt["split_counts"] == {"train": 2, "validation": 1, "test": 3}
    assert receipt["episode_group_counts"] == {"train": 2, "validation": 1, "test": 3}
    assert receipt["test_environment_count"] == 2
    assert len(receipt["existing_world_model_manifest_hash"]) == 64
    assert receipt["latent_dim"] == 2
    assert receipt["action_dim"] == 1
    assert receipt["real_world_origin_verified"] is False
    assert receipt["independent_source_attested"] is False
    assert receipt["files_written"] is False


def test_comparable_identity_vs_operator_supplied_predictor_without_promotion() -> None:
    audit = audit_external_latent_trajectories(_records())
    seen = []

    def pretend_predictor(state: list[float], action: list[float]) -> list[float]:
        seen.append((state, action))
        return [state[0] + .1, .75]

    result = evaluate_external_latent_predictions(audit, predictor=pretend_predictor)
    assert result["status"] == "heldout_latent_comparison_recorded"
    assert len(seen) == 3
    assert result["candidate_mse"] == pytest.approx(0)
    assert result["identity_mse"] > 0
    assert result["existing_world_candidate_evaluation"]["promotion_allowed"] is True
    assert result["qualified_for_manual_review"] is False
    assert result["independent_test_origin_attested"] is False
    assert result["model_activated"] is False
    assert result["files_written"] is False


def test_group_regression_overrides_global_mean_gain() -> None:
    audit = audit_external_latent_trajectories(_records())

    def predictor(state: list[float], _action: list[float]) -> list[float]:
        if state[0] == 4:
            return [state[0] - 3., 0.5]
        return [state[0] + .1, .75]

    result = evaluate_external_latent_predictions(
        audit, predictor=predictor, candidate_weights_verified=True
    )
    assert result["regressed_environment_count"] >= 1
    assert result["qualified_for_manual_review"] is False


@pytest.mark.parametrize(("update", "expected"), [
    (lambda r: r[2].update(episode_id=r[0]["episode_id"]),
     "external_latent_episode_crosses_splits"),
    (lambda r: r[3].update(environment_id=r[0]["environment_id"]),
     "external_latent_environment_crosses_splits"),
    (lambda r: r[3].update(sample_id=r[0]["sample_id"]),
     "external_latent_duplicate_sample_id"),
    (lambda r: r[3].update(encoder_descriptor_hash="0" * 64),
     "external_latent_mixed_encoders"),
    (lambda r: r[3].update(action=[float("nan")]),
     "external_latent_invalid_bounded_numeric_vector"),
    (lambda r: r[3].update(next_state_latent=[3.3, .75, 0]),
     "external_latent_target_dimension_mismatch"),
    (lambda r: r[3].update(state_latent=r[0]["state_latent"],
                         action=r[0]["action"],
                         next_state_latent=r[0]["next_state_latent"]),
     "external_latent_duplicate_transition"),
])
def test_external_rows_fail_closed(update, expected: str) -> None:
    records = _records()
    update(records)
    with pytest.raises(ValueError, match=expected):
        audit_external_latent_trajectories(records)


def test_test_split_requires_more_than_one_independent_environment() -> None:
    records = _records()
    records[4]["environment_id"] = records[3]["environment_id"]
    result = audit_external_latent_trajectories(records)
    assert result["audit_allowed"] is False
    assert "independent_test_environments_insufficient" in result["blockers"]


def test_scoring_rejects_nonfinite_prediction() -> None:
    audit = audit_external_latent_trajectories(_records())
    with pytest.raises(ValueError, match="external_latent_invalid_bounded_numeric_vector"):
        evaluate_external_latent_predictions(
            audit, predictor=lambda _state, _action: [float("nan"), .5]
        )


def test_scoring_rejects_unapproved_audit() -> None:
    audit = audit_external_latent_trajectories(_records())
    audit["audit_allowed"] = False
    with pytest.raises(ValueError, match="external_latent_audit_must_pass_before_evaluation"):
        evaluate_external_latent_predictions(
            audit, predictor=lambda state, _action: state
        )
