from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from hex_cortex.memory.cortex_frozen_encoder import EncoderRunner
from hex_cortex.memory.cortex_frozen_encoder import encode_image_to_latent
from hex_cortex.memory.cortex_media_to_latent_pipeline import build_existing_output_receipt
from hex_cortex.memory.cortex_media_to_latent_pipeline import resolve_comfyui_output_asset
from hex_cortex.memory.cortex_latent_lab import evaluate_latent_prediction

_ALLOWED_SPLITS = {"train", "validation", "test"}
_DEFAULT_ACTION_SCHEMA = ["brightness", "contrast", "translate_x", "translate_y"]


def capture_observed_transition(
    *,
    comfy_root: Path,
    current_image_path: Path,
    next_image_path: Path,
    action: list[float],
    encoder_descriptor: dict[str, object],
    split: str = "auto",
    action_schema: list[str] | None = None,
    domain: str = "observed_visual_transition_v1",
    source_receipt_hash: str | None = None,
    next_source_receipt_hash: str | None = None,
    surprise_threshold: float = 0.25,
    allow_model_download: bool = False,
    operator_approved: bool = False,
    encoder_runner: EncoderRunner | None = None,
) -> dict[str, object]:
    schema = list(action_schema or _DEFAULT_ACTION_SCHEMA)
    blockers = _validate_capture_inputs(
        action=action,
        action_schema=schema,
        split=split,
        domain=domain,
    )
    current_source = build_existing_output_receipt(
        comfy_root=comfy_root,
        image_path=current_image_path,
        source_receipt_hash=source_receipt_hash,
    )
    next_source = build_existing_output_receipt(
        comfy_root=comfy_root,
        image_path=next_image_path,
        source_receipt_hash=next_source_receipt_hash,
    )
    blockers.extend(current_source.get("blockers", []))
    blockers.extend(next_source.get("blockers", []))
    if blockers:
        return _blocked_capture(blockers)
    current_asset, current_asset_receipt = resolve_comfyui_output_asset(
        comfy_root=comfy_root,
        asset=current_source["output_manifest"][0],
    )
    next_asset, next_asset_receipt = resolve_comfyui_output_asset(
        comfy_root=comfy_root,
        asset=next_source["output_manifest"][0],
    )
    if current_asset is None or next_asset is None:
        blockers.extend(current_asset_receipt.get("blockers", []))
        blockers.extend(next_asset_receipt.get("blockers", []))
        return _blocked_capture(blockers)
    current_encoder = encode_image_to_latent(
        descriptor=encoder_descriptor,
        image_path=current_asset,
        allow_model_download=allow_model_download,
        operator_approved=operator_approved,
        include_vector=True,
        runner=encoder_runner,
    )
    current_latent = current_encoder.pop("volatile_embedding", None)
    next_encoder = encode_image_to_latent(
        descriptor=encoder_descriptor,
        image_path=next_asset,
        allow_model_download=allow_model_download,
        operator_approved=operator_approved,
        include_vector=True,
        runner=encoder_runner,
    )
    next_latent = next_encoder.pop("volatile_embedding", None)
    if current_encoder.get("encoded") is not True or not isinstance(current_latent, list):
        return _blocked_capture(["current_encoder_failed"], current_encoder, next_encoder)
    if next_encoder.get("encoded") is not True or not isinstance(next_latent, list):
        return _blocked_capture(["next_encoder_failed"], current_encoder, next_encoder)
    if len(current_latent) != len(next_latent):
        return _blocked_capture(["latent_dimension_mismatch"], current_encoder, next_encoder)
    evaluation = evaluate_latent_prediction(
        current_latent,
        next_latent,
        surprise_threshold=surprise_threshold,
    )
    action_values = [float(value) for value in action]
    action_hash = _stable_hash(action_values)
    sample_seed = {
        "domain": domain,
        "current_image_hash": current_asset_receipt["image_hash"],
        "next_image_hash": next_asset_receipt["image_hash"],
        "action_hash": action_hash,
        "encoder_hash": encoder_descriptor.get("descriptor_hash"),
    }
    sample_id = "transition_" + _stable_hash(sample_seed)[:24]
    resolved_split = _resolve_split(sample_id, split)
    record = {
        "record_type": "observed_transition_v1",
        "sample_id": sample_id,
        "split": resolved_split,
        "domain": domain,
        "current_image_ref": current_asset_receipt["relative_path"],
        "next_image_ref": next_asset_receipt["relative_path"],
        "current_image_hash": current_asset_receipt["image_hash"],
        "next_image_hash": next_asset_receipt["image_hash"],
        "current_source_receipt_hash": current_source["receipt_hash"],
        "current_upstream_receipt_hash": source_receipt_hash,
        "next_source_receipt_hash": next_source["receipt_hash"],
        "next_upstream_receipt_hash": next_source_receipt_hash,
        "action_schema": schema,
        "action_values": action_values,
        "action_hash": action_hash,
        "encoder": {
            "adapter_id": encoder_descriptor.get("adapter_id"),
            "backend": encoder_descriptor.get("backend"),
            "model_ref": encoder_descriptor.get("model_ref"),
            "pooling": encoder_descriptor.get("pooling"),
            "descriptor_hash": encoder_descriptor.get("descriptor_hash"),
            "latent_dim": len(current_latent),
        },
        "current_latent_hash": current_encoder.get("embedding_hash"),
        "next_latent_hash": next_encoder.get("embedding_hash"),
        "evaluation": evaluation,
        "network_call_performed": bool(current_encoder.get("network_call_performed"))
        or bool(next_encoder.get("network_call_performed")),
        "model_call_count": 2,
        "training_performed": False,
        "raw_image_persisted": False,
        "latent_vector_persisted": False,
        "action_vector_persisted": True,
        "blockers": [],
    }
    record["record_hash"] = _stable_hash(record)
    record["next_action"] = "append_transition_record"
    return record


