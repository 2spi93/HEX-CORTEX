from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from hex_cortex.memory.cortex_latent_lab import evaluate_latent_prediction
from hex_cortex.memory.cortex_latent_lab import rollout_latent_dynamics


def build_latent_experiment_receipt(
    *,
    spec: dict[str, object],
    initial_state: list[float],
    actions: list[list[float]],
    weights: list[list[float]],
    observed_final_state: list[float] | None = None,
) -> dict[str, object]:
    blockers = []
    if spec.get("spec_allowed") is not True:
        blockers.append("latent_lab_spec_not_allowed")
    if len(initial_state) != spec.get("latent_dim"):
        blockers.append("initial_state_dimension_mismatch")
    action_dim = spec.get("action_dim")
    if not isinstance(action_dim, int) or any(len(action) != action_dim for action in actions):
        blockers.append("action_dimension_mismatch")
    if blockers:
        return {
            "receipt_type": "latent_world_model_experiment_v1",
            "experiment_allowed": False,
            "rollout_performed": False,
            "training_performed": False,
            "blockers": blockers,
            "next_action": "repair_latent_experiment",
        }
    states = rollout_latent_dynamics(
        initial_state,
        actions,
        weights,
        max_steps=max(1, len(actions)),
    )
    predicted_final = states[-1]
    evaluation = None
    if observed_final_state is not None:
        evaluation = evaluate_latent_prediction(predicted_final, observed_final_state)
    stable = {
        "spec_hash": spec.get("spec_hash"),
        "initial_state_hash": _stable_hash(initial_state),
        "actions_hash": _stable_hash(actions),
        "predicted_final_hash": _stable_hash(predicted_final),
        "step_count": len(actions),
        "evaluation_hash": evaluation.get("evaluation_hash") if evaluation else None,
    }
    return {
        "receipt_type": "latent_world_model_experiment_v1",
        "experiment_id": f"latent_experiment_{uuid4().hex}",
        "experiment_allowed": True,
        "rollout_performed": True,
        "step_count": len(actions),
        "initial_state_hash": stable["initial_state_hash"],
        "actions_hash": stable["actions_hash"],
        "predicted_final_hash": stable["predicted_final_hash"],
        "evaluation": evaluation,
        "training_performed": False,
        "model_call_performed": False,
        "network_call_performed": False,
        "storage_policy": "hash_only",
        "receipt_hash": _stable_hash(stable),
        "blockers": [],
        "next_action": (
            "prepare_training_evaluation_plan"
            if evaluation
            else "collect_observed_transition"
        ),
    }


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
