"""Read-only deep integrity audit of existing compact world-model artifacts.

IMPORTANT: The legacy world-model 'active_predictor_ready' means a
declarative JSON registry exists. This module independently verifies the
file chain, candidate/weights hashes, dataset manifest and split
contamination. It never loads torch, weights or images into inference.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from hex_cortex.memory.cortex_observed_transition_dataset import (
    build_transition_dataset_manifest,
    load_transition_records,
)


def _digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(
        obj, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def _load_json(root: Path, path: Path, blockers: list[str], label: str) -> dict[str, object] | None:
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        blockers.append(f"{label}_file_unavailable")
        return None
    if not 0 < path.stat().st_size <= 3_000_000:
        blockers.append(f"{label}_file_size_invalid")
        return None
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        blockers.append(f"{label}_json_invalid")
        return None
    if not isinstance(result, dict):
        blockers.append(f"{label}_not_object")
        return None
    return result


def _safe_name(value: object) -> str | None:
    if (
        not isinstance(value, str)
        or value in ("", ".", "..")
        or Path(value).name != value
        or value.startswith(".")
        or not value.endswith((".json", ".safetensors"))
    ):
        return None
    return value


def _read_weights(root: Path, path: Path, blockers: list[str], label: str) -> str | None:
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        blockers.append(f"{label}_missing")
        return None
    if not 0 < path.stat().st_size <= 200_000_000:
        blockers.append(f"{label}_size_invalid")
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for part in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(part)
    except OSError:
        blockers.append(f"{label}_unreadable")
        return None
    return digest.hexdigest()


def audit_active_compact_integrity(
    *, project_root: Path, state_root: Path | None = None,
    approved: bool = False,
) -> dict[str, object]:
    if not approved:
        return {
            "status": "blocked",
            "reason": "active_integrity_file_read_requires_approval",
            "files_read": False,
            "model_called": False,
            "files_written": False,
        }
    root = Path(project_root).resolve(strict=True)
    state = (Path(state_root) if state_root else root / ".hex-cortex").resolve()
    if not state.is_relative_to(root):
        raise ValueError("active_integrity_state_outside_project")
    world = state / "world-model"
    dataset_path = world / "transitions.jsonl"
    manifest_path = world / "manifest.json"
    candidate_path = world / "candidate" / "candidate.json"
    active_path = world / "registry" / "active.json"
    blockers: list[str] = []
    warnings: list[str] = []
    manifest = _load_json(root, manifest_path, blockers, "dataset_manifest")
    candidate = _load_json(root, candidate_path, blockers, "trained_candidate")
    active = _load_json(root, active_path, blockers, "active_registry")
    all_rows: list[dict[str, object]] = []
    if dataset_path.is_symlink() or not dataset_path.is_file() or not dataset_path.resolve().is_relative_to(root):
        blockers.append("dataset_missing")
    elif not 0 < dataset_path.stat().st_size <= 8_000_000:
        blockers.append("dataset_size_invalid")
    else:
        try:
            all_rows = load_transition_records(dataset_path)
            if len(all_rows) > 5000:
                raise ValueError("too_many_records")
        except (ValueError, OSError, UnicodeError):
            blockers.append("dataset_records_unreadable")
            all_rows = []

    candidate_weights_verified = False
    active_weights_verified = False
    rebuilt = None
    if all_rows:
        for record in all_rows:
            if record.get("record_hash") != _digest({
                k: v for k, v in record.items()
                if k not in ("record_hash", "next_action")
            }):
                blockers.append("record_content_hash_mismatch")
                break
        rebuilt = build_transition_dataset_manifest(all_rows)
        if rebuilt["blockers"] or not rebuilt["manifest_allowed"]:
            blockers.append("dataset_records_fail_existing_validation")
        if manifest is not None and (
            manifest.get("manifest_hash") != rebuilt["manifest_hash"]
            or manifest.get("split_counts") != rebuilt["split_counts"]
        ):
            blockers.append("manifest_not_bound_to_current_dataset")
        if manifest is not None and (
            manifest.get("manifest_allowed") is not True
            or manifest.get("training_ready") is not True
        ):
            blockers.append("manifest_not_training_ready")

    # Environment/episode labels did not exist in V1. At least reject
    # exact image-hash contamination across train/test and describe
    # unverified environment independence transparently.
    image_splits: dict[str, set[str]] = defaultdict(set)
    pair_splits: dict[str, set[str]] = defaultdict(set)
    domain_values: set[str] = set()
    for row in all_rows:
        split = row.get("split")
        if split not in ("train", "validation", "test"):
            continue
        domain_values.add(str(row.get("domain", "unknown")))
        for key in ("current_image_hash", "next_image_hash"):
            value = row.get(key)
            if isinstance(value, str):
                image_splits[value].add(split)
        first = row.get("current_image_hash")
        second = row.get("next_image_hash")
        if isinstance(first, str) and isinstance(second, str):
            pair_splits[_digest([first, second])].add(split)
    cross_images = sum(len(value) > 1 for value in image_splits.values())
    cross_pairs = sum(len(value) > 1 for value in pair_splits.values())
    if cross_images:
        blockers.append("exact_image_overlap_between_splits")
    if cross_pairs:
        blockers.append("exact_transition_pair_overlap_between_splits")
    warnings.append("environment_and_episode_independence_not_attested_by_v1_dataset")
    if any("controlled" in domain.lower() or "synthetic" in domain.lower()
           for domain in domain_values):
        warnings.append("controlled_visual_transforms_not_real_world_generalization")

    if candidate is not None:
        if candidate.get("candidate_type") != "compact_world_model_candidate_v1":
            blockers.append("trained_candidate_type_invalid")
        if candidate.get("status") != "trained":
            blockers.append("trained_candidate_status_invalid")
        unsealed = {k: v for k, v in candidate.items() if k != "candidate_hash"}
        if candidate.get("candidate_hash") != _digest(unsealed):
            blockers.append("trained_candidate_hash_mismatch")
        if manifest is not None and candidate.get("manifest_hash") != manifest.get("manifest_hash"):
            blockers.append("candidate_dataset_manifest_mismatch")
        if manifest is not None and candidate.get("encoder_descriptor_hash") != manifest.get("encoder_descriptor_hash"):
            blockers.append("candidate_encoder_descriptor_mismatch")
        weight_name = _safe_name(candidate.get("weights_file"))
        if weight_name is None or not weight_name.endswith(".safetensors"):
            blockers.append("trained_weights_filename_invalid")
        else:
            weight_hash = _read_weights(root, candidate_path.parent / weight_name, blockers, "trained_weights")
            if weight_hash is not None and weight_hash != candidate.get("weights_hash"):
                blockers.append("trained_weights_hash_mismatch")
            candidate_weights_verified = weight_hash is not None and weight_hash == candidate.get("weights_hash")

    if active is not None:
        if active.get("registry_type") != "active_compact_world_model_v1":
            blockers.append("active_registry_type_invalid")
        if active.get("registry_hash") != _digest({k: v for k, v in active.items() if k != "registry_hash"}):
            blockers.append("active_registry_integrity_hash_mismatch")
        if candidate is not None and active.get("candidate_hash") != candidate.get("candidate_hash"):
            blockers.append("active_registry_candidate_hash_mismatch")
        name = _safe_name(active.get("candidate_file"))
        active_candidate = (
            _load_json(root, active_path.parent / name, blockers, "active_candidate")
            if name and name.endswith(".json") else None
        )
        if active_candidate is None and name is None:
            blockers.append("active_candidate_filename_invalid")
        if active_candidate is not None and candidate is not None:
            if active_candidate.get("candidate_hash") != candidate.get("candidate_hash"):
                blockers.append("active_candidate_lineage_mismatch")
            if active_candidate.get("promoted") is not True:
                blockers.append("active_candidate_not_promoted")
            if active_candidate.get("weights_hash") != active.get("weights_hash"):
                blockers.append("active_candidate_weights_hash_mismatch")
            if active_candidate.get("promotion_receipt_hash") != _digest({
                "candidate_hash": candidate.get("candidate_hash"),
                "weights_hash": candidate.get("weights_hash"),
            }):
                blockers.append("active_candidate_promotion_receipt_mismatch")
            if active.get("promotion_receipt_hash") != active_candidate.get("promotion_receipt_hash"):
                blockers.append("active_registry_promotion_receipt_mismatch")
            for key, expected in candidate.items():
                if key != "weights_file" and active_candidate.get(key) != expected:
                    blockers.append("active_candidate_source_data_mismatch")
                    break
        if candidate is not None and active.get("weights_hash") != candidate.get("weights_hash"):
            blockers.append("active_weights_candidate_hash_mismatch")
        weights_name = _safe_name(active.get("weights_file"))
        if weights_name is None or not weights_name.endswith(".safetensors"):
            blockers.append("active_weights_filename_invalid")
        else:
            actual = _read_weights(root, active_path.parent / weights_name, blockers, "active_weights")
            if actual is not None and actual != active.get("weights_hash"):
                blockers.append("active_weights_hash_mismatch")
            active_weights_verified = actual is not None and actual == active.get("weights_hash")
        if manifest is not None and active.get("encoder_descriptor_hash") != manifest.get("encoder_descriptor_hash"):
            blockers.append("active_encoder_descriptor_mismatch")
    return {
        "status": "integrity_verified_on_disk" if not blockers else "integrity_blocked",
        "integrity_ok": not blockers,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "transition_record_count": len(all_rows),
        "split_counts": rebuilt.get("split_counts") if rebuilt else None,
        "dataset_domain_values": sorted(domain_values),
        "exact_cross_split_image_overlap_count": cross_images,
        "exact_cross_split_transition_pair_overlap_count": cross_pairs,
        "candidate_weights_sha256_verified": candidate_weights_verified,
        "active_weights_sha256_verified": active_weights_verified,
        "independent_dataset_attested": False,
        "real_world_generalization_certified": False,
        "model_inference_executed": False,
        "gpu_used": False, "files_written": False,
        "automatic_promotion": False,
    }
