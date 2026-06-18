from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_CI_EVIDENCE_EXPORT_PLAN_FILENAME = "cortex-ci-evidence-export-plan.jsonl"
V13_RELEASE_REPORT_FILENAME = "cortex-v13-release-report.jsonl"
DEFAULT_WORKFLOW_PATH = Path(".github") / "workflows" / "hex-cortex-ci-evidence.yml"
DEFAULT_RELEASE_REPORT_PATH = Path("RELEASE_HEX_CORTEX_V1_3_INTERACTIVE_COCKPIT.md")
DEFAULT_EVIDENCE_NAME = "hex-cortex-v1-3-evidence"

_EVIDENCE_PATHS = [
    "RELEASE_HEX_CORTEX_V1_3_INTERACTIVE_COCKPIT.md",
    "artifacts/hex-cortex-ci/**",
    "artifacts/hex-cortex-ui-cockpit/**",
    "artifacts/hex-cortex-interactive-cockpit/**",
]


def build_cortex_ci_evidence_export_plan(profile: Path) -> dict[str, object]:
    release = _latest_jsonl(profile / V13_RELEASE_REPORT_FILENAME)
    blockers = []
    if not release:
        blockers.append("missing_v1_3_release_report")
    elif release.get("release_allowed") is not True:
        blockers.append("v1_3_release_report_not_allowed")
    elif release.get("next_action") != "prepare_ci_artifact_upload":
        blockers.append("v1_3_release_report_not_waiting_ci_evidence_export")
    if not DEFAULT_RELEASE_REPORT_PATH.exists():
        blockers.append("missing_release_report_markdown")
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "ci_evidence_export_plan_ready" if allowed else "ci_evidence_export_plan_blocked"
    next_action = "install_ci_evidence_workflow" if allowed else "repair_ci_evidence_export_plan"
    reasons = ["release_report_ready", "evidence_paths_selected", "workflow_install_ready"] if allowed else blockers
    plan_hash = _hash(str(profile), str(release.get("report_hash") if release else "missing_report"), str(DEFAULT_WORKFLOW_PATH), DEFAULT_EVIDENCE_NAME, decision, next_action, *_EVIDENCE_PATHS, *reasons)
    record = {
        "plan_id": f"cortex_ci_evidence_export_plan_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_release_report_hash": release.get("report_hash") if release else None,
        "workflow_path": str(DEFAULT_WORKFLOW_PATH),
        "evidence_name": DEFAULT_EVIDENCE_NAME,
        "evidence_paths": _EVIDENCE_PATHS,
        "retention_days": 14,
        "export_strategy": "github_actions_evidence_artifact_v4",
        "export_status": status,
        "export_decision": decision,
        "export_allowed": allowed,
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "plan_hash": plan_hash,
    }
    path = profile / CORTEX_CI_EVIDENCE_EXPORT_PLAN_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("plan_hash") == plan_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {"plan_type": "cortex_ci_evidence_export_plan", "profile_path": str(profile), "plan_path": str(path), "plan_count": len(records), "plan_records": [record]}


def summarize_cortex_ci_evidence_export_plans(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_ci_evidence_export_plan",
        "path": str(path),
        "exists": path.exists(),
        "total_plan_count": len(records),
        "allowed_plan_count": sum(1 for item in records if item.get("export_allowed") is True),
        "latest_export_status": latest.get("export_status") if latest else None,
        "latest_export_decision": latest.get("export_decision") if latest else None,
        "latest_export_allowed": latest.get("export_allowed") if latest else None,
        "latest_workflow_path": latest.get("workflow_path") if latest else None,
        "latest_evidence_name": latest.get("evidence_name") if latest else None,
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
