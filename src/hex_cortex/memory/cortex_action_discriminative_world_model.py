from __future__ import annotations

import hashlib
import json
import math
import random
import time
from pathlib import Path

from hex_cortex.memory.cortex_compact_world_model import _batch_tensors
from hex_cortex.memory.cortex_compact_world_model import _build_model
from hex_cortex.memory.cortex_compact_world_model import _encode_transition_record
from hex_cortex.memory.cortex_compact_world_model import _evaluate_rows
from hex_cortex.memory.cortex_compact_world_model import _file_hash
from hex_cortex.memory.cortex_compact_world_model import _identity_baseline_error
from hex_cortex.memory.cortex_compact_world_model import _resolve_device
from hex_cortex.memory.cortex_compact_world_model import build_cached_dinov2_runner
from hex_cortex.memory.cortex_frozen_encoder import EncoderRunner
from hex_cortex.memory.cortex_world_model_eval import evaluate_world_model_candidate

_DEFAULT_ACTION_CATALOG = (
    (-1.0, 0.0),
    (1.0, 0.0),
    (0.0, -1.0),
    (0.0, 1.0),
)


def build_action_discriminative_plan(
    *,
    manifest: dict[str, object],
    hidden_dim: int = 128,
    epochs: int = 100,
    batch_size: int = 16,
    learning_rate: float = 0.001,
    weight_decay: float = 0.0001,
    ranking_margin: float = 0.0001,
    ranking_weight: float = 1.0,
    minimum_top1_accuracy: float = 1.0,
    seed: int = 42,
    device: str = "cpu",
    max_seconds: float = 1800.0,
    action_catalog: tuple[tuple[float, ...], ...] = _DEFAULT_ACTION_CATALOG,
) -> dict[str, object]:
    blockers: list[str] = []
    if manifest.get("manifest_allowed") is not True:
        blockers.append("dataset_manifest_not_allowed")
    if manifest.get("training_ready") is not True:
        blockers.append("dataset_not_training_ready")
    latent_dim = manifest.get("latent_dim")
    records = manifest.get("records")
    if not isinstance(latent_dim, int) or not 1 <= latent_dim <= 65_536:
        blockers.append("latent_dim_invalid")
    if not isinstance(records, list) or not records:
        blockers.append("dataset_records_missing")
    action_dim = None
    if isinstance(records, list) and records:
        first_action = records[0].get("action_values") if isinstance(records[0], dict) else None
        if isinstance(first_action, list):
            action_dim = len(first_action)
    if not isinstance(action_dim, int) or not 1 <= action_dim <= 64:
        blockers.append("action_dim_invalid")
    if any(len(action) != action_dim for action in action_catalog) if isinstance(action_dim, int) else True:
        blockers.append("action_catalog_dimension_mismatch")
    if len(set(action_catalog)) < 2:
        blockers.append("action_catalog_too_small")
    if not 4 <= hidden_dim <= 4096:
        blockers.append("hidden_dim_out_of_range")
    if not 1 <= epochs <= 10_000:
        blockers.append("epochs_out_of_range")
    if not 1 <= batch_size <= 4096:
        blockers.append("batch_size_out_of_range")
    if not 0.0 < learning_rate <= 1.0:
        blockers.append("learning_rate_out_of_range")
    if not 0.0 <= weight_decay <= 1.0:
        blockers.append("weight_decay_out_of_range")
    if not 0.0 < ranking_margin <= 1.0:
        blockers.append("ranking_margin_out_of_range")
    if not 0.0 < ranking_weight <= 100.0:
        blockers.append("ranking_weight_out_of_range")
    if not 0.0 <= minimum_top1_accuracy <= 1.0:
        blockers.append("minimum_top1_accuracy_out_of_range")
    if device not in {"cpu", "cuda", "mps", "auto"}:
        blockers.append("device_unsupported")
    if not 1.0 <= max_seconds <= 86_400.0:
        blockers.append("max_seconds_out_of_range")
    config = {
        "latent_dim": latent_dim,
        "action_dim": action_dim,
        "hidden_dim": hidden_dim,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "weight_decay": weight_decay,
        "ranking_margin": ranking_margin,
        "ranking_weight": ranking_weight,
        "minimum_top1_accuracy": minimum_top1_accuracy,
        "seed": seed,
        "device": device,
        "max_seconds": max_seconds,
        "action_catalog": [list(action) for action in action_catalog],
        "architecture": "residual_mlp_action_discriminative_v2",
        "objective": "transition_mse_plus_counterfactual_margin_ranking",
    }
    payload = {
        "plan_type": "action_discriminative_world_model_plan_v2",
        "plan_allowed": not blockers,
        "manifest_hash": manifest.get("manifest_hash"),
        "config": config,
        "training_performed": False,
        "checkpoint_written": False,
        "blockers": sorted(set(blockers)),
        "next_action": "train_action_discriminative_model" if not blockers else "repair_v2_training_plan",
    }
    payload["plan_hash"] = _stable_hash(payload)
    return payload


