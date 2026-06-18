from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_multi_skill_feedback_score import (
    CORTEX_MULTI_SKILL_FEEDBACK_SCORE_FILENAME,
    CortexMultiSkillFeedbackScoreJsonlStore,
)
from hex_cortex.memory.cortex_skill_usage_history import (
    CORTEX_SKILL_USAGE_HISTORY_FILENAME,
    CortexSkillUsageHistoryJsonlStore,
)
from hex_cortex.memory.cortex_ui_cockpit_builder import (
    CORTEX_UI_COCKPIT_BUILD_FILENAME,
    DEFAULT_CI_ARTIFACT_PATH,
    DEFAULT_COCKPIT_DIR,
    CortexUiCockpitBuildJsonlStore,
)

CORTEX_COCKPIT_DATA_API_FILENAME = "cortex-cockpit-data-api.jsonl"
COCKPIT_DATA_API_JSON_FILENAME = "cockpit-data-api.json"


class CortexCockpitDataApiRecord(BaseModel):
    api_id: str = Field(default_factory=lambda: f"cortex_cockpit_data_api_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    output_path: str
    source_history_hash: str | None
    source_feedback_hash: str | None
    source_build_hash: str | None
    source_ci_export_hash: str | None
    active_skill_count: int = Field(ge=0)
    best_skill_key: str | None
    best_feedback_score: float = Field(ge=0.0, le=1.0)
    latest_feedback_score: float = Field(ge=0.0, le=1.0)
    skill_count: int = Field(ge=0)
    total_usage_count: int = Field(ge=0)
    successful_usage_count: int = Field(ge=0)
    cockpit_build_status: str | None
    ci_export_status: str | None
    api_status: str
    api_decision: str
    api_allowed: bool
    next_action: str
    blockers: list[str]
    api_hash: str
    reasons: list[str]


class CortexCockpitDataApiJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexCockpitDataApiRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexCockpitDataApiRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex cockpit data api {line_number}") from exc
        return records

    def save(self, records: list[CortexCockpitDataApiRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_cockpit_data_api(
    profile: Path,
    *,
    output_dir: Path | None = None,
    ci_artifact_path: Path | None = None,
) -> dict[str, object]:
    output_dir = output_dir or DEFAULT_COCKPIT_DIR
    ci_artifact_path = ci_artifact_path or DEFAULT_CI_ARTIFACT_PATH
    history = _latest_history(profile)
    feedback = _latest_feedback(profile)
    build = _latest_build(profile)
    ci_export = _load_json(ci_artifact_path)
    output_path = output_dir / COCKPIT_DATA_API_JSON_FILENAME
    record = _api_record(profile, output_path, history, feedback, build, ci_export)
    if record.api_allowed:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(_api_payload(record, history, feedback, build, ci_export), indent=2, sort_keys=True), encoding="utf-8")
    path = profile / CORTEX_COCKPIT_DATA_API_FILENAME
    store = CortexCockpitDataApiJsonlStore(path)
    current = store.load()
    current_hashes = {item.api_hash for item in current}
    records = [] if record.api_hash in current_hashes else [record]
    count = store.save([*current, *records])
    return {
        "api_type": "cortex_cockpit_data_api",
        "profile_path": str(profile),
        "api_path": str(path),
        "api_count": count,
        "api_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_cockpit_data_apis(path: Path) -> dict[str, object]:
    records = CortexCockpitDataApiJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.api_allowed]
    return {
        "inspect_type": "cortex_cockpit_data_api",
        "path": str(path),
        "exists": path.exists(),
        "total_api_count": len(records),
        "allowed_api_count": len(allowed),
        "latest_api_id": latest.api_id if latest else None,
        "latest_api_status": latest.api_status if latest else None,
        "latest_api_decision": latest.api_decision if latest else None,
        "latest_api_allowed": latest.api_allowed if latest else None,
        "latest_output_path": latest.output_path if latest else None,
        "latest_best_skill_key": latest.best_skill_key if latest else None,
        "latest_best_feedback_score": latest.best_feedback_score if latest else None,
        "latest_active_skill_count": latest.active_skill_count if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_api_hash": latest.api_hash if latest else None,
    }


def _latest_history(profile: Path):
    records = CortexSkillUsageHistoryJsonlStore(profile / CORTEX_SKILL_USAGE_HISTORY_FILENAME).load()
    return records[-1] if records else None


def _latest_feedback(profile: Path):
    records = CortexMultiSkillFeedbackScoreJsonlStore(profile / CORTEX_MULTI_SKILL_FEEDBACK_SCORE_FILENAME).load()
    return records[-1] if records else None


def _latest_build(profile: Path):
    records = CortexUiCockpitBuildJsonlStore(profile / CORTEX_UI_COCKPIT_BUILD_FILENAME).load()
    return records[-1] if records else None


def _load_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _api_record(profile: Path, output_path: Path, history, feedback, build, ci_export: dict[str, object] | None) -> CortexCockpitDataApiRecord:
    blockers = _blockers(history, feedback, build, ci_export)
    allowed = not blockers
    ci_record = ci_export.get("record", {}) if ci_export else {}
    active_skill_count = _int(ci_record, "active_skill_count") or (history.skill_count if history else 0)
    best_skill_key = history.best_skill_key if history else (feedback.selected_skill_key if feedback else None)
    best_feedback_score = history.best_feedback_score if history else 0.0
    latest_feedback_score = feedback.feedback_score if feedback else 0.0
    status = "ready" if allowed else "blocked"
    decision = "cockpit_data_api_ready" if allowed else "cockpit_data_api_blocked"
    next_action = "build_interactive_cockpit_shell" if allowed else "repair_cockpit_data_api"
    reasons = ["history_ready", "feedback_ready", "cockpit_build_ready", "ci_export_ready", "data_api_written"] if allowed else blockers
    api_hash = _hash(
        str(profile),
        str(output_path),
        history.history_hash if history else "missing_history",
        feedback.feedback_hash if feedback else "missing_feedback",
        build.build_hash if build else "missing_build",
        _ci_export_hash(ci_export) or "missing_ci_export",
        best_skill_key or "missing_skill",
        decision,
        next_action,
        *reasons,
    )
    return CortexCockpitDataApiRecord(
        profile_path=str(profile),
        output_path=str(output_path),
        source_history_hash=history.history_hash if history else None,
        source_feedback_hash=feedback.feedback_hash if feedback else None,
        source_build_hash=build.build_hash if build else None,
        source_ci_export_hash=_ci_export_hash(ci_export),
        active_skill_count=active_skill_count,
        best_skill_key=best_skill_key,
        best_feedback_score=best_feedback_score,
        latest_feedback_score=latest_feedback_score,
        skill_count=history.skill_count if history else 0,
        total_usage_count=history.total_usage_count if history else 0,
        successful_usage_count=history.successful_usage_count if history else 0,
        cockpit_build_status=build.build_status if build else None,
        ci_export_status=_str(ci_record, "export_status"),
        api_status=status,
        api_decision=decision,
        api_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        api_hash=api_hash,
        reasons=reasons,
    )


def _blockers(history, feedback, build, ci_export: dict[str, object] | None) -> list[str]:
    blockers = []
    if history is None:
        blockers.append("missing_skill_usage_history")
    elif history.history_allowed is not True:
        blockers.append("skill_usage_history_not_allowed")
    elif history.next_action != "build_cockpit_data_api":
        blockers.append("skill_usage_history_not_waiting_data_api")
    if feedback is None:
        blockers.append("missing_multi_skill_feedback_score")
    elif feedback.feedback_allowed is not True:
        blockers.append("multi_skill_feedback_not_allowed")
    if build is None:
        blockers.append("missing_ui_cockpit_build")
    elif build.build_allowed is not True:
        blockers.append("ui_cockpit_build_not_allowed")
    if not _ci_export_ok(ci_export):
        blockers.append("missing_or_blocked_ci_artifact_export")
    return blockers


def _api_payload(record: CortexCockpitDataApiRecord, history, feedback, build, ci_export: dict[str, object] | None) -> dict[str, object]:
    return {
        "api_type": "hex_cortex_cockpit_data_api",
        "record": record.model_dump(mode="json"),
        "status": {
            "api_status": record.api_status,
            "api_decision": record.api_decision,
            "next_action": record.next_action,
        },
        "skills": {
            "active_skill_count": record.active_skill_count,
            "best_skill_key": record.best_skill_key,
            "best_feedback_score": record.best_feedback_score,
            "skill_count": record.skill_count,
            "total_usage_count": record.total_usage_count,
            "successful_usage_count": record.successful_usage_count,
            "history_entries": [entry.model_dump(mode="json") for entry in history.history_entries] if history else [],
        },
        "feedback": feedback.model_dump(mode="json") if feedback else None,
        "cockpit_build": build.model_dump(mode="json") if build else None,
        "ci_export": ci_export.get("record") if ci_export else None,
    }


def _ci_export_ok(payload: dict[str, object] | None) -> bool:
    if not payload:
        return False
    record = payload.get("record")
    return bool(isinstance(record, dict) and record.get("export_allowed") is True)


def _ci_export_hash(payload: dict[str, object] | None) -> str | None:
    if not payload:
        return None
    record = payload.get("record")
    if isinstance(record, dict):
        value = record.get("export_hash")
        return value if isinstance(value, str) else None
    return None


def _int(row: dict[str, object], key: str) -> int:
    value = row.get(key)
    return value if isinstance(value, int) else 0


def _str(row: dict[str, object], key: str) -> str | None:
    value = row.get(key)
    return value if isinstance(value, str) else None


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
