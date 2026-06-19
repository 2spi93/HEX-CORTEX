from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_ROUTE_FILENAME = "cortex-route.jsonl"

_ROUTE_BY_OUTPUT = {
    "generate_image": ("asset", "asset.receipt"),
    "generate_video": ("asset", "asset.receipt"),
    "generate_3d_scene": ("asset", "asset.receipt"),
    "render_3d_asset": ("asset", "asset.receipt"),
    "publish_social_content": ("account", "account.receipt"),
    "manage_social_inbox": ("account", "account.receipt"),
    "request_tool": ("tool", "tool.receipt"),
    "speak_text": ("voice", "voice.receipt"),
    "annotate_visual": ("visual", "visual.receipt"),
    "write_text": ("local_output", "output.receipt"),
    "write_code": ("local_output", "output.receipt"),
    "write_document": ("local_output", "output.receipt"),
    "write_structured_data": ("local_output", "output.receipt"),
    "generate_plan": ("local_output", "output.receipt"),
}


def build_cortex_route_receipt(
    profile: Path,
    *,
    pick_record: dict[str, object],
) -> dict[str, object]:
    selected = pick_record.get("selected_action")
    output_id = (
        selected.get("output_id")
        if isinstance(selected, dict)
        else None
    )
    route = _ROUTE_BY_OUTPUT.get(str(output_id))
    blockers = []
    if pick_record.get("pick_allowed") is not True:
        blockers.append("pick_not_allowed")
    if pick_record.get("ready_for_next_receipt") is not True:
        blockers.append("pick_not_ready_for_route")
    if not isinstance(selected, dict):
        blockers.append("selected_action_missing")
    if not isinstance(output_id, str):
        blockers.append("selected_output_missing")
    if route is None:
        blockers.append("selected_output_route_unknown")
    allowed = not blockers
    lane = route[0] if route else None
    next_unit = route[1] if route else None
    route_hash = _hash(
        str(profile),
        str(pick_record.get("pick_hash")),
        str(pick_record.get("action_id")),
        str(output_id),
        str(lane),
        str(next_unit),
        *blockers,
    )
    record = {
        "route_receipt_id": f"cortex_route_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "route_status": "ready" if allowed else "blocked",
        "route_allowed": allowed,
        "pick_hash": pick_record.get("pick_hash"),
        "action_id": pick_record.get("action_id"),
        "output_id": output_id,
        "lane": lane,
        "next_unit": next_unit,
        "external_effect_performed": False,
        "network_call_performed": False,
        "local_process_started": False,
        "next_action": (
            "build_adapter_receipt"
            if allowed
            else "repair_route_receipt"
        ),
        "blockers": blockers,
        "route_hash": route_hash,
    }
    path = profile / CORTEX_ROUTE_FILENAME
    rows = _load(path)
    existing = next(
        (row for row in rows if row.get("route_hash") == route_hash),
        None,
    )
    if existing is None:
        rows.append(record)
        _write(path, rows)
        selected_record = record
    else:
        selected_record = existing
    return {
        "route_type": "cortex_action_route",
        "route_path": str(path),
        "route_count": len(rows),
        "route_records": [selected_record],
    }


def list_cortex_routes() -> list[dict[str, str]]:
    return [
        {
            "output_id": output_id,
            "lane": lane,
            "next_unit": next_unit,
        }
        for output_id, (lane, next_unit) in sorted(_ROUTE_BY_OUTPUT.items())
    ]


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
