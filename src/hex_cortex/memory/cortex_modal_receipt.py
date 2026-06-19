from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from hex_cortex.memory.cortex_modal import describe_cortex_multimodal_capability

CORTEX_MODAL_RECEIPT_FILENAME = "cortex-modal-receipt.jsonl"


def build_cortex_modal_receipt(
    profile: Path,
    *,
    capability_id: str,
    operator_approved: bool,
) -> dict[str, object]:
    capability = describe_cortex_multimodal_capability(capability_id)
    blockers = _blockers(capability, operator_approved)
    allowed = not blockers
    receipt_hash = _hash(str(profile), capability_id, str(operator_approved), *blockers)
    record = {
        "modal_receipt_id": f"cortex_modal_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "capability_id": capability_id,
        "modal_status": "ready" if allowed else "blocked",
        "modal_allowed": allowed,
        "operator_approved": operator_approved,
        "default_mode": capability.get("default_mode"),
        "input_type": capability.get("input_type"),
        "raw_input_persistence_allowed": capability.get("raw_input_persistence_allowed"),
        "capture_performed": False,
        "audio_performed": False,
        "camera_performed": False,
        "screen_performed": False,
        "raw_input_saved": False,
        "next_action": "candidate_adapter_receipt" if allowed else "repair_modal_receipt",
        "blockers": blockers,
        "modal_receipt_hash": receipt_hash,
    }
    path = profile / CORTEX_MODAL_RECEIPT_FILENAME
    rows = _load(path)
    if not any(row.get("modal_receipt_hash") == receipt_hash for row in rows):
        rows.append(record)
    _write(path, rows)
    return {
        "modal_receipt_type": "cortex_modal_receipt",
        "profile_path": str(profile),
        "modal_receipt_path": str(path),
        "modal_receipt_count": len(rows),
        "modal_receipt_records": [record],
    }


def summarize_cortex_modal_receipts(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_modal_receipts",
        "path": str(path),
        "exists": path.exists(),
        "total_modal_receipt_count": len(rows),
        "latest_modal_allowed": latest.get("modal_allowed") if latest else None,
        "latest_capability_id": latest.get("capability_id") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
    }


def _blockers(capability: dict[str, object], operator_approved: bool) -> list[str]:
    blockers = []
    if capability.get("status") == "blocked":
        blockers.append(str(capability.get("blocker", "unknown_capability")))
    if not operator_approved:
        blockers.append("operator_approval_required")
    if capability.get("raw_input_persistence_allowed") is not False:
        blockers.append("raw_input_persistence_not_false")
    return blockers


def _load(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(content, encoding="utf-8")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
