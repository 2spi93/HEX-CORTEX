"""V42: verified V41 visual predictions -> EXISTING CanonicalSpine.

This module does not create an independent memory system. It refuses to
promote predictions to truth, learned skills, tracked identities or world
model observations. Uses canonical hash chaining and durable JSONL store.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from hex_cortex.memory.cortex_object_memory_staging_v41 import (
    stage_verified_object_candidates_v41,
)
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore

_TYPE = "vision.object_mask_predicted.v42"
_SOURCE = "hex_cortex.memory.cortex_object_memory_staging_v41"
_LOCAL_LEDGER = Path("receipts/v42_canonical_spine/visual_predictions.jsonl")
_SHA = re.compile(r"[a-f0-9]{64}")


def _payload(candidate: dict, evidence_sha: str) -> dict:
    """Bounded privacy-conscious references, not pixels or model dialogue."""
    scene = candidate.get("scene_id")
    object_id = candidate.get("object_id")
    if (
        not isinstance(scene, str) or not re.fullmatch(r"[A-Za-z][\w-]{0,63}", scene, re.ASCII)
        or not isinstance(object_id, str)
        or not re.fullmatch(r"[A-Za-z][\w-]{0,63}", object_id, re.ASCII)
    ):
        raise ValueError("v42_scene_or_object_id_invalid")
    photo_sha = candidate.get("source_photo_sha256")
    mask_sha = candidate.get("mask_binary_sha256")
    if not all(isinstance(v, str) and _SHA.fullmatch(v)
               for v in (photo_sha, mask_sha, evidence_sha)):
        raise ValueError("v42_evidence_sha_invalid")
    bbox = candidate.get("visible_mask_bbox")
    prompt = candidate.get("operator_prompt_bbox")
    for box in (bbox, prompt):
        if not isinstance(box, list) or len(box) != 4 or any(type(x) is not int for x in box):
            raise ValueError("v42_bbox_invalid")
        if not (0 <= box[0] < box[2] and 0 <= box[1] < box[3]):
            raise ValueError("v42_bbox_invalid")
    pixels = candidate.get("visible_mask_pixels")
    if type(pixels) is not int or pixels <= 0:
        raise ValueError("v42_pixel_count_invalid")
    mask_file = candidate.get("mask_file")
    if (
        not isinstance(mask_file, str)
        or not mask_file.startswith("receipts/v40_mask_inspection/")
        or ".." in Path(mask_file).parts
        or Path(mask_file).is_absolute()
        or not mask_file.endswith(".png")
    ):
        raise ValueError("v42_mask_file_denied")
    if (
        candidate.get("label_source") != "operator_selected_not_recognized"
        or candidate.get("mask_source") != "mobile_sam_predicted_not_ground_truth"
        or candidate.get("memory_promotion_approved") is not False
        or candidate.get("canonical_spine_event_id") is not None
        or candidate.get("scene_object_id_scope") != "single_image_only"
    ):
        raise ValueError("v42_false_cognition_claim_denied")
    return {
        "scene_id": scene,
        "scene_object_id": object_id,
        "source_image_sha256": photo_sha,
        "predicted_mask_sha256": mask_sha,
        "visible_mask_bbox": bbox,
        "operator_prompt_bbox": prompt,
        "predicted_visible_pixel_count": pixels,
        "verified_local_mask_path": mask_file,
        "v40_inspection_receipt_sha256": evidence_sha,
        "mask_provenance": "mobile_sam_cpu_box_prompt_predicted",
        "semantic_label_provenance": "operator_selected_unverified",
        "object_identity_scope": "single_frame",
        "independent_human_iou": None,
        "real_physics_or_tracking_attested": False,
        "eligible_for_skill_or_model_promotion": False,
    }


def _candidate_key(payload: dict) -> str:
    data = {
        "scene": payload["scene_id"],
        "object": payload["scene_object_id"],
        "source": payload["source_image_sha256"],
        "inspection": payload["v40_inspection_receipt_sha256"],
    }
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _ledger_path(root: Path) -> Path:
    file = root / _LOCAL_LEDGER
    if not file.resolve().is_relative_to(root):
        raise ValueError("v42_ledger_path_denied")
    cursor = file
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError("v42_ledger_symlink_denied")
        cursor = cursor.parent
    if file.exists() and not file.is_file():
        raise ValueError("v42_ledger_file_denied")
    if file.exists() and file.stat().st_size > 4_000_000:
        raise ValueError("v42_ledger_too_large")
    return file


def integrate_v41_with_canonical_spine_v42(
    *,
    project_root: Path,
    inspection_run: str = "latest",
    approved_read: bool = False,
    persist: bool = False,
    approved_write: bool = False,
) -> dict:
    """Stage in-memory by default; persist ONLY into dedicated local spine.

    A newly appended canonical event has a REAL event_id assigned by the
    existing CanonicalSpine, but this is an event about a mask *prediction*.
    """
    if not approved_read:
        return {
            "status": "blocked", "reason": "v42_read_approval_required",
            "files_read": False, "files_written": False, "model_called": False,
        }
    if persist and not approved_write:
        return {
            "status": "blocked", "reason": "v42_write_approval_required",
            "files_read": False, "files_written": False, "model_called": False,
        }
    if not isinstance(persist, bool) or not isinstance(approved_write, bool):
        raise ValueError("v42_permission_invalid")
    root = Path(project_root).resolve(strict=True)
    verified = stage_verified_object_candidates_v41(
        project_root=root, inspection_run=inspection_run, approved_read=True,
    )
    if (
        verified.get("status") != "verified_pixels_pending_memory_lineage"
        or verified.get("v39_audit_rechecked") is not True
        or verified.get("files_written") is not False
        or verified.get("model_called") is not False
        or verified.get("promotion_to_long_term_memory_permitted") is not False
        or verified.get("human_reference_iou_available") is not False
        or verified.get("canonical_spine_lineage_verified") is not False
    ):
        raise ValueError("v42_unverifiable_v41_stage")
    candidates = verified.get("candidates")
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 24:
        raise ValueError("v42_candidates_invalid")
    evidence_sha = verified.get("inspection_receipt_sha256")
    proposals = [_payload(item, evidence_sha) for item in candidates]
    keys = [_candidate_key(item) for item in proposals]
    if len(set(keys)) != len(keys):
        raise ValueError("v42_duplicate_candidate")
    spine = CanonicalSpine()
    ledger = None
    if persist:
        file = _ledger_path(root)
        ledger = CanonicalSpineJsonlStore(file)
        spine = ledger.load()
    if not spine.verify_integrity().ok:
        raise ValueError("v42_spine_corrupted")
    existing_keys: dict[str, dict] = {}
    for prior in spine.events:
        if prior.event_type == _TYPE:
            prior_key = prior.correlation_keys.get("visual_evidence_key")
            if not isinstance(prior_key, str) or prior_key in existing_keys:
                raise ValueError("v42_old_evidence_key_invalid")
            existing_keys[prior_key] = prior.payload
    new_ids: list[str] = []
    already = 0
    for item, key in zip(proposals, keys, strict=True):
        if key in existing_keys:
            if existing_keys[key] != item:
                raise ValueError("v42_existing_evidence_conflict")
            already += 1
            continue
        event = spine.append(
            event_type=_TYPE,
            task_id=f"vision:{item['scene_id']}",
            source=_SOURCE,
            payload=item,
            confidence=None,  # no calibrated segmentation confidence
            correlation_keys={
                "scene_id": item["scene_id"],
                "object_id": item["scene_object_id"],
                "visual_evidence_key": key,
            },
        )
        new_ids.append(event.event_id)
    integrity = spine.verify_integrity()
    if not integrity.ok:
        raise ValueError("v42_spine_hash_chain_invalid")
    if persist and new_ids:
        assert ledger is not None
        ledger.path.parent.mkdir(parents=True, exist_ok=True)
        ledger.save(spine)
        persisted = ledger.load()
        if not persisted.verify_integrity().ok or len(persisted.events) != len(spine.events):
            raise ValueError("v42_spine_readback_invalid")
    # Do not expose ephemeral event IDs as persisted identities.
    return {
        "schema": "hex.vision_to_canonical_spine.v42",
        "status": "canonical_spine_visual_predictions_persisted"
        if persist else "canonical_spine_visual_predictions_staged_in_memory",
        "V41_source_inspection_sha256": evidence_sha,
        "candidate_count": len(proposals),
        "new_event_count": len(new_ids),
        "idempotent_existing_event_count": already,
        "canonical_event_ids": new_ids if persist else [],
        "spine_integrity_ok": True,
        "verified_spine_event_count": len(spine.events),
        "ledger_path": _LOCAL_LEDGER.as_posix() if persist else None,
        "events_are_prediction_observations_not_ground_truth": True,
        "future_same_object_tracking_attested": False,
        "external_capture_provenance_attested": False,
        "human_reference_mask_iou_available": False,
        "world_model_prediction_compared_to_baseline": False,
        "long_term_skill_promotion_attested": False,
        "files_read": True,
        "files_written": persist and bool(new_ids),
        "model_called": False,
        "gpu_used": False,
        "external_network_used": False,
    }
