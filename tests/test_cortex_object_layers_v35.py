"""V35 actual visible pixel layer extraction, reconstruction and operator gates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_object_layers_cli_v35 import main
from hex_cortex.memory.cortex_object_layers_v35 import (
    compose_visible_object_layers,
)


def _test_images(folder: Path):
    Image = pytest.importorskip("PIL.Image")
    original = Image.new("RGB", (4, 3), (22, 34, 55))
    for x in (0, 1):
        original.putpixel((x, 1), (200, 15, 12))
    original.putpixel((2, 1), (44, 220, 30))
    original.save(folder / "photo.png")
    first = Image.new("L", (4, 3), 0)
    first.putpixel((0, 1), 255)
    first.putpixel((1, 1), 255)
    first.save(folder / "red_mask.png")
    second = Image.new("L", (4, 3), 0)
    second.putpixel((1, 1), 255)  # 1 pixel overlaps red mask
    second.putpixel((2, 1), 255)
    second.save(folder / "green_mask.png")
    return original


def _call(root: Path, **kwargs):
    return compose_visible_object_layers(
        project_root=root, image_path="photo.png",
        object_masks=[
            ("red_object", "red_mask.png"),
            ("green_object", "green_mask.png"),
        ],
        approved_read=True, **kwargs,
    )


def test_actual_mask_extraction_overlap_and_exact_recompose_cpu(
    tmp_path: Path,
) -> None:
    _test_images(tmp_path)
    before = hashlib.sha256((tmp_path / "photo.png").read_bytes()).hexdigest()
    receipt = _call(tmp_path)
    assert receipt["status"] == "visible_object_layers_exactly_recomposed"
    assert receipt["object_count"] == 2
    assert receipt["objects"][0]["visible_pixel_count"] == 2
    assert receipt["objects"][1]["visible_pixel_count"] == 1
    assert receipt["background_visible_pixel_count"] == 9
    assert receipt["overlap_pixels_resolved_first_mask_wins"] == 1
    assert receipt["recomposition_exact_pixel_match"] is True
    assert receipt["hidden_occluded_background_reconstructed"] is False
    assert receipt["semantic_segmentation_model_used"] is False
    assert receipt["files_written"] is False
    assert not (tmp_path / "exports").exists()
    assert hashlib.sha256((tmp_path / "photo.png").read_bytes()).hexdigest() == before


def test_explicit_export_produces_real_rgba_png_layers(
    tmp_path: Path,
) -> None:
    Image = pytest.importorskip("PIL.Image")
    before_image = _test_images(tmp_path)
    receipt = _call(
        tmp_path, export_dir="layers-operator-approved", approved_write=True,
    )
    assert receipt["files_written"] is True
    assert len(receipt["exported_relative_paths"]) == 4
    directory = tmp_path / "layers-operator-approved"
    with Image.open(directory / "red_object.png") as layer:
        assert layer.mode == "RGBA"
        assert layer.getpixel((0, 1))[3] == 255
        assert layer.getpixel((2, 1))[3] == 0
    with Image.open(directory / "green_object.png") as layer:
        assert layer.getpixel((1, 1))[3] == 0
        assert layer.getpixel((2, 1))[3] == 255
    with Image.open(directory / "background_visible_only.png") as base:
        assert base.getpixel((0, 1))[3] == 0
        assert base.getpixel((3, 1))[3] == 255
    with Image.open(directory / "recomposed.png") as recomposed:
        assert recomposed.convert("RGB").tobytes() == before_image.tobytes()
    with pytest.raises(ValueError, match="object_layers_export_existing_path_denied"):
        _call(
            tmp_path, export_dir="layers-operator-approved", approved_write=True,
        )


def test_export_needs_its_own_permission_before_file_reads(tmp_path: Path) -> None:
    result = compose_visible_object_layers(
        project_root=tmp_path, image_path="not-real.png",
        object_masks=[("some_object", "missing.png")],
    )
    assert result["status"] == "blocked"
    assert result["files_read"] is False
    result = compose_visible_object_layers(
        project_root=tmp_path, image_path="not-real.png",
        object_masks=[("some_object", "missing.png")],
        approved_read=True, export_dir="out",
    )
    assert result["status"] == "blocked"
    assert result["reason"] == "object_layers_export_approval_required"


def test_source_mask_dimensions_and_path_traversal_rejected(tmp_path: Path) -> None:
    Image = pytest.importorskip("PIL.Image")
    _test_images(tmp_path)
    invalid = Image.new("L", (2, 2), 255)
    invalid.save(tmp_path / "wrong.png")
    with pytest.raises(ValueError, match="object_layers_mask_size_mismatch"):
        compose_visible_object_layers(
            project_root=tmp_path, image_path="photo.png",
            object_masks=[("obj", "wrong.png")],
            approved_read=True,
        )
    with pytest.raises(ValueError, match="object_layers_path_denied"):
        compose_visible_object_layers(
            project_root=tmp_path, image_path="photo.png",
            object_masks=[("obj", "../another_mask.png")],
            approved_read=True,
        )


def test_discard_empty_mask_no_false_claim(tmp_path: Path) -> None:
    Image = pytest.importorskip("PIL.Image")
    _test_images(tmp_path)
    Image.new("L", (4, 3), 0).save(tmp_path / "blank.png")
    with pytest.raises(ValueError, match="object_layers_empty_or_fully_occluded_object"):
        compose_visible_object_layers(
            project_root=tmp_path, image_path="photo.png",
            object_masks=[("blank_object", "blank.png")],
            approved_read=True,
        )


def test_dry_run_and_no_permission_cli(capsys: pytest.CaptureFixture[str]) -> None:
    args = ["--image", "unavailable.png", "--mask", "obj=mask.png"]
    assert main([*args, "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["files_read"] is False
    assert main(args) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "blocked"
    assert result["files_written"] is False
