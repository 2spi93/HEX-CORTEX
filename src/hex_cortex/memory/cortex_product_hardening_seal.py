from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_PRODUCT_HARDENING_SEAL_FILENAME = "cortex-product-hardening-seal.jsonl"
EXPERIENCE_AUDIT_SEAL_FILENAME = "cortex-experience-audit-seal.jsonl"
V13_RELEASE_REPORT_FILENAME = "cortex-v13-release-report.jsonl"
CI_EVIDENCE_EXPORT_PLAN_FILENAME = "cortex-ci-evidence-export-plan.jsonl"
USER_DOCS_DRAFT_FILENAME = "cortex-user-docs-draft.jsonl"
OPERATOR_UI_WORDING_PATCH_FILENAME = "cortex-operator-ui-wording-patch.jsonl"


def build_cortex_product_hardening_seal(profile: Path) -> dict[str, object]:
    sources = {
        "experience_audit_seal": _latest_jsonl(profile / EXPERIENCE_AUDIT_SEAL_FILENAME),
        "v13_release_report": _latest_jsonl(profile / V13_RELEASE_REPORT_FILENAME),
        "ci_evidence_export_plan": _latest_jsonl(profile / CI_EVIDENCE_EXPORT_PLAN_FILENAME),
        "user_docs_draft": _latest_jsonl(profile / USER_DOCS_DRAFT_FILENAME),
        "operator_ui_wording_patch": _latest_jsonl(profile / OPERATOR_UI_WORDING_PATCH_FILENAME),
    }
    blockers = _blockers(sources)
    allowed = not blockers
    score = 1.0 if allowed else 0.0
    status = "sealed" if allowed else "blocked"
    decision = "product_hardening_seal_ready" if allowed else "product_hardening_seal_blocked"
    next_action = "tag_hex_cortex_v1_3_product_hardened_or_begin_v1_4" if allowed else "repair_product_hardening_seal"
    reasons = [
        "experience_audit_seal_ready",
        "release_report_ready",
        "ci_evidence_export_ready",
        "user_docs_ready",
        "operator_wording_patch_ready",
        "product_hardening_closed",
    ] if allowed else blockers
    source_hashes = _source_hashes(sources)
    seal_hash = _hash(str(profile), decision, next_action, str(score), *source_hashes.values(), *reasons)
    record = {
        "seal_id": f"cortex_product_hardening_seal_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "hardening_status": status,
        "hardening_decision": decision,
        "hardening_allowed": allowed,
        "hardening_level": "v1_3_product_hardened" if allowed else "blocked",
        "release_score": score,
        "ci_evidence_score": score,
        "docs_score": score,
        "operator_ui_score": score,
        "overall_hardening_score": score,
        "source_hashes": source_hashes,
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "seal_hash": seal_hash,
    }
    path = profile / CORTEX_PRODUCT_HARDENING_SEAL_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("seal_hash") == seal_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {"seal_type": "cortex_product_hardening_seal", "profile_path": str(profile), "seal_path": str(path), "seal_count": len(records), "seal_records": [record]}


def summarize_cortex_product_hardening_seals(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_product_hardening_seal",
        "path": str(path),
        "exists": path.exists(),
        "total_seal_count": len(records),
        "allowed_seal_count": sum(1 for item in records if item.get("hardening_allowed") is True),
        "latest_hardening_status": latest.get("hardening_status") if latest else None,
        "latest_hardening_decision": latest.get("hardening_decision") if latest else None,
        "latest_hardening_allowed": latest.get("hardening_allowed") if latest else None,
        "latest_hardening_level": latest.get("hardening_level") if latest else None,
        "latest_overall_hardening_score": latest.get("overall_hardening_score") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_seal_hash": latest.get("seal_hash") if latest else None,
    }


def _blockers(sources: dict[str, dict[str, object] | None]) -> list[str]:
    blockers = []
    if not _allowed(sources["experience_audit_seal"], "seal_allowed"):
        blockers.append("missing_or_blocked_experience_audit_seal")
    if not _allowed(sources["v13_release_report"], "release_allowed"):
        blockers.append("missing_or_blocked_v13_release_report")
    if not _allowed(sources["ci_evidence_export_plan"], "export_allowed"):
        blockers.append("missing_or_blocked_ci_evidence_export_plan")
    if not _allowed(sources["user_docs_draft"], "docs_allowed"):
        blockers.append("missing_or_blocked_user_docs_draft")
    patch = sources["operator_ui_wording_patch"]
    if not _allowed(patch, "patch_allowed"):
        blockers.append("missing_or_blocked_operator_ui_wording_patch")
    elif patch.get("next_action") != "seal_product_hardening_v1_3":
        blockers.append("operator_ui_wording_patch_not_waiting_hardening_seal")
    return blockers


def _source_hashes(sources: dict[str, dict[str, object] | None]) -> dict[str, str | None]:
    return {
        "experience_audit_seal": _field(sources["experience_audit_seal"], "seal_hash"),
        "v13_release_report": _field(sources["v13_release_report"], "report_hash"),
        "ci_evidence_export_plan": _field(sources["ci_evidence_export_plan"], "plan_hash"),
        "user_docs_draft": _field(sources["user_docs_draft"], "docs_hash"),
        "operator_ui_wording_patch": _field(sources["operator_ui_wording_patch"], "patch_hash"),
    }


def _allowed(row: dict[str, object] | None, key: str) -> bool:
    return bool(row and row.get(key) is True)


def _field(row: dict[str, object] | None, key: str) -> str | None:
    value = row.get(key) if row else None
    return value if isinstance(value, str) else None


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
