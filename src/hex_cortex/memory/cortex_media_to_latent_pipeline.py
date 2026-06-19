from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from hex_cortex.memory.cortex_frozen_encoder import EncoderRunner
from hex_cortex.memory.cortex_frozen_encoder import encode_image_to_latent
from hex_cortex.memory.cortex_latent_lab import evaluate_latent_prediction
from hex_cortex.memory.cortex_latent_lab import predict_latent_transition

_ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
_ALLOWED_SOURCE_RECEIPTS = {"comfyui_execution_v1", "comfyui_existing_output_v1"}


def build_existing_output_receipt(
    *,
    comfy_root: Path,
    image_path: Path,
    source_receipt_hash: str | None = None,
) -> dict[str, object]:
    output_root = (comfy_root.resolve() / "output").resolve()
    image = image_path.resolve()
    blockers: list[str] = []
    if not image.is_file():
        blockers.append("image_missing")
    if not image.is_relative_to(output_root):
        blockers.append("image_outside_comfyui_output")
    relative = image.relative_to(output_root) if not blockers else None
    stable = {
        "relative_path": relative.as_posix() if relative else None,
        "source_receipt_hash": source_receipt_hash,
        "blockers": blockers,
    }
    return {
        "receipt_type": "comfyui_existing_output_v1",
        "status": "observed" if not blockers else "blocked",
        "generation_performed": False,
        "network_call_performed": False,
        "source_receipt_hash": source_receipt_hash,
        "output_manifest": (
            [
                {
                    "asset_kind": "images",
                    "filename": relative.name,
                    "subfolder": "" if relative.parent == Path(".") else relative.parent.as_posix(),
                    "folder_type": "output",
                    "node_id": None,
                }
            ]
            if relative is not None
            else []
        ),
        "receipt_hash": _stable_hash(stable),
        "blockers": blockers,
        "next_action": "encode_existing_output" if not blockers else "repair_existing_output_source",
    }


def resolve_comfyui_output_asset(
    *,
    comfy_root: Path,
    asset: dict[str, object],
    max_asset_bytes: int = 100 * 1024 * 1024,
) -> tuple[Path | None, dict[str, object]]:
    blockers: list[str] = []
    output_root = (comfy_root.resolve() / "output").resolve()
    filename = asset.get("filename")
    subfolder = asset.get("subfolder", "")
    asset_kind = asset.get("asset_kind")
    folder_type = asset.get("folder_type")
    if folder_type != "output":
        blockers.append("asset_folder_type_not_output")
    if asset_kind != "images":
        blockers.append("asset_kind_not_image")
    if not isinstance(filename, str) or not filename.strip():
        blockers.append("asset_filename_missing")
    elif Path(filename).name != filename or Path(filename).is_absolute():
        blockers.append("asset_filename_unsafe")
    if not isinstance(subfolder, str):
        blockers.append("asset_subfolder_invalid")
        subfolder = ""
    subpath = Path(subfolder)
    if subpath.is_absolute() or ".." in subpath.parts:
        blockers.append("asset_subfolder_unsafe")
    candidate = (output_root / subpath / str(filename)).resolve()
    if not candidate.is_relative_to(output_root):
        blockers.append("asset_path_escape")
    if candidate.suffix.lower() not in _ALLOWED_IMAGE_EXTENSIONS:
        blockers.append("asset_extension_unsupported")
    size_bytes: int | None = None
    image_hash: str | None = None
    if not blockers:
        if not candidate.is_file():
            blockers.append("asset_file_missing")
        else:
            size_bytes = candidate.stat().st_size
            if size_bytes <= 0:
                blockers.append("asset_file_empty")
            elif size_bytes > max_asset_bytes:
                blockers.append("asset_file_too_large")
            else:
                image_hash = _file_hash(candidate)
    relative_path = None
    if candidate.is_relative_to(output_root):
        relative_path = candidate.relative_to(output_root).as_posix()
    receipt = {
        "receipt_type": "comfyui_output_asset_resolution_v1",
        "asset_resolved": not blockers,
        "relative_path": relative_path,
        "asset_kind": asset_kind,
        "folder_type": folder_type,
        "extension": candidate.suffix.lower(),
        "size_bytes": size_bytes,
        "image_hash": image_hash,
        "absolute_path_persisted": False,
        "raw_asset_persisted": False,
        "blockers": sorted(set(blockers)),
        "resolution_hash": _stable_hash(
            {
                "relative_path": relative_path,
                "asset_kind": asset_kind,
                "folder_type": folder_type,
                "size_bytes": size_bytes,
                "image_hash": image_hash,
                "blockers": sorted(set(blockers)),
            }
        ),
        "next_action": "encode_resolved_asset" if not blockers else "repair_output_manifest",
    }
    return (candidate if not blockers else None), receipt


