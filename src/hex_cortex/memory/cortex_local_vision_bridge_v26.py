"""Explicit DINOv2 CPU bridge using EXISTING FrozenEncoder; no download.

Produces source-linked embedding hash and metadata, NOT semantic object
recognition. No model weights are included in this repository.
"""
from __future__ import annotations

from pathlib import Path

from hex_cortex.memory.cortex_frozen_encoder import (
    EncoderRunner, build_frozen_encoder_descriptor, encode_image_to_latent,
)
from hex_cortex.memory.cortex_universal_sensing_v26 import observe_local_file


def encode_operator_image(
    *,
    project_root: Path, image_path: Path,
    approved_read: bool = False,
    approved_encoding: bool = False,
    model_ref: str = "facebook/dinov2-base",
    runner: EncoderRunner | None = None,
) -> dict[str, object]:
    if not (approved_read and approved_encoding):
        return {
            "status": "blocked", "reason": "image_read_and_encoder_approval_required",
            "encoder_called": False, "image_read": False,
        }
    source = observe_local_file(
        root=project_root, path=image_path,
        modality="image", approved=True,
    )
    descriptor = build_frozen_encoder_descriptor(
        model_ref=model_ref, pooling="cls", device="cpu",
    )
    receipt = encode_image_to_latent(
        descriptor=descriptor, image_path=image_path,
        allow_model_download=False, operator_approved=True,
        include_vector=False, runner=runner,
    )
    return {
        "status": "embedding_created" if receipt["status"] == "encoded" else "blocked",
        "source_sha256": source["source_sha256"],
        "width_px": source["features"]["width_px"],
        "height_px": source["features"]["height_px"],
        "embedding_sha256": receipt.get("embedding_hash"),
        "embedding_dim": receipt.get("embedding_dim"),
        "encoder_receipt_sha256": receipt.get("receipt_hash"),
        "encoder_status": receipt["status"],
        "encoder_error_type": receipt.get("error_type"),
        "cpu_requested": True,
        "network_call_performed": False,
        "model_download_allowed": False,
        "object_detection_performed": False,
        "semantic_caption_verified": False,
        "raw_image_persisted": False,
        "embedding_vector_persisted": False,
        "files_written": False,
        "blockers": receipt.get("blockers", []),
    }
