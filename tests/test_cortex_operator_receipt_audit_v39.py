"""Read-only V39 exact evidence consistency, refusals and local lineage limits."""
from __future__ import annotations

import hashlib
import json

import pytest

from hex_cortex.memory.cortex_operator_receipt_audit_cli_v39 import main
from hex_cortex.memory.cortex_operator_receipt_audit_v39 import (
    audit_uploaded_v38_receipts_v39,
)

MODEL_SHA = "6dbb90523a35330fedd7f1d3dfc66f995213d81b29a5ca8108dbcdd4e37d6c2f"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _save(file, doc):
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def _fixtures(root):
    photos = []
    rows = []
    run_rel = "receipts/v38_uploaded_exploration/run-20261013T173800-031171Z"
    for i in range(1, 14):
        scene_id = f"scene{i:02d}_sample"
        image = f"images/v38_uploaded/{scene_id}.jpg"
        blob = f"local_photo_{i}".encode()
        image_path = root / image
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(blob)
        boxes = [{"object_id": "item", "bbox": [1, 2, 10, 11]}]
        photos.append({
            "scene_id": scene_id,
            "type": "photographic" if i <= 9 else "graphic",
            "relative_image": image,
            "width": 100, "height": 80,
            "sha256": _sha(blob),
            "boxes": boxes,
        })
        if i > 9:
            continue
        receipt = {
            "status": "segmented_cpu_masks_ready",
            "provider": "mobile_sam_vit_t_cpu",
            "model_called": True, "gpu_used": False,
            "files_written": False, "original_image_modified": False,
            "checkpoint_sha256": MODEL_SHA,
            "source_sha256": _sha(blob),
            "image_size": [100, 80],
            "inference_ms": float(500 + i),
            "objects": [{
                "object_id": "item", "bbox": [1, 2, 10, 11],
                "prompt_type": "operator_box", "visible_pixel_count": i * 20,
                "mask_sha256": _sha(f"mask{i}".encode()),
                "reference_iou": None,
            }],
        }
        _save(root / run_rel / f"{scene_id}.json", receipt)
        rows.append({
            "scene_id": scene_id, "input_kind": "photographic",
            "model_ms_with_reload": float(500 + i),
            "boxes_count": 1, "per_object_pixels": {"item": i * 20},
            "reference_iou": None,
            "receipt_path": f"{run_rel}/{scene_id}.json",
        })
    _save(root / "research/v38_uploaded/boxes.json", {
        "schema": "hex.v38.operator_uploaded_box_exploration.v1",
        "checkpoint_sha256": MODEL_SHA, "samples": photos,
    })
    _save(root / run_rel / "summary.json", {
        "schema": "hex.v38.operator_uploaded_exploration_summary.v1",
        "status": "completed", "real_cpu_model_executed": True,
        "gpu_used": False, "ground_truth_annotation_present": False,
        "mean_reference_iou": None, "world_model_generalization_attested": False,
        "sample_results": rows,
    })
    return run_rel


def test_denied_before_any_file_read(tmp_path):
    result = audit_uploaded_v38_receipts_v39(project_root=tmp_path)
    assert result["status"] == "blocked"
    assert result["files_read"] is False
    assert not list(tmp_path.iterdir())


def test_nine_photo_receipts_and_candidates_verified_not_promoted(tmp_path):
    run = _fixtures(tmp_path)
    result = audit_uploaded_v38_receipts_v39(
        project_root=tmp_path, run_selection=run, approved_read=True,
    )
    assert result["status"] == "v39_receipt_consistency_pass"
    assert result["photographic_scenes_consistent"] == 9
    assert result["operator_prompted_objects_consistent"] == 9
    assert result["inference_ms_observed_min"] == 501
    assert result["inference_ms_observed_max"] == 509
    assert result["source_content_hashes_verified_locally"] is True
    assert result["original_segmentation_pixels_available_in_receipts"] is False
    assert result["quality_iou_estimated"] is False
    assert result["generalization_attested"] is False
    assert result["canonical_spine_event_lineage_verified"] is False
    assert result["model_called"] is False
    assert result["files_written"] is False
    assert all(not o["persistable_object_memory_verified"] for o in result["object_candidates"])


def test_latest_run_cli_and_dry_run(tmp_path, capsys):
    _fixtures(tmp_path)
    assert main(["--project-root", str(tmp_path), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["files_read"] is False
    assert main(["--project-root", str(tmp_path), "--latest", "--approve-read"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "v39_receipt_consistency_pass"


@pytest.mark.parametrize(("tamper", "expected"), [
    ("image", "v39_photo_hash_mismatch"),
    ("checkpoint", "v39_cpu_receipt_contract_invalid"),
    ("bbox", "v39_object_provenance_invalid"),
    ("mask", "v39_object_provenance_invalid"),
    ("summary", "v39_unexpected_summary_claim"),
])
def test_tampered_data_fail_closed(tmp_path, tamper, expected):
    run = _fixtures(tmp_path)
    file = tmp_path / run / "scene01_sample.json"
    doc = json.loads(file.read_text())
    if tamper == "image":
        (tmp_path / "images/v38_uploaded/scene01_sample.jpg").write_bytes(b"changed")
    elif tamper == "summary":
        s = tmp_path / run / "summary.json"
        summary = json.loads(s.read_text())
        summary["mean_reference_iou"] = 0.95
        _save(s, summary)
    else:
        if tamper == "checkpoint":
            doc["checkpoint_sha256"] = "0" * 64
        elif tamper == "bbox":
            doc["objects"][0]["bbox"] = [1, 2, 20, 20]
        else:
            doc["objects"][0]["mask_sha256"] = "bad"
        _save(file, doc)
    with pytest.raises(ValueError, match=expected):
        audit_uploaded_v38_receipts_v39(
            project_root=tmp_path, run_selection=run, approved_read=True,
        )


def test_refuses_out_of_scope_folder(tmp_path):
    _fixtures(tmp_path)
    with pytest.raises(ValueError, match="v39_run_directory_denied"):
        audit_uploaded_v38_receipts_v39(
            project_root=tmp_path, run_selection="../private",
            approved_read=True,
        )


def test_reports_do_not_create_fake_model_or_memory_attestations(tmp_path):
    _fixtures(tmp_path)
    output = audit_uploaded_v38_receipts_v39(
        project_root=tmp_path, approved_read=True,
    )
    assert output["source_capture_independence_verified"] is False
    assert output["independent_human_reference_masks_available"] is False
    assert output["model_promoted"] is False
    assert output["physical_action_executed"] is False
