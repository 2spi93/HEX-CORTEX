from __future__ import annotations

import hashlib
import html
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_cockpit_data_api import (
    COCKPIT_DATA_API_JSON_FILENAME,
    CORTEX_COCKPIT_DATA_API_FILENAME,
    CortexCockpitDataApiJsonlStore,
)
from hex_cortex.memory.cortex_ui_cockpit_builder import DEFAULT_COCKPIT_DIR

CORTEX_INTERACTIVE_COCKPIT_SHELL_FILENAME = "cortex-interactive-cockpit-shell.jsonl"
DEFAULT_INTERACTIVE_COCKPIT_DIR = Path("artifacts") / "hex-cortex-interactive-cockpit"


class CortexInteractiveCockpitShellRecord(BaseModel):
    shell_id: str = Field(default_factory=lambda: f"cortex_interactive_cockpit_shell_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_api_hash: str | None
    data_api_path: str
    output_dir: str
    html_path: str
    summary_path: str
    widgets_rendered: list[str]
    interactions_enabled: list[str]
    best_skill_key: str | None
    best_feedback_score: float = Field(ge=0.0, le=1.0)
    active_skill_count: int = Field(ge=0)
    shell_status: str
    shell_decision: str
    shell_allowed: bool
    next_action: str
    blockers: list[str]
    shell_hash: str
    reasons: list[str]


class CortexInteractiveCockpitShellJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexInteractiveCockpitShellRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexInteractiveCockpitShellRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex interactive cockpit shell {line_number}") from exc
        return records

    def save(self, records: list[CortexInteractiveCockpitShellRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_interactive_cockpit_shell(
    profile: Path,
    *,
    output_dir: Path | None = None,
    data_api_path: Path | None = None,
) -> dict[str, object]:
    output_dir = output_dir or DEFAULT_INTERACTIVE_COCKPIT_DIR
    data_api_path = data_api_path or (DEFAULT_COCKPIT_DIR / COCKPIT_DATA_API_JSON_FILENAME)
    api_record = _latest_api_record(profile)
    data_api = _load_json(data_api_path)
    record = _shell_record(profile, output_dir, data_api_path, api_record, data_api)
    if record.shell_allowed:
        output_dir.mkdir(parents=True, exist_ok=True)
        summary = _summary_payload(record, api_record, data_api)
        Path(record.summary_path).write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        Path(record.html_path).write_text(_render_html(summary), encoding="utf-8")
    path = profile / CORTEX_INTERACTIVE_COCKPIT_SHELL_FILENAME
    store = CortexInteractiveCockpitShellJsonlStore(path)
    current = store.load()
    current_hashes = {item.shell_hash for item in current}
    records = [] if record.shell_hash in current_hashes else [record]
    count = store.save([*current, *records])
    return {
        "shell_type": "cortex_interactive_cockpit_shell",
        "profile_path": str(profile),
        "shell_path": str(path),
        "shell_count": count,
        "shell_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_interactive_cockpit_shells(path: Path) -> dict[str, object]:
    records = CortexInteractiveCockpitShellJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.shell_allowed]
    return {
        "inspect_type": "cortex_interactive_cockpit_shell",
        "path": str(path),
        "exists": path.exists(),
        "total_shell_count": len(records),
        "allowed_shell_count": len(allowed),
        "latest_shell_id": latest.shell_id if latest else None,
        "latest_shell_status": latest.shell_status if latest else None,
        "latest_shell_decision": latest.shell_decision if latest else None,
        "latest_shell_allowed": latest.shell_allowed if latest else None,
        "latest_html_path": latest.html_path if latest else None,
        "latest_summary_path": latest.summary_path if latest else None,
        "latest_best_skill_key": latest.best_skill_key if latest else None,
        "latest_best_feedback_score": latest.best_feedback_score if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_shell_hash": latest.shell_hash if latest else None,
    }


def _latest_api_record(profile: Path):
    records = CortexCockpitDataApiJsonlStore(profile / CORTEX_COCKPIT_DATA_API_FILENAME).load()
    return records[-1] if records else None


def _load_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _shell_record(profile: Path, output_dir: Path, data_api_path: Path, api_record, data_api: dict[str, object] | None) -> CortexInteractiveCockpitShellRecord:
    blockers = _blockers(api_record, data_api)
    allowed = not blockers
    status = "built" if allowed else "blocked"
    decision = "interactive_cockpit_shell_built" if allowed else "interactive_cockpit_shell_blocked"
    next_action = "operate_interactive_cockpit" if allowed else "repair_interactive_cockpit_shell"
    reasons = ["cockpit_data_api_ready", "interactive_shell_rendered", "embedded_data_loaded"] if allowed else blockers
    html_path = output_dir / "index.html"
    summary_path = output_dir / "interactive-cockpit-summary.json"
    api_hash = api_record.api_hash if api_record else None
    best_skill_key = api_record.best_skill_key if api_record else None
    best_feedback_score = api_record.best_feedback_score if api_record else 0.0
    active_skill_count = api_record.active_skill_count if api_record else 0
    widgets = ["status_cards", "skill_usage_table", "feedback_breakdown", "json_drilldown", "text_filter"] if allowed else []
    interactions = ["filter", "expand_drilldown", "copy_json_snapshot"] if allowed else []
    shell_hash = _hash(
        str(profile),
        str(data_api_path),
        api_hash or "missing_api_hash",
        best_skill_key or "missing_skill",
        str(best_feedback_score),
        decision,
        next_action,
        *reasons,
    )
    return CortexInteractiveCockpitShellRecord(
        profile_path=str(profile),
        source_api_hash=api_hash,
        data_api_path=str(data_api_path),
        output_dir=str(output_dir),
        html_path=str(html_path),
        summary_path=str(summary_path),
        widgets_rendered=widgets,
        interactions_enabled=interactions,
        best_skill_key=best_skill_key,
        best_feedback_score=best_feedback_score,
        active_skill_count=active_skill_count,
        shell_status=status,
        shell_decision=decision,
        shell_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        shell_hash=shell_hash,
        reasons=reasons,
    )


def _blockers(api_record, data_api: dict[str, object] | None) -> list[str]:
    blockers = []
    if api_record is None:
        blockers.append("missing_cockpit_data_api_record")
    elif api_record.api_allowed is not True:
        blockers.append("cockpit_data_api_not_allowed")
    elif api_record.next_action != "build_interactive_cockpit_shell":
        blockers.append("cockpit_data_api_not_waiting_interactive_shell")
    if not data_api:
        blockers.append("missing_cockpit_data_api_json")
    else:
        record = data_api.get("record")
        if not isinstance(record, dict) or record.get("api_allowed") is not True:
            blockers.append("cockpit_data_api_json_not_allowed")
    return blockers


def _summary_payload(record: CortexInteractiveCockpitShellRecord, api_record, data_api: dict[str, object] | None) -> dict[str, object]:
    return {
        "shell_type": "hex_cortex_interactive_cockpit_static_shell",
        "shell_record": record.model_dump(mode="json"),
        "api_record": api_record.model_dump(mode="json") if api_record else None,
        "data_api": data_api,
    }


def _render_html(summary: dict[str, object]) -> str:
    encoded = json.dumps(summary, sort_keys=True).replace("</", "<\\/")
    shell = summary["shell_record"]
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8" />',
            '<meta name="viewport" content="width=device-width, initial-scale=1" />',
            "<title>HEX-CORTEX Interactive Cockpit</title>",
            "<style>",
            "body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#07111f;color:#e5eefc;margin:0;padding:28px;}",
            ".wrap{max-width:1180px;margin:0 auto;}.top{display:flex;gap:16px;align-items:center;justify-content:space-between;flex-wrap:wrap;}",
            "input{background:#0f1b31;color:#e5eefc;border:1px solid #2d3d63;border-radius:12px;padding:12px 14px;min-width:280px;}",
            ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;margin:18px 0;}",
            ".card{background:#0d1830;border:1px solid #26385f;border-radius:16px;padding:16px;box-shadow:0 8px 26px #0005;}",
            ".value{font-size:26px;font-weight:800;color:#8ef0b3}.muted{color:#9fb2d9}.bad{color:#fca5a5}.tag{display:inline-block;border:1px solid #355080;border-radius:999px;padding:4px 8px;margin:4px;color:#c7d2fe;}",
            "table{width:100%;border-collapse:collapse;background:#0d1830;border-radius:14px;overflow:hidden}th,td{border-bottom:1px solid #26385f;padding:10px;text-align:left}th{color:#a5b4fc}",
            "details{background:#0d1830;border:1px solid #26385f;border-radius:16px;padding:14px;margin:14px 0}summary{cursor:pointer;color:#bfdbfe;font-weight:700}",
            "pre{white-space:pre-wrap;word-break:break-word;background:#020817;border:1px solid #1e2d4f;border-radius:12px;padding:14px;color:#dbeafe;}",
            "button{background:#1d4ed8;color:white;border:0;border-radius:12px;padding:11px 14px;cursor:pointer}",
            "</style>",
            "</head>",
            "<body><main class=\"wrap\">",
            "<div class=\"top\"><div><h1>HEX-CORTEX Interactive Cockpit</h1><p class=\"muted\">Self-contained local cockpit shell with embedded API data.</p></div><input id=\"filter\" placeholder=\"Filter skill, status, panel...\" /></div>",
            "<section id=\"cards\" class=\"grid\"></section>",
            "<section class=\"card\"><h2>Skill usage</h2><div id=\"skillTable\"></div></section>",
            "<details open><summary>Feedback breakdown</summary><div id=\"feedback\"></div></details>",
            "<details><summary>Full JSON drilldown</summary><button id=\"copy\">Copy JSON snapshot</button><pre id=\"json\"></pre></details>",
            f'<script id="payload" type="application/json">{encoded}</script>',
            "<script>",
            "const DATA=JSON.parse(document.getElementById('payload').textContent);",
            "const api=DATA.data_api||{}; const rec=api.record||{}; const skills=(api.skills&&api.skills.history_entries)||[]; const feedback=api.feedback||{}; const shell=DATA.shell_record||{};",
            "function q(v){return String(v===undefined||v===null?'—':v)}",
            "function card(title,value,detail){return `<article class='card'><h3>${title}</h3><div class='value'>${q(value)}</div><p class='muted'>${q(detail)}</p></article>`}",
            "function render(){const f=document.getElementById('filter').value.toLowerCase(); const blob=JSON.stringify(DATA).toLowerCase(); const hidden=f&&!blob.includes(f); document.getElementById('cards').style.display=hidden?'none':'grid'; document.getElementById('cards').innerHTML=[card('API status',rec.api_status,rec.api_decision),card('Best skill',rec.best_skill_key,'feedback '+q(rec.best_feedback_score)),card('Active skills',rec.active_skill_count,'successful '+q(rec.successful_usage_count)+'/'+q(rec.total_usage_count)),card('Next action',rec.next_action,'shell '+q(shell.shell_status))].join(''); renderSkills(f); renderFeedback(); document.getElementById('json').textContent=JSON.stringify(DATA,null,2)}",
            "function renderSkills(f){let rows=skills.filter(s=>!f||JSON.stringify(s).toLowerCase().includes(f)); if(!rows.length){document.getElementById('skillTable').innerHTML='<p class=muted>No matching skill.</p>';return} document.getElementById('skillTable').innerHTML='<table><thead><tr><th>Skill</th><th>Domain</th><th>Usage</th><th>Success</th><th>Avg feedback</th></tr></thead><tbody>'+rows.map(s=>`<tr><td>${q(s.skill_key)}</td><td>${q(s.domain)}</td><td>${q(s.usage_count)}</td><td>${q(s.success_count)}</td><td>${q(s.average_feedback_score)}</td></tr>`).join('')+'</tbody></table>'}",
            "function renderFeedback(){document.getElementById('feedback').innerHTML=['route_quality_score','skill_use_success_score','guidance_quality_score','outcome_score','stability_score','feedback_score'].map(k=>`<span class='tag'>${k}: ${q(feedback[k])}</span>`).join('')}",
            "document.getElementById('filter').addEventListener('input',render); document.getElementById('copy').addEventListener('click',()=>navigator.clipboard&&navigator.clipboard.writeText(JSON.stringify(DATA,null,2))); render();",
            "</script>",
            "</main></body></html>",
        ]
    )


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
