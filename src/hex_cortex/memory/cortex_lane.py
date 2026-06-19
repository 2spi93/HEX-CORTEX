from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_LANE_FILENAME = "cortex-lane.jsonl"

_NEXT_ACTIONS = {
    "local_output": "run_local_output_adapter",
    "tool": "run_tool_adapter",
    "voice": "run_voice_adapter",
    "visual": "run_visual_adapter",
}


def build_cortex_output_receipt(
    profile: Path,
    *,
    route_record: dict[str, object],
    request_hash: str,
) -> dict[str, object]:
    return _build_lane_receipt(
        profile,
        route_record=route_record,
        request_hash=request_hash,
        expected_lane="local_output",
    )


def build_cortex_tool_receipt(
    profile: Path,
    *,
    route_record: dict[str, object],
    request_hash: str,
) -> dict[str, object]:
    return _build_lane_receipt(
        profile,
        route_record=route_record,
        request_hash=request_hash,
        expected_lane="tool",
    )


def build_cortex_voice_receipt(
    profile: Path,
    *,
    route_record: dict[str, object],
    request_hash: str,
) -> dict[str, object]:
    return _build_lane_receipt(
        profile,
        route_record=route_record,
        request_hash=request_hash,
        expected_lane="voice",
    )


def build_cortex_visual_receipt(
    profile: Path,
    *,
    route_record: dict[str, object],
    request_hash: str,
) -> dict[str, object]:
    return _build_lane_receipt(
        profile,
        route_record=route_record,
        request_hash=request_hash,
        expected_lane="visual",
    )


def _build_lane_receipt(
    profile: Path,
    *,
    route_record: dict[str, object],
    request_hash: str,
    expected_lane: str,
) -> dict[str, object]:
    blockers = []
    if route_record.get("route_allowed") is not True:
        blockers.append("route_not_allowed")
    if route_record.get("lane") != expected_lane:
        blockers.append("route_lane_mismatch")
    if not _text(route_record.get("route_hash")):
        blockers.append("missing_route_hash")
    if not _text(request_hash):
        blockers.append("missing_lane_request_hash")
    allowed = not blockers
    receipt_hash = _hash(
        str(profile),
        str(route_record.get("route_hash")),
        expected_lane,
        request_hash,
        *blockers,
    )
    record = {
        "lane_receipt_id": f"cortex_lane_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "lane_status": "ready" if allowed else "blocked",
        "lane_allowed": allowed,
        "route_hash": route_record.get("route_hash"),
        "action_id": route_record.get("action_id"),
        "output_id": route_record.get("output_id"),
        "lane": expected_lane,
        "request_hash": request_hash,
        "raw_request_persisted": False,
        "external_effect_performed": False,
        "tool_call_performed": False,
        "network_call_performed": False,
        "local_process_started": False,
        "next_action": (
            _NEXT_ACTIONS[expected_lane]
            if allowed
            else "repair_lane_receipt"
        ),
        "blockers": blockers,
        "lane_receipt_hash": receipt_hash,
    }
    path = profile / CORTEX_LANE_FILENAME
    rows = _load(path)
    existing = next(
        (
            row
            for row in rows
            if row.get("lane_receipt_hash") == receipt_hash
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
        "lane_receipt_type": "cortex_lane_receipt",
        "lane_receipt_path": str(path),
        "lane_receipt_count": len(rows),
        "lane_receipt_records": [selected],
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
    content = "".join(
        json.dumps(row, sort_keys=True) + "\n"
        for row in rows
    )
    path.write_text(content, encoding="utf-8")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
