from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_STATE_FILENAME = "cortex-state.jsonl"


def build_cortex_state(
    profile: Path,
    *,
    seen_records: list[dict[str, object]],
) -> dict[str, object]:
    usable = [record for record in seen_records if record.get("seen_allowed") is True]
    blockers = [] if usable else ["no_allowed_seen_records"]
    capabilities = sorted(
        {
            str(record.get("capability_id"))
            for record in usable
            if record.get("capability_id") is not None
        }
    )
    confidences = [
        float(record["confidence"])
        for record in usable
        if isinstance(record.get("confidence"), int | float)
    ]
    average_confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
    source_hashes = sorted(
        str(record.get("seen_hash"))
        for record in usable
        if isinstance(record.get("seen_hash"), str)
    )
    state_hash = _hash(
        str(profile),
        *capabilities,
        *source_hashes,
        str(average_confidence),
        *blockers,
    )
    record = {
        "state_id": f"cortex_state_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "state_status": "ready" if not blockers else "blocked",
        "state_allowed": not blockers,
        "source_count": len(usable),
        "capabilities": capabilities,
        "average_confidence": average_confidence,
        "source_hashes": source_hashes,
        "raw_inputs_saved": False,
        "next_action": "predict_next_state" if not blockers else "repair_world_state",
        "blockers": blockers,
        "state_hash": state_hash,
    }
    path = profile / CORTEX_STATE_FILENAME
    rows = _load(path)
    if not any(row.get("state_hash") == state_hash for row in rows):
        rows.append(record)
    _write(path, rows)
    return {
        "state_type": "cortex_world_state",
        "state_path": str(path),
        "state_count": len(rows),
        "state_records": [record],
    }


def summarize_cortex_state(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_world_state",
        "path": str(path),
        "exists": path.exists(),
        "total_state_count": len(rows),
        "latest_state_allowed": latest.get("state_allowed") if latest else None,
        "latest_source_count": latest.get("source_count") if latest else None,
        "latest_capabilities": latest.get("capabilities") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
    }


def _load(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
