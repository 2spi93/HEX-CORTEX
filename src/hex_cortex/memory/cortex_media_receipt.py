from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_MEDIA_RECEIPT_FILENAME = "cortex-media-receipt.jsonl"


def build_cortex_media_receipt(
    profile: Path,
    *,
    candidate: dict[str, object],
    request_hash: str,
    source_state_hash: str | None = None,
) -> dict[str, object]:
    blockers = []
    if candidate.get("candidate_ready") is not True:
        blockers.append("media_candidate_not_ready")
    if not _text(candidate.get("provider_id")):
        blockers.append("missing_media_provider_id")
    if not _text(candidate.get("output_id")):
        blockers.append("missing_media_output_id")
    if not _text(request_hash):
        blockers.append("missing_media_request_hash")
    if candidate.get("raw_input_persistence_allowed") is not False:
        blockers.append("media_raw_persistence_not_false")
    allowed = not blockers
    receipt_hash = _hash(
        str(profile),
        str(candidate.get("provider_id")),
        str(candidate.get("output_id")),
        request_hash,
        str(source_state_hash),
        str(candidate.get("transport")),
        *blockers,
    )
    record = {
        "media_receipt_id": f"cortex_media_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "media_receipt_status": "ready" if allowed else "blocked",
        "media_receipt_allowed": allowed,
        "provider_id": candidate.get("provider_id"),
        "output_id": candidate.get("output_id"),
        "transport": candidate.get("transport"),
        "local_provider": candidate.get("local_provider"),
        "request_hash": request_hash,
        "source_state_hash": source_state_hash,
        "raw_prompt_persisted": False,
        "raw_media_persisted": False,
        "generation_performed": False,
        "network_call_performed": False,
        "local_process_started": False,
        "next_action": _next_action(candidate, allowed),
        "blockers": blockers,
        "media_receipt_hash": receipt_hash,
    }
    path = profile / CORTEX_MEDIA_RECEIPT_FILENAME
    rows = _load(path)
    existing = next(
        (
            row
            for row in rows
            if row.get("media_receipt_hash") == receipt_hash
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
        "media_receipt_type": "cortex_media_receipt",
        "media_receipt_path": str(path),
        "media_receipt_count": len(rows),
        "media_receipt_records": [selected],
    }


def summarize_cortex_media_receipts(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_media_receipt",
        "path": str(path),
        "exists": path.exists(),
        "total_media_receipt_count": len(rows),
        "latest_media_receipt_allowed": (
            latest.get("media_receipt_allowed") if latest else None
        ),
        "latest_provider_id": latest.get("provider_id") if latest else None,
        "latest_output_id": latest.get("output_id") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
    }


def _next_action(candidate: dict[str, object], allowed: bool) -> str:
    if not allowed:
        return "repair_media_receipt"
    if candidate.get("local_provider") is True:
        return "run_local_media_adapter"
    return "request_remote_media_execution"


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
