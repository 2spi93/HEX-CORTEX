from __future__ import annotations

import hashlib
import json
import math
import random
import shutil
import time
from pathlib import Path
from typing import Any

from hex_cortex.memory.cortex_frozen_encoder import EncoderRunner
from hex_cortex.memory.cortex_frozen_encoder import encode_image_to_latent
from hex_cortex.memory.cortex_world_model_eval import evaluate_world_model_candidate


def build_compact_predictor_plan(
    *,
    manifest: dict[str, object],
    hidden_dim: int = 128,
    epochs: int = 40,
    batch_size: int = 8,
    learning_rate: float = 0.001,
    weight_decay: float = 0.0001,
    seed: int = 42,
    device: str = "cpu",
    max_seconds: float = 900.0,
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
    if not 0 <= seed <= 2**31 - 1:
        blockers.append("seed_out_of_range")
    if device not in {"cpu", "cuda", "mps", "auto"}:
        blockers.append("device_unsupported")
    if not 1.0 <= max_seconds <= 86_400.0:
        blockers.append("max_seconds_out_of_range")
    blockers = sorted(set(blockers))
    config = {
        "latent_dim": latent_dim,
        "action_dim": action_dim,
        "hidden_dim": hidden_dim,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "weight_decay": weight_decay,
        "seed": seed,
        "device": device,
        "max_seconds": max_seconds,
        "architecture": "residual_mlp_v1",
    }
    stable = {
        "manifest_hash": manifest.get("manifest_hash"),
        "config": config,
        "blockers": blockers,
    }
    return {
        "plan_type": "compact_world_model_training_plan_v1",
        "plan_allowed": not blockers,
        "manifest_hash": manifest.get("manifest_hash"),
        "config": config,
        "run_performed": False,
        "checkpoint_written": False,
        "training_performed": False,
        "plan_hash": _stable_hash(stable),
        "blockers": blockers,
        "next_action": "execute_compact_training" if not blockers else "repair_training_plan",
    }


def build_cached_dinov2_runner() -> EncoderRunner:
    state: dict[str, Any] = {
        "processor": None,
        "model": None,
        "torch": None,
        "device": None,
        "model_ref": None,
        "local_files_only": None,
        "cache": {},
    }

    def runner(
        image_path: Path,
        model_ref: str,
        pooling: str,
        device: str,
        local_files_only: bool,
    ) -> tuple[list[float], dict[str, object]]:
        cache_key = (
            str(image_path.resolve()),
            model_ref,
            pooling,
            device,
            local_files_only,
            image_path.stat().st_mtime_ns,
            image_path.stat().st_size,
        )
        cached = state["cache"].get(cache_key)
        if cached is not None:
            vector, metadata = cached
            return list(vector), {**metadata, "session_cache_hit": True}
        if (
            state["model"] is None
            or state["model_ref"] != model_ref
            or state["local_files_only"] != local_files_only
            or str(state["device"]) != str(device)
        ):
            import torch
            from transformers import AutoImageProcessor, AutoModel

            resolved_device = _resolve_device(torch, device)
            processor = AutoImageProcessor.from_pretrained(
                model_ref,
                local_files_only=local_files_only,
            )
            model = AutoModel.from_pretrained(
                model_ref,
                local_files_only=local_files_only,
            )
            model.eval()
            model.requires_grad_(False)
            model.to(resolved_device)
            state.update(
                {
                    "processor": processor,
                    "model": model,
                    "torch": torch,
                    "device": resolved_device,
                    "model_ref": model_ref,
                    "local_files_only": local_files_only,
                    "cache": {},
                }
            )
        from PIL import Image

        torch = state["torch"]
        processor = state["processor"]
        model = state["model"]
        resolved_device = state["device"]
        with Image.open(image_path) as image:
            inputs = processor(images=image.convert("RGB"), return_tensors="pt")
        inputs = {name: value.to(resolved_device) for name, value in inputs.items()}
        with torch.inference_mode():
            outputs = model(**inputs)
            hidden = outputs.last_hidden_state
            embedding = hidden[:, 0, :] if pooling == "cls" else hidden[:, 1:, :].mean(dim=1)
        vector = embedding[0].detach().to("cpu").float().tolist()
        metadata = {
            "device": str(resolved_device),
            "dtype": str(embedding.dtype),
            "model_eval_mode": model.training is False,
            "requires_grad": any(parameter.requires_grad for parameter in model.parameters()),
            "input_shape": list(inputs["pixel_values"].shape),
            "hidden_size": int(model.config.hidden_size),
            "patch_size": model.config.patch_size,
            "session_cache_hit": False,
        }
        state["cache"][cache_key] = (list(vector), dict(metadata))
        return vector, metadata

    return runner


def train_compact_predictor(
    *,
    plan: dict[str, object],
    manifest: dict[str, object],
    comfy_root: Path,
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
    config = plan["config"]
    records = manifest.get("records")
    if not isinstance(config, dict) or not isinstance(records, list):
        return _blocked_training(["training_inputs_invalid"])
    started = time.monotonic()
    seed = int(config["seed"])
    random.seed(seed)
    torch.manual_seed(seed)
    resolved_device = _resolve_device(torch, str(config["device"]))
    runner = encoder_runner or build_cached_dinov2_runner()
    encoded_rows: list[dict[str, object]] = []
    for record in records:
        if time.monotonic() - started > float(config["max_seconds"]):
            return _blocked_training(["training_time_budget_exceeded"])
        if not isinstance(record, dict):
            return _blocked_training(["transition_record_invalid"])
        row = _encode_transition_record(
            record=record,
            comfy_root=comfy_root,
            encoder_descriptor=encoder_descriptor,
            encoder_runner=runner,
        )
        if row.get("allowed") is not True:
            return _blocked_training(list(row.get("blockers", ["transition_encoding_failed"])))
        encoded_rows.append(row)
    model = _build_model(
        torch,
        latent_dim=int(config["latent_dim"]),
        action_dim=int(config["action_dim"]),
        hidden_dim=int(config["hidden_dim"]),
    ).to(resolved_device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["learning_rate"]),
        weight_decay=float(config["weight_decay"]),
    )
    train_rows = [row for row in encoded_rows if row["split"] == "train"]
    validation_rows = [row for row in encoded_rows if row["split"] == "validation"]
    test_rows = [row for row in encoded_rows if row["split"] == "test"]
    if not train_rows or not validation_rows or not test_rows:
        return _blocked_training(["all_dataset_splits_required"])
    best_state: dict[str, object] | None = None
    best_validation = math.inf
    history: list[dict[str, float | int]] = []
    batch_size = int(config["batch_size"])
    for epoch in range(int(config["epochs"])):
        if time.monotonic() - started > float(config["max_seconds"]):
            break
        random.Random(seed + epoch).shuffle(train_rows)
        model.train()
        epoch_losses: list[float] = []
        for offset in range(0, len(train_rows), batch_size):
            batch = train_rows[offset : offset + batch_size]
            state_tensor, action_tensor, target_tensor = _batch_tensors(
                torch,
                batch,
                resolved_device,
            )
            optimizer.zero_grad(set_to_none=True)
            prediction = model(state_tensor, action_tensor)
            loss = torch.nn.functional.mse_loss(prediction, target_tensor)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            epoch_losses.append(float(loss.detach().to("cpu")))
        validation_error = _evaluate_rows(torch, model, validation_rows, resolved_device)
        train_error = sum(epoch_losses) / max(len(epoch_losses), 1)
        history.append(
            {
                "epoch": epoch + 1,
                "train_prediction_error": round(train_error, 10),
                "validation_prediction_error": round(validation_error, 10),
            }
        )
        if validation_error < best_validation:
            best_validation = validation_error
            best_state = {
                name: tensor.detach().to("cpu").clone()
                for name, tensor in model.state_dict().items()
            }
    if best_state is None:
        return _blocked_training(["no_training_epoch_completed"])
    model.load_state_dict(best_state)
    model.to(resolved_device)
    model.eval()
    train_error = _evaluate_rows(torch, model, train_rows, resolved_device)
    validation_error = _evaluate_rows(torch, model, validation_rows, resolved_device)
    test_error = _evaluate_rows(torch, model, test_rows, resolved_device)
    identity_baseline_error = _identity_baseline_error(torch, test_rows)
    evaluation = evaluate_world_model_candidate(
        baseline={"prediction_error": identity_baseline_error},
        candidate={"prediction_error": test_error},
        required_metrics=["prediction_error"],
        max_regression_fraction=0.0,
        minimum_improvement_fraction=0.01,
    )
    promotion_allowed = (
        manifest.get("promotion_ready") is True
        and evaluation.get("promotion_allowed") is True
    )
    target = output_dir.resolve()
    target.mkdir(parents=True, exist_ok=True)
    weights_path = target / "predictor.safetensors"
    save_file(best_state, str(weights_path))
    weights_hash = _file_hash(weights_path)
    candidate = {
        "candidate_type": "compact_world_model_candidate_v1",
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
        },
        "evaluation": evaluation,
        "promotion_allowed": promotion_allowed,
        "promotion_blockers": (
            []
            if promotion_allowed
            else sorted(
                set(
                    ([] if manifest.get("promotion_ready") is True else ["dataset_not_promotion_ready"])
                    + list(evaluation.get("blockers", []))
                )
            )
        ),
        "history": history,
        "device": str(resolved_device),
        "training_seconds": round(time.monotonic() - started, 3),
        "training_performed": True,
        "checkpoint_written": True,
        "raw_image_persisted": False,
        "latent_vector_persisted": False,
        "next_action": "promote_candidate" if promotion_allowed else "collect_more_or_better_transitions",
    }
    candidate["candidate_hash"] = _stable_hash(candidate)
    manifest_path = target / "candidate.json"
    manifest_path.write_text(
        json.dumps(candidate, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "receipt_type": "compact_world_model_training_receipt_v1",
        "status": "trained",
        "candidate_manifest": str(manifest_path),
        "candidate_hash": candidate["candidate_hash"],
        "weights_hash": weights_hash,
        "promotion_allowed": promotion_allowed,
        "metrics": candidate["metrics"],
        "evaluation": evaluation,
        "training_performed": True,
        "checkpoint_written": True,
        "raw_image_persisted": False,
        "latent_vector_persisted": False,
        "blockers": [],
        "next_action": candidate["next_action"],
    }


def promote_compact_predictor(
    *,
    candidate_manifest_path: Path,
    registry_dir: Path,
    operator_approved: bool = False,
) -> dict[str, object]:
    if not operator_approved:
        return _blocked_promotion(["operator_approval_required"])
    try:
        candidate = json.loads(candidate_manifest_path.resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _blocked_promotion(["candidate_manifest_invalid"])
    if not isinstance(candidate, dict):
        return _blocked_promotion(["candidate_manifest_not_object"])
    if candidate.get("promotion_allowed") is not True:
        return _blocked_promotion(["candidate_not_promotable"])
    source_dir = candidate_manifest_path.resolve().parent
    weights_file = candidate.get("weights_file")
    if not isinstance(weights_file, str) or Path(weights_file).name != weights_file:
        return _blocked_promotion(["candidate_weights_filename_invalid"])
    source_weights = source_dir / weights_file
    if not source_weights.is_file() or _file_hash(source_weights) != candidate.get("weights_hash"):
        return _blocked_promotion(["candidate_weights_hash_mismatch"])
    target = registry_dir.resolve()
    target.mkdir(parents=True, exist_ok=True)
    target_weights = target / "active_predictor.safetensors"
    target_candidate = target / "active_candidate.json"
    shutil.copy2(source_weights, target_weights)
    active_candidate = dict(candidate)
    active_candidate["weights_file"] = target_weights.name
    active_candidate["promoted"] = True
    active_candidate["promotion_receipt_hash"] = _stable_hash(
        {
            "candidate_hash": candidate.get("candidate_hash"),
            "weights_hash": candidate.get("weights_hash"),
        }
    )
    target_candidate.write_text(
        json.dumps(active_candidate, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    active = {
        "registry_type": "active_compact_world_model_v1",
        "candidate_file": target_candidate.name,
        "weights_file": target_weights.name,
        "candidate_hash": candidate.get("candidate_hash"),
        "weights_hash": candidate.get("weights_hash"),
        "dataset_domain": candidate.get("dataset_domain"),
        "encoder_descriptor_hash": candidate.get("encoder_descriptor_hash"),
        "promotion_receipt_hash": active_candidate["promotion_receipt_hash"],
    }
    active["registry_hash"] = _stable_hash(active)
    active_path = target / "active.json"
    active_path.write_text(json.dumps(active, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {
        "receipt_type": "compact_world_model_promotion_v1",
        "status": "promoted",
        "active_registry": str(active_path),
        "candidate_hash": candidate.get("candidate_hash"),
        "weights_hash": candidate.get("weights_hash"),
        "promotion_performed": True,
        "blockers": [],
        "next_action": "run_active_predictor_probe",
    }


def predict_with_active_compact_model(
    *,
    active_registry_path: Path,
    comfy_root: Path,
    image_path: Path,
    action: list[float],
    encoder_descriptor: dict[str, object],
    encoder_runner: EncoderRunner | None = None,
) -> dict[str, object]:
    try:
        import torch
        from safetensors.torch import load_file
    except ImportError:
        return _blocked_prediction(["torch_or_safetensors_missing"])
    try:
        active = json.loads(active_registry_path.resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _blocked_prediction(["active_registry_invalid"])
    if not isinstance(active, dict):
        return _blocked_prediction(["active_registry_not_object"])
    root = active_registry_path.resolve().parent
    candidate_path = root / str(active.get("candidate_file"))
    weights_path = root / str(active.get("weights_file"))
    try:
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _blocked_prediction(["active_candidate_invalid"])
    if _file_hash(weights_path) != active.get("weights_hash"):
        return _blocked_prediction(["active_weights_hash_mismatch"])
    config = candidate.get("config")
    if not isinstance(config, dict):
        return _blocked_prediction(["active_candidate_config_invalid"])
    if len(action) != int(config["action_dim"]):
        return _blocked_prediction(["action_dimension_mismatch"])
    output_root = (comfy_root.resolve() / "output").resolve()
    image = image_path.resolve()
    if not image.is_file() or not image.is_relative_to(output_root):
        return _blocked_prediction(["image_outside_comfyui_output"])
    runner = encoder_runner or build_cached_dinov2_runner()
    encoder_receipt = encode_image_to_latent(
        descriptor=encoder_descriptor,
        image_path=image,
        include_vector=True,
        runner=runner,
    )
    latent = encoder_receipt.pop("volatile_embedding", None)
    if encoder_receipt.get("encoded") is not True or not isinstance(latent, list):
        return _blocked_prediction(["active_encoder_failed"])
    model = _build_model(
        torch,
        latent_dim=int(config["latent_dim"]),
        action_dim=int(config["action_dim"]),
        hidden_dim=int(config["hidden_dim"]),
    )
    model.load_state_dict(load_file(str(weights_path), device="cpu"))
    model.eval()
    with torch.inference_mode():
        state_tensor = torch.tensor([latent], dtype=torch.float32)
        action_tensor = torch.tensor([action], dtype=torch.float32)
        predicted = model(state_tensor, action_tensor)[0].tolist()
    return {
        "receipt_type": "active_compact_world_model_prediction_v1",
        "status": "predicted",
        "candidate_hash": active.get("candidate_hash"),
        "registry_hash": active.get("registry_hash"),
        "image_hash": encoder_receipt.get("image_hash"),
        "latent_state_hash": encoder_receipt.get("embedding_hash"),
        "action_hash": _stable_hash([float(value) for value in action]),
        "predicted_latent_hash": _stable_hash([round(float(value), 10) for value in predicted]),
        "latent_dim": len(predicted),
        "network_call_performed": False,
        "model_call_performed": True,
        "training_performed": False,
        "raw_image_persisted": False,
        "latent_vector_persisted": False,
        "blockers": [],
        "next_action": "compare_with_observed_next_state",
    }


def _encode_transition_record(
    *,
    record: dict[str, object],
    comfy_root: Path,
    encoder_descriptor: dict[str, object],
    encoder_runner: EncoderRunner,
) -> dict[str, object]:
    output_root = (comfy_root.resolve() / "output").resolve()
    current_path = (output_root / str(record.get("current_image_ref"))).resolve()
    next_path = (output_root / str(record.get("next_image_ref"))).resolve()
    if not current_path.is_relative_to(output_root) or not next_path.is_relative_to(output_root):
        return {"allowed": False, "blockers": ["transition_image_path_escape"]}
    if not current_path.is_file() or not next_path.is_file():
        return {"allowed": False, "blockers": ["transition_image_missing"]}
    if _file_hash(current_path) != record.get("current_image_hash"):
        return {"allowed": False, "blockers": ["current_image_hash_mismatch"]}
    if _file_hash(next_path) != record.get("next_image_hash"):
        return {"allowed": False, "blockers": ["next_image_hash_mismatch"]}
    current_receipt = encode_image_to_latent(
        descriptor=encoder_descriptor,
        image_path=current_path,
        include_vector=True,
        runner=encoder_runner,
    )
    next_receipt = encode_image_to_latent(
        descriptor=encoder_descriptor,
        image_path=next_path,
        include_vector=True,
        runner=encoder_runner,
    )
    current_latent = current_receipt.pop("volatile_embedding", None)
    next_latent = next_receipt.pop("volatile_embedding", None)
    if current_receipt.get("embedding_hash") != record.get("current_latent_hash"):
        return {"allowed": False, "blockers": ["current_latent_hash_mismatch"]}
    if next_receipt.get("embedding_hash") != record.get("next_latent_hash"):
        return {"allowed": False, "blockers": ["next_latent_hash_mismatch"]}
    if not isinstance(current_latent, list) or not isinstance(next_latent, list):
        return {"allowed": False, "blockers": ["latent_vector_unavailable"]}
    return {
        "allowed": True,
        "sample_id": record.get("sample_id"),
        "split": record.get("split"),
        "state": current_latent,
        "action": [float(value) for value in record.get("action_values", [])],
        "target": next_latent,
    }


def _build_model(torch_module, *, latent_dim: int, action_dim: int, hidden_dim: int):
    class ResidualMLP(torch_module.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.network = torch_module.nn.Sequential(
                torch_module.nn.Linear(latent_dim + action_dim, hidden_dim),
                torch_module.nn.GELU(),
                torch_module.nn.Linear(hidden_dim, latent_dim),
            )

        def forward(self, state, action):
            return state + self.network(torch_module.cat((state, action), dim=-1))

    return ResidualMLP()


def _batch_tensors(torch_module, rows, device):
    state = torch_module.tensor([row["state"] for row in rows], dtype=torch_module.float32, device=device)
    action = torch_module.tensor([row["action"] for row in rows], dtype=torch_module.float32, device=device)
    target = torch_module.tensor([row["target"] for row in rows], dtype=torch_module.float32, device=device)
    return state, action, target


def _evaluate_rows(torch_module, model, rows, device) -> float:
    model.eval()
    state, action, target = _batch_tensors(torch_module, rows, device)
    with torch_module.inference_mode():
        prediction = model(state, action)
        error = torch_module.nn.functional.mse_loss(prediction, target)
    return float(error.detach().to("cpu"))


def _identity_baseline_error(torch_module, rows) -> float:
    state = torch_module.tensor([row["state"] for row in rows], dtype=torch_module.float32)
    target = torch_module.tensor([row["target"] for row in rows], dtype=torch_module.float32)
    return float(torch_module.nn.functional.mse_loss(state, target))


def _resolve_device(torch_module, requested: str):
    if requested != "auto":
        return torch_module.device(requested)
    if torch_module.cuda.is_available():
        return torch_module.device("cuda")
    mps = getattr(torch_module.backends, "mps", None)
    if mps is not None and mps.is_available():
        return torch_module.device("mps")
    return torch_module.device("cpu")


def _blocked_training(blockers: list[str]) -> dict[str, object]:
    return {
        "receipt_type": "compact_world_model_training_receipt_v1",
        "status": "blocked",
        "training_performed": False,
        "checkpoint_written": False,
        "blockers": sorted(set(blockers)),
        "next_action": "repair_compact_training",
    }


def _blocked_promotion(blockers: list[str]) -> dict[str, object]:
    return {
        "receipt_type": "compact_world_model_promotion_v1",
        "status": "blocked",
        "promotion_performed": False,
        "blockers": sorted(set(blockers)),
        "next_action": "repair_candidate_or_gate",
    }


def _blocked_prediction(blockers: list[str]) -> dict[str, object]:
    return {
        "receipt_type": "active_compact_world_model_prediction_v1",
        "status": "blocked",
        "model_call_performed": False,
        "blockers": sorted(set(blockers)),
        "next_action": "repair_active_predictor",
    }


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