def build_baseline_action_weights(
    latent_dim: int,
    action_dim: int,
    *,
    scale: float = 0.01,
) -> list[list[float]]:
    if not 1 <= latent_dim <= 65_536:
        raise ValueError("latent_dim_out_of_range")
    if not 1 <= action_dim <= 4_096:
        raise ValueError("action_dim_out_of_range")
    if not 0.0 <= scale <= 1.0:
        raise ValueError("scale_out_of_range")
    weights: list[list[float]] = []
    for index in range(latent_dim):
        row = [0.0] * action_dim
        sign = 1.0 if (index // action_dim) % 2 == 0 else -1.0
        row[index % action_dim] = scale * sign
        weights.append(row)
    return weights


def run_media_to_latent_pipeline(
    *,
    source_receipt: dict[str, object],
    comfy_root: Path,
    encoder_descriptor: dict[str, object],
    action: list[float] | None = None,
    observed_image_path: Path | None = None,
    surprise_threshold: float = 0.25,
    baseline_scale: float = 0.01,
    allow_model_download: bool = False,
    operator_approved: bool = False,
    encoder_runner: EncoderRunner | None = None,
    output_index: int = 0,
) -> dict[str, object]:
    blockers = _validate_source_receipt(source_receipt)
    manifest = source_receipt.get("output_manifest")
    if not isinstance(manifest, list) or not manifest:
        blockers.append("output_manifest_missing")
    elif not 0 <= output_index < len(manifest):
        blockers.append("output_index_out_of_range")
    if blockers:
        return _blocked_pipeline(blockers, "repair_media_source_receipt")
    raw_asset = manifest[output_index]
    if not isinstance(raw_asset, dict):
        return _blocked_pipeline(["output_manifest_asset_invalid"], "repair_output_manifest")
    image_path, asset_receipt = resolve_comfyui_output_asset(
        comfy_root=comfy_root,
        asset=raw_asset,
    )
    if image_path is None:
        return _blocked_pipeline(list(asset_receipt["blockers"]), "repair_output_manifest")
    action_values = [0.0, 0.0, 0.0, 0.0] if action is None else action
    action_blockers = _validate_action(action_values)
    if action_blockers:
        return _blocked_pipeline(action_blockers, "repair_action_vector")
    encoder_receipt = encode_image_to_latent(
        descriptor=encoder_descriptor,
        image_path=image_path,
        allow_model_download=allow_model_download,
        operator_approved=operator_approved,
        include_vector=True,
        runner=encoder_runner,
    )
    current_latent = encoder_receipt.pop("volatile_embedding", None)
    if encoder_receipt.get("encoded") is not True or not isinstance(current_latent, list):
        return _blocked_pipeline(
            list(encoder_receipt.get("blockers", ["current_image_encoding_failed"])),
            "repair_encoder_runtime",
            encoder_receipt=encoder_receipt,
            asset_receipt=asset_receipt,
        )
    weights = build_baseline_action_weights(
        len(current_latent),
        len(action_values),
        scale=baseline_scale,
    )
    predicted_latent = predict_latent_transition(current_latent, action_values, weights)
    evaluation = None
    observed_receipt = None
    observed_latent_hash = None
    network_call_performed = bool(encoder_receipt.get("network_call_performed"))
    model_call_count = 1
    if observed_image_path is not None:
        observed_receipt = encode_image_to_latent(
            descriptor=encoder_descriptor,
            image_path=observed_image_path,
            allow_model_download=allow_model_download,
            operator_approved=operator_approved,
            include_vector=True,
            runner=encoder_runner,
        )
        observed_latent = observed_receipt.pop("volatile_embedding", None)
        network_call_performed = network_call_performed or bool(
            observed_receipt.get("network_call_performed")
        )
        model_call_count += 1
        if observed_receipt.get("encoded") is not True or not isinstance(observed_latent, list):
            return _blocked_pipeline(
                list(observed_receipt.get("blockers", ["observed_image_encoding_failed"])),
                "repair_observed_encoder_runtime",
                encoder_receipt=encoder_receipt,
                asset_receipt=asset_receipt,
            )
        observed_latent_hash = _stable_hash([round(value, 10) for value in observed_latent])
        evaluation = evaluate_latent_prediction(
            predicted_latent,
            observed_latent,
            surprise_threshold=surprise_threshold,
        )
    source_receipt_hash = source_receipt.get("receipt_hash")
    upstream_source_receipt_hash = _resolve_upstream_source_receipt_hash(source_receipt)
    stable = {
        "source_receipt_hash": source_receipt_hash,
        "upstream_source_receipt_hash": upstream_source_receipt_hash,
        "asset_resolution_hash": asset_receipt["resolution_hash"],
        "encoder_receipt_hash": encoder_receipt.get("receipt_hash"),
        "action_hash": _stable_hash(action_values),
        "predicted_latent_hash": _stable_hash([round(value, 10) for value in predicted_latent]),
        "observed_latent_hash": observed_latent_hash,
        "evaluation_hash": evaluation.get("evaluation_hash") if evaluation else None,
        "predictor_kind": "deterministic_action_residual_baseline_v1",
    }
    return {
        "receipt_type": "media_to_latent_pipeline_v1",
        "status": "completed",
        "pipeline_completed": True,
        "source_receipt_type": source_receipt.get("receipt_type"),
        "source_receipt_hash": source_receipt_hash,
        "upstream_source_receipt_hash": upstream_source_receipt_hash,
        "asset": asset_receipt,
        "encoder": encoder_receipt,
        "latent_dim": len(current_latent),
        "latent_state_hash": encoder_receipt.get("embedding_hash"),
        "action_dim": len(action_values),
        "action_hash": stable["action_hash"],
        "predictor_kind": stable["predictor_kind"],
        "predictor_trained": False,
        "baseline_scale": baseline_scale,
        "predicted_latent_hash": stable["predicted_latent_hash"],
        "observed_encoder": observed_receipt,
        "observed_latent_hash": observed_latent_hash,
        "evaluation": evaluation,
        "surprise_evaluated": evaluation is not None,
        "network_call_performed": network_call_performed,
        "model_call_performed": True,
        "model_call_count": model_call_count,
        "training_performed": False,
        "raw_image_persisted": False,
        "embedding_vector_persisted": False,
        "latent_vector_persisted": False,
        "receipt_hash": _stable_hash(stable),
        "blockers": [],
        "next_action": (
            "record_surprise_and_prepare_observed_transition"
            if evaluation is not None and evaluation.get("surprising") is True
            else "prepare_observed_transition_dataset"
        ),
    }


def _resolve_upstream_source_receipt_hash(source_receipt: dict[str, object]) -> object:
    upstream = source_receipt.get("source_receipt_hash")
    return upstream if upstream is not None else source_receipt.get("receipt_hash")


def _validate_source_receipt(source_receipt: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    receipt_type = source_receipt.get("receipt_type")
    if receipt_type not in _ALLOWED_SOURCE_RECEIPTS:
        blockers.append("source_receipt_type_unsupported")
    if receipt_type == "comfyui_execution_v1":
        if source_receipt.get("status") != "completed":
            blockers.append("comfyui_execution_not_completed")
        if source_receipt.get("generation_performed") is not True:
            blockers.append("generation_not_performed")
    if receipt_type == "comfyui_existing_output_v1":
        if source_receipt.get("status") != "observed":
            blockers.append("existing_output_not_observed")
    return blockers


def _validate_action(action: list[float]) -> list[str]:
    blockers: list[str] = []
    if not 1 <= len(action) <= 64:
        blockers.append("action_dimension_out_of_range")
    for value in action:
        if not isinstance(value, int | float) or not math.isfinite(float(value)):
            blockers.append("action_value_invalid")
            break
        if abs(float(value)) > 1.0:
            blockers.append("action_value_out_of_range")
            break
    return blockers


def _blocked_pipeline(
    blockers: list[str],
    next_action: str,
    *,
    encoder_receipt: dict[str, object] | None = None,
    asset_receipt: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "receipt_type": "media_to_latent_pipeline_v1",
        "status": "blocked",
        "pipeline_completed": False,
        "asset": asset_receipt,
        "encoder": encoder_receipt,
        "network_call_performed": bool(
            encoder_receipt and encoder_receipt.get("network_call_performed")
        ),
        "model_call_performed": bool(
            encoder_receipt and encoder_receipt.get("model_call_performed")
        ),
        "training_performed": False,
        "raw_image_persisted": False,
        "embedding_vector_persisted": False,
        "latent_vector_persisted": False,
        "blockers": sorted(set(blockers)),
        "next_action": next_action,
    }


def append_receipt_jsonl(path: Path, receipt: dict[str, object]) -> None:
    if receipt.get("pipeline_completed") is not True:
        raise ValueError("only completed pipeline receipts may be persisted")
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")


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
