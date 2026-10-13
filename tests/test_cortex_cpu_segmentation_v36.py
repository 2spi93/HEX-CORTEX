"""V36-A CPU provider: synthetic adapter tests, not real MobileSAM validation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_cpu_segmentation_cli_v36 import main
from hex_cortex.memory.cortex_cpu_segmentation_v36 import segment_boxes_cpu_v36


def _dataset(root: Path):
    Image = pytest.importorskip("PIL.Image")
    image = Image.new("RGB", (8, 6), (11, 22, 33))
    image.save(root / "scene.png")
    mask = Image.new("L", (8, 6), 0)
    for x in (1, 2):
        for y in (1, 2):
            mask.putpixel((x, y), 255)
    mask.save(root / "gold.png")
    (root / "trusted-model.pt").write_bytes(b"test-only-not-real-weights")
    sha = hashlib.sha256((root / "trusted-model.pt").read_bytes()).hexdigest()
    return mask, sha


def _params(root: Path, digest: str):
    return {
        "project_root": root,
        "image_path": "scene.png",
        "checkpoint_path": "trusted-model.pt",
        "checkpoint_sha256": digest,
        "object_boxes": {"cup": (1, 1, 3, 3)},
    }


def test_no_read_or_model_without_approval(tmp_path: Path):
    _, digest = _dataset(tmp_path)
    params = _params(tmp_path, digest)
    denied = segment_boxes_cpu_v36(**params)
    assert denied["status"] == "blocked"
    assert denied["files_read"] is False
    denied = segment_boxes_cpu_v36(**params, approved_read=True)
    assert denied["reason"] == "v36_checkpoint_load_approval_required"


def test_injected_mask_exact_iou_and_no_implicit_file_writes(tmp_path: Path):
    mask, digest = _dataset(tmp_path)
    def fake_backend(image, boxes, checkpoint):
        assert image.size == (8, 6)
        assert boxes["cup"] == (1, 1, 3, 3)
        assert checkpoint.name == "trusted-model.pt"
        return {"cup": mask}
    params = _params(tmp_path, digest)
    receipt = segment_boxes_cpu_v36(
        **params, reference_masks={"cup": "gold.png"},
        approved_read=True, approved_model_load=True,
        _infer=fake_backend,
    )
    assert receipt["status"] == "segmented_cpu_masks_ready"
    assert receipt["provider"] == "injected_test_provider"
    assert receipt["model_called"] is False
    assert receipt["gpu_used"] is False
    assert receipt["objects"][0]["reference_iou"] == 1.0
    assert receipt["objects"][0]["visible_pixel_count"] == 4
    assert receipt["files_written"] is False
    assert not (tmp_path / "out").exists()


def test_export_needs_explicit_write_and_never_overwrites(tmp_path: Path):
    mask, digest = _dataset(tmp_path)
    params = _params(tmp_path, digest)
    def infer(image, boxes, checkpoint):
        return {"cup": mask}
    result = segment_boxes_cpu_v36(
        **params, approved_read=True, approved_model_load=True,
        export_dir="out", _infer=infer,
    )
    assert result["status"] == "blocked"
    assert result["files_read"] is False
    result = segment_boxes_cpu_v36(
        **params, approved_read=True, approved_model_load=True,
        export_dir="out", approved_write=True, _infer=infer,
    )
    assert result["files_written"] is True
    assert (tmp_path / "out" / "cup.png").is_file()
    with pytest.raises(ValueError, match="v36_export_existing_path_denied"):
        segment_boxes_cpu_v36(
            **params, approved_read=True, approved_model_load=True,
            export_dir="out", approved_write=True, _infer=infer,
        )


def test_checkpoint_hash_fail_closed_before_model_call(tmp_path: Path):
    mask, _ = _dataset(tmp_path)
    called = []
    def backend(*args):
        called.append(True)
        return {"cup": mask}
    params = _params(tmp_path, "0" * 64)
    with pytest.raises(ValueError, match="v36_checkpoint_digest_mismatch"):
        segment_boxes_cpu_v36(
            **params, approved_read=True, approved_model_load=True, _infer=backend,
        )
    assert called == []


def test_path_traversal_and_box_bounds_denied(tmp_path: Path):
    mask, digest = _dataset(tmp_path)
    params = _params(tmp_path, digest)
    params["image_path"] = "../outside.png"
    with pytest.raises(ValueError, match="v36_path_denied"):
        segment_boxes_cpu_v36(
            **params, approved_read=True, approved_model_load=True,
            _infer=lambda *args: {"cup": mask},
        )
    params["image_path"] = "scene.png"
    params["object_boxes"] = {"cup": (0, 0, 99, 99)}
    with pytest.raises(ValueError, match="v36_box_bounds_invalid"):
        segment_boxes_cpu_v36(
            **params, approved_read=True, approved_model_load=True,
            _infer=lambda *args: {"cup": mask},
        )


def test_cli_dry_run_never_reads_or_loads(capsys):
    rc = main([
        "--image", "not-there.png", "--checkpoint", "not-there.pt",
        "--checkpoint-sha256", "0" * 64, "--box", "cup=1,1,2,2",
        "--dry-run",
    ])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["files_read"] is False
    assert report["model_called"] is False


def test_cli_no_approval_denied(capsys):
    rc = main([
        "--image", "not-there.png", "--checkpoint", "not-there.pt",
        "--checkpoint-sha256", "0" * 64, "--box", "cup=1,1,2,2",
    ])
    assert rc == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "v36_image_read_approval_required"
