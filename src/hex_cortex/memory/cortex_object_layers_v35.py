"""V35: CPU pixel-exact visible-object layers from operator-approved masks.

This is NOT semantic segmentation, generated inpainting or 3D. Reuses
mask outputs from external models such as SAM and RGBA-oriented editors.
Makes explicit that hidden background is UNKNOWN, not reconstructed.
No network, model calls, hardware, GPU or writes unless separately approved.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}\Z")


def _approved_image(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if (
        not isinstance(relative, str) or not relative
        or candidate.is_absolute() or ".." in candidate.parts
    ):
        raise ValueError("object_layers_path_denied")
    path = root / candidate
    if (
        path.is_symlink() or not path.is_file()
        or not path.resolve().is_relative_to(root)
        or path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp")
        or not 0 < path.stat().st_size <= 16_000_000
    ):
        raise ValueError("object_layers_image_denied")
    return path.resolve()


def _mask_pixels(mask) -> int:
    """Count opaque pixels in a binary 8-bit Pillow image."""
    return mask.histogram()[255]


def compose_visible_object_layers(
    *,
    project_root: Path,
    image_path: str,
    object_masks: list[tuple[str, str]],
    approved_read: bool = False,
    export_dir: str | None = None,
    approved_write: bool = False,
) -> dict[str, object]:
    if not approved_read:
        return {
            "status": "blocked", "reason": "object_layers_approval_required",
            "files_read": False, "files_written": False,
        }
    if export_dir is not None and not approved_write:
        return {
            "status": "blocked", "reason": "object_layers_export_approval_required",
            "files_read": False, "files_written": False,
        }
    if approved_write and export_dir is None:
        raise ValueError("object_layers_export_directory_required")
    if not isinstance(object_masks, list) or not 1 <= len(object_masks) <= 24:
        raise ValueError("object_layers_count_invalid")
    root = Path(project_root).resolve(strict=True)
    source = _approved_image(root, image_path)
    image_names = []
    for entry in object_masks:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise ValueError("object_layers_mask_spec_invalid")
        name, file = entry
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError("object_layers_object_id_invalid")
        image_names.append((name, _approved_image(root, file)))
    if len({name for name, _ in image_names}) != len(image_names):
        raise ValueError("object_layers_duplicate_object_id")
    if any(mask == source for _, mask in image_names):
        raise ValueError("object_layers_mask_is_source")

    try:
        from PIL import Image, ImageChops
    except ImportError as exc:
        raise ValueError("object_layers_pillow_missing") from exc
    with Image.open(source) as original_file:
        if original_file.width < 1 or original_file.height < 1 or (
            original_file.width * original_file.height > 16_000_000
        ):
            raise ValueError("object_layers_image_dimensions_invalid")
        original = original_file.convert("RGBA")
    if original.getchannel("A").getextrema() != (255, 255):
        raise ValueError("object_layers_source_must_be_opaque")
    width, height = original.size
    blank = Image.new("L", original.size, 0)
    occupied = blank.copy()
    extracted = []
    details = []
    overlap_pixels = 0
    source_alpha = original.getchannel("A")

    # First mask has first ownership. Later masks cannot claim its pixels.
    # This produces disjoint visible layers without hallucinating occlusion.
    for name, path in image_names:
        with Image.open(path) as raw_mask:
            if raw_mask.size != original.size:
                raise ValueError("object_layers_mask_size_mismatch")
            mask = raw_mask.convert("L").point(
                lambda value: 255 if value >= 128 else 0,
            )
        collision = ImageChops.multiply(mask, occupied)
        overlap_pixels += _mask_pixels(collision)
        exclusive = ImageChops.multiply(mask, ImageChops.invert(occupied))
        occupied = ImageChops.lighter(occupied, exclusive)
        count = _mask_pixels(exclusive)
        if count == 0:
            raise ValueError("object_layers_empty_or_fully_occluded_object")
        item = original.copy()
        item.putalpha(ImageChops.multiply(source_alpha, exclusive))
        extracted.append((name, item))
        details.append({
            "object_id": name,
            "visible_pixel_count": count,
            "visible_fraction": round(count / (width * height), 6),
            "alpha_layer_sha256": hashlib.sha256(item.tobytes()).hexdigest(),
            "segmentation_ground_truth_attested": False,
        })
    background = original.copy()
    background.putalpha(ImageChops.invert(occupied))
    composite = background.copy()
    for _, obj in extracted:
        composite = Image.alpha_composite(composite, obj)
    if composite.tobytes() != original.tobytes():
        raise ValueError("object_layers_pixel_recomposition_not_exact")

    export_paths = []
    if export_dir is not None:
        target = Path(export_dir)
        if target.is_absolute() or ".." in target.parts or not target.parts:
            raise ValueError("object_layers_export_path_denied")
        output = root / target
        if not output.parent.resolve().is_relative_to(root):
            raise ValueError("object_layers_export_outside_root")
        if output.exists():
            raise ValueError("object_layers_export_existing_path_denied")
        output.mkdir(parents=True, exist_ok=False)
        background.save(output / "background_visible_only.png")
        export_paths.append(str((output / "background_visible_only.png").relative_to(root)))
        for name, obj in extracted:
            file = output / f"{name}.png"
            obj.save(file)
            export_paths.append(str(file.relative_to(root)))
        composite.save(output / "recomposed.png")
        export_paths.append(str((output / "recomposed.png").relative_to(root)))
    return {
        "status": "visible_object_layers_exactly_recomposed",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "canvas_size": [width, height],
        "object_count": len(extracted),
        "objects": details,
        "background_visible_pixel_count": width * height - _mask_pixels(occupied),
        "overlap_pixels_resolved_first_mask_wins": overlap_pixels,
        "recomposition_exact_pixel_match": True,
        "reconstruction_type": "visible_pixels_only_from_operator_masks",
        "object_recognition_performed": False,
        "semantic_segmentation_model_used": False,
        "hidden_occluded_background_reconstructed": False,
        "external_mask_provenance_attested": False,
        "exported_relative_paths": export_paths,
        "files_written": bool(export_paths),
        "gpu_used": False,
        "model_called": False,
        "physical_action_executed": False,
    }
