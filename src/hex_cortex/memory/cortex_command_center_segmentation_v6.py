"""V6 opt-in one-shot CPU MobileSAM on explicitly uploaded LOCAL image bytes.

Reuses V36's real MobileSAM predictor and its pinned checkpoint checks.
No implicit uploads, saving source/masks, model download, GPU, or tool calls.
The only network transmission is the browser's explicit same-origin POST
to this localhost Command Center. The model is NOT a human reference.
"""
from __future__ import annotations

import base64
import hashlib
import io
import re
import time
from pathlib import Path

from hex_cortex.memory.cortex_cpu_segmentation_v36 import (
    _file, _mobile_sam_box_infer, _sha256_file,
)

TRUSTED_CHECKPOINT_SHA256 = (
    "6dbb90523a35330fedd7f1d3dfc66f995213d81b29a5ca8108dbcdd4e37d6c2f"
)
_OBJECT_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}")
_MAX_UPLOAD = 8_000_000
_MAX_PIXELS = 16_000_000


def segment_browser_photo_cpu(
    *, root: Path, image_bytes: bytes, box: tuple[int, int, int, int],
    object_id: str, approved_operator_upload: bool,
    approved_model_load: bool, infer=None,
) -> dict:
    """Bounded CPU inference with in-memory PNG response and zero persistence."""
    if not approved_operator_upload or not approved_model_load:
        raise PermissionError("v6_explicit_local_upload_and_cpu_approval_required")
    if not isinstance(image_bytes, bytes) or not 0 < len(image_bytes) <= _MAX_UPLOAD:
        raise ValueError("v6_photo_upload_invalid")
    if not isinstance(object_id, str) or not _OBJECT_ID.fullmatch(object_id):
        raise ValueError("v6_object_label_invalid")
    if (
        not isinstance(box, (tuple, list)) or len(box) != 4
        or any(type(value) is not int for value in box)
    ):
        raise ValueError("v6_bbox_format_invalid")
    project = Path(root).resolve(strict=True)
    checkpoint = _file(
        project, "weights/mobile_sam.pt", suffixes={".pt"}, max_bytes=200_000_000,
    )
    digest = _sha256_file(checkpoint)
    if digest != TRUSTED_CHECKPOINT_SHA256:
        raise ValueError("v6_checkpoint_sha256_untrusted")
    try:
        from PIL import Image, ImageFile, UnidentifiedImageError
    except ImportError as exc:
        raise ValueError("v6_pillow_missing") from exc
    # A finite, explicit upper bound prevents decompression bomb allocations.
    if ImageFile.LOAD_TRUNCATED_IMAGES:
        raise ValueError("v6_truncated_image_mode_denied")
    try:
        with Image.open(io.BytesIO(image_bytes)) as decoded:
            if decoded.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("v6_image_format_denied")
            if (
                not 0 < decoded.width * decoded.height <= _MAX_PIXELS
                or decoded.width > 8192 or decoded.height > 8192
            ):
                raise ValueError("v6_image_dimensions_denied")
            if decoded.mode in ("RGBA", "LA") and decoded.getchannel("A").getextrema() != (255, 255):
                raise ValueError("v6_image_transparency_denied")
            image = decoded.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("v6_image_decode_denied") from exc
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height):
        raise ValueError("v6_bbox_outside_image")
    began = time.perf_counter()
    result = (infer or _mobile_sam_box_infer)(
        image, {object_id: (x0, y0, x1, y1)}, checkpoint,
    )
    duration = round((time.perf_counter() - began) * 1000, 2)
    if not isinstance(result, dict) or set(result) != {object_id}:
        raise ValueError("v6_inference_schema_denied")
    candidate = result[object_id]
    if not isinstance(candidate, Image.Image) or candidate.size != image.size:
        raise ValueError("v6_inference_shape_denied")
    mask = candidate.convert("L").point(lambda p: 255 if p >= 128 else 0)
    visible = mask.histogram()[255]
    if not 0 < visible <= _MAX_PIXELS:
        raise ValueError("v6_mask_empty_or_invalid")
    png = io.BytesIO()
    mask.save(png, format="PNG", optimize=True)
    rgba = Image.new("RGBA", mask.size, (0, 226, 199, 0))
    rgba.putalpha(mask.point(lambda pixel: 116 if pixel else 0))
    overlay = io.BytesIO()
    rgba.save(overlay, format="PNG", optimize=True)
    return {
        "schema": "hex.local_browser_mobilesam.v6",
        "status": "one_shot_mobile_sam_mask_ready",
        "provider": "mobile_sam_vit_t_cpu" if infer is None else "test_double_not_real_inference",
        "cpu_only_requested": True, "gpu_used": False,
        "model_called": infer is None,
        "source_sha256": hashlib.sha256(image_bytes).hexdigest(),
        "checkpoint_sha256": digest,
        "object_id": object_id,
        "bbox_xyxy": list(box),
        "mask_binary_sha256": hashlib.sha256(mask.tobytes()).hexdigest(),
        "mask_visible_pixels": visible,
        "image_width": image.width, "image_height": image.height,
        "inference_ms_including_load": duration,
        "mask_png_b64": base64.b64encode(png.getvalue()).decode("ascii"),
        "overlay_png_b64": base64.b64encode(overlay.getvalue()).decode("ascii"),
        "mask_origin": "mobile_sam_prediction_not_human_ground_truth",
        "independent_human_iou": None,
        "files_written": False, "spine_persisted": False,
        "world_model_evaluated": False,
        "physical_action_executed": False,
    }
