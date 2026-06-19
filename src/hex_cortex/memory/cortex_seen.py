from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from hex_cortex.memory.cortex_sensor_providers import get_cortex_sensor_provider

CORTEX_SEEN_FILENAME = "cortex-seen.jsonl"


def build_cortex_seen(
    profile: Path,
    *,
    provider_id: str,
    summary: str,
    confidence: float,
    approved: bool,
) -> dict[str, object]:
    provider = get_cortex_sensor_provider(provider_id)
    blockers = _blockers(provider, summary, confidence, approved)
    allowed = not blockers
    summary_hash = _hash(summary) if summary else None
    seen_hash = _hash(
        str(profile),
        provider_id,
        summary_hash or "missing_summary",
        str(confidence),
        str(approved),
        *blockers,
    )
    record = {
        "seen_id": f"cortex_seen_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "provider_id": provider_id,
        "capability_id": provider.get("capability_id"),
        "seen_status": "ready" if allowed else "blocked",
        "seen_allowed": allowed,
        "approved": approved,
        "confidence": confidence,
        "summary_length": len(summary),
        "summary_hash": summary_hash,
        "raw_input_saved": False,
        "raw_output_saved": False,
        "next_action": "build_world_state" if allowed else "repair_seen_receipt",
        "blockers": blockers,
        "seen_hash": seen_hash,
    }
    path = profile / CORTEX_SEEN_FILENAME
    rows = _load(path)
    if not any(row.get("seen_hash") == seen_hash for row in rows):
        rows.append(record)
    _write(path, rows)
    return {
        "seen_type": "cortex_seen",
        "seen_path": str(path),
        "seen_count": len(rows),
        "seen_records": [record],
    }


def summarize_cortex_seen(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_seen",
        "path": str(path),
        "exists": path.exists(),
        "total_seen_count": len(rows),
        "latest_seen_allowed": latest.get("seen_allowed") if latest else None,
        "latest_provider_id": latest.get("provider_id") if latest else None,
        "latest_capability_id": latest.get("capability_id") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
    }


def _blockers(
    provider: dict[str, object],
    summary: str,
    confidence: float,
    approved: bool,
) -> list[str]:
    blockers = []
    if provider.get("state") == "blocked":
        blockers.append(str(provider.get("blocker", "unknown_provider")))
    if not approved:
        blockers.append("approval_required")
    if not summary.strip():
        blockers.append("missing_summary")
    if confidence < 0 or confidence > 1:
        blockers.append("confidence_out_of_range")
    if provider.get("raw_input_persistence_allowed") is not False:
        blockers.append("raw_input_persistence_not_false")
    return blockers


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
