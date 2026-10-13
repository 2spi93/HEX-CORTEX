"""V37: opt-in real CPU MobileSAM synthetic smoke, with ephemeral reference masks.

This is deliberately NOT an independent image benchmark or evidence of
generalization. A smoke only establishes that the model executes on CPU.
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from hex_cortex.memory.cortex_cpu_segmentation_v36 import segment_boxes_cpu_v36

if TYPE_CHECKING:
    from collections.abc import Callable


def run_real_cpu_smoke_v37(
    *,
    project_root: Path,
    checkpoint_path: str,
    checkpoint_sha256: str,
    approved_read: bool = False,
    approved_model_load: bool = False,
    approved_temp_write: bool = False,
    _infer: Callable | None = None,
) -> dict:
    """Create a temporary labeled scene and run a prompted MobileSAM pass.

    Temp scene+mask are removed even if model loading/inference fails.
    The real MobileSAM path is used unless _infer is supplied by a unit test.
    """
    if not (approved_read and approved_model_load and approved_temp_write):
        return {
            "status": "blocked",
            "reason": "v37_explicit_read_model_load_and_temp_write_required",
            "files_read": False,
            "files_written": False,
            "model_called": False,
            "gpu_used": False,
        }
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise ValueError("v37_pillow_missing") from exc

    root = Path(project_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("v37_project_root_invalid")

    # Stable fixture, but *not* independent of this source code.
    size = (384, 288)
    box = (48, 54, 180, 218)
    fixture_sha = ""
    with tempfile.TemporaryDirectory(prefix=".v37-cpu-smoke-", dir=root) as tempdir:
        temp = Path(tempdir)
        scene = Image.new("RGB", size)
        px = scene.load()
        for y in range(size[1]):
            for x in range(size[0]):
                px[x, y] = (
                    42 + x // 24,
                    48 + y // 20,
                    62 + (x + y) // 55,
                )
        truth = Image.new("L", size, 0)
        ImageDraw.Draw(scene).ellipse((54, 60, 174, 212), fill=(218, 102, 55))
        ImageDraw.Draw(truth).ellipse((54, 60, 174, 212), fill=255)
        # Distractor: different object on the same image.
        ImageDraw.Draw(scene).rectangle((237, 78, 344, 202), fill=(51, 165, 130))
        scene.save(temp / "scene.png")
        truth.save(temp / "reference.png")
        fixture_sha = hashlib.sha256((temp / "scene.png").read_bytes()).hexdigest()

        receipt = segment_boxes_cpu_v36(
            project_root=root,
            image_path=str((temp / "scene.png").relative_to(root)),
            checkpoint_path=checkpoint_path,
            checkpoint_sha256=checkpoint_sha256,
            object_boxes={"synthetic_ellipse": box},
            reference_masks={
                "synthetic_ellipse": str((temp / "reference.png").relative_to(root)),
            },
            approved_read=True,
            approved_model_load=True,
            approved_write=False,
            _infer=_infer,
        )
    # All temporary files have been deleted at this point, even if inference failed.
    return {
        "schema": "hex.real_cpu_synthetic_smoke.v37",
        "status": "synthetic_smoke_executed",
        "input_kind": "generated_synthetic_scene_not_real_photo",
        "source_image_sha256": fixture_sha,
        "model_provider": receipt["provider"],
        "actual_mobile_sam_inference_called": receipt["model_called"],
        "checkpoint_sha256": receipt["checkpoint_sha256"],
        "requested_device": "cpu",
        "gpu_used": receipt["gpu_used"],
        "inference_including_load_ms": receipt["inference_ms"],
        "object_count": len(receipt["objects"]),
        "synthetic_reference_iou": receipt["objects"][0]["reference_iou"],
        "visible_pixel_count": receipt["objects"][0]["visible_pixel_count"],
        "segmentation_mask_sha256": receipt["objects"][0]["mask_sha256"],
        "synthetic_reference_is_ground_truth_for_generated_shapes": True,
        "independent_visual_generalization_attested": False,
        "canonical_spine_lineage_verified": False,
        "model_promoted": False,
        "checkpoint_modified": False,
        "temporary_fixture_written_then_deleted": True,
        "files_persisted": False,
        "physical_action_executed": False,
    }
