from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from collections.abc import Callable
from pathlib import Path
from time import monotonic

EncoderRunner = Callable[
    [Path, str, str, str, bool],
    tuple[list[float], dict[str, object]],
]

_ALLOWED_POOLING = {"cls", "mean_patch"}
_ALLOWED_DEVICE = {"auto", "cpu", "cuda", "mps"}


def build_frozen_encoder_descriptor(
    *,
    model_ref: str = "facebook/dinov2-base",
    pooling: str = "cls",
    device: str = "auto",
) -> dict[str, object]:
    blockers: list[str] = []
    if not model_ref.strip():
        blockers.append("model_ref_missing")
    if pooling not in _ALLOWED_POOLING:
        blockers.append("pooling_unsupported")
    if device not in _ALLOWED_DEVICE:
        blockers.append("device_unsupported")
    allowed = not blockers
    stable = {
        "model_ref": model_ref,
        "pooling": pooling,
        "device": device,
        "blockers": blockers,
    }
    return {
        "descriptor_type": "frozen_encoder_adapter_v1",
        "adapter_id": "vision.dinov2.frozen",
        "backend": "transformers_dinov2",
        "model_ref": model_ref,
        "pooling": pooling,
        "device": device,
        "frozen": True,
        "training_allowed": False,
        "local_files_only_default": True,
        "raw_image_persistence_allowed": False,
        "raw_embedding_persistence_allowed": False,
        "descriptor_allowed": allowed,
        "blockers": blockers,
        "descriptor_hash": _stable_hash(stable),
        "next_action": "probe_encoder_runtime" if allowed else "repair_encoder_descriptor",
    }


def probe_frozen_encoder_runtime(
    descriptor: dict[str, object],
    *,
    model_cache_present: bool | None = None,
) -> dict[str, object]:
    dependency_facts = {
        "torch_available": importlib.util.find_spec("torch") is not None,
        "transformers_available": importlib.util.find_spec("transformers") is not None,
        "pillow_available": importlib.util.find_spec("PIL") is not None,
    }
    dependencies_ready = all(dependency_facts.values())
    cache_ready = model_cache_present is True
    runtime_ready = (
        descriptor.get("descriptor_allowed") is True
        and dependencies_ready
        and cache_ready
    )
    blockers: list[str] = []
    if descriptor.get("descriptor_allowed") is not True:
        blockers.append("encoder_descriptor_not_allowed")
    blockers.extend(
        f"dependency_missing:{name.removesuffix('_available')}"
        for name, available in dependency_facts.items()
        if not available
    )
    if model_cache_present is False:
        blockers.append("model_cache_missing")
    if model_cache_present is None:
        blockers.append("model_cache_not_checked")
    return {
        "receipt_type": "frozen_encoder_runtime_probe_v1",
        "adapter_id": descriptor.get("adapter_id"),
        "model_ref": descriptor.get("model_ref"),
        "dependency_facts": dependency_facts,
        "model_cache_present": model_cache_present,
        "runtime_ready": runtime_ready,
        "network_call_performed": False,
        "model_loaded": False,
        "blockers": blockers,
        "next_action": "encode_image" if runtime_ready else "install_or_cache_encoder_runtime",
    }


def build_encoder_plan(
    *,
    descriptor: dict[str, object],
    image_path: Path,
    allow_model_download: bool = False,
    operator_approved: bool = False,
    include_vector: bool = False,
) -> dict[str, object]:
    blockers: list[str] = []
    image = image_path.resolve()
    if descriptor.get("descriptor_allowed") is not True:
        blockers.append("encoder_descriptor_not_allowed")
    if not image.is_file():
        blockers.append("image_missing")
    elif image.stat().st_size > 100 * 1024 * 1024:
        blockers.append("image_too_large")
    if allow_model_download and not operator_approved:
        blockers.append("operator_approval_required_for_download")
    stable = {
        "descriptor_hash": descriptor.get("descriptor_hash"),
        "image_hash": _file_hash(image) if image.is_file() else None,
        "allow_model_download": allow_model_download,
        "include_vector": include_vector,
        "blockers": blockers,
    }
    allowed = not blockers
    return {
        "plan_type": "frozen_encoder_plan_v1",
        "plan_allowed": allowed,
        "adapter_id": descriptor.get("adapter_id"),
        "model_ref": descriptor.get("model_ref"),
        "image_path": str(image),
        "image_hash": stable["image_hash"],
        "allow_model_download": allow_model_download,
        "local_files_only": not allow_model_download,
        "include_vector": include_vector,
        "training_performed": False,
        "network_call_performed": False,
        "model_call_performed": False,
        "blockers": blockers,
        "plan_hash": _stable_hash(stable),
        "next_action": "execute_encoder_plan" if allowed else "repair_encoder_plan",
    }


