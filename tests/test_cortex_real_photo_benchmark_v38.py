"""V38 real-image evaluation rails: no fabricated generalization evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_real_photo_benchmark_cli_v38 import main
from hex_cortex.memory.cortex_real_photo_benchmark_v38 import (
    evaluate_real_photo_masks_v38,
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sample(root: Path, index: int, group: str | None = None, split="test") -> dict:
    Image = pytest.importorskip("PIL.Image")
    from PIL import ImageDraw
    image = Image.new("RGB", (20, 16), (30 + index, 40 + index, 50 + index))
    truth = Image.new("L", image.size, 0)
    ImageDraw.Draw(image).rectangle((2, 3, 7, 9), fill=(240, 40, 20))
    ImageDraw.Draw(truth).rectangle((2, 3, 7, 9), fill=255)
    image.save(root / f"photo{index}.png")
    truth.save(root / f"mask{index}.png")
    return {
        "scene_id": f"scene{index}",
        "source_kind": "operator_real_photo",
        "source_group": group or f"group{index}",
        "split": split,
        "image": f"photo{index}.png",
        "objects": [{
            "object_id": "object1", "box": [1, 2, 9, 11],
            "reference_mask": f"mask{index}.png",
        }],
    }


def _manifest(root: Path, samples: list[dict]):
    (root / "manifest.json").write_text(
        json.dumps({"schema": "hex.real_photo_benchmark.v38", "samples": samples}),
        encoding="utf-8",
    )


def _run(root: Path, *, preflight_only=True, approved_read=True, approved_model_load=False,
         infer=None):
    return evaluate_real_photo_masks_v38(
        project_root=root, manifest_path="manifest.json",
        checkpoint_path="checkpoint.pt", checkpoint_sha256=_sha(b"model"),
        approved_read=approved_read, approved_model_load=approved_model_load,
        preflight_only=preflight_only, _infer=infer,
    )


def test_denied_without_permission_does_not_read(tmp_path):
    result = _run(tmp_path, approved_read=False)
    assert result["status"] == "blocked"
    assert result["model_called"] is False
    assert not list(tmp_path.iterdir())


def test_preflight_single_real_photo_labeled_preliminary(tmp_path):
    pytest.importorskip("PIL.Image")
    _manifest(tmp_path, [_sample(tmp_path, 1)])
    result = _run(tmp_path)
    assert result["status"] == "manifest_preflight_pass"
    assert result["model_called"] is False
    assert result["annotated_object_count"] == 1
    assert result["minimum_10_distinct_source_groups_met"] is False
    assert result["independent_generalization_attested"] is False


def test_true_cpu_segmentation_adapter_e2e_iou_with_injected_backend(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    (tmp_path / "checkpoint.pt").write_bytes(b"model")
    _manifest(tmp_path, [_sample(tmp_path, 2)])
    expected = Image.open(tmp_path / "mask2.png").copy()
    def offline_inference(image, boxes, checkpoint):
        assert image.size == (20, 16)
        assert boxes == {"object1": (1, 2, 9, 11)}
        assert checkpoint.name == "checkpoint.pt"
        return {"object1": expected}
    output = _run(
        tmp_path, preflight_only=False, approved_model_load=True,
        infer=offline_inference,
    )
    assert output["status"] == "operator_real_photo_benchmark_executed"
    assert output["provider"] == "test_injected_provider"
    assert output["actual_mobile_sam_inference_called"] is False
    assert output["mean_operator_reference_iou"] == 1.0
    assert output["p50_per_photo_ms_including_model_load"] >= 0
    assert output["model_promoted"] is False
    assert output["files_written"] is False
    assert output["independent_visual_generalization_attested"] is False
    assert output["preflight"]["source_group_count"] == 1


def test_checkpoint_approval_gate_never_opens_file(tmp_path):
    _manifest(tmp_path, [{"bad": "sample"}])
    denied = _run(tmp_path, preflight_only=False, approved_model_load=False)
    assert denied["status"] == "blocked"
    assert denied["files_read"] is False


def test_duplicate_image_refused_even_with_distinct_scenes(tmp_path):
    pytest.importorskip("PIL.Image")
    a = _sample(tmp_path, 1)
    b = _sample(tmp_path, 2)
    b["image"] = a["image"]
    _manifest(tmp_path, [a, b])
    with pytest.raises(ValueError, match="v38_exact_duplicate_photo_denied"):
        _run(tmp_path)


def test_source_group_cross_split_rejected(tmp_path):
    pytest.importorskip("PIL.Image")
    a = _sample(tmp_path, 1, group="same_source", split="train")
    b = _sample(tmp_path, 2, group="same_source", split="test")
    _manifest(tmp_path, [a, b])
    with pytest.raises(ValueError, match="v38_cross_split_source_contamination"):
        _run(tmp_path)


def test_ten_distinct_groups_is_necessary_but_not_independent_attestation(tmp_path):
    pytest.importorskip("PIL.Image")
    samples = [_sample(tmp_path, i) for i in range(10)]
    _manifest(tmp_path, samples)
    result = _run(tmp_path)
    assert result["sample_count"] == 10
    assert result["source_group_count"] == 10
    assert result["minimum_10_distinct_source_groups_met"] is True
    assert result["independent_generalization_attested"] is False
    assert result["near_duplicate_and_semantic_leakage_checked"] is False


def test_path_traversal_and_invalid_manual_mask_dimensions_denied(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    sample = _sample(tmp_path, 1)
    sample["image"] = "../outside.png"
    _manifest(tmp_path, [sample])
    with pytest.raises(ValueError, match="v38_path_denied"):
        _run(tmp_path)
    sample["image"] = "photo1.png"
    Image.new("L", (5, 5), 255).save(tmp_path / "mask1.png")
    _manifest(tmp_path, [sample])
    with pytest.raises(ValueError, match="v38_reference_dimensions_invalid"):
        _run(tmp_path)


def test_manifest_must_be_operator_real_not_synthetic(tmp_path):
    pytest.importorskip("PIL.Image")
    sample = _sample(tmp_path, 1)
    sample["source_kind"] = "synthetic"
    _manifest(tmp_path, [sample])
    with pytest.raises(ValueError, match="v38_operator_real_photo_declaration_required"):
        _run(tmp_path)


def test_nonfinite_and_duplicate_json_keys_denied(tmp_path):
    (tmp_path / "manifest.json").write_text('{"schema":"hex.real_photo_benchmark.v38","samples":NaN}')
    with pytest.raises(ValueError, match="v38_nonfinite_json_denied"):
        _run(tmp_path)
    (tmp_path / "manifest.json").write_text('{"schema":"a","schema":"b","samples":[]}')
    with pytest.raises(ValueError, match="v38_duplicate_json_key_denied"):
        _run(tmp_path)


def test_cli_dry_run_and_denied_not_read(capsys):
    args = [
        "--manifest", "does-not-exist.json", "--checkpoint", "missing.pt",
        "--checkpoint-sha256", "0" * 64,
    ]
    assert main([*args, "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["model_called"] is False
    assert main(args) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "v38_read_approval_required"
