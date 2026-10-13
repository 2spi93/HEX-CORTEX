"""V36-A: actual opt-in CPU MobileSAM segmentation, grounded 2D box prompts.

No implicit model download, auto-generation, GPU, or file writes. This
module is an optional provider for V35; it does not replace its compositor.
The checkpoint must be operator-trusted, local and SHA256-pinned before
MobileSAM's third-party checkpoint loader is invoked.
"""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from typing import Callable

_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}")
_SHA = re.compile(r"[a-f0-9]{64}")


def _file(root: Path, rel: str, *, suffixes: set[str], max_bytes: int) -> Path:
    if not isinstance(rel, str) or not rel:
        raise ValueError("v36_path_denied")
    proposed = Path(rel)
    if proposed.is_absolute() or ".." in proposed.parts:
        raise ValueError("v36_path_denied")
    target = root / proposed
    if not target.resolve().is_relative_to(root):
        raise ValueError("v36_path_denied")
    cursor = target
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError("v36_symlink_denied")
        cursor = cursor.parent
    if (
        not target.is_file() or target.suffix.lower() not in suffixes
        or not 0 < target.stat().st_size <= max_bytes
    ):
        raise ValueError("v36_input_file_denied")
    return target


def _sha256_file(file: Path) -> str:
    digest = hashlib.sha256()
    with file.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iou(predicted, reference) -> float:
    """Exact foreground IoU for equal-sized binary Pillow L masks."""
    if predicted.size != reference.size:
        raise ValueError("v36_reference_mask_dimensions_invalid")
    a = predicted.convert("L").point(lambda x: 255 if x >= 128 else 0)
    b = reference.convert("L").point(lambda x: 255 if x >= 128 else 0)
    lhs = a.tobytes()
    rhs = b.tobytes()
    union = sum(x == 255 or y == 255 for x, y in zip(lhs, rhs))
    intersection = sum(x == 255 and y == 255 for x, y in zip(lhs, rhs))
    return 1.0 if union == 0 else intersection / union


def _mobile_sam_box_infer(original, boxes: dict[str, tuple[int, int, int, int]], checkpoint: Path):
    """Optional third-party real inference. Caller already approved and pinned weights."""
    try:
        import numpy as np
        from mobile_sam import SamPredictor, sam_model_registry
    except ImportError as exc:
        raise ValueError("v36_mobilesam_numpy_missing") from exc
    model = sam_model_registry["vit_t"](checkpoint=str(checkpoint))
    model.to(device="cpu")
    model.eval()
    predictor = SamPredictor(model)
    predictor.set_image(np.asarray(original.convert("RGB")))
    output = {}
    for object_id, box in boxes.items():
        masks, _, _ = predictor.predict(
            box=np.asarray(box, dtype=np.float32), multimask_output=False,
        )
        if len(masks) != 1:
            raise ValueError("v36_segmentation_result_invalid")
        from PIL import Image
        output[object_id] = Image.fromarray(masks[0].astype(np.uint8) * 255)
    return output


