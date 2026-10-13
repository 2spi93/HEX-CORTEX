"""Actual CPU forward pass on existing active compact residual-MLP weights.

No DINOv2 download, real camera, model training, GPU, device action or
checkpoint mutation. An all-zero input only checks checkpoint runtime
compatibility and does NOT evaluate predictive accuracy/generalization.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path

from hex_cortex.memory.cortex_active_world_integrity_v31 import (
    audit_active_compact_integrity,
)
from hex_cortex.memory.cortex_compact_world_model import _build_model


def run_active_world_cpu_smoke(
    *,
    project_root: Path, approved_read: bool = False,
    approved_inference: bool = False,
) -> dict[str, object]:
    if not (approved_read and approved_inference):
        return {
            "status": "blocked",
            "reason": "active_world_smoke_requires_read_and_cpu_inference_approval",
            "model_forward_calls": 0, "files_written": False,
        }
    root = Path(project_root).resolve(strict=True)
    integrity = audit_active_compact_integrity(
        project_root=root, approved=True,
    )
    if not integrity["artifact_chain_ok"]:
        return {
            "status": "blocked", "reason": "active_model_artifact_chain_invalid",
            "artifact_integrity_blockers": integrity["blockers"],
            "model_forward_calls": 0, "files_written": False,
        }
    state = root / ".hex-cortex" / "world-model" / "registry"
    active = json.loads((state / "active.json").read_text(encoding="utf-8"))
    candidate = json.loads((state / active["candidate_file"]).read_text(encoding="utf-8"))
    config = candidate.get("config")
    if not isinstance(config, dict) or config.get("architecture") != "residual_mlp_v1":
        raise ValueError("active_smoke_unsupported_architecture")
    latent_dim = config.get("latent_dim")
    action_dim = config.get("action_dim")
    hidden_dim = config.get("hidden_dim")
    if (
        type(latent_dim) is not int or not 2 <= latent_dim <= 2048
        or type(action_dim) is not int or not 1 <= action_dim <= 64
        or type(hidden_dim) is not int or not 4 <= hidden_dim <= 4096
    ):
        raise ValueError("active_smoke_invalid_dimensions")
    try:
        import torch
        from safetensors.torch import load_file
    except ImportError as exc:
        raise ValueError("active_smoke_torch_or_safetensors_unavailable") from exc
    model = _build_model(
        torch, latent_dim=latent_dim,
        action_dim=action_dim, hidden_dim=hidden_dim,
    ).to("cpu")
    started = time.perf_counter()
    model.load_state_dict(
        load_file(str(state / active["weights_file"]), device="cpu"),
        strict=True,
    )
    model.eval()
    model.requires_grad_(False)
    with torch.inference_mode():
        latent = torch.zeros((1, latent_dim), dtype=torch.float32, device="cpu")
        action = torch.zeros((1, action_dim), dtype=torch.float32, device="cpu")
        output = model(latent, action)[0].to("cpu").tolist()
    if len(output) != latent_dim or not all(math.isfinite(v) for v in output):
        raise ValueError("active_smoke_nonfinite_or_invalid_prediction")
    latency_ms = int((time.perf_counter() - started) * 1000)
    output_hash = hashlib.sha256(json.dumps(
        [round(float(v), 9) for v in output], separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return {
        "status": "cpu_forward_completed",
        "candidate_hash": active["candidate_hash"],
        "weights_sha256_verified": integrity["active_weights_sha256_verified"],
        "artifact_chain_ok": True,
        "dataset_split_evidence_ok": integrity["dataset_split_evidence_ok"],
        "dataset_evidence_blockers": [
            b for b in integrity["blockers"]
            if b in {
                "exact_image_overlap_between_splits",
                "exact_transition_pair_overlap_between_splits",
            }
        ],
        "architecture": "existing_residual_mlp_v1",
        "latent_dim": latent_dim,
        "action_dim": action_dim,
        "hidden_dim": hidden_dim,
        "model_forward_calls": 1,
        "input": "synthetic_zero_vector_no_real_encoder",
        "predicted_latent_sha256": output_hash,
        "elapsed_load_plus_forward_ms": latency_ms,
        "gpu_used": False,
        "torch_inference_mode": True,
        "real_world_prediction_tested": False,
        "independent_generalization_proven": False,
        "model_promoted": False, "files_written": False,
        "physical_action_executed": False,
    }