def encode_image_to_latent(
    *,
    descriptor: dict[str, object],
    image_path: Path,
    allow_model_download: bool = False,
    operator_approved: bool = False,
    include_vector: bool = False,
    runner: EncoderRunner | None = None,
) -> dict[str, object]:
    plan = build_encoder_plan(
        descriptor=descriptor,
        image_path=image_path,
        allow_model_download=allow_model_download,
        operator_approved=operator_approved,
        include_vector=include_vector,
    )
    if plan["plan_allowed"] is not True:
        return {
            "receipt_type": "frozen_encoder_receipt_v1",
            "status": "blocked",
            "encoded": False,
            "plan": plan,
            "blockers": list(plan["blockers"]),
            "next_action": "repair_encoder_plan",
        }
    caller = runner or _run_dinov2
    started = monotonic()
    vector: list[float] = []
    runtime_metadata: dict[str, object] = {}
    error_type: str | None = None
    try:
        vector, runtime_metadata = caller(
            Path(plan["image_path"]),
            str(descriptor["model_ref"]),
            str(descriptor["pooling"]),
            str(descriptor["device"]),
            bool(plan["local_files_only"]),
        )
    except Exception as exc:  # noqa: BLE001
        error_type = type(exc).__name__
    if error_type is None and not _valid_vector(vector):
        error_type = "InvalidEmbeddingVector"
    if error_type is not None:
        return {
            "receipt_type": "frozen_encoder_receipt_v1",
            "status": "failed",
            "encoded": False,
            "adapter_id": descriptor.get("adapter_id"),
            "model_ref": descriptor.get("model_ref"),
            "network_call_performed": allow_model_download,
            "model_call_performed": True,
            "training_performed": False,
            "error_type": error_type,
            "blockers": ["encoder_execution_failed"],
            "next_action": "inspect_encoder_runtime",
        }
    normalized = _l2_normalize(vector)
    embedding_hash = _stable_hash([round(value, 10) for value in normalized])
    stable = {
        "descriptor_hash": descriptor.get("descriptor_hash"),
        "image_hash": plan["image_hash"],
        "embedding_hash": embedding_hash,
        "embedding_dim": len(normalized),
        "runtime_metadata": runtime_metadata,
    }
    receipt: dict[str, object] = {
        "receipt_type": "frozen_encoder_receipt_v1",
        "status": "encoded",
        "encoded": True,
        "adapter_id": descriptor.get("adapter_id"),
        "backend": descriptor.get("backend"),
        "model_ref": descriptor.get("model_ref"),
        "pooling": descriptor.get("pooling"),
        "device_requested": descriptor.get("device"),
        "device_resolved": runtime_metadata.get("device"),
        "image_hash": plan["image_hash"],
        "embedding_hash": embedding_hash,
        "embedding_dim": len(normalized),
        "embedding_l2_norm": round(math.sqrt(sum(value * value for value in normalized)), 8),
        "latency_ms": round((monotonic() - started) * 1000, 3),
        "frozen": True,
        "model_eval_mode": runtime_metadata.get("model_eval_mode", True),
        "requires_grad": runtime_metadata.get("requires_grad", False),
        "local_files_only": plan["local_files_only"],
        "network_call_performed": allow_model_download,
        "model_call_performed": True,
        "training_performed": False,
        "raw_image_persisted": False,
        "embedding_vector_persisted": False,
        "runtime_metadata": runtime_metadata,
        "receipt_hash": _stable_hash(stable),
        "blockers": [],
        "next_action": "feed_volatile_latent_to_world_model",
    }
    if include_vector:
        receipt["volatile_embedding"] = normalized
    return receipt


def _run_dinov2(
    image_path: Path,
    model_ref: str,
    pooling: str,
    device: str,
    local_files_only: bool,
) -> tuple[list[float], dict[str, object]]:
    import torch
    from PIL import Image
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
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        inputs = processor(images=rgb, return_tensors="pt")
    inputs = {name: value.to(resolved_device) for name, value in inputs.items()}
    with torch.inference_mode():
        outputs = model(**inputs)
        hidden = outputs.last_hidden_state
        if pooling == "cls":
            embedding = hidden[:, 0, :]
        else:
            embedding = hidden[:, 1:, :].mean(dim=1)
    vector = embedding[0].detach().to("cpu").float().tolist()
    return vector, {
        "device": str(resolved_device),
        "dtype": str(embedding.dtype),
        "model_eval_mode": model.training is False,
        "requires_grad": any(parameter.requires_grad for parameter in model.parameters()),
        "input_shape": list(inputs["pixel_values"].shape),
        "hidden_size": int(model.config.hidden_size),
        "patch_size": model.config.patch_size,
    }


def _resolve_device(torch_module, requested: str):
    if requested != "auto":
        return torch_module.device(requested)
    if torch_module.cuda.is_available():
        return torch_module.device("cuda")
    mps = getattr(torch_module.backends, "mps", None)
    if mps is not None and mps.is_available():
        return torch_module.device("mps")
    return torch_module.device("cpu")


def _valid_vector(vector: object) -> bool:
    return (
        isinstance(vector, list)
        and bool(vector)
        and all(isinstance(value, int | float) and math.isfinite(float(value)) for value in vector)
    )


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(float(value) ** 2 for value in vector))
    if norm <= 0.0:
        raise ValueError("embedding_zero_norm")
    return [float(value) / norm for value in vector]


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
