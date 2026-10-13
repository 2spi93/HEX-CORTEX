"""V39: audit actual V38 exploratory receipts without pretending to verify scene truth.

Reads operator-created receipts, original images and the fixed human-selected box
manifest. Does NOT infer model authenticity, source rights, masks, correctness,
canonical events or independent generalization. No files are written.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

_SHA = re.compile(r"[0-9a-f]{64}")
_RUN_NAME = re.compile(r"run-\d{8}T\d{6}-\d{6}Z")
_BOXES_SCHEMA = "hex.v38.operator_uploaded_box_exploration.v1"
_SUMMARY_SCHEMA = "hex.v38.operator_uploaded_exploration_summary.v1"
_EXPECTED_PROVIDER = "mobile_sam_vit_t_cpu"
_BASE = Path("receipts/v38_uploaded_exploration")


def _read_json(path: Path, max_bytes: int) -> tuple[dict, str]:
    if not path.is_file() or not 0 < path.stat().st_size <= max_bytes:
        raise ValueError("v39_receipt_file_denied")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8-sig"), parse_constant=_deny_float,
                           object_pairs_hook=_unique_keys)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("v39_invalid_json") from exc
    if not isinstance(value, dict):
        raise ValueError("v39_json_must_be_object")
    return value, hashlib.sha256(raw).hexdigest()


def _deny_float(_value: str) -> None:
    raise ValueError("v39_json_nonfinite_denied")


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, val in pairs:
        if key in result:
            raise ValueError("v39_json_duplicate_keys_denied")
        result[key] = val
    return result


def _checked_relative(root: Path, raw: str, *, ext: str, max_bytes: int) -> Path:
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise ValueError("v39_path_denied")
    part = Path(raw.replace("\\", "/"))
    if part.is_absolute() or ".." in part.parts or part == Path("."):
        raise ValueError("v39_path_denied")
    dest = root / part
    if not dest.resolve().is_relative_to(root):
        raise ValueError("v39_path_denied")
    cursor = dest
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError("v39_symlink_denied")
        cursor = cursor.parent
    if (not dest.is_file() or dest.suffix.lower() != ext
            or not 0 < dest.stat().st_size <= max_bytes):
        raise ValueError("v39_file_denied")
    return dest


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as inp:
        for block in iter(lambda: inp.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_folder(root: Path, selection: str) -> Path:
    base = root / _BASE
    if selection == "latest":
        if not base.is_dir() or base.is_symlink():
            raise ValueError("v39_no_operator_runs")
        found = sorted(
            (p for p in base.iterdir() if p.is_dir() and not p.is_symlink()
             and _RUN_NAME.fullmatch(p.name)),
            key=lambda p: p.name, reverse=True,
        )
        if not found:
            raise ValueError("v39_no_operator_runs")
        return found[0]
    part = Path(selection.replace("\\", "/"))
    if part.is_absolute() or part.parent != _BASE or not _RUN_NAME.fullmatch(part.name):
        raise ValueError("v39_run_directory_denied")
    chosen = root / part
    if chosen.is_symlink() or not chosen.is_dir() or not chosen.resolve().is_relative_to(root):
        raise ValueError("v39_run_directory_denied")
    return chosen


def audit_uploaded_v38_receipts_v39(
    *, project_root: Path, run_selection: str = "latest",
    manifest_path: str = "research/v38_uploaded/boxes.json",
    approved_read: bool = False,
) -> dict:
    """Audit completion, exact files, hashes, boxes and receipt consistency.

    Operates on original 9 *photographic* scenes only, not the four mixed
    illustrations in the opt-in OOD set. Fails closed on any mismatch.
    """
    if not approved_read:
        return {
            "status": "blocked", "reason": "v39_explicit_read_approval_required",
            "files_read": False, "files_written": False, "model_called": False,
        }
    root = Path(project_root).resolve(strict=True)
    folder = _run_folder(root, run_selection)
    manifest_file = _checked_relative(root, manifest_path, ext=".json", max_bytes=100_000)
    manifest, manifest_hash = _read_json(manifest_file, 100_000)
    if manifest.get("schema") != _BOXES_SCHEMA:
        raise ValueError("v39_manifest_schema_mismatch")
    model_sha = manifest.get("checkpoint_sha256")
    if not isinstance(model_sha, str) or not _SHA.fullmatch(model_sha):
        raise ValueError("v39_checkpoint_sha_invalid")
    items = manifest.get("samples")
    if not isinstance(items, list) or len(items) != 13:
        raise ValueError("v39_manifest_sample_count_invalid")
    samples = {s.get("scene_id"): s for s in items
               if isinstance(s, dict) and s.get("type") == "photographic"}
    if len(samples) != 9:
        raise ValueError("v39_expected_nine_photographs")
    summary_path = folder / "summary.json"
    summary, summary_hash = _read_json(summary_path, 2_000_000)
    if (summary.get("schema") != _SUMMARY_SCHEMA
            or summary.get("status") != "completed"
            or summary.get("real_cpu_model_executed") is not True
            or summary.get("gpu_used") is not False
            or summary.get("ground_truth_annotation_present") is not False
            or summary.get("mean_reference_iou") is not None
            or summary.get("world_model_generalization_attested") is not False):
        raise ValueError("v39_unexpected_summary_claim")
    rows = summary.get("sample_results")
    if not isinstance(rows, list) or len(rows) != 9:
        raise ValueError("v39_summary_scene_count_invalid")
    if set(folder.glob("scene*.json")) != {folder / f"{scene_id}.json" for scene_id in samples}:
        raise ValueError("v39_missing_or_extra_receipts")
    checked_scenes: set[str] = set()
    candidates: list[dict] = []
    timings: list[float] = []
    receipt_hashes = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("v39_summary_row_invalid")
        scene_id = row.get("scene_id")
        if scene_id not in samples or scene_id in checked_scenes:
            raise ValueError("v39_duplicate_or_unknown_scene")
        checked_scenes.add(scene_id)
        source = samples[scene_id]
        if row.get("input_kind") != "photographic" or row.get("reference_iou") is not None:
            raise ValueError("v39_row_claim_invalid")
        expected_path = (_BASE / folder.name / f"{scene_id}.json").as_posix()
        declared_path = row.get("receipt_path")
        if not isinstance(declared_path, str) or declared_path.replace("\\", "/") != expected_path:
            raise ValueError("v39_receipt_path_mismatch")
        receipt, receipt_sha = _read_json(folder / f"{scene_id}.json", 2_000_000)
        receipt_hashes[scene_id] = receipt_sha
        source_path = _checked_relative(
            root, source.get("relative_image"), ext=".jpg", max_bytes=16_000_000,
        )
        source_hash = _sha256_file(source_path)
        if (source_hash != source.get("sha256")
                or source_hash != receipt.get("source_sha256")):
            raise ValueError("v39_photo_hash_mismatch")
        if (
            receipt.get("status") != "segmented_cpu_masks_ready"
            or receipt.get("provider") != _EXPECTED_PROVIDER
            or receipt.get("model_called") is not True
            or receipt.get("gpu_used") is not False
            or receipt.get("files_written") is not False
            or receipt.get("original_image_modified") is not False
            or receipt.get("checkpoint_sha256") != model_sha
            or receipt.get("image_size") != [source.get("width"), source.get("height")]
        ):
            raise ValueError("v39_cpu_receipt_contract_invalid")
        boxes = source.get("boxes")
        objects = receipt.get("objects")
        if not isinstance(boxes, list) or not isinstance(objects, list):
            raise ValueError("v39_objects_invalid")
        expected = {o.get("object_id"): o for o in boxes if isinstance(o, dict)}
        returned = {o.get("object_id"): o for o in objects if isinstance(o, dict)}
        if (len(expected) != len(boxes) or len(returned) != len(objects)
                or not expected or set(expected) != set(returned)
                or row.get("boxes_count") != len(boxes)):
            raise ValueError("v39_object_ids_mismatch")
        pixels_by_name = row.get("per_object_pixels")
        if not isinstance(pixels_by_name, dict) or set(pixels_by_name) != set(expected):
            raise ValueError("v39_pixels_summary_mismatch")
        t = receipt.get("inference_ms")
        if (type(t) not in (float, int) or not math.isfinite(t) or t <= 0
                or row.get("model_ms_with_reload") != t):
            raise ValueError("v39_timing_mismatch")
        timings.append(float(t))
        for obj_id in sorted(expected):
            obj = returned[obj_id]
            original_box = expected[obj_id].get("bbox")
            pixels = obj.get("visible_pixel_count")
            maskhash = obj.get("mask_sha256")
            if (
                not isinstance(original_box, list)
                or len(original_box) != 4
                or any(type(v) is not int for v in original_box)
                or obj.get("bbox") != original_box
                or obj.get("prompt_type") != "operator_box"
                or type(pixels) is not int or not 0 < pixels <= source["width"] * source["height"]
                or pixels_by_name[obj_id] != pixels
                or not isinstance(maskhash, str) or not _SHA.fullmatch(maskhash)
                or obj.get("reference_iou") is not None
            ):
                raise ValueError("v39_object_provenance_invalid")
            candidates.append({
                "scene_id": scene_id,
                "object_id": obj_id,
                "source_photo_sha256": source_hash,
                "reported_visible_mask_sha256": maskhash,
                "operator_prompt_bbox": original_box,
                "reported_visible_pixels": pixels,
                "source_label_kind": "operator_selected_name_not_model_recognition",
                "mask_kind": "provider_reported_prediction_not_stored",
                "persistable_object_memory_verified": False,
            })
    if checked_scenes != set(samples):
        raise ValueError("v39_unexpected_scene_coverage")
    return {
        "schema": "hex.operator_exploration_receipt_audit.v39",
        "status": "v39_receipt_consistency_pass",
        "run_dir": (_BASE / folder.name).as_posix(),
        "manifest_sha256": manifest_hash,
        "summary_sha256": summary_hash,
        "receipt_sha256_by_scene": receipt_hashes,
        "photographic_scenes_consistent": len(checked_scenes),
        "operator_prompted_objects_consistent": len(candidates),
        "inference_ms_observed_min": min(timings),
        "inference_ms_observed_max": max(timings),
        "provider_reported_cpu_only": True,
        "source_content_hashes_verified_locally": True,
        "original_segmentation_pixels_available_in_receipts": False,
        "independent_human_reference_masks_available": False,
        "source_capture_independence_verified": False,
        "quality_iou_estimated": False,
        "canonical_spine_event_lineage_verified": False,
        "generalization_attested": False,
        "object_candidates": candidates,
        "files_read": True,
        "files_written": False,
        "model_called": False,
        "model_promoted": False,
        "physical_action_executed": False,
    }
