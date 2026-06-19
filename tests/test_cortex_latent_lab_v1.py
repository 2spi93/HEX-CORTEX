import pytest

from hex_cortex.memory.cortex_latent_experiment import build_latent_experiment_receipt
from hex_cortex.memory.cortex_latent_lab import build_latent_lab_spec
from hex_cortex.memory.cortex_latent_lab import evaluate_latent_prediction
from hex_cortex.memory.cortex_latent_lab import predict_latent_transition
from hex_cortex.memory.cortex_latent_lab import rollout_latent_dynamics


def test_latent_lab_spec_is_safe_and_hash_only() -> None:
    spec = build_latent_lab_spec(latent_dim=3, action_dim=2, horizons=[1, 4])
    assert spec["spec_allowed"] is True
    assert spec["storage_policy"] == "hash_only"
    assert spec["training_performed"] is False
    assert len(spec["spec_hash"]) == 64


def test_latent_lab_spec_rejects_bad_horizons() -> None:
    spec = build_latent_lab_spec(horizons=[4, 1, 4])
    assert spec["spec_allowed"] is False
    assert "horizons_must_be_unique_sorted" in spec["blockers"]


def test_latent_transition_uses_state_and_action() -> None:
    predicted = predict_latent_transition(
        [1.0, 2.0],
        [0.5, -1.0],
        [[2.0, 1.0], [0.0, 0.5]],
        [0.25, 0.0],
    )
    assert predicted == [1.25, 1.5]


def test_latent_transition_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="weights shape mismatch"):
        predict_latent_transition([1.0, 2.0], [1.0], [[1.0]])


def test_latent_rollout_returns_all_states() -> None:
    states = rollout_latent_dynamics(
        [0.0, 0.0],
        [[1.0], [2.0]],
        [[1.0], [0.5]],
    )
    assert states == [[0.0, 0.0], [1.0, 0.5], [3.0, 1.5]]


def test_latent_prediction_reports_error_level() -> None:
    close = evaluate_latent_prediction([1.0, 1.0], [1.01, 0.99])
    far = evaluate_latent_prediction([4.0, 4.0], [1.0, 1.0])
    assert close["surprising"] is False
    assert far["surprising"] is True
    assert close["storage_policy"] == "hash_only"


def test_latent_experiment_receipt_with_observation() -> None:
    spec = build_latent_lab_spec(latent_dim=2, action_dim=1, horizons=[1])
    receipt = build_latent_experiment_receipt(
        spec=spec,
        initial_state=[0.0, 0.0],
        actions=[[1.0]],
        weights=[[1.0], [0.5]],
        observed_final_state=[1.0, 0.5],
    )
    assert receipt["experiment_allowed"] is True
    assert receipt["rollout_performed"] is True
    assert receipt["evaluation"]["surprising"] is False
    assert receipt["training_performed"] is False


def test_latent_experiment_rejects_dimension_mismatch() -> None:
    spec = build_latent_lab_spec(latent_dim=2, action_dim=2)
    receipt = build_latent_experiment_receipt(
        spec=spec,
        initial_state=[0.0],
        actions=[[1.0]],
        weights=[[1.0]],
    )
    assert receipt["experiment_allowed"] is False
    assert "initial_state_dimension_mismatch" in receipt["blockers"]
    assert "action_dimension_mismatch" in receipt["blockers"]
