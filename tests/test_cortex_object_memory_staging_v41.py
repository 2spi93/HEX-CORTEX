"""V41 stage (not promote) pixels from V40: integrity, no writes, no fake events."""
from __future__ import annotations

import json

import pytest

from hex_cortex.memory.cortex_mask_visual_inspection_v40 import (
    export_verified_v40_masks,
)
from hex_cortex.memory.cortex_object_memory_staging_v41 import (
    stage_verified_object_candidates_v41,
)
from test_cortex_mask_visual_inspection_v40 import _fixtures


def _valid_inspection(root):
    sha, old, mask = _fixtures(root)

    def predicted(image, boxes, checkpoint):
        assert image.size == (20, 16)
        return {"object1": mask}

    output = export_verified_v40_masks(
        project_root=root, checkpoint_path="weights/model.pt",
        checkpoint_sha256=sha, approved_read=True,
        approved_model_load=True, approved_write=True,
        _infer=predicted,
    )
    path = root / output["new_output_dir"] / "inspection.json"
    # Fixture simulates the real provider's receipt: this test does NOT
    # claim a real MobileSAM run occurred in CI.
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["provider"] = "mobile_sam_vit_t_cpu"
    obj["model_called"] = True
    path.write_text(json.dumps(obj), encoding="utf-8")
    return output, path


def test_permission_gate_prevents_file_reads_and_writes(tmp_path):
    result = stage_verified_object_candidates_v41(project_root=tmp_path)
    assert result["status"] == "blocked"
    assert result["files_read"] is False
    assert result["files_written"] is False
    assert not list(tmp_path.iterdir())


def test_verified_v40_pixels_become_pending_not_promoted(tmp_path):
    pytest.importorskip("PIL.Image")
    output, _ = _valid_inspection(tmp_path)
    result = stage_verified_object_candidates_v41(
        project_root=tmp_path, approved_read=True,
    )
    assert result["status"] == "verified_pixels_pending_memory_lineage"
    assert result["scene_count"] == 3
    assert result["verified_object_masks"] == 3
    assert result["files_written"] is False
    assert result["model_called"] is False
    assert result["human_reference_iou_available"] is False
    assert result["same_object_across_frames_verified"] is False
    assert result["canonical_spine_lineage_verified"] is False
    assert result["promotion_to_long_term_memory_permitted"] is False
    assert all(obj["canonical_spine_event_id"] is None for obj in result["candidates"])
    assert all(obj["scene_object_id_scope"] == "single_image_only" for obj in result["candidates"])
    assert all(obj["visible_mask_pixels"] == 25 for obj in result["candidates"])
    assert (tmp_path / output["new_output_dir"] / "inspection.json").exists()


def test_mask_pixel_tampering_fails_even_when_png_valid(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    output, _ = _valid_inspection(tmp_path)
    candidate = output["records"][0]["objects"][0]["mask_png"]
    path = tmp_path / candidate
    with Image.open(path) as source:
        mask = source.convert("L")
    mask.putpixel((3, 3), 0)
    mask.save(path)
    with pytest.raises(ValueError, match="v41_prediction_pixel_integrity_failed"):
        stage_verified_object_candidates_v41(project_root=tmp_path, approved_read=True)


def test_forged_quality_or_model_claims_rejected(tmp_path):
    pytest.importorskip("PIL.Image")
    _, path = _valid_inspection(tmp_path)
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["mean_reference_iou"] = 0.99
    path.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ValueError, match="v41_inspection_contract_invalid"):
        stage_verified_object_candidates_v41(project_root=tmp_path, approved_read=True)


def test_inspection_file_claim_outside_run_rejected(tmp_path):
    pytest.importorskip("PIL.Image")
    _, path = _valid_inspection(tmp_path)
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["records"][0]["objects"][0]["mask_png"] = (
        "receipts/v40_mask_inspection/run-20261013T120000-000000Z/other.png"
    )
    path.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ValueError, match="v39_file_denied|v41_mask_path_not_bound_to_run"):
        stage_verified_object_candidates_v41(project_root=tmp_path, approved_read=True)
