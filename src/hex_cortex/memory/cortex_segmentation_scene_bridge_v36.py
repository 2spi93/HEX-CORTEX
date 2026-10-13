"""V36-C: normalize CPU box-segmentation receipts into typed object scenes.

This is an evidence adapter, NOT independently attested scene cognition.
Segmentation masks and labels remain predictions/operator assertions.
No file read/write, no model invocation and no new event sourcing store.
"""
from __future__ import annotations

import hashlib
import json
import math

from hex_cortex.memory.cortex_object_scene_v36 import build_object_scene_evidence


def build_scene_from_cpu_masks(
    *,
    segmentation_receipt: dict,
    scene_id: str,
    source_group: str,
    split: str,
    object_labels: dict[str, str],
    source_event_ids: list[str],
    label_source: str = "operator",
) -> dict:
    """Convert bounded model-reported masks to an unpromoted V36-B scene."""
    if not isinstance(segmentation_receipt, dict):
        raise ValueError("v36_bridge_receipt_invalid")
    if segmentation_receipt.get("status") != "segmented_cpu_masks_ready":
        raise ValueError("v36_bridge_no_successful_segmentation")
    if segmentation_receipt.get("provider") not in (
        "mobile_sam_vit_t_cpu", "injected_test_provider",
    ):
        raise ValueError("v36_bridge_provider_unknown")
    if segmentation_receipt.get("gpu_used") is not False:
        raise ValueError("v36_bridge_gpu_claim_invalid")
    if segmentation_receipt.get("original_image_modified") is not False:
        raise ValueError("v36_bridge_source_modified")
    image_hash = segmentation_receipt.get("source_sha256")
    size = segmentation_receipt.get("image_size")
    raw_objects = segmentation_receipt.get("objects")
    if (
        not isinstance(size, list) or len(size) != 2
        or any(type(v) is not int for v in size)
        or not isinstance(raw_objects, list)
        or not 1 <= len(raw_objects) <= 24
    ):
        raise ValueError("v36_bridge_scene_dimensions_invalid")
    if not isinstance(object_labels, dict):
        raise ValueError("v36_bridge_labels_required")
    seen: set[str] = set()
    objects = []
    for item in raw_objects:
        if not isinstance(item, dict):
            raise ValueError("v36_bridge_object_invalid")
        object_id = item.get("object_id")
        if not isinstance(object_id, str) or object_id in seen:
            raise ValueError("v36_bridge_duplicate_or_missing_id")
        seen.add(object_id)
        if item.get("prompt_type") != "operator_box":
            raise ValueError("v36_bridge_prompt_provenance_invalid")
        if type(item.get("visible_pixel_count")) is not int or item["visible_pixel_count"] < 1:
            raise ValueError("v36_bridge_mask_empty")
        if (
            not isinstance(item.get("reference_iou"), (int, float, type(None)))
            or isinstance(item.get("reference_iou"), bool)
        ):
            raise ValueError("v36_bridge_reference_iou_invalid")
        iou = item.get("reference_iou")
        if iou is not None and (not math.isfinite(iou) or not 0 <= iou <= 1):
            raise ValueError("v36_bridge_reference_iou_invalid")
        if object_id not in object_labels:
            raise ValueError("v36_bridge_label_missing")
        objects.append({
            "object_id": object_id,
            "bbox": item.get("bbox"),
            "visible_mask_sha256": item.get("mask_sha256"),
            "label": object_labels[object_id],
            "label_source": label_source,
            "label_confidence": 1.0 if label_source == "operator" else 0.0,
        })
    if set(object_labels) != seen:
        raise ValueError("v36_bridge_labels_do_not_match_objects")
    scene = build_object_scene_evidence(
        scene_id=scene_id,
        source_image_sha256=image_hash,
        canvas_size=tuple(size),
        objects=objects,
        source_event_ids=source_event_ids,
        source_group=source_group,
        split=split,
    )
    canonical = json.dumps(
        segmentation_receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return {
        "status": "v36_cpu_segmentation_scene_built",
        "schema": "hex.cpu_segmentation_scene.v36",
        "scene": scene,
        "segmentation_receipt_sha256": hashlib.sha256(canonical).hexdigest(),
        "mask_semantics": "model_predicted_mask_from_operator_bbox",
        "label_semantics": "operator_assertion" if label_source == "operator" else "unattested_model_label",
        "observation_and_prediction_separated": True,
        "reported_provider": segmentation_receipt["provider"],
        "real_model_run_independently_attested": False,
        "spine_event_lineage_independently_verified": False,
        "files_written": False,
        "model_called": False,
        "model_promoted": False,
        "physical_action_executed": False,
    }
