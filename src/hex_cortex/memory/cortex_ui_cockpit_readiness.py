from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

CORTEX_UI_COCKPIT_READINESS_FILENAME = "cortex-ui-cockpit-readiness.jsonl"
CI_ARTIFACT_EXPORT_PATH = Path("artifacts") / "hex-cortex-ci" / "cortex-ci-artifact-export.json"
_PROFILE_SOURCES = {
    "frontier_oracle_fallback": "cortex-frontier-oracle-fallback.jsonl",
    "active_skill_index": "cortex-active-skill-index.jsonl",
    "guidance_quality_score": "cortex-guidance-quality-score.jsonl",
    "loop_close_report": "cortex-loop-close-report.jsonl",
    "world_model_simulation": "cortex-world-model-simulation-slot.jsonl",
    "local_compact_expert_adapter": "cortex-local-compact-expert-adapter.jsonl",
}
_READY_PANELS = [
    "system_overview_panel",
    "active_skills_panel",
    "guidance_quality_panel",
    "world_model_panel",
    "frontier_oracle_panel",
    "ci_artifact_panel",
]
_READY_METRICS = [
    "active_skill_count",
    "latest_skill_key",
    "quality_score",
    "benefit_score",
    "risk_score",
    "surprise_score",
    "oracle_required",
    "local_path_remains_primary",
    "loop_close_status",
]


