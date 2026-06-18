from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from hex_cortex.memory.cortex_operator_ui_wording_polish_plan import (
    CORTEX_OPERATOR_UI_WORDING_POLISH_PLAN_FILENAME,
)

CORTEX_OPERATOR_UI_WORDING_PATCH_FILENAME = "cortex-operator-ui-wording-patch.jsonl"
DEFAULT_INTERACTIVE_COCKPIT_INDEX = Path("artifacts") / "hex-cortex-interactive-cockpit" / "index.html"


def build_cortex_operator_ui_wording_patch(
    profile: Path,
    *,
    index_path: Path | None = None,
) -> dict[str, object]:
    index_path = index_path or DEFAULT_INTERACTIVE_COCKPIT_INDEX
    plan = _latest_jsonl(profile / CORTEX_OPERATOR_UI_WORDING_POLISH_PLAN_FILENAME)
    blockers = _blockers(plan, index_path)
    allowed = not blockers
    applied_items: list[dict[str, object]] = []
    skipped_items: list[dict[str, object]] = []
    if allowed:
        original = index_path.read_text(encoding="utf-8")
        patched = original
        for item in plan.get("wording_items", []):
            if not isinstance(item, dict):
                continue
            source = item.get("source_label")
            target = item.get("target_label")
            item_id = item.get("item_id")
            if not isinstance(source, str) or not isinstance(target, str) or not isinstance(item_id, str):
                continue
            if source in patched:
                patched = patched.replace(source, target)
                applied_items.append({"item_id": item_id, "source_label": source, "target_label": target})
            elif target in patched:
                skipped_items.append({"item_id": item_id, "reason": "already_applied"})
            else:
                skipped_items.append({"item_id": item_id, "reason": "source_not_found"})
        if patched != original:
            index_path.write_text(patched, encoding="utf-8")
    status = "applied" if allowed else "blocked"
    decision = "operator_ui_wording_patch_applied" if allowed else "operator_ui_wording_patch_blocked"
    next_action = "seal_product_hardening_v1_3" if allowed else "repair_operator_ui_wording_patch"
    reasons = ["wording_plan_ready", "html_copy_patch_completed", "kernel_remains_closed"] if allowed else blockers
    patch_hash = _hash(
        str(profile),
        str(index_path),
        str(plan.get("plan_hash") if plan else "missing_plan"),
        decision,
        next_action,
        *[str(item) for item in applied_items],
        *[str(item) for item in skipped_items],
        *reasons,
    )
    record = {
        "patch_id": f"cortex_operator_ui_wording_patch_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_plan_hash": plan.get("plan_hash") if plan else None,
        "index_path": str(index_path),
        "patch_status": status,
        "patch_decision": decision,
        "patch_allowed": allowed,
        "applied_item_count": len(applied_items),
        "skipped_item_count": len(skipped_items),
        "applied_items": applied_items,
        "skipped_items": skipped_items,
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "patch_hash": patch_hash,
    }
    path = profile / CORTEX_OPERATOR_UI_WORDING_PATCH_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("patch_hash") == patch_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {"patch_type": "cortex_operator_ui_wording_patch", "profile_path": str(profile), "patch_path": str(path), "patch_count": len(records), "patch_records": [record]}


def summarize_cortex_operator_ui_wording_patches(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_operator_ui_wording_patch",
        "path": str(path),
        "exists": path.exists(),
        "total_patch_count": len(records),
        "allowed_patch_count": sum(1 for item in records if item.get("patch_allowed") is True),
        "latest_patch_status": latest.get("patch_status") if latest else None,
        "latest_patch_decision": latest.get("patch_decision") if latest else None,
        "latest_patch_allowed": latest.get("patch_allowed") if latest else None,
        "latest_applied_item_count": latest.get("applied_item_count") if latest else None,
        "latest_skipped_item_count": latest.get("skipped_item_count") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_patch_hash": latest.get("patch_hash") if latest else None,
    }


def _blockers(plan: dict[str, object] | None, index_path: Path) -> list[str]:
    blockers = []
    if not plan:
        blockers.append("missing_operator_ui_wording_polish_plan")
    elif plan.get("wording_allowed") is not True:
        blockers.append("operator_ui_wording_plan_not_allowed")
    elif plan.get("next_action") != "apply_operator_ui_wording_polish":
        blockers.append("operator_ui_wording_plan_not_waiting_patch")
    if not index_path.exists():
        blockers.append("missing_interactive_cockpit_index")
    return blockers


def _latest_jsonl(path: Path) -> dict[str, object] | None:
    records = _load_jsonl(path)
    return records[-1] if records else None


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
