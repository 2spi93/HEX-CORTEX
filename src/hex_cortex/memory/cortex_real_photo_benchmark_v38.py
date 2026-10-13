"""V38: opt-in source-separated REAL-photo mask benchmark (CPU, no persistence).

Operator-supplied natural photographs and pixel-accurate annotation masks.
The actual provenance and correctness of those annotations are NOT independently
verified by this module. A synthetic smoke is never accepted as photo evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

from hex_cortex.memory.cortex_cpu_segmentation_v36 import segment_boxes_cpu_v36

_MANIFEST_SCHEMA = "hex.real_photo_benchmark.v38"
_MAX_SAMPLES = 25
_ALLOWED_SPLITS = frozenset({"train", "validation", "test"})


def _relative_file(root: Path, raw: object, suffixes: set[str], max_bytes: int) -> Path:
    if not isinstance(raw, str) or not raw or "\\x00" in raw:
        raise ValueError("v38_path_denied")
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts or rel == Path("."):
        raise ValueError("v38_path_denied")
    result = root / rel
    if not result.resolve().is_relative_to(root):
        raise ValueError("v38_path_denied")
    cursor = result
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError("v38_symlink_denied")
        cursor = cursor.parent
    if (
        not result.is_file() or result.suffix.lower() not in suffixes
        or not 0 < result.stat().st_size <= max_bytes
    ):
        raise ValueError("v38_file_denied")
    return result


def _sha256(file: Path) -> str:
    sha = hashlib.sha256()
    with file.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def _no_nonfinite_constant(value: str) -> None:
    raise ValueError("v38_nonfinite_json_denied")


def _reject_repeated_json_keys(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("v38_duplicate_json_key_denied")
        result[k] = v
    return result


def _percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 4)
    position = (len(ordered) - 1) * p
    lo = math.floor(position)
    hi = math.ceil(position)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo), 4)


def _preflight(*, root: Path, manifest_path: str) -> tuple[list[dict], dict]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("v38_pillow_required") from exc

    file = _relative_file(root, manifest_path, {".json"}, 250_000)
    with file.open("r", encoding="utf-8") as f:
        manifest = json.load(
            f, parse_constant=_no_nonfinite_constant,
            object_pairs_hook=_reject_repeated_json_keys,
        )
    if not isinstance(manifest, dict) or manifest.get("schema") != _MANIFEST_SCHEMA:
        raise ValueError("v38_manifest_schema_invalid")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not 1 <= len(samples) <= _MAX_SAMPLES:
        raise ValueError("v38_sample_count_invalid")
    scene_ids: set[str] = set()
    path_hashes: set[str] = set()
    groups_by_split: dict[str, set[str]] = {}
    image_by_split: dict[str, set[str]] = {}
    ready: list[dict] = []
    annotated_count = 0
    for item in samples:
        if not isinstance(item, dict) or item.get("source_kind") != "operator_real_photo":
            raise ValueError("v38_operator_real_photo_declaration_required")
        scene_id = item.get("scene_id")
        group = item.get("source_group")
        split = item.get("split")
        if (
            not isinstance(scene_id, str) or not scene_id.isidentifier()
            or len(scene_id) > 64 or scene_id in scene_ids
        ):
            raise ValueError("v38_scene_id_invalid_or_reused")
        scene_ids.add(scene_id)
        if not isinstance(group, str) or not group.isidentifier() or len(group) > 64:
            raise ValueError("v38_source_group_invalid")
        if split not in _ALLOWED_SPLITS:
            raise ValueError("v38_split_invalid")
        image_file = _relative_file(
            root, item.get("image"), {".png", ".jpg", ".jpeg", ".webp"}, 16_000_000,
        )
        image_hash = _sha256(image_file)
        if image_hash in path_hashes:
            raise ValueError("v38_exact_duplicate_photo_denied")
        path_hashes.add(image_hash)
        groups_by_split.setdefault(group, set()).add(split)
        image_by_split.setdefault(image_hash, set()).add(split)
        with Image.open(image_file) as image:
            if not 0 < image.width * image.height <= 16_000_000:
                raise ValueError("v38_image_dimensions_denied")
            size = image.size
        objects = item.get("objects")
        if not isinstance(objects, list) or not 1 <= len(objects) <= 24:
            raise ValueError("v38_objects_missing")
        box_by_id: dict[str, tuple[int, int, int, int]] = {}
        reference_by_id: dict[str, str] = {}
        annotations = []
        for obj in objects:
            if not isinstance(obj, dict):
                raise ValueError("v38_annotation_invalid")
            name = obj.get("object_id")
            box = obj.get("box")
            if (
                not isinstance(name, str) or not name.isidentifier() or len(name) > 48
                or name in box_by_id
            ):
                raise ValueError("v38_object_id_invalid")
            if (
                not isinstance(box, list) or len(box) != 4
                or any(type(v) is not int for v in box)
            ):
                raise ValueError("v38_box_invalid")
            x1, y1, x2, y2 = box
            if not (0 <= x1 < x2 <= size[0] and 0 <= y1 < y2 <= size[1]):
                raise ValueError("v38_box_out_of_bounds")
            mask_file = _relative_file(root, obj.get("reference_mask"), {".png"}, 16_000_000)
            with Image.open(mask_file) as mask:
                if mask.size != size:
                    raise ValueError("v38_reference_dimensions_invalid")
                if mask.mode not in ("1", "L"):
                    raise ValueError("v38_reference_must_be_grayscale")
                mask_extrema = mask.convert("L").getextrema()
                if mask_extrema == (0, 0):
                    raise ValueError("v38_reference_empty")
            box_by_id[name] = (x1, y1, x2, y2)
            reference_by_id[name] = str(mask_file.relative_to(root))
            annotations.append({
                "object_id": name,
                "operator_reference_mask_sha256": _sha256(mask_file),
            })
        annotated_count += len(annotations)
        ready.append({
            "scene_id": scene_id,
            "source_group": group,
            "split": split,
            "image": str(image_file.relative_to(root)),
            "source_image_sha256": image_hash,
            "boxes": box_by_id,
            "references": reference_by_id,
            "annotations": annotations,
        })
    overlap_groups = sum(len(splits) > 1 for splits in groups_by_split.values())
    overlap_images = sum(len(splits) > 1 for splits in image_by_split.values())
    if overlap_groups or overlap_images:
        raise ValueError("v38_cross_split_source_contamination")
    group_count = len(groups_by_split)
    preliminary = {
        "manifest_sha256": _sha256(file),
        "sample_count": len(ready),
        "source_group_count": group_count,
        "annotated_object_count": annotated_count,
        "exact_duplicate_images_detected": False,
        "exact_cross_split_leakage_detected": False,
        "source_group_cross_split_leakage_detected": False,
        "minimum_10_distinct_source_groups_met": group_count >= 10,
        "near_duplicate_and_semantic_leakage_checked": False,
        "photos_and_annotations_independently_verified": False,
        "independent_generalization_attested": False,
    }
    return ready, preliminary


def evaluate_real_photo_masks_v38(
    *,
    project_root: Path,
    manifest_path: str,
    checkpoint_path: str,
    checkpoint_sha256: str,
    approved_read: bool = False,
    approved_model_load: bool = False,
    preflight_only: bool = False,
    _infer=None,
) -> dict:
    """Read-only batch: no automatic downloads or file writes, no GPU.

    Per-image wall time includes model load; it is not steady-state latency.
    """
    if not approved_read:
        return {
            "status": "blocked", "reason": "v38_read_approval_required",
            "files_read": False, "model_called": False, "files_written": False,
        }
    if not preflight_only and not approved_model_load:
        return {
            "status": "blocked", "reason": "v38_model_approval_required",
            "files_read": False, "model_called": False, "files_written": False,
        }
    root = Path(project_root).resolve(strict=True)
    samples, preflight = _preflight(root=root, manifest_path=manifest_path)
    if preflight_only:
        return {
            "status": "manifest_preflight_pass",
            **preflight,
            "files_read": True, "model_called": False, "files_written": False,
            "gpu_used": False,
        }
    records = []
    ious: list[float] = []
    timings: list[float] = []
    for entry in samples:
        receipt = segment_boxes_cpu_v36(
            project_root=root,
            image_path=entry["image"],
            checkpoint_path=checkpoint_path,
            checkpoint_sha256=checkpoint_sha256,
            object_boxes=entry["boxes"],
            reference_masks=entry["references"],
            approved_read=True,
            approved_model_load=True,
            _infer=_infer,
        )
        if receipt.get("status") != "segmented_cpu_masks_ready":
            raise ValueError("v38_segmentation_failed")
        if receipt.get("source_sha256") != entry["source_image_sha256"]:
            raise ValueError("v38_image_changed_since_preflight")
        if receipt.get("gpu_used") is not False:
            raise ValueError("v38_unexpected_gpu")
        timing = receipt["inference_ms"]
        if not isinstance(timing, (int, float)) or not math.isfinite(timing):
            raise ValueError("v38_timing_invalid")
        timings.append(float(timing))
        image_objects = []
        for predicted in receipt["objects"]:
            iou = predicted.get("reference_iou")
            if not isinstance(iou, (int, float)) or not math.isfinite(iou):
                raise ValueError("v38_real_reference_iou_required")
            ious.append(float(iou))
            annotation = next(
                x for x in entry["annotations"] if x["object_id"] == predicted["object_id"]
            )
            image_objects.append({
                "object_id": predicted["object_id"],
                "reference_iou": iou,
                "predicted_mask_sha256": predicted["mask_sha256"],
                "operator_reference_mask_sha256": annotation["operator_reference_mask_sha256"],
                "operator_box": predicted["bbox"],
            })
        records.append({
            "scene_id": entry["scene_id"],
            "source_group": entry["source_group"],
            "split": entry["split"],
            "source_image_sha256": entry["source_image_sha256"],
            "per_photo_elapsed_ms_including_model_load": timing,
            "objects": image_objects,
        })
    return {
        "schema": "hex.real_photo_benchmark_result.v38",
        "status": "operator_real_photo_benchmark_executed",
        "provider": "test_injected_provider" if _infer else "mobile_sam_vit_t_cpu",
        "actual_mobile_sam_inference_called": _infer is None,
        "checkpoint_sha256": checkpoint_sha256,
        "preflight": preflight,
        "mean_operator_reference_iou": round(statistics.mean(ious), 6),
        "minimum_operator_reference_iou": round(min(ious), 6),
        "p50_per_photo_ms_including_model_load": _percentile(timings, 0.50),
        "p95_per_photo_ms_including_model_load": _percentile(timings, 0.95),
        "per_photo_model_loaded_each_time": True,
        "independent_visual_generalization_attested": False,
        "operator_annotation_quality_independently_verified": False,
        "records": records,
        "gpu_used": False,
        "files_written": False,
        "model_promoted": False,
        "canonical_spine_lineage_verified": False,
        "physical_action_executed": False,
    }
