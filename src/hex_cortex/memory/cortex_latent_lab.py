from __future__ import annotations

import hashlib
import json
import math


def build_latent_lab_spec(
    *,
    latent_dim: int = 8,
    action_dim: int = 4,
    horizons: list[int] | None = None,
) -> dict[str, object]:
    horizons = list(horizons or [1, 4, 16])
    blockers = []
    if not 2 <= latent_dim <= 65_536:
        blockers.append("latent_dim_out_of_range")
    if not 1 <= action_dim <= 4_096:
        blockers.append("action_dim_out_of_range")
    if not horizons or horizons != sorted(set(horizons)):
        blockers.append("horizons_must_be_unique_sorted")
    elif any(step < 1 or step > 256 for step in horizons):
        blockers.append("horizons_out_of_range")
    stable = {
        "latent_dim": latent_dim,
        "action_dim": action_dim,
        "horizons": horizons,
        "blockers": blockers,
    }
    return {
        "spec_type": "latent_world_model_lab_v1",
        "latent_dim": latent_dim,
        "action_dim": action_dim,
        "horizons": horizons,
        "encoder_policy": "frozen_external_encoder",
        "predictor_kind": "action_conditioned_residual_v1",
        "uncertainty_head": True,
        "storage_policy": "hash_only",
        "training_performed": False,
        "spec_allowed": not blockers,
        "blockers": blockers,
        "spec_hash": _stable_hash(stable),
        "next_action": "run_latent_baseline" if not blockers else "repair_latent_lab_spec",
    }


def predict_latent_transition(
    state: list[float],
    action: list[float],
    weights: list[list[float]],
    bias: list[float] | None = None,
) -> list[float]:
    if not state or not action:
        raise ValueError("state and action must be non-empty")
    if len(weights) != len(state) or any(len(row) != len(action) for row in weights):
        raise ValueError("weights shape mismatch")
    if bias is not None and len(bias) != len(state):
        raise ValueError("bias shape mismatch")
    result = []
    for index, current in enumerate(state):
        delta = sum(float(w) * float(a) for w, a in zip(weights[index], action))
        result.append(float(current) + delta + (float(bias[index]) if bias else 0.0))
    return result


def rollout_latent_dynamics(
    initial_state: list[float],
    actions: list[list[float]],
    weights: list[list[float]],
    *,
    max_steps: int = 64,
) -> list[list[float]]:
    if len(actions) > max_steps or not 1 <= max_steps <= 256:
        raise ValueError("invalid rollout length")
    states = [list(map(float, initial_state))]
    for action in actions:
        states.append(predict_latent_transition(states[-1], action, weights))
    return states


def evaluate_latent_prediction(
    predicted: list[float],
    observed: list[float],
    *,
    surprise_threshold: float = 0.25,
) -> dict[str, object]:
    if not predicted or len(predicted) != len(observed):
        raise ValueError("prediction shape mismatch")
    if surprise_threshold <= 0:
        raise ValueError("surprise_threshold must be positive")
    errors = [float(p) - float(o) for p, o in zip(predicted, observed)]
    mse = sum(value * value for value in errors) / len(errors)
    rmse = math.sqrt(mse)
    scale = max(math.sqrt(sum(float(v) ** 2 for v in observed) / len(observed)), 1e-9)
    normalized_error = rmse / scale
    surprise_score = min(1.0, normalized_error / surprise_threshold)
    metrics = {
        "mse": round(mse, 8),
        "rmse": round(rmse, 8),
        "normalized_error": round(normalized_error, 8),
        "surprise_score": round(surprise_score, 8),
    }
    return {
        "evaluation_type": "latent_prediction_evaluation_v1",
        **metrics,
        "surprising": surprise_score >= 1.0,
        "prediction_hash": _stable_hash(predicted),
        "observation_hash": _stable_hash(observed),
        "storage_policy": "hash_only",
        "evaluation_hash": _stable_hash(metrics),
    }


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
