"""V40 exact replay proof, overlay exports and non-destructive cleanup."""
from __future__ import annotations

import hashlib
import json

import pytest

from hex_cortex.memory.cortex_mask_visual_inspection_cli_v40 import main
from hex_cortex.memory.cortex_mask_visual_inspection_v40 import (
    export_verified_v40_masks,
)

SCENES = [
    "scene01_conversation", "scene02_auditorium", "scene03_jump",
    "scene04_ropes", "scene05_strength", "scene06_track",
    "scene07_racecar", "scene08_factory_tablet", "scene09_factory_handover",
]


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def _fake_mask():
    Image = pytest.importorskip("PIL.Image")
    from PIL import ImageDraw
    mask = Image.new("L", (20, 16), 0)
    ImageDraw.Draw(mask).rectangle((2, 2, 6, 6), fill=255)
    return mask


def _fixtures(root):
    Image = pytest.importorskip("PIL.Image")
    mask = _fake_mask()
    mask_hash = _digest(mask.tobytes())
    checkpoint = root / "weights/model.pt"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_bytes(b"test-only-model")
    sha = _digest(checkpoint.read_bytes())
    run = "receipts/v38_uploaded_exploration/run-20261013T173800-031171Z"
    samples = []
    rows = []
    for i in range(1, 14):
        scene_id = SCENES[i - 1] if i <= 9 else f"scene{i:02d}_graphic"
        path = root / "images/v38_uploaded" / f"{scene_id}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (20, 16), (10 + i, 50, 100)).save(path)
        source_hash = _digest(path.read_bytes())
        box = [1, 1, 9, 9]
        samples.append({
            "scene_id": scene_id,
            "type": "photographic" if i <= 9 else "illustration",
            "relative_image": str(path.relative_to(root)).replace("\\", "/"),
            "width": 20, "height": 16,
            "sha256": source_hash,
            "boxes": [{"object_id": "object1", "bbox": box}],
        })
        if i > 9:
            continue
        receipt = {
            "status": "segmented_cpu_masks_ready", "provider": "mobile_sam_vit_t_cpu",
            "model_called": True, "gpu_used": False, "files_written": False,
            "original_image_modified": False,
            "source_sha256": source_hash, "checkpoint_sha256": sha,
            "image_size": [20, 16], "inference_ms": float(600 + i),
            "objects": [{
                "object_id": "object1", "bbox": box, "prompt_type": "operator_box",
                "visible_pixel_count": 25, "mask_sha256": mask_hash, "reference_iou": None,
            }],
        }
        _write_json(root / run / f"{scene_id}.json", receipt)
        rows.append({
            "scene_id": scene_id, "input_kind": "photographic",
            "model_ms_with_reload": float(600 + i), "boxes_count": 1,
            "per_object_pixels": {"object1": 25}, "reference_iou": None,
            "receipt_path": f"{run}/{scene_id}.json",
        })
    _write_json(root / "research/v38_uploaded/boxes.json", {
        "schema": "hex.v38.operator_uploaded_box_exploration.v1",
        "checkpoint_sha256": sha, "samples": samples,
    })
    _write_json(root / run / "summary.json", {
        "schema": "hex.v38.operator_uploaded_exploration_summary.v1",
        "status": "completed", "real_cpu_model_executed": True,
        "gpu_used": False, "ground_truth_annotation_present": False,
        "mean_reference_iou": None, "world_model_generalization_attested": False,
        "sample_results": rows,
    })
    return sha, run, mask


def _run(root, sha, *, scenes=None, infer=None, **kwargs):
    return export_verified_v40_masks(
        project_root=root, checkpoint_path="weights/model.pt",
        checkpoint_sha256=sha, scenes=scenes,
        approved_read=True, approved_model_load=True, approved_write=True,
        _infer=infer, **kwargs,
    )


def test_gate_refuses_model_and_file_operations(tmp_path):
    res = export_verified_v40_masks(
        project_root=tmp_path, checkpoint_path="weights/model.pt",
        checkpoint_sha256="0" * 64,
    )
    assert res["status"] == "blocked"
    assert res["files_written"] is False
    assert not list(tmp_path.iterdir())


def test_replay_three_scenes_reproduces_original_mask_and_local_preview(tmp_path):
    sha, previous, mask = _fixtures(tmp_path)
    def predict(image, boxes, ckpt):
        assert image.size == (20, 16)
        assert boxes == {"object1": (1, 1, 9, 9)}
        return {"object1": mask}
    report = _run(tmp_path, sha, infer=predict)
    assert report["status"] == "verified_mask_replay_exported"
    assert report["scene_count"] == 3
    assert report["mask_count"] == 3
    assert report["original_v38_mask_bytes_reproduced"] is True
    assert report["model_called"] is False
    assert report["mean_reference_iou"] is None
    assert report["canon_spine_lineage_verified"] is False
    assert report["source_audit_run"] == previous
    assert all(x["objects"][0]["old_mask_sha256_equal"] for x in report["records"])
    for row in report["records"]:
        obj = row["objects"][0]
        assert (tmp_path / obj["mask_png"]).exists()
        assert (tmp_path / obj["preview_png"]).exists()
    assert (tmp_path / report["new_output_dir"] / "inspection.json").is_file()
    assert (tmp_path / previous / "summary.json").is_file()


def test_mismatched_replay_deletes_only_new_folder(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    sha, old_path, _ = _fixtures(tmp_path)
    def changed_prediction(image, boxes, ckpt):
        return {"object1": Image.new("L", (20, 16), 255)}
    with pytest.raises(ValueError, match="v40_replayed_mask_hash_or_pixel_mismatch"):
        _run(tmp_path, sha, infer=changed_prediction, scenes=["scene07_racecar"])
    parent = tmp_path / "receipts/v40_mask_inspection"
    assert parent.is_dir() and not list(parent.iterdir())
    assert (tmp_path / old_path / "summary.json").is_file()


def test_selection_fail_closed_and_no_write(tmp_path):
    sha, _, mask = _fixtures(tmp_path)
    with pytest.raises(ValueError, match="v40_unrecognized_photo_scene"):
        _run(tmp_path, sha, scenes=["scene13_graphic"], infer=lambda *a: {"object1": mask})
    with pytest.raises(ValueError, match="v40_selection_invalid"):
        _run(tmp_path, sha, scenes=["scene07_racecar"] * 2,
             infer=lambda *a: {"object1": mask})
    assert not (tmp_path / "receipts/v40_mask_inspection").exists()


def test_cli_dry_run(tmp_path, capsys):
    assert main(["--project-root", str(tmp_path), "--checkpoint-sha256", "0" * 64,
                 "--dry-run"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "dry_run"
    assert result["model_called"] is False
    assert result["files_written"] is False
