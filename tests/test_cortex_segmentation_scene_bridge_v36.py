"""V36-C cross-module integration: masks to scene graph, audit, and fail-closed."""
from __future__ import annotations

import hashlib

import pytest

from hex_cortex.memory.cortex_segmentation_scene_bridge_v36 import (
    build_scene_from_cpu_masks,
)
from hex_cortex.memory.cortex_object_scene_v36 import (
    audit_scene_split_independence,
)


def _sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _receipt():
    return {
        "status": "segmented_cpu_masks_ready",
        "provider": "injected_test_provider",
        "source_sha256": _sha("image-1"),
        "image_size": [128, 90],
        "gpu_used": False,
        "original_image_modified": False,
        "objects": [
            {
                "object_id": "cup",
                "bbox": [2, 3, 31, 40],
                "mask_sha256": _sha("cup-mask"),
                "visible_pixel_count": 99,
                "prompt_type": "operator_box",
                "reference_iou": 0.75,
            },
            {
                "object_id": "book",
                "bbox": [50, 3, 92, 70],
                "mask_sha256": _sha("book-mask"),
                "visible_pixel_count": 200,
                "prompt_type": "operator_box",
                "reference_iou": None,
            },
        ],
    }


def _build(receipt=None, **overrides):
    args = dict(
        segmentation_receipt=receipt if receipt is not None else _receipt(),
        scene_id="scene1", source_group="capture1",
        split="test", source_event_ids=["evt1"],
        object_labels={"cup": "cup", "book": "book"},
    )
    args.update(overrides)
    return build_scene_from_cpu_masks(**args)


def test_receipt_converts_to_scene_and_relations_without_promoting():
    result = _build()
    assert result == _build()
    assert result["model_called"] is False
    assert result["files_written"] is False
    assert result["spine_event_lineage_independently_verified"] is False
    assert result["real_model_run_independently_attested"] is False
    scene = result["scene"]
    assert scene["source_event_ids"] == ["evt1"]
    assert scene["source_image_sha256"] == _sha("image-1")
    assert scene["evidence_type"] == "observed_metadata"
    assert {obj["object_id"] for obj in scene["objects"]} == {"cup", "book"}
    assert {
        "subject_id": "cup", "predicate": "left_of", "object_id": "book"
    } in scene["relations_2d_bbox_only"]


@pytest.mark.parametrize(("corruption", "expected"), [
    ({"status": "blocked"}, "no_successful_segmentation"),
    ({"provider": "untrusted"}, "provider_unknown"),
    ({"gpu_used": True}, "gpu_claim_invalid"),
    ({"original_image_modified": True}, "source_modified"),
    ({"image_size": [0, 0]}, "canvas_invalid"),
])
def test_receipt_cannot_silently_override_metadata(corruption, expected):
    item = _receipt()
    item.update(corruption)
    with pytest.raises(ValueError, match=expected):
        _build(item)


def test_forged_reference_quality_and_missing_label_rejected():
    item = _receipt()
    item["objects"][0]["reference_iou"] = float("nan")
    with pytest.raises(ValueError, match="reference_iou_invalid"):
        _build(item)
    with pytest.raises(ValueError, match="label_missing"):
        _build(object_labels={"book": "book"})


def test_source_group_leakage_detected_after_bridge():
    a = _build(split="train")
    b = _build(split="test", scene_id="scene2")
    report = audit_scene_split_independence([a["scene"], b["scene"]])
    assert report["status"] == "split_conflict"
    assert report["independent_generalization_attested"] is False


def test_real_cpu_road_with_injected_model_and_pillow(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    from hex_cortex.memory.cortex_cpu_segmentation_v36 import segment_boxes_cpu_v36
    Image.new("RGB", (12, 10), (100, 60, 10)).save(tmp_path / "photo.png")
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"test-only")
    sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    mask = Image.new("L", (12, 10), 0)
    for x in (1, 2, 3):
        for y in (1, 2, 3):
            mask.putpixel((x, y), 255)

    def fake_cpu(image, boxes, weights):
        assert image.size == (12, 10)
        assert boxes["cup"] == (1, 1, 4, 4)
        return {"cup": mask}

    receipt = segment_boxes_cpu_v36(
        project_root=tmp_path, image_path="photo.png",
        checkpoint_path="model.pt", checkpoint_sha256=sha,
        object_boxes={"cup": (1, 1, 4, 4)},
        approved_read=True, approved_model_load=True, _infer=fake_cpu,
    )
    result = _build(
        receipt, scene_id="photoA", source_group="episodeA",
        object_labels={"cup": "cup"},
    )
    assert result["scene"]["objects"][0]["visible_mask_sha256"] == receipt["objects"][0]["mask_sha256"]
    assert result["real_model_run_independently_attested"] is False
    assert result["model_promoted"] is False
