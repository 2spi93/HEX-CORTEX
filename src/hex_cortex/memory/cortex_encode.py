from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_ENCODE_FILENAME = "cortex-encode.jsonl"

_ENCODERS = [
    {
        "encoder_id": "text_encoder",
        "modality": "text",
        "input_contract": "text_or_document_hash",
    },
    {
        "encoder_id": "image_encoder",
        "modality": "image",
        "input_contract": "image_hash",
    },
    {
        "encoder_id": "video_encoder",
        "modality": "video",
        "input_contract": "video_or_frame_sequence_hash",
    },
    {
        "encoder_id": "audio_encoder",
        "modality": "audio",
        "input_contract": "audio_or_transcript_hash",
    },
    {
        "encoder_id": "geometry_encoder",
        "modality": "geometry_3d",
        "input_contract": "depth_point_cloud_mesh_or_scene_hash",
    },
]


def list_cortex_encoders() -> list[dict[str, object]]:
    return [
        {
            **item,
            "state": "candidate",
            "local_preferred": True,
            "raw_input_persistence_allowed": False,
            "encoding_enabled": False,
        }
        for item in _ENCODERS
    ]


def get_cortex_encoder(encoder_id: str) -> dict[str, object]:
    for item in list_cortex_encoders():
        if item["encoder_id"] == encoder_id:
            return item
    return {
        "encoder_id": encoder_id,
        "state": "blocked",
        "blocker": "unknown_encoder_candidate",
    }


def build_cortex_encode_receipt(
    profile: Path,
    *,
    encoder_id: str,
    source_hash: str,
    adapter_available: bool,
    embedding_dimensions: int,
    batch_size: int = 1,
) -> dict[str, object]:
    encoder = get_cortex_encoder(encoder_id)
    blockers = []
    if encoder.get("state") == "blocked":
        blockers.append(str(encoder.get("blocker")))
    if not _text(source_hash):
        blockers.append("missing_encoder_source_hash")
    if not adapter_available:
        blockers.append("encoder_adapter_unavailable")
    if embedding_dimensions < 1 or embedding_dimensions > 65536:
        blockers.append("embedding_dimensions_out_of_range")
    if batch_size < 1 or batch_size > 1024:
        blockers.append("encoder_batch_size_out_of_range")
    if encoder.get("raw_input_persistence_allowed") is not False:
        blockers.append("encoder_raw_persistence_not_false")
    allowed = not blockers
    receipt_hash = _hash(
        str(profile),
        encoder_id,
        source_hash,
        str(adapter_available),
        str(embedding_dimensions),
        str(batch_size),
        *blockers,
    )
    record = {
        "encode_receipt_id": f"cortex_encode_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "encode_status": "ready" if allowed else "blocked",
        "encode_allowed": allowed,
        "encoder_id": encoder_id,
        "modality": encoder.get("modality"),
        "input_contract": encoder.get("input_contract"),
        "source_hash": source_hash,
        "embedding_dimensions": embedding_dimensions,
        "batch_size": batch_size,
        "raw_input_persisted": False,
        "embedding_persisted": False,
        "encoding_performed": False,
        "model_call_performed": False,
        "network_call_performed": False,
        "next_action": (
            "run_local_encoder"
            if allowed
            else "repair_encoder_receipt"
        ),
        "blockers": blockers,
        "encode_receipt_hash": receipt_hash,
    }
    path = profile / CORTEX_ENCODE_FILENAME
    rows = _load(path)
    existing = next(
        (
            row
            for row in rows
            if row.get("encode_receipt_hash") == receipt_hash
        ),
        None,
    )
    if existing is None:
        rows.append(record)
        _write(path, rows)
        selected = record
    else:
        selected = existing
    return {
        "encode_type": "cortex_encode_receipt",
        "encode_path": str(path),
        "encode_count": len(rows),
        "encode_records": [selected],
    }


def summarize_cortex_encode_receipts(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_encode_receipt",
        "path": str(path),
        "exists": path.exists(),
        "total_encode_count": len(rows),
        "latest_encode_allowed": latest.get("encode_allowed") if latest else None,
        "latest_encoder_id": latest.get("encoder_id") if latest else None,
        "latest_modality": latest.get("modality") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
    }


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _load(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(row, sort_keys=True) + "\n"
        for row in rows
    )
    path.write_text(text, encoding="utf-8")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
