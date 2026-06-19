from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

LATENT_LAB_FILENAME = "cortex-latent-world-model-lab.jsonl"
LatentPredictor = Callable[[list[float], dict[str, float]], dict[str, object]]


def build_latent_world_model_plan() -> dict[str, object]:
    return {
        "plan_type": "latent_world_model_lab_v1",
        "representation_space": "latent_embedding",
        "encoder_policy": "frozen_or_versioned_encoder",
        "transition_model": "action_conditioned_predictor",
        "uncertainty_required": True,
        "planner": "bounded_latent_mpc",
        "maximum_horizon_steps": 32,
        "raw_sensor_persistence_allowed": False,
        "raw_latent_persistence_allowed": False,
        "promotion_requires_offline_evaluation": True,
        "next_action": "collect_versioned_latent_transition_samples",
    }


def build_latent_transition_sample(
    *,
    encoder_id: str,
    encoder_version: str,
    current_latent: list[float],
    action: dict[str, float],
    next_latent: list[float],
    episode_id: str,
    step_index: int,
    split: str,
) -> dict[str, object]:
    _validate_vector(current_latent, "current_latent")
    _validate_vector(next_latent, "next_latent")
    if len(current_latent) != len(next_latent):
        raise ValueError("latent dimensions must match")
    if not encoder_id.strip() or not encoder_version.strip() or not episode_id.strip():
        raise ValueError("encoder and episode identifiers must be non-empty")
    if step_index < 0:
        raise ValueError("step_index must be non-negative")
    if split not in {"train", "validation", "test"}:
        raise ValueError("split must be train, validation, or test")
    if not action or not all(
        isinstance(key, str) and isinstance(value, int | float)
        for key, value in action.items()
    ):
        raise ValueError("action must be a non-empty numeric mapping")
    stable = {
        "encoder_id": encoder_id,
        "encoder_version": encoder_version,
        "current_latent_hash": _hash(current_latent),
        "action_hash": _hash(action),
        "next_latent_hash": _hash(next_latent),
        "episode_id": episode_id,
        "step_index": step_index,
        "split": split,
    }
    return {
        "sample_type": "latent_transition_sample",
        **stable,
        "latent_dimensions": len(current_latent),
        "raw_sensor_persisted": False,
        "raw_latent_persisted": False,
        "raw_action_persisted": False,
        "sample_hash": _hash(stable),
    }


def simulate_latent_mpc(
    *,
    current_latent: list[float],
    goal_latent: list[float],
    candidate_action_sequences: list[list[dict[str, float]]],
    predictor: LatentPredictor,
    uncertainty_weight: float = 0.25,
) -> dict[str, object]:
    _validate_vector(current_latent, "current_latent")
    _validate_vector(goal_latent, "goal_latent")
    if len(current_latent) != len(goal_latent):
        raise ValueError("current and goal latent dimensions must match")
    if not candidate_action_sequences:
        raise ValueError("at least one candidate action sequence is required")
    if uncertainty_weight < 0 or uncertainty_weight > 10:
        raise ValueError("uncertainty_weight must be in [0, 10]")
    rows = []
    for candidate_index, actions in enumerate(candidate_action_sequences):
        if not actions or len(actions) > 32:
            raise ValueError("each action sequence must contain 1 to 32 steps")
        state = list(current_latent)
        total_uncertainty = 0.0
        step_hashes = []
        for action in actions:
            if not action or not all(
                isinstance(key, str) and isinstance(value, int | float)
                for key, value in action.items()
            ):
                raise ValueError("actions must be non-empty numeric mappings")
            prediction = predictor(state, {key: float(value) for key, value in action.items()})
            next_state = prediction.get("next_latent")
            uncertainty = prediction.get("uncertainty", 0.0)
            if not isinstance(next_state, list):
                raise ValueError("predictor must return next_latent list")
            _validate_vector(next_state, "predicted_latent")
            if len(next_state) != len(state):
                raise ValueError("predictor changed latent dimensions")
            if not isinstance(uncertainty, int | float) or uncertainty < 0:
                raise ValueError("predictor uncertainty must be non-negative")
            state = [float(value) for value in next_state]
            total_uncertainty += float(uncertainty)
            step_hashes.append(_hash({"action": action, "latent": state}))
        goal_energy = _mean_squared_error(state, goal_latent)
        mean_uncertainty = total_uncertainty / len(actions)
        total_cost = goal_energy + (mean_uncertainty * uncertainty_weight)
        rows.append(
            {
                "candidate_index": candidate_index,
                "horizon_steps": len(actions),
                "goal_energy": round(goal_energy, 8),
                "mean_uncertainty": round(mean_uncertainty, 8),
                "total_cost": round(total_cost, 8),
                "action_sequence_hash": _hash(actions),
                "predicted_terminal_latent_hash": _hash(state),
                "step_hashes": step_hashes,
            }
        )
    ranked = sorted(rows, key=lambda row: (float(row["total_cost"]), int(row["candidate_index"])))
    selected = ranked[0]
    receipt_basis = {
        "current_latent_hash": _hash(current_latent),
        "goal_latent_hash": _hash(goal_latent),
        "candidate_rows": ranked,
        "uncertainty_weight": uncertainty_weight,
    }
    return {
        "simulation_type": "latent_mpc_simulation",
        "simulation_allowed": True,
        "candidate_count": len(ranked),
        "selected_candidate_index": selected["candidate_index"],
        "selected_total_cost": selected["total_cost"],
        "ranked_candidates": ranked,
        "current_latent_hash": receipt_basis["current_latent_hash"],
        "goal_latent_hash": receipt_basis["goal_latent_hash"],
        "raw_latent_persisted": False,
        "raw_actions_persisted": False,
        "external_effect_performed": False,
        "simulation_hash": _hash(receipt_basis),
        "next_action": "evaluate_selected_latent_plan_offline",
    }


def append_latent_lab_receipt(
    profile: Path,
    *,
    receipt: dict[str, object],
) -> dict[str, object]:
    if receipt.get("simulation_allowed") is not True:
        raise ValueError("only allowed simulations can be persisted")
    record = {
        "receipt_id": f"latent_lab_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "simulation_hash": receipt.get("simulation_hash"),
        "selected_candidate_index": receipt.get("selected_candidate_index"),
        "selected_total_cost": receipt.get("selected_total_cost"),
        "candidate_count": receipt.get("candidate_count"),
        "raw_latent_persisted": False,
        "raw_actions_persisted": False,
        "external_effect_performed": False,
    }
    path = profile / LATENT_LAB_FILENAME
    rows = _load(path)
    existing = next(
        (row for row in rows if row.get("simulation_hash") == record["simulation_hash"]),
        None,
    )
    if existing is None:
        rows.append(record)
        _write(path, rows)
        selected = record
    else:
        selected = existing
    return {
        "receipt_type": "latent_world_model_lab_receipt",
        "path": str(path),
        "receipt_count": len(rows),
        "receipt_records": [selected],
    }


def _validate_vector(values: list[float], label: str) -> None:
    if not isinstance(values, list) or not values or len(values) > 65536:
        raise ValueError(f"{label} must contain 1 to 65536 values")
    if not all(isinstance(value, int | float) for value in values):
        raise ValueError(f"{label} must be numeric")


def _mean_squared_error(left: list[float], right: list[float]) -> float:
    return sum((float(a) - float(b)) ** 2 for a, b in zip(left, right, strict=True)) / len(left)


def _hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _load(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
