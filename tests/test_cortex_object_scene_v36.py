"""Tests: V36 object scene contracts, source lineage, isolation, and spatial uncertainty."""
import hashlib

import pytest

from hex_cortex.memory.cortex_object_scene_v36 import (
    audit_scene_split_independence,
    build_object_scene_evidence,
)


def _h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _packet(*, split="train", group="sourceA", image="imageA", generated=False):
    return build_object_scene_evidence(
        scene_id="sceneA", source_image_sha256=_h(image),
        canvas_size=(100, 100), source_event_ids=["evt1"],
        source_group=group, split=split, generated=generated,
        objects=[
            {
                "object_id": "cup", "bbox": [10, 10, 30, 40],
                "visible_mask_sha256": _h("cup-mask"), "label": "cup",
                "label_source": "operator", "label_confidence": 1.0,
            },
            {
                "object_id": "book", "bbox": [40, 10, 80, 40],
                "visible_mask_sha256": _h("book-mask"), "label": "book",
                "label_source": "model", "label_confidence": 0.7,
            },
        ],
    )


def test_scene_spatial_relations_lineage_and_reproducible_hash():
    a = _packet()
    assert a == _packet()
    assert a["packet_sha256"] == _packet()["packet_sha256"]
    assert a["evidence_type"] == "observed_metadata"
    assert a["model_called"] is False
    assert {
        "subject_id": "cup", "predicate": "left_of", "object_id": "book"
    } in a["relations_2d_bbox_only"]
    assert a["objects"][0]["occluded_area_unknown"] is True


def test_generated_hypotheses_never_become_observations():
    a = _packet(generated=True)
    assert a["evidence_type"] == "generated_hypothesis"
    assert all(o["generated"] for o in a["objects"])


@pytest.mark.parametrize("field,value,expected", [
    ("label_confidence", float("nan"), "confidence"),
    ("label_confidence", 1.5, "confidence"),
    ("bbox", [1, 1, 101, 2], "bbox_out_of_bounds"),
    ("visible_mask_sha256", "not-a-hash", "mask_hash"),
    ("object_id", "../bad", "object_id"),
])
def test_invalid_object_fails_closed(field, value, expected):
    item = {
        "object_id": "cup", "bbox": [10, 10, 30, 40],
        "visible_mask_sha256": _h("mask"),
        "label": "cup", "label_source": "operator",
        "label_confidence": 0.9,
    }
    item[field] = value
    with pytest.raises(ValueError, match=expected):
        build_object_scene_evidence(
            scene_id="scene1", source_image_sha256=_h("scene1"),
            canvas_size=(100, 100), objects=[item],
            source_event_ids=["evt1"], source_group="episode1",
            split="test",
        )


def test_split_audit_catches_exact_group_and_image_cross_contamination():
    a = _packet(split="train", group="one", image="same")
    b = _packet(split="test", group="one", image="same")
    report = audit_scene_split_independence([a, b])
    assert report["status"] == "split_conflict"
    assert report["source_group_cross_split_count"] == 1
    assert report["exact_image_cross_split_count"] == 1
    assert report["independent_generalization_attested"] is False


def test_distinct_source_groups_and_images_are_only_necessary_check():
    a = _packet(split="train", group="one", image="photo1")
    b = _packet(split="test", group="two", image="photo2")
    report = audit_scene_split_independence([a, b])
    assert report["status"] == "no_exact_split_conflict_detected"
    assert report["independent_generalization_attested"] is False


def test_duplicate_ids_or_no_lineage_refused():
    a = _packet()
    with pytest.raises(ValueError, match="event_lineage_required"):
        build_object_scene_evidence(
            scene_id="x", source_image_sha256=_h("x"),
            canvas_size=(100, 100), objects=a["objects"],
            source_event_ids=[], source_group="g", split="test",
        )
    with pytest.raises(ValueError, match="duplicate_object_id"):
        build_object_scene_evidence(
            scene_id="x", source_image_sha256=_h("x"),
            canvas_size=(100, 100), objects=[a["objects"][0]] * 2,
            source_event_ids=["evt"], source_group="g", split="test",
        )
