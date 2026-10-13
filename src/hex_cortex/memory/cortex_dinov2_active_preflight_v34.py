"""V34: verify the active compact world's exact DINOv2 CPU encoder contract.

No image/weights are downloaded, no GPU is touched and nothing is written.
Optional cache inspection reads local Hugging Face metadata. An additional
operator approval is required to LOAD actual cached weights on CPU.
A cache hint alone is not evidence that the model loads or predicts well.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from hex_cortex.memory.cortex_active_world_integrity_v31 import (
    audit_active_compact_integrity,
)
from hex_cortex.memory.cortex_frozen_encoder import (
    build_frozen_encoder_descriptor,
)

CacheProbe = Callable[[str], dict[str, bool]]
CpuLoader = Callable[[str], dict[str, object]]


def _cached_files(model_ref: str) -> dict[str, bool]:
    """Purely local hub cache lookups; no Hub API or model load."""
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return {
            "config": False, "preprocessor": False,
            "weights_file_hint": False,
        }
    def present(name: str) -> bool:
        try:
            located = try_to_load_from_cache(model_ref, name)
        except (ValueError, OSError):
            return False
        return isinstance(located, str) and Path(located).is_file()
    return {
        "config": present("config.json"),
        "preprocessor": present("preprocessor_config.json"),
        "weights_file_hint": any(present(name) for name in (
            "model.safetensors", "pytorch_model.bin",
            "model.safetensors.index.json", "pytorch_model.bin.index.json",
        )),
    }


def _load_cached_cpu(model_ref: str) -> dict[str, object]:
    try:
        from transformers import AutoImageProcessor, AutoModel
    except ImportError as exc:
        raise ValueError("active_encoder_optional_dependencies_unavailable") from exc
    # local_files_only and trust_remote_code=False prevent automatic fetch
    # and execution of remote, repository-defined Python model code.
    AutoImageProcessor.from_pretrained(
        model_ref, local_files_only=True, trust_remote_code=False,
    )
    model = AutoModel.from_pretrained(
        model_ref, local_files_only=True, trust_remote_code=False,
    )
    model = model.to("cpu")
    model.eval()
    model.requires_grad_(False)
    hidden_size = getattr(model.config, "hidden_size", None)
    if type(hidden_size) is not int:
        raise ValueError("active_encoder_model_hidden_size_invalid")
    if any(param.device.type != "cpu" for param in model.parameters()):
        raise ValueError("active_encoder_model_loaded_on_non_cpu_device")
    return {
        "hidden_size": hidden_size,
        "device": "cpu",
        "model_eval_mode": True,
        "requires_grad": False,
    }


def inspect_active_dinov2(
    *,
    project_root: Path,
    approved_read: bool = False,
    approved_cache_probe: bool = False,
    approved_load: bool = False,
    model_ref: str = "facebook/dinov2-base",
    pooling: str = "cls",
    cache_probe: CacheProbe | None = None,
    cpu_loader: CpuLoader | None = None,
) -> dict[str, object]:
    if not approved_read:
        return {
            "status": "blocked", "reason": "active_encoder_read_approval_required",
            "cache_probed": False, "encoder_loaded": False,
            "files_written": False,
        }
    if approved_load and not approved_cache_probe:
        return {
            "status": "blocked",
            "reason": "active_encoder_load_requires_separate_cache_permission",
            "cache_probed": False, "encoder_loaded": False,
            "files_written": False,
        }
    project = Path(project_root).resolve(strict=True)
    integrity = audit_active_compact_integrity(
        project_root=project, approved=True,
    )
    if not integrity["artifact_chain_ok"]:
        return {
            "status": "blocked", "reason": "active_encoder_checkpoint_chain_invalid",
            "artifact_blockers": integrity["blockers"],
            "cache_probed": False, "encoder_loaded": False,
            "files_written": False,
        }
    registry_path = project / ".hex-cortex" / "world-model" / "registry" / "active.json"
    active = json.loads(registry_path.read_text(encoding="utf-8"))
    candidate = json.loads((
        registry_path.parent / active["candidate_file"]
    ).read_text(encoding="utf-8"))
    descriptor = build_frozen_encoder_descriptor(
        model_ref=model_ref, pooling=pooling, device="cpu",
    )
    if descriptor.get("device") != "cpu" or descriptor.get("descriptor_allowed") is not True:
        raise ValueError("active_encoder_cpu_descriptor_required")
    expected = active["encoder_descriptor_hash"]
    matches = descriptor["descriptor_hash"] == expected
    report: dict[str, object] = {
        "status": "active_encoder_descriptor_matches" if matches
        else "active_encoder_descriptor_mismatch",
        "descriptor_matches_active_checkpoint": matches,
        "expected_descriptor_hash": expected,
        "computed_descriptor_hash": descriptor["descriptor_hash"],
        "requested_device": "cpu",
        "model_ref": model_ref,
        "pooling": pooling,
        "checkpoint_latent_dim": candidate["config"]["latent_dim"],
        "active_artifact_chain_verified": True,
        "legacy_split_evidence_ok": integrity["dataset_split_evidence_ok"],
        "cache_probed": False, "encoder_loaded": False,
        "model_inference_performed": False,
        "cache_not_model_load_attestation": True,
        "network_requested": False, "gpu_used": False,
        "model_promoted": False, "files_written": False,
    }
    if not matches or not approved_cache_probe:
        return report
    facts = (cache_probe or _cached_files)(model_ref)
    if not isinstance(facts, dict) or any(type(facts.get(key)) is not bool for key in (
        "config", "preprocessor", "weights_file_hint",
    )):
        raise ValueError("active_encoder_invalid_local_cache_probe")
    report["cache_probed"] = True
    report["local_cache_facts"] = facts
    if not all(facts.values()):
        report["status"] = "active_encoder_cached_artifacts_missing"
        return report
    report["status"] = "active_encoder_cached_files_detected_not_loaded"
    if not approved_load:
        return report
    try:
        loaded = (cpu_loader or _load_cached_cpu)(model_ref)
    except (OSError, RuntimeError, ValueError) as exc:
        report["status"] = "active_encoder_load_failed"
        report["error_type"] = type(exc).__name__
        return report
    if (
        not isinstance(loaded, dict)
        or loaded.get("device") != "cpu"
        or loaded.get("hidden_size") != report["checkpoint_latent_dim"]
        or loaded.get("model_eval_mode") is not True
        or loaded.get("requires_grad") is not False
    ):
        report["status"] = "active_encoder_cpu_or_dimension_mismatch"
        return report
    report["status"] = "active_encoder_cached_weights_loaded_cpu"
    report["encoder_loaded"] = True
    report["loaded_hidden_size"] = loaded["hidden_size"]
    return report
