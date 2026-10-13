"""V40: audited MobileSAM mask replay, visible overlays, no invented ground truth.

All images/masks/previews remain under a new operator-approved local folder.
Original V38 receipts are checked before any inference; actual binary mask
bytes must reproduce their reported SHA256 and pixel counts exactly.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from hex_cortex.memory.cortex_cpu_segmentation_v36 import segment_boxes_cpu_v36
from hex_cortex.memory.cortex_operator_receipt_audit_v39 import (
    _BASE,
    _checked_relative,
    _read_json,
    _run_folder,
    audit_uploaded_v38_receipts_v39,
)

_DEFAULT_SCENES = ("scene03_jump", "scene07_racecar", "scene09_factory_handover")
_OUTPUT = Path("receipts/v40_mask_inspection")


def export_verified_v40_masks(
    *,
    project_root: Path,
    checkpoint_path: str,
    checkpoint_sha256: str,
    scenes: list[str] | None = None,
    run_selection: str = "latest",
    manifest_path: str = "research/v38_uploaded/boxes.json",
    approved_read: bool = False,
    approved_model_load: bool = False,
    approved_write: bool = False,
    _infer=None,
) -> dict:
    """Replay selected source scenes and validate PNGs against old V38 hashes.

    Injected inference is strictly for tests; real inference is the default.
    Returns path-only local artifact receipts (no image pixels/photographs).
    """
    if not approved_read:
        return {"status": "blocked", "reason": "v40_read_approval_required",
                "files_read": False, "files_written": False, "model_called": False}
    if not approved_model_load:
        return {"status": "blocked", "reason": "v40_model_approval_required",
                "files_read": False, "files_written": False, "model_called": False}
    if not approved_write:
        return {"status": "blocked", "reason": "v40_write_approval_required",
                "files_read": False, "files_written": False, "model_called": False}
    if not isinstance(checkpoint_sha256, str) or len(checkpoint_sha256) != 64:
        raise ValueError("v40_checkpoint_sha_missing")
    root = Path(project_root).resolve(strict=True)
    selected = list(_DEFAULT_SCENES) if scenes is None else scenes
    if (
        not isinstance(selected, list) or not 1 <= len(selected) <= 9
        or any(not isinstance(s, str) for s in selected)
        or len(set(selected)) != len(selected)
    ):
        raise ValueError("v40_selection_invalid")

    audit = audit_uploaded_v38_receipts_v39(
        project_root=root, run_selection=run_selection,
        manifest_path=manifest_path, approved_read=True,
    )
    if audit["status"] != "v39_receipt_consistency_pass":
        raise ValueError("v40_upstream_receipts_not_audited")
    old_run = _run_folder(root, run_selection)
    mf = _checked_relative(root, manifest_path, ext=".json", max_bytes=100_000)
    manifest, _ = _read_json(mf, 100_000)
    assert isinstance(manifest["samples"], list)
    samples = {
        entry["scene_id"]: entry
        for entry in manifest["samples"]
        if entry.get("type") == "photographic"
    }
    if not set(selected) <= set(samples):
        raise ValueError("v40_unrecognized_photo_scene")
    for scene in selected:
        old, _ = _read_json(old_run / f"{scene}.json", 2_000_000)
        if old.get("checkpoint_sha256") != checkpoint_sha256:
            raise ValueError("v40_checkpoint_digest_differs_from_v38")
    # Image source and V39 old receipts have already been checked. V36 checks
    # the actual checkpoint hash against the operator's supplied SHA before
    # model deserialization.
    try:
        from PIL import Image, ImageChops, ImageFilter
    except ImportError as exc:
        raise ValueError("v40_pillow_missing") from exc

    parent = root / _OUTPUT
    if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
        raise ValueError("v40_output_parent_denied")
    parent.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(UTC).strftime("run-%Y%m%dT%H%M%S-%fZ")
    dest = parent / run_id
    dest.mkdir(exist_ok=False)
    result = []
    try:
        for scene in selected:
            item = samples[scene]
            old, old_sha = _read_json(old_run / f"{scene}.json", 2_000_000)
            original = _checked_relative(
                root, item["relative_image"], ext=".jpg", max_bytes=16_000_000,
            )
            if hashlib.sha256(original.read_bytes()).hexdigest() != old["source_sha256"]:
                raise ValueError("v40_original_image_changed")
            original_boxes = {
                obj["object_id"]: tuple(obj["bbox"]) for obj in item["boxes"]
            }
            if len(original_boxes) != len(item["boxes"]):
                raise ValueError("v40_duplicate_prompt_id")
            mask_folder = (_OUTPUT / run_id / scene).as_posix()
            receipt = segment_boxes_cpu_v36(
                project_root=root,
                image_path=item["relative_image"],
                checkpoint_path=checkpoint_path,
                checkpoint_sha256=checkpoint_sha256,
                object_boxes=original_boxes,
                approved_read=True, approved_model_load=True,
                export_dir=mask_folder, approved_write=True,
                _infer=_infer,
            )
            if (
                receipt.get("status") != "segmented_cpu_masks_ready"
                or receipt.get("source_sha256") != old["source_sha256"]
                or receipt.get("gpu_used") is not False
                or receipt.get("checkpoint_sha256") != checkpoint_sha256
            ):
                raise ValueError("v40_unexpected_replay_provider")
            if receipt.get("provider") != ("injected_test_provider" if _infer else "mobile_sam_vit_t_cpu"):
                raise ValueError("v40_unexpected_replay_provider")
            actual = {o["object_id"]: o for o in receipt["objects"]}
            expected = {o["object_id"]: o for o in old["objects"]}
            if set(actual) != set(expected) or len(actual) != len(receipt["objects"]):
                raise ValueError("v40_replayed_object_set_differs")
            with Image.open(original) as im:
                canvas = im.convert("RGBA")
            objects = []
            for object_id in sorted(actual):
                new = actual[object_id]
                previous = expected[object_id]
                path = root / mask_folder / f"{object_id}.png"
                with Image.open(path) as im:
                    mask = im.convert("L")
                raw_mask_digest = hashlib.sha256(mask.tobytes()).hexdigest()
                pixel_count = mask.histogram()[255]
                if (
                    new["mask_sha256"] != raw_mask_digest
                    or raw_mask_digest != previous["mask_sha256"]
                    or new["visible_pixel_count"] != pixel_count
                    or pixel_count != previous["visible_pixel_count"]
                    or new["bbox"] != previous["bbox"]
                ):
                    raise ValueError("v40_replayed_mask_hash_or_pixel_mismatch")
                # Transparent cyan overlay with a red 1px morphological edge.
                tint = Image.new("RGBA", mask.size, (0, 195, 225, 0))
                tint.putalpha(mask.point(lambda value: 118 if value >= 128 else 0))
                marked = Image.alpha_composite(canvas, tint)
                edge = ImageChops.difference(
                    mask.filter(ImageFilter.MaxFilter(3)),
                    mask.filter(ImageFilter.MinFilter(3)),
                )
                marked.paste((255, 40, 40, 255), (0, 0), edge)
                preview = root / mask_folder / f"{object_id}.preview.png"
                marked.convert("RGB").save(preview)
                objects.append({
                    "object_id": object_id,
                    "mask_png": (Path(mask_folder) / f"{object_id}.png").as_posix(),
                    "preview_png": (Path(mask_folder) / f"{object_id}.preview.png").as_posix(),
                    "binary_mask_sha256_verified": raw_mask_digest,
                    "old_mask_sha256_equal": True,
                    "visible_pixels_verified": pixel_count,
                    "operator_prompt_bbox": new["bbox"],
                    "independent_human_reference_iou": None,
                })
            result.append({
                "scene_id": scene,
                "original_receipt_sha256": old_sha,
                "source_image_sha256": old["source_sha256"],
                "objects": objects,
                "replay_ms_including_model_load": receipt["inference_ms"],
                "scene_ground_truth_available": False,
            })
        evidence = {
            "schema": "hex.mask_inspection.v40",
            "status": "verified_mask_replay_exported",
            "source_audit_run": (_BASE / old_run.name).as_posix(),
            "new_output_dir": (_OUTPUT / run_id).as_posix(),
            "scene_count": len(result),
            "mask_count": sum(len(s["objects"]) for s in result),
            "provider": "injected_test_provider" if _infer else "mobile_sam_vit_t_cpu",
            "model_called": _infer is None,
            "gpu_used": False,
            "checkpoint_sha256": checkpoint_sha256,
            "original_v38_mask_bytes_reproduced": True,
            "source_labels_from_operator_not_model_recognition": True,
            "human_annotation_present": False,
            "mean_reference_iou": None,
            "real_world_quality_attested": False,
            "world_model_generalization_attested": False,
            "canon_spine_lineage_verified": False,
            "model_promoted": False,
            "records": result,
            "files_written": True,
            "source_images_modified": False,
        }
        (dest / "inspection.json").write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        return evidence
    except Exception:
        # Only this newly allocated run folder is touched; never delete
        # pre-existing V38 run directories, user images or other runs.
        shutil.rmtree(dest)
        raise
