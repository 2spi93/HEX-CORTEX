from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_OPERATOR_UI_WORDING_POLISH_PLAN_FILENAME = "cortex-operator-ui-wording-polish-plan.jsonl"
USER_DOCS_DRAFT_FILENAME = "cortex-user-docs-draft.jsonl"

_WORDING_ITEMS = [
    {"item_id": "ui_wording_001", "source_label": "API status", "target_label": "Cortex status", "surface": "status_card"},
    {"item_id": "ui_wording_002", "source_label": "Best skill", "target_label": "Best routed skill", "surface": "status_card"},
    {"item_id": "ui_wording_003", "source_label": "Next action", "target_label": "Next operator action", "surface": "status_card"},
    {"item_id": "ui_wording_004", "source_label": "Full JSON drilldown", "target_label": "Evidence drilldown", "surface": "drilldown"},
    {"item_id": "ui_wording_005", "source_label": "Copy JSON snapshot", "target_label": "Copy evidence snapshot", "surface": "drilldown"},
    {"item_id": "ui_wording_006", "source_label": "Filter skill, status, panel...", "target_label": "Filter by skill, status, score, or panel...", "surface": "filter"},
]


def build_cortex_operator_ui_wording_polish_plan(profile: Path) -> dict[str, object]:
    docs = _latest_jsonl(profile / USER_DOCS_DRAFT_FILENAME)
    blockers = []
    if not docs:
        blockers.append("missing_user_docs_draft")
    elif docs.get("docs_allowed") is not True:
        blockers.append("user_docs_draft_not_allowed")
    elif docs.get("next_action") != "plan_operator_ui_wording_polish":
        blockers.append("user_docs_draft_not_waiting_ui_wording_polish")
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "operator_ui_wording_polish_plan_ready" if allowed else "operator_ui_wording_polish_plan_blocked"
    next_action = "apply_operator_ui_wording_polish" if allowed else "repair_operator_ui_wording_polish_plan"
    reasons = ["user_docs_ready", "wording_items_planned", "kernel_remains_closed"] if allowed else blockers
    plan_hash = _hash(
        str(profile),
        str(docs.get("docs_hash") if docs else "missing_docs"),
        decision,
        next_action,
        *[item["item_id"] + item["source_label"] + item["target_label"] for item in _WORDING_ITEMS],
        *reasons,
    )
    record = {
        "plan_id": f"cortex_operator_ui_wording_polish_plan_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_docs_hash": docs.get("docs_hash") if docs else None,
        "wording_status": status,
        "wording_decision": decision,
        "wording_allowed": allowed,
        "wording_item_count": len(_WORDING_ITEMS) if allowed else 0,
        "wording_items": _WORDING_ITEMS if allowed else [],
        "application_policy": "html_copy_patch_only_no_kernel_reopen" if allowed else "blocked",
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "plan_hash": plan_hash,
    }
    path = profile / CORTEX_OPERATOR_UI_WORDING_POLISH_PLAN_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("plan_hash") == plan_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {"plan_type": "cortex_operator_ui_wording_polish_plan", "profile_path": str(profile), "plan_path": str(path), "plan_count": len(records), "plan_records": [record]}


def summarize_cortex_operator_ui_wording_polish_plans(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_operator_ui_wording_polish_plan",
        "path": str(path),
        "exists": path.exists(),
        "total_plan_count": len(records),
        "allowed_plan_count": sum(1 for item in records if item.get("wording_allowed") is True),
        "latest_wording_status": latest.get("wording_status") if latest else None,
        "latest_wording_decision": latest.get("wording_decision") if latest else None,
        "latest_wording_allowed": latest.get("wording_allowed") if latest else None,
        "latest_wording_item_count": latest.get("wording_item_count") if latest else None,
        "latest_application_policy": latest.get("application_policy") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_plan_hash": latest.get("plan_hash") if latest else None,
    }


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