def segment_boxes_cpu_v36(
    *,
    project_root: Path,
    image_path: str,
    checkpoint_path: str,
    checkpoint_sha256: str,
    object_boxes: dict[str, tuple[int, int, int, int]],
    reference_masks: dict[str, str] | None = None,
    approved_read: bool = False,
    approved_model_load: bool = False,
    export_dir: str | None = None,
    approved_write: bool = False,
    _infer: Callable | None = None,
) -> dict:
    """Segment supplied boxes using true MobileSAM CPU if installed.

    Injected `_infer` is only for deterministic tests, NOT proof of real weights.
    """
    if not approved_read:
        return {"status": "blocked", "reason": "v36_image_read_approval_required", "files_read": False, "model_called": False}
    if not approved_model_load:
        return {"status": "blocked", "reason": "v36_checkpoint_load_approval_required", "files_read": False, "model_called": False}
    if export_dir is not None and not approved_write:
        return {"status": "blocked", "reason": "v36_export_approval_required", "files_read": False, "model_called": False}
    if approved_write and export_dir is None:
        raise ValueError("v36_export_directory_required")
    if not isinstance(checkpoint_sha256, str) or not _SHA.fullmatch(checkpoint_sha256):
        raise ValueError("v36_checkpoint_digest_required")
    if not isinstance(object_boxes, dict) or not 1 <= len(object_boxes) <= 24:
        raise ValueError("v36_object_boxes_invalid")
    if reference_masks is not None and (
        not isinstance(reference_masks, dict) or
        set(reference_masks) != set(object_boxes)
    ):
        raise ValueError("v36_reference_masks_invalid")
    root = Path(project_root).resolve(strict=True)
    output = None
    if export_dir is not None:
        path = Path(export_dir)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ValueError("v36_export_path_denied")
        output = root / path
        if not output.resolve().is_relative_to(root):
            raise ValueError("v36_export_path_denied")
        cursor = output
        while cursor != root:
            if cursor.is_symlink():
                raise ValueError("v36_symlink_denied")
            cursor = cursor.parent
        if output.exists():
            raise ValueError("v36_export_existing_path_denied")
        if not output.parent.is_dir():
            raise ValueError("v36_export_parent_required")

    original_file = _file(root, image_path, suffixes={".png", ".jpg", ".jpeg", ".webp"}, max_bytes=16_000_000)
    checkpoint = _file(root, checkpoint_path, suffixes={".pt", ".pth"}, max_bytes=200_000_000)
    digest = _sha256_file(checkpoint)
    if digest != checkpoint_sha256:
        raise ValueError("v36_checkpoint_digest_mismatch")

    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("v36_pillow_missing") from exc
    with Image.open(original_file) as source:
        if not (0 < source.width * source.height <= 16_000_000):
            raise ValueError("v36_image_dimensions_invalid")
        if source.mode in ("RGBA", "LA") and source.getchannel("A").getextrema() != (255, 255):
            raise ValueError("v36_image_transparency_denied")
        original = source.convert("RGB")
    width, height = original.size
    boxes = {}
    for object_id, box in object_boxes.items():
        if not isinstance(object_id, str) or not _ID.fullmatch(object_id):
            raise ValueError("v36_object_id_invalid")
        if (
            not isinstance(box, (tuple, list)) or len(box) != 4
            or any(type(x) is not int for x in box)
        ):
            raise ValueError("v36_box_invalid")
        x1, y1, x2, y2 = box
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError("v36_box_bounds_invalid")
        boxes[object_id] = (x1, y1, x2, y2)

    references = {}
    if reference_masks:
        for object_id, rel in reference_masks.items():
            file = _file(root, rel, suffixes={".png"}, max_bytes=16_000_000)
            with Image.open(file) as source:
                if source.size != original.size:
                    raise ValueError("v36_reference_mask_dimensions_invalid")
                references[object_id] = source.convert("L")

    started = time.perf_counter()
    masks = (_infer or _mobile_sam_box_infer)(original, boxes, checkpoint)
    inference_ms = round((time.perf_counter() - started) * 1000, 2)
    if not isinstance(masks, dict) or set(masks) != set(boxes):
        raise ValueError("v36_segmentation_result_invalid")
    result = []
    normalized = {}
    for object_id in boxes:
        mask = masks[object_id]
        if not isinstance(mask, Image.Image) or mask.size != original.size:
            raise ValueError("v36_segmentation_result_invalid")
        binary = mask.convert("L").point(lambda val: 255 if val >= 128 else 0)
        count = binary.histogram()[255]
        if count == 0:
            raise ValueError("v36_segmentation_empty_object")
        normalized[object_id] = binary
        result.append({
            "object_id": object_id,
            "prompt_type": "operator_box",
            "bbox": list(boxes[object_id]),
            "visible_pixel_count": count,
            "mask_sha256": hashlib.sha256(binary.tobytes()).hexdigest(),
            "reference_iou": round(_iou(binary, references[object_id]), 6) if object_id in references else None,
            "independently_attested_mask": False,
        })
    saved = []
    if output is not None:
        output.mkdir(exist_ok=False)
        for object_id, mask in normalized.items():
            target = output / f"{object_id}.png"
            mask.save(target)
            saved.append(str(target.relative_to(root)))
    return {
        "status": "segmented_cpu_masks_ready",
        "provider": "injected_test_provider" if _infer else "mobile_sam_vit_t_cpu",
        "model_called": _infer is None,
        "gpu_used": False,
        "checkpoint_sha256": digest,
        "source_sha256": _sha256_file(original_file),
        "image_size": [width, height],
        "objects": result,
        "inference_ms": inference_ms,
        "model_weights_came_from_verified_trusted_source_attested": False,
        "benchmark_is_independent": False,
        "exported_mask_paths": saved,
        "files_read": True,
        "files_written": bool(saved),
        "original_image_modified": False,
        "physical_action_executed": False,
    }
