"""V36-C CLI evidence input permissions and redacted errors."""
from __future__ import annotations

import hashlib
import json

from hex_cortex.memory.cortex_segmentation_scene_bridge_cli_v36 import main


def _sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def _args(root):
    return [
        "--project-root", str(root), "--receipt", "receipt.json",
        "--scene-id", "scene1", "--source-group", "session1",
        "--split", "test", "--label", "cup=cup",
        "--source-event-id", "evt1",
    ]


def test_no_permission_no_read(tmp_path, capsys):
    assert main(_args(tmp_path)) == 2
    assert json.loads(capsys.readouterr().out)["files_read"] is False
    assert main([*_args(tmp_path), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["files_read"] is False


def test_approved_valid_saved_segmentation_receipt(tmp_path, capsys):
    record = {
        "status": "segmented_cpu_masks_ready",
        "provider": "mobile_sam_vit_t_cpu", "gpu_used": False,
        "original_image_modified": False, "image_size": [20, 20],
        "source_sha256": _sha("photo"),
        "objects": [{
            "object_id": "cup", "bbox": [1, 1, 5, 6],
            "mask_sha256": _sha("mask"), "visible_pixel_count": 8,
            "prompt_type": "operator_box", "reference_iou": None,
        }],
    }
    (tmp_path / "receipt.json").write_text(json.dumps(record), encoding="utf-8")
    assert main([*_args(tmp_path), "--approve-read"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "v36_cpu_segmentation_scene_built"
    assert result["model_called"] is False
    assert result["reported_provider"] == "mobile_sam_vit_t_cpu"
    assert result["real_model_run_independently_attested"] is False
    assert result["scene"]["source_event_ids"] == ["evt1"]


def test_unsafe_path_and_bad_json_are_rejected(tmp_path, capsys):
    args = _args(tmp_path)
    args[args.index("--receipt") + 1] = "../secret.json"
    assert main([*args, "--approve-read"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "v36_bridge_receipt_path_denied"
    (tmp_path / "receipt.json").write_text('{"value":NaN}', encoding="utf-8")
    assert main([*_args(tmp_path), "--approve-read"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"
