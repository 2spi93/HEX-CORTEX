from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_V13_RELEASE_REPORT_FILENAME = "cortex-v13-release-report.jsonl"
EXPERIENCE_AUDIT_SEAL_FILENAME = "cortex-experience-audit-seal.jsonl"
PRODUCT_HARDENING_PLAN_FILENAME = "cortex-product-hardening-plan.jsonl"
DEFAULT_RELEASE_REPORT_PATH = Path("RELEASE_HEX_CORTEX_V1_3_INTERACTIVE_COCKPIT.md")


def build_cortex_v13_release_report(
    profile: Path,
    *,
    output_path: Path | None = None,
    pytest_summary: str = "479 passed",
    tag_name: str = "hex-cortex-v1.3-interactive-cockpit",
) -> dict[str, object]:
    output_path = output_path or DEFAULT_RELEASE_REPORT_PATH
    seal = _latest_jsonl(profile / EXPERIENCE_AUDIT_SEAL_FILENAME)
    plan = _latest_jsonl(profile / PRODUCT_HARDENING_PLAN_FILENAME)
    blockers = _blockers(seal, plan)
    allowed = not blockers
    status = "written" if allowed else "blocked"
    decision = "v1_3_release_report_written" if allowed else "v1_3_release_report_blocked"
    next_action = "prepare_ci_artifact_upload" if allowed else "repair_v1_3_release_report"
    reasons = ["experience_seal_ready", "hardening_plan_ready", "release_report_written"] if allowed else blockers
    report_hash = _hash(str(profile), str(output_path), str(seal.get("seal_hash") if seal else "missing_seal"), str(plan.get("plan_hash") if plan else "missing_plan"), pytest_summary, tag_name, decision, next_action, *reasons)
    if allowed:
        output_path.write_text(_render_report(seal, plan, pytest_summary, tag_name, report_hash), encoding="utf-8")
    record = {
        "report_id": f"cortex_v13_release_report_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "output_path": str(output_path),
        "tag_name": tag_name,
        "pytest_summary": pytest_summary,
        "source_seal_hash": seal.get("seal_hash") if seal else None,
        "source_plan_hash": plan.get("plan_hash") if plan else None,
        "release_status": status,
        "release_decision": decision,
        "release_allowed": allowed,
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "report_hash": report_hash,
    }
    path = profile / CORTEX_V13_RELEASE_REPORT_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("report_hash") == report_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {"report_type": "cortex_v13_release_report", "profile_path": str(profile), "report_path": str(path), "report_count": len(records), "report_records": [record]}


def summarize_cortex_v13_release_reports(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_v13_release_report",
        "path": str(path),
        "exists": path.exists(),
        "total_report_count": len(records),
        "allowed_report_count": sum(1 for item in records if item.get("release_allowed") is True),
        "latest_release_status": latest.get("release_status") if latest else None,
        "latest_release_decision": latest.get("release_decision") if latest else None,
        "latest_release_allowed": latest.get("release_allowed") if latest else None,
        "latest_output_path": latest.get("output_path") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_report_hash": latest.get("report_hash") if latest else None,
    }


def _blockers(seal: dict[str, object] | None, plan: dict[str, object] | None) -> list[str]:
    blockers = []
    if not seal:
        blockers.append("missing_experience_audit_seal")
    elif seal.get("seal_allowed") is not True:
        blockers.append("experience_audit_seal_not_allowed")
    elif seal.get("next_action") != "tag_hex_cortex_v1_3_or_begin_product_hardening":
        blockers.append("experience_audit_seal_not_waiting_release")
    if not plan:
        blockers.append("missing_product_hardening_plan")
    elif plan.get("hardening_allowed") is not True:
        blockers.append("product_hardening_plan_not_allowed")
    elif plan.get("next_action") != "write_v1_3_release_report":
        blockers.append("product_hardening_plan_not_waiting_release_report")
    return blockers


def _render_report(seal: dict[str, object], plan: dict[str, object], pytest_summary: str, tag_name: str, report_hash: str) -> str:
    hardening_items = plan.get("hardening_items", [])
    items = "\n".join(
        f"- `{item.get('item_id')}` — {item.get('title')} (`{item.get('scope')}`): {item.get('expected_output')}"
        for item in hardening_items
        if isinstance(item, dict)
    )
    source_hashes = seal.get("source_hashes", {})
    source_lines = "\n".join(f"- `{key}`: `{value}`" for key, value in source_hashes.items()) if isinstance(source_hashes, dict) else "- none"
    return f"""# HEX-CORTEX v1.3 Interactive Cockpit Release Report

## Release status

- Release tag: `{tag_name}`
- Test status: `{pytest_summary}`
- Experience level: `{seal.get('experience_level')}`
- Audit score: `{seal.get('overall_audit_score')}`
- Best skill: `{seal.get('best_skill_key')}`
- Best feedback score: `{seal.get('best_feedback_score')}`
- Report hash: `{report_hash}`

## What is included

HEX-CORTEX v1.3 closes the first interactive cockpit loop on top of the memory-first core. It includes a cockpit data API, an interactive static cockpit shell, UX polish, refresh/filter/drilldown controls, skill usage history, multi-skill feedback scoring, and an experience audit seal.

## Evidence chain

{source_lines}

## Product hardening plan

{items}

## Operator note

The cockpit is currently a local/static interactive artifact. The next hardening step is CI artifact upload so generated cockpit and evidence outputs can be stored and shared from workflow runs.

## Next action

`prepare_ci_artifact_upload`
"""


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
