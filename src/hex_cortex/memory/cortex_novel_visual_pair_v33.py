"""V33: read-only, novel-image paired evaluation of the ACTIVE world model.

All existing 108 training/validation/test image hashes are excluded.
True novel-image identity is checked against stored SHA256 values; this
does NOT prove an independent source scene or general world dynamics.
Actual DINOv2 and compact MLP run ONLY with separate explicit approvals.
Model training, files, network, GPU, promotion and actuators untouched.
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
from hex_cortex.memory.cortex_frozen_encoder import (
    EncoderRunner, build_frozen_encoder_descriptor, encode_image_to_latent,
)
from hex_cortex.memory.cortex_observed_transition_dataset import (
    load_transition_records,
)
from hex_cortex.memory.cortex_world_model_eval import evaluate_world_model_candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def _in_scope_image(root: Path, relative: str) -> Path:
    if (
        not isinstance(relative, str) or not relative
        or Path(relative).is_absolute() or ".." in Path(relative).parts
    ):
        raise ValueError("novel_pair_image_path_invalid")
    source = root / relative
    if (
        source.is_symlink() or not source.is_file()
        or not source.resolve().is_relative_to(root)
        or source.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp")
        or not 0 < source.stat().st_size <= 20_000_000
    ):
        raise ValueError("novel_pair_image_file_unavailable_or_out_of_scope")
    return source.resolve()


def evaluate_new_visual_pair(
    *, project_root: Path, image_root: Path,
    current_image: str, next_image: str,
    action: list[float], action_schema: list[str],
    approved_read: bool = False, approved_encoding: bool = False,
    approved_inference: bool = False,
    model_ref: str = "facebook/dinov2-base",
    pooling: str = "cls",
    encoder_runner: EncoderRunner | None = None,
) -> dict[str, object]:
    if not approved_read:
        return {
            "status": "blocked", "reason": "novel_pair_read_approval_required",
            "model_forward_calls": 0, "files_written": False,
        }
    project = Path(project_root).resolve(strict=True)
    images = Path(image_root).resolve(strict=True)
    current = _in_scope_image(images, current_image)
    target = _in_scope_image(images, next_image)
    if current == target:
        raise ValueError("novel_pair_same_image_file_denied")
    if (
        not isinstance(action, list) or not 1 <= len(action) <= 64
        or any(type(value) not in (float, int) or not math.isfinite(value)
               or abs(value) > 1 for value in action)
    ):
        raise ValueError("novel_pair_invalid_bounded_action")
    if (
        not isinstance(action_schema, list) or len(action_schema) != len(action)
        or any(not isinstance(item, str) or not item.strip() for item in action_schema)
    ):
        raise ValueError("novel_pair_invalid_action_schema")
    audit = audit_active_compact_integrity(project_root=project, approved=True)
    if not audit["artifact_chain_ok"]:
        return {
            "status": "blocked", "reason": "novel_pair_existing_checkpoint_chain_invalid",
            "artifact_blockers": audit["blockers"],
            "model_forward_calls": 0, "files_written": False,
        }
    world = project / ".hex-cortex" / "world-model"
    rows = load_transition_records(world / "transitions.jsonl")
    seen: set[str] = set()
    for row in rows:
        seen.add(str(row["current_image_hash"]))
        seen.add(str(row["next_image_hash"]))
    current_hash = _sha256(current)
    next_hash = _sha256(target)
    if current_hash == next_hash:
        raise ValueError("novel_pair_identical_image_content")
    if current_hash in seen or next_hash in seen:
        return {
            "status": "blocked", "reason": "novel_pair_image_seen_in_active_dataset",
            "current_seen": current_hash in seen,
            "next_seen": next_hash in seen,
            "model_forward_calls": 0,
            "files_written": False,
        }
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    active = json.loads((world / "registry" / "active.json").read_text(encoding="utf-8"))
    promoted = json.loads((world / "registry" / active["candidate_file"]).read_text(encoding="utf-8"))
    config = promoted.get("config")
    if not isinstance(config, dict) or config.get("architecture") != "residual_mlp_v1":
        raise ValueError("novel_pair_unsupported_model_architecture")
    if len(action) != config.get("action_dim"):
        raise ValueError("novel_pair_action_dim_does_not_match_checkpoint")
    old_schema = rows[0].get("action_schema")
    if action_schema != old_schema:
        raise ValueError("novel_pair_action_semantics_mismatch")
    descriptor = build_frozen_encoder_descriptor(
        model_ref=model_ref, pooling=pooling, device="cpu",
    )
    if descriptor.get("device") != "cpu":
        raise ValueError("novel_pair_encoder_device_must_be_cpu")
    if descriptor["descriptor_hash"] != active.get("encoder_descriptor_hash"):
        raise ValueError("novel_pair_encoder_identity_mismatch")
    preflight = {
        "status": "novel_pair_preflight_only",
        "current_image_sha256": current_hash,
        "next_image_sha256": next_hash,
        "novel_exact_image_hashes": True,
        "compared_against_existing_image_hashes": len(seen),
        "legacy_dataset_split_evidence_ok": audit["dataset_split_evidence_ok"],
        "current_checkpoint_chain_verified": True,
        "action_schema_matched": True,
        "encoder_descriptor_hash": descriptor["descriptor_hash"],
        "active_training_manifest_hash": manifest["manifest_hash"],
        "legacy_dataset_domain": manifest.get("domain"),
        "model_forward_calls": 0,
        "encoder_calls": 0,
        "test_episode_and_scene_independence_attested": False,
        "real_world_calibration_proven": False,
        "model_activated": False,
        "files_written": False,
        "gpu_used": False,
    }
    if not (approved_encoding and approved_inference):
        return preflight
    start = time.monotonic()
    receipts = []
    latents: list[list[float]] = []
    for image in (current, target):
        receipt = encode_image_to_latent(
            descriptor=descriptor, image_path=image,
            allow_model_download=False, operator_approved=True,
            include_vector=True, runner=encoder_runner,
        )
        volatile = receipt.pop("volatile_embedding", None)
        if not receipt.get("encoded") or not isinstance(volatile, list):
            return {
                **preflight, "status": "blocked",
                "reason": "novel_pair_encoder_not_operational_or_not_cached",
                "encoder_error_type": receipt.get("error_type"),
            }
        if receipt.get("device_resolved") not in ("cpu", None):
            raise ValueError("novel_pair_encoder_not_cpu")
        latents.append(volatile)
        receipts.append(receipt)
    expected_dim = config.get("latent_dim")
    if any(len(v) != expected_dim for v in latents):
        raise ValueError("novel_pair_encoded_latent_dimension_mismatch")
    try:
        import torch
        from safetensors.torch import load_file
    except ImportError as exc:
        raise ValueError("novel_pair_torch_or_safetensors_unavailable") from exc
    model = _build_model(torch, latent_dim=expected_dim,
                         action_dim=len(action), hidden_dim=config["hidden_dim"])
    model.load_state_dict(load_file(
        str(world / "registry" / active["weights_file"]), device="cpu"
    ), strict=True)
    model.to("cpu")
    model.eval()
    model.requires_grad_(False)
    with torch.inference_mode():
        predicted = model(
            torch.tensor([latents[0]], dtype=torch.float32, device="cpu"),
            torch.tensor([action], dtype=torch.float32, device="cpu"),
        )[0].to("cpu").tolist()
    baseline_mse = sum((a-b)**2 for a,b in zip(latents[0],latents[1],strict=True))/len(predicted)
    candidate_mse = sum((a-b)**2 for a,b in zip(predicted,latents[1],strict=True))/len(predicted)
    if not math.isfinite(candidate_mse) or not math.isfinite(baseline_mse):
        raise ValueError("novel_pair_nonfinite_prediction_loss")
    descriptive = evaluate_world_model_candidate(
        baseline={"prediction_error": baseline_mse},
        candidate={"prediction_error": candidate_mse},
        required_metrics=["prediction_error"],
        minimum_improvement_fraction=0.01,
        max_regression_fraction=0.,
    )
    return {
        **preflight,
        "status": "single_novel_pair_cpu_comparison_recorded",
        "encoder_calls": 2,
        "model_forward_calls": 1,
        "latent_dim": expected_dim,
        "identity_baseline_mse": round(baseline_mse, 10),
        "active_candidate_mse": round(candidate_mse, 10),
        "candidate_better_on_this_pair": candidate_mse < baseline_mse,
        "existing_evaluator_says_promotion_allowed_on_one_pair": descriptive["promotion_allowed"],
        "promotion_allowed_by_novel_pair_study": False,
        "reported_model_metric_scope": "single_pair_only_no_statistical_generalization",
        "current_embedding_sha256": receipts[0]["embedding_hash"],
        "target_embedding_sha256": receipts[1]["embedding_hash"],
        "predicted_embedding_sha256": hashlib.sha256(json.dumps(
            [round(float(v), 10) for v in predicted], separators=(",", ":")
        ).encode()).hexdigest(),
        "latency_seconds_including_encoder": round(time.monotonic()-start, 4),
        "model_activated": False, "gpu_used": False, "files_written": False,
        "physical_action_executed": False,
    }