def train_action_discriminative_model(
    *,
    plan: dict[str, object],
    manifest: dict[str, object],
    environment_root: Path,
    encoder_descriptor: dict[str, object],
    output_dir: Path,
    operator_approved: bool = False,
    encoder_runner: EncoderRunner | None = None,
) -> dict[str, object]:
    if not operator_approved:
        return _blocked_training(["operator_approval_required"])
    if plan.get("plan_allowed") is not True:
        return _blocked_training(["training_plan_not_allowed"])
    if plan.get("manifest_hash") != manifest.get("manifest_hash"):
        return _blocked_training(["manifest_hash_mismatch"])
    try:
        import torch
        from safetensors.torch import save_file
    except ImportError:
        return _blocked_training(["torch_or_safetensors_missing"])
    config = plan.get("config")
    records = manifest.get("records")
    if not isinstance(config, dict) or not isinstance(records, list):
        return _blocked_training(["training_inputs_invalid"])

    started = time.monotonic()
    seed = int(config["seed"])
    random.seed(seed)
    torch.manual_seed(seed)
    device = _resolve_device(torch, str(config["device"]))
    runner = encoder_runner or build_cached_dinov2_runner()
    encoded_rows: list[dict[str, object]] = []
    for record in records:
        if time.monotonic() - started > float(config["max_seconds"]):
            return _blocked_training(["training_time_budget_exceeded"])
        if not isinstance(record, dict):
            return _blocked_training(["transition_record_invalid"])
        row = _encode_transition_record(
            record=record,
            comfy_root=environment_root,
            encoder_descriptor=encoder_descriptor,
            encoder_runner=runner,
        )
        if row.get("allowed") is not True:
            return _blocked_training(list(row.get("blockers", ["transition_encoding_failed"])))
        encoded_rows.append(row)

    train_rows = [row for row in encoded_rows if row["split"] == "train"]
    validation_rows = [row for row in encoded_rows if row["split"] == "validation"]
    test_rows = [row for row in encoded_rows if row["split"] == "test"]
    if not train_rows or not validation_rows or not test_rows:
        return _blocked_training(["all_dataset_splits_required"])

    model = _build_model(
        torch,
        latent_dim=int(config["latent_dim"]),
        action_dim=int(config["action_dim"]),
        hidden_dim=int(config["hidden_dim"]),
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["learning_rate"]),
        weight_decay=float(config["weight_decay"]),
    )
    action_catalog = [tuple(float(value) for value in action) for action in config["action_catalog"]]
    best_state = None
    best_validation_objective = math.inf
    history: list[dict[str, float | int]] = []
    for epoch in range(int(config["epochs"])):
        if time.monotonic() - started > float(config["max_seconds"]):
            break
        random.Random(seed + epoch).shuffle(train_rows)
        model.train()
        batch_losses = []
        ranking_losses = []
        for offset in range(0, len(train_rows), int(config["batch_size"])):
            batch = train_rows[offset : offset + int(config["batch_size"])]
            state, action, target = _batch_tensors(torch, batch, device)
            optimizer.zero_grad(set_to_none=True)
            prediction = model(state, action)
            transition_loss = torch.nn.functional.mse_loss(prediction, target)
            ranking_loss = _counterfactual_ranking_loss(
                torch,
                model,
                state,
                action,
                target,
                action_catalog,
                margin=float(config["ranking_margin"]),
            )
            loss = transition_loss + float(config["ranking_weight"]) * ranking_loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            batch_losses.append(float(transition_loss.detach().to("cpu")))
            ranking_losses.append(float(ranking_loss.detach().to("cpu")))
        validation_transition = _evaluate_rows(torch, model, validation_rows, device)
        validation_policy = _policy_metrics(torch, model, validation_rows, device, action_catalog)
        validation_objective = validation_transition + (
            1.0 - float(validation_policy["top1_action_accuracy"])
        )
        history.append(
            {
                "epoch": epoch + 1,
                "train_prediction_error": round(sum(batch_losses) / max(len(batch_losses), 1), 10),
                "train_ranking_loss": round(sum(ranking_losses) / max(len(ranking_losses), 1), 10),
                "validation_prediction_error": round(validation_transition, 10),
                "validation_top1_action_accuracy": round(float(validation_policy["top1_action_accuracy"]), 8),
            }
        )
        if validation_objective < best_validation_objective:
            best_validation_objective = validation_objective
            best_state = {
                name: tensor.detach().to("cpu").clone()
                for name, tensor in model.state_dict().items()
            }
    if best_state is None:
        return _blocked_training(["no_training_epoch_completed"])

    model.load_state_dict(best_state)
    model.to(device)
    model.eval()
    train_error = _evaluate_rows(torch, model, train_rows, device)
    validation_error = _evaluate_rows(torch, model, validation_rows, device)
    test_error = _evaluate_rows(torch, model, test_rows, device)
    identity_baseline_error = _identity_baseline_error(torch, test_rows)
    test_policy = _policy_metrics(torch, model, test_rows, device, action_catalog)
    transition_evaluation = evaluate_world_model_candidate(
        baseline={"prediction_error": identity_baseline_error},
        candidate={"prediction_error": test_error},
        required_metrics=["prediction_error"],
        max_regression_fraction=0.0,
        minimum_improvement_fraction=0.01,
    )
    policy_gate_passed = (
        float(test_policy["top1_action_accuracy"]) + 1e-12
        >= float(config["minimum_top1_accuracy"])
        and float(test_policy["positive_margin_rate"]) >= 1.0
    )
    promotion_allowed = (
        manifest.get("promotion_ready") is True
        and transition_evaluation.get("promotion_allowed") is True
        and policy_gate_passed
    )

    target_dir = output_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    weights_path = target_dir / "predictor.safetensors"
    save_file(best_state, str(weights_path))
    weights_hash = _file_hash(weights_path)
    promotion_blockers = []
    if manifest.get("promotion_ready") is not True:
        promotion_blockers.append("dataset_not_promotion_ready")
    promotion_blockers.extend(transition_evaluation.get("blockers", []))
    if float(test_policy["top1_action_accuracy"]) + 1e-12 < float(config["minimum_top1_accuracy"]):
        promotion_blockers.append("test_top1_action_accuracy_below_threshold")
    if float(test_policy["positive_margin_rate"]) < 1.0:
        promotion_blockers.append("correct_action_margin_not_strictly_positive")

    candidate = {
        "candidate_type": "action_discriminative_world_model_candidate_v2",
        "status": "trained",
        "architecture": config["architecture"],
        "config": config,
        "manifest_hash": manifest.get("manifest_hash"),
        "dataset_domain": manifest.get("domain"),
        "encoder_descriptor_hash": manifest.get("encoder_descriptor_hash"),
        "weights_file": weights_path.name,
        "weights_hash": weights_hash,
        "metrics": {
            "train_prediction_error": train_error,
            "validation_prediction_error": validation_error,
            "test_prediction_error": test_error,
            "identity_baseline_prediction_error": identity_baseline_error,
            **test_policy,
        },
        "transition_evaluation": transition_evaluation,
        "policy_gate_passed": policy_gate_passed,
        "promotion_allowed": promotion_allowed,
        "promotion_blockers": sorted(set(promotion_blockers)),
        "history": history,
        "device": str(device),
        "training_seconds": round(time.monotonic() - started, 3),
        "training_performed": True,
        "checkpoint_written": True,
        "raw_image_persisted": False,
        "latent_vector_persisted": False,
        "next_action": "promote_candidate" if promotion_allowed else "collect_retrain_or_revise_representation",
    }
    candidate["candidate_hash"] = _stable_hash(candidate)
    candidate_path = target_dir / "candidate.json"
    candidate_path.write_text(
        json.dumps(candidate, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "receipt_type": "action_discriminative_training_receipt_v2",
        "status": "trained",
        "candidate_manifest": str(candidate_path),
        "candidate_hash": candidate["candidate_hash"],
        "weights_hash": weights_hash,
        "promotion_allowed": promotion_allowed,
        "metrics": candidate["metrics"],
        "policy_gate_passed": policy_gate_passed,
        "training_performed": True,
        "checkpoint_written": True,
        "raw_image_persisted": False,
        "latent_vector_persisted": False,
        "blockers": [],
        "next_action": candidate["next_action"],
    }


def _counterfactual_ranking_loss(
    torch_module,
    model,
    state,
    observed_action,
    target,
    action_catalog,
    *,
    margin: float,
):
    true_prediction = model(state, observed_action)
    true_distance = ((true_prediction - target) ** 2).mean(dim=1)
    losses = []
    for candidate in action_catalog:
        candidate_tensor = torch_module.tensor(
            [candidate] * state.shape[0],
            dtype=state.dtype,
            device=state.device,
        )
        different = (candidate_tensor != observed_action).any(dim=1)
        if not bool(different.any()):
            continue
        candidate_prediction = model(state, candidate_tensor)
        candidate_distance = ((candidate_prediction - target) ** 2).mean(dim=1)
        raw = torch_module.relu(margin + true_distance - candidate_distance)
        losses.append(raw[different])
    if not losses:
        return true_distance.mean() * 0.0
    return torch_module.cat(losses).mean()


def _policy_metrics(torch_module, model, rows, device, action_catalog) -> dict[str, float]:
    model.eval()
    correct_top1 = 0
    correct_top2 = 0
    reciprocal_ranks = []
    margins = []
    with torch_module.inference_mode():
        for row in rows:
            state = torch_module.tensor([row["state"]], dtype=torch_module.float32, device=device)
            target = torch_module.tensor([row["target"]], dtype=torch_module.float32, device=device)
            observed = tuple(float(value) for value in row["action"])
            scored = []
            for candidate in action_catalog:
                action = torch_module.tensor([candidate], dtype=torch_module.float32, device=device)
                prediction = model(state, action)
                distance = float(((prediction - target) ** 2).mean().detach().to("cpu"))
                scored.append((distance, tuple(candidate)))
            scored.sort(key=lambda item: (item[0], item[1]))
            rank = next(index for index, (_, action) in enumerate(scored, start=1) if action == observed)
            true_distance = next(distance for distance, action in scored if action == observed)
            best_wrong = min(distance for distance, action in scored if action != observed)
            correct_top1 += rank == 1
            correct_top2 += rank <= 2
            reciprocal_ranks.append(1.0 / rank)
            margins.append(best_wrong - true_distance)
    count = max(len(rows), 1)
    return {
        "top1_action_accuracy": correct_top1 / count,
        "top2_action_accuracy": correct_top2 / count,
        "mean_reciprocal_rank": sum(reciprocal_ranks) / count,
        "mean_correct_action_margin": sum(margins) / count,
        "positive_margin_rate": sum(margin > 0.0 for margin in margins) / count,
    }


def _blocked_training(blockers: list[str]) -> dict[str, object]:
    return {
        "receipt_type": "action_discriminative_training_receipt_v2",
        "status": "blocked",
        "training_performed": False,
        "checkpoint_written": False,
        "blockers": sorted(set(blockers)),
        "next_action": "repair_action_discriminative_training",
    }


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