def append_transition_jsonl(path: Path, record: dict[str, object]) -> dict[str, object]:
    if record.get("record_type") != "observed_transition_v1" or record.get("blockers"):
        raise ValueError("only valid observed transition records may be appended")
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    sample_id = record.get("sample_id")
    if target.is_file():
        for existing in load_transition_records(target):
            if existing.get("sample_id") == sample_id:
                return {
                    "append_type": "observed_transition_append_v1",
                    "appended": False,
                    "duplicate": True,
                    "sample_id": sample_id,
                    "dataset_path": str(target),
                    "next_action": "retain_existing_transition",
                }
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    return {
        "append_type": "observed_transition_append_v1",
        "appended": True,
        "duplicate": False,
        "sample_id": sample_id,
        "dataset_path": str(target),
        "next_action": "rebuild_transition_manifest",
    }


def load_transition_records(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.resolve().open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid_transition_jsonl_line:{line_number}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"transition_record_not_object:{line_number}")
            records.append(payload)
    return records


def build_transition_dataset_manifest(
    records: list[dict[str, object]],
    *,
    min_train: int = 8,
    min_validation: int = 2,
    min_test: int = 2,
) -> dict[str, object]:
    blockers: list[str] = []
    accepted: list[dict[str, object]] = []
    seen: set[str] = set()
    encoder_hashes: set[object] = set()
    latent_dims: set[object] = set()
    action_schemas: set[str] = set()
    domains: set[object] = set()
    for index, record in enumerate(records):
        record_blockers = _validate_transition_record(record)
        if record_blockers:
            blockers.extend(f"record_{index}:{blocker}" for blocker in record_blockers)
            continue
        sample_id = str(record["sample_id"])
        if sample_id in seen:
            blockers.append(f"duplicate_sample_id:{sample_id}")
            continue
        seen.add(sample_id)
        encoder = record["encoder"]
        encoder_hashes.add(encoder.get("descriptor_hash"))
        latent_dims.add(encoder.get("latent_dim"))
        action_schemas.add(_stable_hash(record["action_schema"]))
        domains.add(record.get("domain"))
        accepted.append(record)
    if len(encoder_hashes) > 1:
        blockers.append("mixed_encoder_descriptors")
    if len(latent_dims) > 1:
        blockers.append("mixed_latent_dimensions")
    if len(action_schemas) > 1:
        blockers.append("mixed_action_schemas")
    if len(domains) > 1:
        blockers.append("mixed_transition_domains")
    split_counts = {
        split: sum(record.get("split") == split for record in accepted)
        for split in ("train", "validation", "test")
    }
    smoke_ready = all(split_counts[split] >= 1 for split in split_counts)
    training_ready = (
        split_counts["train"] >= min_train
        and split_counts["validation"] >= min_validation
        and split_counts["test"] >= min_test
    )
    blockers = sorted(set(blockers))
    manifest_allowed = bool(accepted) and not blockers
    stable_samples = [
        {
            "sample_id": record["sample_id"],
            "split": record["split"],
            "record_hash": record["record_hash"],
        }
        for record in accepted
    ]
    manifest_hash = _stable_hash(stable_samples)
    return {
        "manifest_type": "observed_transition_dataset_v1",
        "manifest_allowed": manifest_allowed,
        "sample_count": len(accepted),
        "split_counts": split_counts,
        "smoke_ready": smoke_ready,
        "training_ready": training_ready,
        "promotion_ready": training_ready and split_counts["test"] >= min_test,
        "thresholds": {
            "min_train": min_train,
            "min_validation": min_validation,
            "min_test": min_test,
        },
        "domain": next(iter(domains), None),
        "encoder_descriptor_hash": next(iter(encoder_hashes), None),
        "latent_dim": next(iter(latent_dims), None),
        "action_schema_hash": next(iter(action_schemas), None),
        "records": accepted,
        "manifest_hash": manifest_hash,
        "raw_image_storage": "external_relative_references_only",
        "latent_storage": "hashes_only_reencode_on_training",
        "blockers": blockers,
        "next_action": (
            "train_compact_predictor"
            if manifest_allowed and training_ready
            else "collect_more_observed_transitions"
        ),
    }


