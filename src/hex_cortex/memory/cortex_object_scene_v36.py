"""V36: object-centric scene evidence. Metadata only; no model or file access.

Observed and generated evidence remain separate. Spatial relations are
computed only from visible 2D bounding boxes; they are NOT 3D physics.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")
_SHA = re.compile(r"[0-9a-f]{64}")
_SPLITS = frozenset({"train", "validation", "test"})


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"object_scene_{field}_invalid")
    return value


def _hash(value: object, field: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError(f"object_scene_{field}_invalid")
    return value


def _bbox(value: object, width: int, height: int) -> tuple[int, int, int, int]:
    if (
        not isinstance(value, (list, tuple)) or len(value) != 4
        or any(type(v) is not int for v in value)
    ):
        raise ValueError("object_scene_bbox_invalid")
    x1, y1, x2, y2 = value
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError("object_scene_bbox_out_of_bounds")
    return x1, y1, x2, y2


def _relations(first: dict, second: dict) -> list[str]:
    ax1, ay1, ax2, ay2 = first["bbox"]
    bx1, by1, bx2, by2 = second["bbox"]
    result: list[str] = []
    if ax2 <= bx1:
        result.append("left_of")
    if ay2 <= by1:
        result.append("above")
    if ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2:
        result.append("bbox_overlaps")
    return result


def build_object_scene_evidence(
    *,
    scene_id: str,
    source_image_sha256: str,
    canvas_size: tuple[int, int],
    objects: list[dict],
    source_event_ids: list[str],
    source_group: str,
    split: str,
    generated: bool = False,
) -> dict:
    """Create a canonical, bounded read-only packet; no implicit persistence."""
    _identifier(scene_id, "id")
    _hash(source_image_sha256, "image_hash")
    _identifier(source_group, "source_group")
    if split not in _SPLITS:
        raise ValueError("object_scene_split_invalid")
    if (
        not isinstance(canvas_size, tuple) or len(canvas_size) != 2
        or any(type(v) is not int or v <= 0 for v in canvas_size)
        or canvas_size[0] * canvas_size[1] > 16_000_000
    ):
        raise ValueError("object_scene_canvas_invalid")
    if not isinstance(objects, list) or not 1 <= len(objects) <= 24:
        raise ValueError("object_scene_object_count_invalid")
    if (
        not isinstance(source_event_ids, list)
        or not 1 <= len(source_event_ids) <= 32
        or len(set(source_event_ids)) != len(source_event_ids)
    ):
        raise ValueError("object_scene_event_lineage_required")
    events = [_identifier(event, "event_id") for event in source_event_ids]
    if type(generated) is not bool:
        raise ValueError("object_scene_generated_flag_invalid")
    normal: list[dict] = []
    seen: set[str] = set()
    for item in objects:
        if not isinstance(item, dict):
            raise ValueError("object_scene_object_invalid")
        obj_id = _identifier(item.get("object_id"), "object_id")
        if obj_id in seen:
            raise ValueError("object_scene_duplicate_object_id")
        seen.add(obj_id)
        box = _bbox(item.get("bbox"), *canvas_size)
        mask_hash = _hash(item.get("visible_mask_sha256"), "mask_hash")
        label = item.get("label")
        if not isinstance(label, str) or not 1 <= len(label) <= 100:
            raise ValueError("object_scene_label_invalid")
        label_source = item.get("label_source")
        if label_source not in ("operator", "model", "unknown"):
            raise ValueError("object_scene_label_source_invalid")
        score = item.get("label_confidence")
        if type(score) not in (float, int) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("object_scene_confidence_invalid")
        normal.append({
            "object_id": obj_id,
            "bbox": list(box),
            "visible_mask_sha256": mask_hash,
            "label": label,
            "label_source": label_source,
            "label_confidence": float(score),
            "occluded_area_unknown": True,
            "generated": generated,
        })
    normal.sort(key=lambda o: o["object_id"])
    relations = [
        {"subject_id": a["object_id"], "predicate": relation, "object_id": b["object_id"]}
        for a in normal for b in normal if a is not b
        for relation in _relations(a, b)
    ]
    packet = {
        "schema": "hex.object_scene.v36",
        "scene_id": scene_id,
        "source_image_sha256": source_image_sha256,
        "source_group": source_group,
        "split": split,
        "canvas_size": list(canvas_size),
        "evidence_type": "generated_hypothesis" if generated else "observed_metadata",
        "objects": normal,
        "relations_2d_bbox_only": relations,
        "source_event_ids": events,
        "files_written": False,
        "model_called": False,
        "physical_action_executed": False,
    }
    packet["packet_sha256"] = hashlib.sha256(
        json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return packet


def audit_scene_split_independence(packets: list[dict]) -> dict:
    """Reject exact image or source-group overlap between dataset splits.

    This is a necessary check, NOT proof of near-duplicate or causal
    independence. Returns no raw image references.
    """
    if not isinstance(packets, list) or not packets:
        raise ValueError("object_scene_audit_requires_packets")
    by_group: dict[str, set[str]] = {}
    by_image: dict[str, set[str]] = {}
    for item in packets:
        if not isinstance(item, dict) or item.get("schema") != "hex.object_scene.v36":
            raise ValueError("object_scene_audit_schema_invalid")
        group = _identifier(item.get("source_group"), "source_group")
        image = _hash(item.get("source_image_sha256"), "image_hash")
        split = item.get("split")
        if split not in _SPLITS:
            raise ValueError("object_scene_split_invalid")
        by_group.setdefault(group, set()).add(split)
        by_image.setdefault(image, set()).add(split)
    leaked_groups = sum(len(value) > 1 for value in by_group.values())
    leaked_images = sum(len(value) > 1 for value in by_image.values())
    return {
        "status": "split_conflict" if leaked_groups or leaked_images else "no_exact_split_conflict_detected",
        "independent_generalization_attested": False,
        "source_group_cross_split_count": leaked_groups,
        "exact_image_cross_split_count": leaked_images,
        "scene_count": len(packets),
        "source_group_count": len(by_group),
        "reason": "near_duplicates_and_shared_semantic_sources_not_checked",
    }
