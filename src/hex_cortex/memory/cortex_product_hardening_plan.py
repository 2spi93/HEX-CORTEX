from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_PRODUCT_HARDENING_PLAN_FILENAME = "cortex-product-hardening-plan.jsonl"
EXPERIENCE_AUDIT_SEAL_FILENAME = "cortex-experience-audit-seal.jsonl"

_HARDENING_ITEMS = [
    {
        "item_id": "product_hardening_001",
        "title": "Stabilize generated artifact policy",
        "scope": "repo_hygiene",
        "expected_output": "Confirm generated runtime artifacts remain ignored unless explicitly exported.",
    },
    {
        "item_id": "product_hardening_002",
        "title": "Write v1.3 release report",
        "scope": "release_documentation",
        "expected_output": "Create a human-readable release report summarizing tests, tags, cockpit state, and audit seal.",
    },
    {
        "item_id": "product_hardening_003",
        "title": "Prepare CI artifact upload",
        "scope": "ci_distribution",
        "expected_output": "Prepare GitHub Actions artifact export for cockpit and CI evidence outputs.",
    },
    {
        "item_id": "product_hardening_004",
        "title": "Prepare user documentation",
        "scope": "operator_docs",
        "expected_output": "Document how to run the cockpit, refresh data, and interpret scores.",
    },
    {
        "item_id": "product_hardening_005",
        "title": "Plan final operator UI wording polish",
        "scope": "operator_experience",
        "expected_output": "Track remaining wording/UI copy issues without reopening the kernel.",
    },
]


def build_cortex_product_hardening_plan(profile: Path) -> dict[str, object]:
    seal = _latest_jsonl(profile / EXPERIENCE_AUDIT_SEAL_FILENAME)
    blockers = []
    if not seal:
        blockers.append("missing_experience_audit_seal")
    elif seal.get("seal_allowed") is not True:
        blockers.append("experience_audit_seal_not_allowed")
    elif seal.get("next_action") != "tag_hex_cortex_v1_3_or_begin_product_hardening":
        blockers.append("experience_audit_seal_not_waiting_product_hardening")
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "product_hardening_plan_ready" if allowed else "product_hardening_plan_blocked"
    next_action = "write_v1_3_release_report" if allowed else "repair_product_hardening_plan"
    reasons = ["experience_audit_seal_ready", "hardening_items_planned", "product_phase_unlocked"] if allowed else blockers
    plan_hash = _hash(str(profile), str(seal.get("seal_hash") if seal else "missing_seal"), decision, next_action, *[item["item_id"] for item in _HARDENING_ITEMS], *reasons)
    record = {
        "plan_id": f"cortex_product_hardening_plan_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_seal_hash": seal.get("seal_hash") if seal else None,
        "source_experience_level": seal.get("experience_level") if seal else None,
        "hardening_status": status,
        "hardening_decision": decision,
        "hardening_allowed": allowed,
        "hardening_item_count": len(_HARDENING_ITEMS) if allowed else 0,
        "hardening_items": _HARDENING_ITEMS if allowed else [],
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "plan_hash": plan_hash,
    }
    path = profile / CORTEX_PRODUCT_HARDENING_PLAN_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("plan_hash") == plan_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {
        "plan_type": "cortex_product_hardening_plan",
        "profile_path": str(profile),
        "plan_path": str(path),
        "plan_count": len(records),
        "plan_records": [record],
    }


def summarize_cortex_product_hardening_plans(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_product_hardening_plan",
        "path": str(path),
        "exists": path.exists(),
        "total_plan_count": len(records),
        "allowed_plan_count": sum(1 for item in records if item.get("hardening_allowed") is True),
        "latest_hardening_status": latest.get("hardening_status") if latest else None,
        "latest_hardening_decision": latest.get("hardening_decision") if latest else None,
        "latest_hardening_allowed": latest.get("hardening_allowed") if latest else None,
        "latest_hardening_item_count": latest.get("hardening_item_count") if latest else None,
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
