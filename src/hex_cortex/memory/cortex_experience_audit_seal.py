from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_EXPERIENCE_AUDIT_SEAL_FILENAME = "cortex-experience-audit-seal.jsonl"
DATA_API_FILENAME = "cortex-cockpit-data-api.jsonl"
INTERACTIVE_SHELL_FILENAME = "cortex-interactive-cockpit-shell.jsonl"
UX_POLISH_FILENAME = "cortex-interactive-cockpit-ux-polish.jsonl"
REFRESH_PLUS_FILENAME = "cortex-cockpit-live-refresh-filters-drilldown-plus.jsonl"
SKILL_USAGE_HISTORY_FILENAME = "cortex-skill-usage-history.jsonl"


def build_cortex_experience_audit_seal(profile: Path) -> dict[str, object]:
    sources = {
        "data_api": _latest_jsonl(profile / DATA_API_FILENAME),
        "interactive_shell": _latest_jsonl(profile / INTERACTIVE_SHELL_FILENAME),
        "ux_polish": _latest_jsonl(profile / UX_POLISH_FILENAME),
        "refresh_plus": _latest_jsonl(profile / REFRESH_PLUS_FILENAME),
        "skill_usage_history": _latest_jsonl(profile / SKILL_USAGE_HISTORY_FILENAME),
    }
    blockers = _blockers(sources)
    allowed = not blockers
    score = 1.0 if allowed else 0.0
    status = "sealed" if allowed else "blocked"
    decision = "experience_audit_seal_ready" if allowed else "experience_audit_seal_blocked"
    next_action = "tag_hex_cortex_v1_3_or_begin_product_hardening" if allowed else "repair_experience_audit_seal"
    reasons = ["data_api_ready", "interactive_shell_ready", "ux_polish_ready", "refresh_plus_ready", "usage_history_ready"] if allowed else blockers
    source_hashes = _source_hashes(sources)
    seal_hash = _hash(str(profile), decision, next_action, str(score), *source_hashes.values(), *reasons)
    record = {
        "seal_id": f"cortex_experience_audit_seal_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "seal_status": status,
        "seal_decision": decision,
        "seal_allowed": allowed,
        "experience_level": "interactive_cockpit_v1_3_operable" if allowed else "blocked",
        "data_api_score": score,
        "shell_score": score,
        "ux_score": score,
        "refresh_score": score,
        "usage_history_score": score,
        "overall_audit_score": score,
        "source_hashes": source_hashes,
        "best_skill_key": _best_skill_key(sources),
        "best_feedback_score": _best_feedback_score(sources),
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "seal_hash": seal_hash,
    }
    path = profile / CORTEX_EXPERIENCE_AUDIT_SEAL_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("seal_hash") == seal_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {
        "seal_type": "cortex_experience_audit_seal",
        "profile_path": str(profile),
        "seal_path": str(path),
        "seal_count": len(records),
        "seal_records": [record],
    }


def summarize_cortex_experience_audit_seals(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_experience_audit_seal",
        "path": str(path),
        "exists": path.exists(),
        "total_seal_count": len(records),
        "allowed_seal_count": sum(1 for item in records if item.get("seal_allowed") is True),
        "latest_seal_status": latest.get("seal_status") if latest else None,
        "latest_seal_decision": latest.get("seal_decision") if latest else None,
        "latest_seal_allowed": latest.get("seal_allowed") if latest else None,
        "latest_experience_level": latest.get("experience_level") if latest else None,
        "latest_overall_audit_score": latest.get("overall_audit_score") if latest else None,
        "latest_best_skill_key": latest.get("best_skill_key") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_seal_hash": latest.get("seal_hash") if latest else None,
    }


def _blockers(sources: dict[str, dict[str, object] | None]) -> list[str]:
    blockers = []
    if not _allowed(sources["data_api"], "api_allowed"):
        blockers.append("missing_or_blocked_data_api")
    elif sources["data_api"].get("next_action") != "build_interactive_cockpit_shell":
        blockers.append("data_api_not_in_expected_state")
    if not _allowed(sources["interactive_shell"], "shell_allowed"):
        blockers.append("missing_or_blocked_interactive_shell")
    elif sources["interactive_shell"].get("next_action") != "operate_interactive_cockpit":
        blockers.append("interactive_shell_not_operable")
    if not _allowed(sources["ux_polish"], "polish_allowed"):
        blockers.append("missing_or_blocked_ux_polish")
    elif sources["ux_polish"].get("next_action") != "build_live_refresh_filters_drilldown_plus":
        blockers.append("ux_polish_not_in_expected_state")
    if not _allowed(sources["refresh_plus"], "plus_allowed"):
        blockers.append("missing_or_blocked_refresh_plus")
    elif sources["refresh_plus"].get("next_action") != "operate_interactive_cockpit_v1_3":
        blockers.append("refresh_plus_not_operable")
    if not _allowed(sources["skill_usage_history"], "history_allowed"):
        blockers.append("missing_or_blocked_skill_usage_history")
    return blockers


def _source_hashes(sources: dict[str, dict[str, object] | None]) -> dict[str, str | None]:
    return {
        "data_api": _field(sources["data_api"], "api_hash"),
        "interactive_shell": _field(sources["interactive_shell"], "shell_hash"),
        "ux_polish": _field(sources["ux_polish"], "polish_hash"),
        "refresh_plus": _field(sources["refresh_plus"], "plus_hash"),
        "skill_usage_history": _field(sources["skill_usage_history"], "history_hash"),
    }


def _best_skill_key(sources: dict[str, dict[str, object] | None]) -> str | None:
    return _field(sources["data_api"], "best_skill_key") or _field(sources["skill_usage_history"], "best_skill_key")


def _best_feedback_score(sources: dict[str, dict[str, object] | None]) -> float:
    value = sources["data_api"].get("best_feedback_score") if sources["data_api"] else None
    if isinstance(value, int | float):
        return float(value)
    value = sources["skill_usage_history"].get("best_feedback_score") if sources["skill_usage_history"] else None
    return float(value) if isinstance(value, int | float) else 0.0


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