def write_transition_manifest(path: Path, manifest: dict[str, object]) -> None:
    if manifest.get("manifest_allowed") is not True:
        raise ValueError("transition manifest is not allowed")
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _validate_capture_inputs(
    *,
    action: list[float],
    action_schema: list[str],
    split: str,
    domain: str,
) -> list[str]:
    blockers: list[str] = []
    if split != "auto" and split not in _ALLOWED_SPLITS:
        blockers.append("split_invalid")
    if not domain.strip():
        blockers.append("domain_missing")
    if not 1 <= len(action) <= 64:
        blockers.append("action_dimension_out_of_range")
    if len(action) != len(action_schema):
        blockers.append("action_schema_dimension_mismatch")
    if len(set(action_schema)) != len(action_schema):
        blockers.append("action_schema_duplicate_names")
    if not all(isinstance(name, str) and name.strip() for name in action_schema):
        blockers.append("action_schema_invalid")
    for value in action:
        if not isinstance(value, int | float) or not math.isfinite(float(value)):
            blockers.append("action_value_invalid")
            break
        if abs(float(value)) > 1.0:
            blockers.append("action_value_out_of_range")
            break
    return blockers


def _validate_transition_record(record: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    if record.get("record_type") != "observed_transition_v1":
        blockers.append("record_type_invalid")
    if not isinstance(record.get("sample_id"), str) or not record.get("sample_id"):
        blockers.append("sample_id_missing")
    if record.get("split") not in _ALLOWED_SPLITS:
        blockers.append("split_invalid")
    for key in (
        "current_image_hash",
        "next_image_hash",
        "action_hash",
        "current_latent_hash",
        "next_latent_hash",
        "record_hash",
    ):
        if not _is_sha256(record.get(key)):
            blockers.append(f"{key}_invalid")
    if not isinstance(record.get("current_image_ref"), str):
        blockers.append("current_image_ref_invalid")
    if not isinstance(record.get("next_image_ref"), str):
        blockers.append("next_image_ref_invalid")
    if not isinstance(record.get("action_values"), list):
        blockers.append("action_values_invalid")
    if not isinstance(record.get("action_schema"), list):
        blockers.append("action_schema_invalid")
    encoder = record.get("encoder")
    if not isinstance(encoder, dict):
        blockers.append("encoder_invalid")
    elif not isinstance(encoder.get("latent_dim"), int):
        blockers.append("latent_dim_invalid")
    if record.get("latent_vector_persisted") is not False:
        blockers.append("latent_vector_persistence_forbidden")
    if record.get("raw_image_persisted") is not False:
        blockers.append("raw_image_persistence_forbidden")
    return blockers


def _resolve_split(sample_id: str, split: str) -> str:
    if split in _ALLOWED_SPLITS:
        return split
    bucket = int(hashlib.sha256(sample_id.encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 70:
        return "train"
    if bucket < 85:
        return "validation"
    return "test"


def _blocked_capture(
    blockers: list[str],
    current_encoder: dict[str, object] | None = None,
    next_encoder: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "record_type": "observed_transition_v1",
        "status": "blocked",
        "current_encoder": current_encoder,
        "next_encoder": next_encoder,
        "network_call_performed": bool(
            (current_encoder and current_encoder.get("network_call_performed"))
            or (next_encoder and next_encoder.get("network_call_performed"))
        ),
        "training_performed": False,
        "raw_image_persisted": False,
        "latent_vector_persisted": False,
        "blockers": sorted(set(blockers)),
        "next_action": "repair_transition_capture",
    }


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value.lower())
    )


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