class CortexUiCockpitReadinessRecord(BaseModel):
    cockpit_id: str = Field(default_factory=lambda: f"cortex_ui_cockpit_readiness_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    ci_artifact_path: str
    source_fallback_hash: str | None
    source_ci_export_hash: str | None
    source_quality_score_hash: str | None
    source_loop_report_hash: str | None
    latest_skill_key: str | None
    active_skill_count: int = Field(ge=0)
    panels_ready: list[str]
    metrics_ready: list[str]
    display_contract_version: str
    cockpit_status: str
    cockpit_decision: str
    cockpit_allowed: bool
    next_action: str
    blockers: list[str]
    cockpit_hash: str
    reasons: list[str]


class CortexUiCockpitReadinessJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexUiCockpitReadinessRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexUiCockpitReadinessRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex ui cockpit readiness {line_number}") from exc
        return records

    def save(self, records: list[CortexUiCockpitReadinessRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_ui_cockpit_readiness(profile: Path, ci_artifact_path: Path | None = None) -> dict[str, object]:
    ci_artifact_path = ci_artifact_path or CI_ARTIFACT_EXPORT_PATH
    sources = {name: _latest_jsonl(profile / filename) for name, filename in _PROFILE_SOURCES.items()}
    ci_export = _load_json(ci_artifact_path)
    record = _readiness_record(profile, ci_artifact_path, sources, ci_export)
    path = profile / CORTEX_UI_COCKPIT_READINESS_FILENAME
    store = CortexUiCockpitReadinessJsonlStore(path)
    current = store.load()
    if record.source_fallback_hash and any(item.source_fallback_hash == record.source_fallback_hash for item in current):
        records: list[CortexUiCockpitReadinessRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "cockpit_type": "cortex_ui_cockpit_readiness",
        "profile_path": str(profile),
        "cockpit_path": str(path),
        "cockpit_count": count,
        "cockpit_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_ui_cockpit_readiness(path: Path) -> dict[str, object]:
    records = CortexUiCockpitReadinessJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.cockpit_allowed]
    return {
        "inspect_type": "cortex_ui_cockpit_readiness",
        "path": str(path),
        "exists": path.exists(),
        "total_cockpit_count": len(records),
        "allowed_cockpit_count": len(allowed),
        "latest_cockpit_id": latest.cockpit_id if latest else None,
        "latest_cockpit_status": latest.cockpit_status if latest else None,
        "latest_cockpit_decision": latest.cockpit_decision if latest else None,
        "latest_cockpit_allowed": latest.cockpit_allowed if latest else None,
        "latest_active_skill_count": latest.active_skill_count if latest else None,
        "latest_skill_key": latest.latest_skill_key if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_cockpit_hash": latest.cockpit_hash if latest else None,
    }


def _readiness_record(
    profile: Path,
    ci_artifact_path: Path,
    sources: dict[str, dict[str, object] | None],
    ci_export: dict[str, object] | None,
) -> CortexUiCockpitReadinessRecord:
    blockers = _blockers(sources, ci_export)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "ui_cockpit_readiness_ready" if allowed else "ui_cockpit_readiness_blocked"
    next_action = "build_ui_cockpit" if allowed else "repair_ui_cockpit_readiness"
    reasons = ["sources_ready", "panels_ready", "metrics_ready", "ci_artifact_ready"] if allowed else blockers
    active_skill_count = _int(sources["active_skill_index"], "active_skill_count")
    latest_skill_key = _latest_skill_key(sources, ci_export)
    panels = list(_READY_PANELS) if allowed else []
    metrics = list(_READY_METRICS) if allowed else []
    cockpit_hash = _hash(
        str(profile),
        str(ci_artifact_path),
        _str(sources["frontier_oracle_fallback"], "fallback_hash") or "missing_fallback_hash",
        _ci_export_hash(ci_export) or "missing_ci_hash",
        _str(sources["guidance_quality_score"], "score_hash") or "missing_quality_hash",
        _str(sources["loop_close_report"], "report_hash") or "missing_report_hash",
        latest_skill_key or "missing_skill",
        decision,
        next_action,
        *reasons,
    )
    return CortexUiCockpitReadinessRecord(
        profile_path=str(profile),
        ci_artifact_path=str(ci_artifact_path),
        source_fallback_hash=_str(sources["frontier_oracle_fallback"], "fallback_hash"),
        source_ci_export_hash=_ci_export_hash(ci_export),
        source_quality_score_hash=_str(sources["guidance_quality_score"], "score_hash"),
        source_loop_report_hash=_str(sources["loop_close_report"], "report_hash"),
        latest_skill_key=latest_skill_key,
        active_skill_count=active_skill_count,
        panels_ready=panels,
        metrics_ready=metrics,
        display_contract_version="ui_cockpit_readiness_v1",
        cockpit_status=status,
        cockpit_decision=decision,
        cockpit_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        cockpit_hash=cockpit_hash,
        reasons=reasons,
    )


def _blockers(sources: dict[str, dict[str, object] | None], ci_export: dict[str, object] | None) -> list[str]:
    blockers = []
    if not _ok(sources["frontier_oracle_fallback"], "fallback_allowed"):
        blockers.append("missing_or_blocked_frontier_oracle_fallback")
    elif sources["frontier_oracle_fallback"].get("next_action") != "prepare_ui_cockpit_readiness":
        blockers.append("frontier_oracle_not_waiting_ui_cockpit")
    if not _ok(sources["active_skill_index"], "index_allowed"):
        blockers.append("missing_or_blocked_active_skill_index")
    elif _int(sources["active_skill_index"], "active_skill_count") < 1:
        blockers.append("active_skill_count_below_one")
    if not _ok(sources["guidance_quality_score"], "score_allowed"):
        blockers.append("missing_or_blocked_guidance_quality_score")
    elif float(sources["guidance_quality_score"].get("quality_score", 0.0)) < 0.8:
        blockers.append("guidance_quality_below_ui_threshold")
    if not _ok(sources["loop_close_report"], "report_allowed"):
        blockers.append("missing_or_blocked_loop_close_report")
    if not _ok(sources["world_model_simulation"], "simulation_allowed"):
        blockers.append("missing_or_blocked_world_model_simulation")
    if not _ok(sources["local_compact_expert_adapter"], "adapter_allowed"):
        blockers.append("missing_or_blocked_local_compact_adapter")
    if not _ci_export_ok(ci_export):
        blockers.append("missing_or_blocked_ci_artifact_export")
    return blockers


def _latest_jsonl(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows[-1] if rows else None


def _load_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _ok(row: dict[str, object] | None, key: str) -> bool:
    return bool(row and row.get(key) is True)


def _int(row: dict[str, object] | None, key: str) -> int:
    value = row.get(key) if row else 0
    return value if isinstance(value, int) else 0


def _str(row: dict[str, object] | None, key: str) -> str | None:
    value = row.get(key) if row else None
    return value if isinstance(value, str) else None


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


def _latest_skill_key(sources: dict[str, dict[str, object] | None], ci_export: dict[str, object] | None) -> str | None:
    for source, key in (
        ("frontier_oracle_fallback", "selected_skill_key"),
        ("loop_close_report", "selected_skill_key"),
        ("guidance_quality_score", "selected_skill_key"),
    ):
        value = _str(sources[source], key)
        if value:
            return value
    record = ci_export.get("record") if ci_export else None
    if isinstance(record, dict):
        value = record.get("latest_skill_key")
        if isinstance(value, str):
            return value
    return None


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
