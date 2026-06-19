from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_PICK_FILENAME = "cortex-pick.jsonl"


def build_cortex_pick(
    profile: Path,
    *,
    proposal_record: dict[str, object],
    action_id: str | None = None,
    mode: str = "manual",
    approved: bool = False,
    auto_safe: bool = False,
) -> dict[str, object]:
    ranked = _ranked(proposal_record)
    resolved_id = action_id or _text(
        proposal_record.get("recommended_action_id")
    )
    selected = next(
        (item for item in ranked if item.get("action_id") == resolved_id),
        None,
    )
    blockers = _blockers(
        proposal_record=proposal_record,
        ranked=ranked,
        selected=selected,
        action_id=resolved_id,
        mode=mode,
        approved=approved,
        auto_safe=auto_safe,
    )
    allowed = not blockers
    needs_approval = (
        selected.get("requires_operator") is True
        if selected is not None
        else None
    )
    ready_for_next_receipt = (
        allowed
        and selected is not None
        and (
            (mode == "manual" and (approved or not needs_approval))
            or (mode == "auto_safe" and auto_safe and not needs_approval)
        )
    )
    selected_hash = (
        _hash(json.dumps(selected, sort_keys=True))
        if selected is not None
        else None
    )
    pick_hash = _hash(
        str(profile),
        str(proposal_record.get("proposal_hash")),
        str(resolved_id),
        mode,
        str(approved),
        str(auto_safe),
        str(selected_hash),
        *blockers,
    )
    record = {
        "pick_id": f"cortex_pick_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "pick_status": "ready" if allowed else "blocked",
        "pick_allowed": allowed,
        "mode": mode,
        "proposal_hash": proposal_record.get("proposal_hash"),
        "goal_id": proposal_record.get("goal_id"),
        "source_state_hash": proposal_record.get("source_state_hash"),
        "action_id": resolved_id,
        "selected_action_hash": selected_hash,
        "selected_action": selected,
        "requires_operator": needs_approval,
        "approved": approved,
        "auto_safe": auto_safe,
        "ready_for_next_receipt": ready_for_next_receipt,
        "action_executed": False,
        "tool_call_performed": False,
        "network_call_performed": False,
        "next_action": _next_action(
            allowed=allowed,
            ready=ready_for_next_receipt,
            needs_approval=needs_approval,
            approved=approved,
            mode=mode,
        ),
        "blockers": blockers,
        "pick_hash": pick_hash,
    }
    path = profile / CORTEX_PICK_FILENAME
    rows = _load(path)
    existing = next(
        (row for row in rows if row.get("pick_hash") == pick_hash),
        None,
    )
    if existing is None:
        rows.append(record)
        _write(path, rows)
        selected_record = record
    else:
        selected_record = existing
    return {
        "pick_type": "cortex_action_pick",
        "pick_path": str(path),
        "pick_count": len(rows),
        "pick_records": [selected_record],
    }


def summarize_cortex_picks(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_action_pick",
        "path": str(path),
        "exists": path.exists(),
        "total_pick_count": len(rows),
        "latest_pick_allowed": latest.get("pick_allowed") if latest else None,
        "latest_action_id": latest.get("action_id") if latest else None,
        "latest_ready_for_next_receipt": (
            latest.get("ready_for_next_receipt") if latest else None
        ),
        "latest_next_action": latest.get("next_action") if latest else None,
    }


def _blockers(
    *,
    proposal_record: dict[str, object],
    ranked: list[dict[str, object]],
    selected: dict[str, object] | None,
    action_id: str | None,
    mode: str,
    approved: bool,
    auto_safe: bool,
) -> list[str]:
    blockers = []
    if proposal_record.get("proposal_allowed") is not True:
        blockers.append("proposal_not_allowed")
    if not _text(proposal_record.get("proposal_hash")):
        blockers.append("missing_proposal_hash")
    if not ranked:
        blockers.append("ranked_actions_missing")
    if not action_id:
        blockers.append("action_id_missing")
    if action_id and selected is None:
        blockers.append("action_not_found")
    if mode not in {"manual", "auto_safe"}:
        blockers.append("mode_invalid")
    if selected is not None:
        if selected.get("within_cost_budget") is not True:
            blockers.append("action_outside_cost_budget")
        if selected.get("decision") in {"reject_candidate", "blocked"}:
            blockers.append("action_rejected")
    if mode == "auto_safe":
        if not auto_safe:
            blockers.append("auto_safe_not_allowed")
        if selected is not None and selected.get("requires_operator") is True:
            blockers.append("auto_safe_sensitive_action_forbidden")
        if approved:
            blockers.append("auto_safe_manual_approval_conflict")
    return blockers


def _next_action(
    *,
    allowed: bool,
    ready: bool,
    needs_approval: bool | None,
    approved: bool,
    mode: str,
) -> str:
    if not allowed:
        return "repair_action_pick"
    if needs_approval and not approved:
        return "request_operator_for_next_receipt"
    if not ready:
        return "review_action_pick"
    if mode == "auto_safe":
        return "prepare_auto_safe_receipt"
    return "prepare_manual_receipt"


def _ranked(proposal_record: dict[str, object]) -> list[dict[str, object]]:
    value = proposal_record.get("ranked_actions")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


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
