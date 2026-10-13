"""Read-only CPU safetensors adapter to EXISTING residual-MLP world predictor.

Training remains exclusively in cortex_compact_world_model. This adapter
does not download weights, activate candidates, write files, or use a GPU.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hex_cortex.memory.cortex_compact_world_model import _build_model
from hex_cortex.memory.cortex_external_latent_evaluation_v30 import (
    evaluate_external_latent_predictions,
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluate_local_compact_on_external(
    audit: dict[str, object],
    *,
    candidate_manifest_path: Path,
    approved: bool = False,
) -> dict[str, object]:
    if not approved:
        return {
            "status": "blocked", "reason": "compact_external_inference_approval_required",
            "model_calls": 0, "files_written": False,
        }
    if audit.get("audit_allowed") is not True:
        raise ValueError("compact_external_audit_must_pass")
    if (
        candidate_manifest_path.is_symlink()
        or not candidate_manifest_path.is_file()
        or candidate_manifest_path.stat().st_size > 100_000
    ):
        raise ValueError("compact_external_candidate_file_invalid")
    try:
        candidate = json.loads(candidate_manifest_path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("compact_external_candidate_json_invalid") from exc
    if not isinstance(candidate, dict) or candidate.get("candidate_type") != "compact_world_model_candidate_v1":
        raise ValueError("compact_external_candidate_type_invalid")
    if candidate.get("status") != "trained":
        raise ValueError("compact_external_candidate_not_trained")
    expected_hash = candidate.get("candidate_hash")
    raw_candidate = {k: v for k, v in candidate.items() if k != "candidate_hash"}
    actual_hash = hashlib.sha256(
        json.dumps(raw_candidate, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if expected_hash != actual_hash:
        raise ValueError("compact_external_candidate_manifest_hash_mismatch")
    config = candidate.get("config")
    if not isinstance(config, dict) or config.get("architecture") != "residual_mlp_v1":
        raise ValueError("compact_external_incompatible_architecture")
    if (
        config.get("latent_dim") != audit.get("latent_dim")
        or config.get("action_dim") != audit.get("action_dim")
        or candidate.get("encoder_descriptor_hash") != audit.get("encoder_descriptor_hash")
    ):
        raise ValueError("compact_external_encoder_or_dimension_mismatch")
    hidden_dim = config.get("hidden_dim")
    if type(hidden_dim) is not int or not 4 <= hidden_dim <= 4096:
        raise ValueError("compact_external_invalid_hidden_dim")
    name = candidate.get("weights_file")
    if (
        not isinstance(name, str) or Path(name).name != name
        or not name.endswith(".safetensors")
    ):
        raise ValueError("compact_external_invalid_weights_filename")
    weights = candidate_manifest_path.parent / name
    if weights.is_symlink() or not weights.is_file() or weights.stat().st_size > 200_000_000:
        raise ValueError("compact_external_weights_missing_or_too_large")
    if _file_sha256(weights) != candidate.get("weights_hash"):
        raise ValueError("compact_external_weights_hash_mismatch")
    try:
        import torch
        from safetensors.torch import load_file
    except ImportError as exc:
        raise ValueError("compact_external_torch_or_safetensors_missing") from exc
    model = _build_model(
        torch, latent_dim=int(config["latent_dim"]),
        action_dim=int(config["action_dim"]), hidden_dim=hidden_dim,
    ).to("cpu")
    model.load_state_dict(load_file(str(weights), device="cpu"), strict=True)
    model.eval()
    model.requires_grad_(False)
    count = 0

    def predict(state: list[float], action: list[float]) -> list[float]:
        nonlocal count
        with torch.inference_mode():
            s = torch.tensor([state], dtype=torch.float32, device="cpu")
            a = torch.tensor([action], dtype=torch.float32, device="cpu")
            vector = model(s, a)[0].detach().tolist()
        count += 1
        return vector

    result = evaluate_external_latent_predictions(
        audit, predictor=predict,
        predictor_kind="existing_compact_residual_mlp_safetensors_cpu",
        candidate_weights_verified=True,
    )
    result.update({
        "actual_cpu_model_forward_calls": count,
        "candidate_hash": expected_hash,
        "candidate_weights_hash": candidate["weights_hash"],
        "encoder_descriptor_hash": candidate["encoder_descriptor_hash"],
        "candidate_training_manifest_hash": candidate.get("manifest_hash"),
        "training_test_independence_independently_attested": False,
        "gpu_requested": False, "torch_inference_mode": True,
        "checkpoint_modified": False,
    })
    return result
