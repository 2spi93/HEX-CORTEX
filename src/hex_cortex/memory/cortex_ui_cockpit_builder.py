from __future__ import annotations

import hashlib
import html
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_ui_cockpit_readiness import (
    CORTEX_UI_COCKPIT_READINESS_FILENAME,
    CortexUiCockpitReadinessJsonlStore,
    CortexUiCockpitReadinessRecord,
)

CORTEX_UI_COCKPIT_BUILD_FILENAME = "cortex-ui-cockpit-build.jsonl"
DEFAULT_COCKPIT_DIR = Path("artifacts") / "hex-cortex-ui-cockpit"
DEFAULT_CI_ARTIFACT_PATH = Path("artifacts") / "hex-cortex-ci" / "cortex-ci-artifact-export.json"


class CortexUiCockpitBuildRecord(BaseModel):
    build_id: str = Field(default_factory=lambda: f"cortex_ui_cockpit_build_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_readiness_hash: str | None
    ci_artifact_path: str
    output_dir: str
    html_path: str
    summary_path: str
    panels_rendered: list[str]
    metrics_rendered: list[str]
    active_skill_count: int = Field(ge=0)
    latest_skill_key: str | None
    build_status: str
    build_decision: str
    build_allowed: bool
    next_action: str
    blockers: list[str]
    build_hash: str
    reasons: list[str]


class CortexUiCockpitBuildJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexUiCockpitBuildRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexUiCockpitBuildRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex ui cockpit build {line_number}") from exc
        return records

    def save(self, records: list[CortexUiCockpitBuildRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_ui_cockpit(
    profile: Path,
    *,
    output_dir: Path | None = None,
    ci_artifact_path: Path | None = None,
) -> dict[str, object]:
    output_dir = output_dir or DEFAULT_COCKPIT_DIR
    ci_artifact_path = ci_artifact_path or DEFAULT_CI_ARTIFACT_PATH
    readiness = _latest_readiness(profile)
    ci_artifact = _load_json(ci_artifact_path)
    record = _build_record(profile, output_dir, ci_artifact_path, readiness, ci_artifact)
    if record.build_allowed:
        output_dir.mkdir(parents=True, exist_ok=True)
        summary = _summary_payload(record, readiness, ci_artifact)
        Path(record.summary_path).write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        Path(record.html_path).write_text(_render_html(summary), encoding="utf-8")
    path = profile / CORTEX_UI_COCKPIT_BUILD_FILENAME
    store = CortexUiCockpitBuildJsonlStore(path)
    current = store.load()
    count = store.save([*current, record])
    return {
        "build_type": "cortex_ui_cockpit_build",
        "profile_path": str(profile),
        "build_path": str(path),
        "build_count": count,
        "build_records": [record.model_dump(mode="json")],
    }


def summarize_cortex_ui_cockpit_builds(path: Path) -> dict[str, object]:
    records = CortexUiCockpitBuildJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.build_allowed]
    return {
        "inspect_type": "cortex_ui_cockpit_build",
        "path": str(path),
        "exists": path.exists(),
        "total_build_count": len(records),
        "allowed_build_count": len(allowed),
        "latest_build_id": latest.build_id if latest else None,
        "latest_build_status": latest.build_status if latest else None,
        "latest_build_decision": latest.build_decision if latest else None,
        "latest_build_allowed": latest.build_allowed if latest else None,
        "latest_html_path": latest.html_path if latest else None,
        "latest_summary_path": latest.summary_path if latest else None,
        "latest_active_skill_count": latest.active_skill_count if latest else None,
        "latest_skill_key": latest.latest_skill_key if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_build_hash": latest.build_hash if latest else None,
    }


def _latest_readiness(profile: Path) -> CortexUiCockpitReadinessRecord | None:
    records = CortexUiCockpitReadinessJsonlStore(profile / CORTEX_UI_COCKPIT_READINESS_FILENAME).load()
    return records[-1] if records else None


def _load_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _build_record(profile: Path, output_dir: Path, ci_artifact_path: Path, readiness, ci_artifact) -> CortexUiCockpitBuildRecord:
    blockers = []
    if readiness is None:
        blockers.append("missing_ui_cockpit_readiness")
    elif readiness.cockpit_allowed is not True:
        blockers.append("ui_cockpit_readiness_not_allowed")
    elif readiness.next_action != "build_ui_cockpit":
        blockers.append("ui_cockpit_readiness_not_waiting_build")
    if not _ci_artifact_ready(ci_artifact):
        blockers.append("missing_or_blocked_ci_artifact_export")
    allowed = not blockers
    html_path = output_dir / "index.html"
    summary_path = output_dir / "cockpit-summary.json"
    status = "built" if allowed else "blocked"
    decision = "ui_cockpit_built" if allowed else "ui_cockpit_build_blocked"
    next_action = "operate_ui_cockpit" if allowed else "repair_ui_cockpit_build"
    reasons = ["readiness_ready", "ci_artifact_loaded", "static_cockpit_built"] if allowed else blockers
    panels = readiness.panels_ready if readiness and allowed else []
    metrics = readiness.metrics_ready if readiness and allowed else []
    build_hash = _hash(
        str(profile),
        readiness.cockpit_hash if readiness else "missing_readiness",
        _ci_export_hash(ci_artifact) or "missing_ci_hash",
        str(html_path),
        str(summary_path),
        decision,
        next_action,
        *reasons,
    )
    return CortexUiCockpitBuildRecord(
        profile_path=str(profile),
        source_readiness_hash=readiness.cockpit_hash if readiness else None,
        ci_artifact_path=str(ci_artifact_path),
        output_dir=str(output_dir),
        html_path=str(html_path),
        summary_path=str(summary_path),
        panels_rendered=panels,
        metrics_rendered=metrics,
        active_skill_count=readiness.active_skill_count if readiness else 0,
        latest_skill_key=readiness.latest_skill_key if readiness else None,
        build_status=status,
        build_decision=decision,
        build_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        build_hash=build_hash,
        reasons=reasons,
    )


def _summary_payload(record: CortexUiCockpitBuildRecord, readiness, ci_artifact: dict[str, object] | None) -> dict[str, object]:
    latest = ci_artifact.get("latest", {}) if ci_artifact else {}
    ci_record = ci_artifact.get("record", {}) if ci_artifact else {}
    return {
        "cockpit_type": "hex_cortex_ui_cockpit_static",
        "build_record": record.model_dump(mode="json"),
        "readiness": readiness.model_dump(mode="json") if readiness else None,
        "ci_export_record": ci_record,
        "latest": latest,
    }


def _render_html(summary: dict[str, object]) -> str:
    build = summary["build_record"]
    readiness = summary.get("readiness") or {}
    ci_record = summary.get("ci_export_record") or {}
    latest = summary.get("latest") or {}
    panels = build.get("panels_rendered", [])
    metrics = build.get("metrics_rendered", [])
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8" />',
            '<meta name="viewport" content="width=device-width, initial-scale=1" />',
            "<title>HEX-CORTEX Cockpit</title>",
            "<style>",
            "body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#0b1020;color:#eef2ff;margin:0;padding:32px;}",
            ".wrap{max-width:1120px;margin:0 auto;}",
            ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;}",
            ".card{background:#111936;border:1px solid #26345f;border-radius:16px;padding:18px;box-shadow:0 10px 30px #0004;}",
            ".ok{color:#86efac}.muted{color:#a5b4fc}.value{font-size:28px;font-weight:800;margin:8px 0;}",
            "code{background:#020617;border:1px solid #1e293b;border-radius:8px;padding:2px 6px;}",
            "ul{padding-left:18px} li{margin:6px 0}",
            "</style>",
            "</head>",
            "<body><main class=\"wrap\">",
            "<h1>HEX-CORTEX Cockpit</h1>",
            f"<p class=\"muted\">Static cockpit generated from CI artifact and local cortex runtime evidence. Build: <code>{_e(build.get('build_hash'))}</code></p>",
            "<section class=\"grid\">",
            _card("Status", _e(build.get("build_status")), _e(build.get("build_decision"))),
            _card("Active skills", str(_e(build.get("active_skill_count"))), _e(build.get("latest_skill_key"))),
            _card("CI export", _e(ci_record.get("export_status")), _e(ci_record.get("export_decision"))),
            _card("Next action", _e(build.get("next_action")), ""),
            "</section>",
            "<h2>Panels ready</h2>",
            _list(panels),
            "<h2>Metrics ready</h2>",
            _list(metrics),
            "<h2>Evidence snapshot</h2>",
            "<section class=\"grid\">",
            _evidence_card("Guidance quality", latest, "guidance_quality_score", ["quality_score", "score_decision"]),
            _evidence_card("World model", latest, "world_model_simulation", ["benefit_score", "risk_score", "surprise_score", "simulation_decision"]),
            _evidence_card("Frontier oracle", latest, "frontier_oracle_fallback", ["oracle_mode", "oracle_required", "local_path_remains_primary"]),
            _evidence_card("Loop close", latest, "loop_close_report", ["report_status", "report_decision"]),
            "</section>",
            "</main></body></html>",
        ]
    )


def _card(title: str, value: str, detail: str) -> str:
    return f'<article class="card"><h3>{html.escape(title)}</h3><div class="value ok">{value}</div><p class="muted">{detail}</p></article>'


def _evidence_card(title: str, latest: dict[str, object], key: str, fields: list[str]) -> str:
    row = latest.get(key, {})
    if not isinstance(row, dict):
        row = {}
    items = "".join(f"<li><code>{html.escape(field)}</code>: {html.escape(str(row.get(field, '—')))}</li>" for field in fields)
    return f'<article class="card"><h3>{html.escape(title)}</h3><ul>{items}</ul></article>'


def _list(values: list[object]) -> str:
    return "<ul>" + "".join(f"<li><code>{html.escape(str(value))}</code></li>" for value in values) + "</ul>"


def _e(value: object) -> str:
    return html.escape(str(value if value is not None else "—"))


def _ci_artifact_ready(payload: dict[str, object] | None) -> bool:
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


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
