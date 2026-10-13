"""V41 — verified V40 mask bytes -> read-only object-memory staging candidates.

Candidates are NOT CanonicalSpine memories. Their lineage, identity across
frames, semantics, ground truth and world-model efficacy remain unverified.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from hex_cortex.memory.cortex_operator_receipt_audit_v39 import (
    _checked_relative,
    _read_json,
    audit_uploaded_v38_receipts_v39,
)

_RUN = re.compile(r"run-\d{8}T\d{6}-\d{6}Z")
_SHA = re.compile(r"[0-9a-f]{64}")
_BASE = Path("receipts/v40_mask_inspection")


def _mask(path: Path, size: tuple[int, int]) -> tuple[str, int, list[int], bytes]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("v41_pillow_required") from exc
    with Image.open(path) as source:
        if source.size != size or source.mode not in ("1", "L"):
            raise ValueError("v41_mask_mode_or_shape_invalid")
        grayscale = source.convert("L")
        raw = grayscale.tobytes()
        if not raw or any(value not in (0, 255) for value in raw):
            raise ValueError("v41_mask_must_be_binary")
        bounds = grayscale.getbbox()
        if bounds is None:
            raise ValueError("v41_mask_empty")
        return (
            hashlib.sha256(raw).hexdigest(),
            raw.count(255),
            list(bounds),
            raw,
        )


def _folder(root: Path, selection: str) -> Path:
    base = root / _BASE
    if selection == "latest":
        if not base.is_dir() or base.is_symlink():
            raise ValueError("v41_no_inspection_runs")
        found = sorted(
            (
                p for p in base.iterdir()
                if p.is_dir() and not p.is_symlink() and _RUN.fullmatch(p.name)
            ),
            reverse=True, key=lambda p: p.name,
        )
        if not found:
            raise ValueError("v41_no_inspection_runs")
        return found[0]
    part = Path(selection.replace("\\", "/"))
    if part.parent != _BASE or not _RUN.fullmatch(part.name):
        raise ValueError("v41_inspection_run_denied")
    result = root / part
    if result.is_symlink() or not result.is_dir() or not result.resolve().is_relative_to(root):
        raise ValueError("v41_inspection_run_denied")
    return result


def stage_verified_object_candidates_v41(
    *,
    project_root: Path,
    inspection_run: str = "latest",
    approved_read: bool = False,
) -> dict:
    """Verify on-disk binary masks & original sources, then emit no-write proposals."""
    if not approved_read:
        return {
            "status": "blocked",
            "reason": "v41_read_approval_required",
            "files_read": False,
            "files_written": False,
            "model_called": False,
        }
    root = Path(project_root).resolve(strict=True)
    folder = _folder(root, inspection_run)
    inspection, inspection_sha = _read_json(folder / "inspection.json", 500_000)
    if (
        inspection.get("schema") != "hex.mask_inspection.v40"
        or inspection.get("status") != "verified_mask_replay_exported"
        or inspection.get("original_v38_mask_bytes_reproduced") is not True
        or inspection.get("provider") != "mobile_sam_vit_t_cpu"
        or inspection.get("model_called") is not True
        or inspection.get("gpu_used") is not False
        or inspection.get("human_annotation_present") is not False
        or inspection.get("mean_reference_iou") is not None
        or inspection.get("world_model_generalization_attested") is not False
        or inspection.get("new_output_dir") != (_BASE / folder.name).as_posix()
    ):
        raise ValueError("v41_inspection_contract_invalid")
    old_run = inspection.get("source_audit_run")
    if not isinstance(old_run, str) or not old_run:
        raise ValueError("v41_upstream_run_missing")
    audited = audit_uploaded_v38_receipts_v39(
        project_root=root, run_selection=old_run, approved_read=True,
    )
    if audited.get("status") != "v39_receipt_consistency_pass":
        raise ValueError("v41_v39_audit_failed")
    records = inspection.get("records")
    if (
        not isinstance(records, list)
        or not 1 <= len(records) <= 9
        or inspection.get("scene_count") != len(records)
    ):
        raise ValueError("v41_scene_count_invalid")

    # V39 re-hashes the source photos and checks all 9 original model receipts.
    v39_by_scene: dict[str, dict[str, dict]] = {}
    for item in audited["object_candidates"]:
        v39_by_scene.setdefault(item["scene_id"], {})[item["object_id"]] = item

    manifest, _ = _read_json(
        _checked_relative(root, "research/v38_uploaded/boxes.json", ext=".json", max_bytes=100_000),
        100_000,
    )
    manifest_scenes = {
        entry["scene_id"]: entry for entry in manifest["samples"]
        if isinstance(entry, dict) and entry.get("type") == "photographic"
    }

    scene_ids: set[str] = set()
    all_candidates: list[dict] = []
    relations: list[dict] = []
    local_edges: list[dict] = []
    expected_masks = 0
    checked_pngs: set[Path] = set()

    for scene in records:
        if not isinstance(scene, dict):
            raise ValueError("v41_scene_invalid")
        scene_id = scene.get("scene_id")
        if (
            not isinstance(scene_id, str)
            or scene_id not in v39_by_scene or scene_id in scene_ids
        ):
            raise ValueError("v41_scene_unknown_or_duplicate")
        scene_ids.add(scene_id)
        objs = scene.get("objects")
        if not isinstance(objs, list) or not objs:
            raise ValueError("v41_objects_missing")
        if set(o.get("object_id") for o in objs if isinstance(o, dict)) != set(
            v39_by_scene[scene_id]
        ) or len(objs) != len(v39_by_scene[scene_id]):
            raise ValueError("v41_object_set_mismatch")
        expected_masks += len(objs)

        # The checked V38 source manifest supplies measured pixel dimensions.
        source = manifest_scenes.get(scene_id)
        if source is None:
            raise ValueError("v41_no_verified_original_image")
        dimensions = (source["width"], source["height"])
        if (
            any(type(n) is not int or n <= 0 for n in dimensions)
            or dimensions[0] * dimensions[1] > 16_000_000
        ):
            raise ValueError("v41_source_dimensions_invalid")
        scene_candidates: list[dict] = []
        masks: dict[str, bytes] = {}
        if scene.get("source_image_sha256") != source["sha256"]:
            raise ValueError("v41_source_hash_mismatch")
        for obj in objs:
            object_id = obj["object_id"]
            previous = v39_by_scene[scene_id][object_id]
            relative = obj.get("mask_png")
            png = _checked_relative(root, relative, ext=".png", max_bytes=16_000_000)
            expected_rel = (_BASE / folder.name / scene_id / f"{object_id}.png")
            if png != root / expected_rel or png in checked_pngs:
                raise ValueError("v41_mask_path_not_bound_to_run")
            checked_pngs.add(png)
            sha, pixels, actual_box, raw = _mask(png, dimensions)
            if (
                not _SHA.fullmatch(sha)
                or sha != obj.get("binary_mask_sha256_verified")
                or sha != previous["reported_visible_mask_sha256"]
                or obj.get("old_mask_sha256_equal") is not True
                or pixels != obj.get("visible_pixels_verified")
                or pixels != previous["reported_visible_pixels"]
                or obj.get("operator_prompt_bbox") != previous["operator_prompt_bbox"]
            ):
                raise ValueError("v41_prediction_pixel_integrity_failed")
            proposal = {
                "scene_id": scene_id,
                "object_id": object_id,
                "source_photo_sha256": source["sha256"],
                "mask_binary_sha256": sha,
                "mask_file": relative,
                "operator_prompt_bbox": previous["operator_prompt_bbox"],
                "visible_mask_bbox": actual_box,
                "visible_mask_pixels": pixels,
                "label_source": "operator_selected_not_recognized",
                "mask_source": "mobile_sam_predicted_not_ground_truth",
                "scene_object_id_scope": "single_image_only",
                "canonical_spine_event_id": None,
                "memory_promotion_approved": False,
            }
            scene_candidates.append(proposal)
            all_candidates.append(proposal)
            masks[object_id] = raw
        # Bounding-box spatial relations are geometric, not causal or 3D.
        for left in scene_candidates:
            x1, y1, x2, y2 = left["visible_mask_bbox"]
            for right in scene_candidates:
                if left is right:
                    continue
                a, b, c, d = right["visible_mask_bbox"]
                if x2 <= a:
                    relations.append({
                        "scene_id": scene_id, "subject": left["object_id"],
                        "relation": "image_left_of", "object": right["object_id"],
                    })
                if y2 <= b:
                    relations.append({
                        "scene_id": scene_id, "subject": left["object_id"],
                        "relation": "image_above", "object": right["object_id"],
                    })
                if x1 < c and a < x2 and y1 < d and b < y2:
                    overlap = sum(
                        p == 255 and q == 255
                        for p, q in zip(
                            masks[left["object_id"]], masks[right["object_id"]], strict=True,
                        )
                    )
                    if left["object_id"] < right["object_id"]:
                        local_edges.append({
                            "scene_id": scene_id,
                            "object_a": left["object_id"],
                            "object_b": right["object_id"],
                            "overlapping_foreground_pixels": overlap,
                            "depth_or_occlusion_order_inferred": False,
                        })

    if inspection.get("mask_count") != expected_masks:
        raise ValueError("v41_inspection_mask_count_mismatch")
    return {
        "schema": "hex.pending_object_memory.v41",
        "status": "verified_pixels_pending_memory_lineage",
        "inspection_receipt_sha256": inspection_sha,
        "scene_count": len(scene_ids),
        "verified_object_masks": len(all_candidates),
        "candidates": all_candidates,
        "spatial_relations_2d_only": relations,
        "foreground_overlap_2d_only": local_edges,
        "v39_audit_rechecked": True,
        "source_capture_independence_attested": False,
        "human_reference_iou_available": False,
        "same_object_across_frames_verified": False,
        "canonical_spine_lineage_verified": False,
        "world_model_prediction_verified": False,
        "model_improvement_attested": False,
        "promotion_to_long_term_memory_permitted": False,
        "files_read": True,
        "files_written": False,
        "model_called": False,
        "gpu_used": False,
        "physical_action_executed": False,
    }
