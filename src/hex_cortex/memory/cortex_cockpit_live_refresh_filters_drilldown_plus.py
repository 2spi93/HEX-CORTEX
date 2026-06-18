from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_interactive_cockpit_shell import DEFAULT_INTERACTIVE_COCKPIT_DIR
from hex_cortex.memory.cortex_interactive_cockpit_ux_polish import (
    CORTEX_INTERACTIVE_COCKPIT_UX_POLISH_FILENAME,
    CortexInteractiveCockpitUxPolishJsonlStore,
)

CORTEX_COCKPIT_LIVE_REFRESH_FILTERS_DRILLDOWN_PLUS_FILENAME = "cortex-cockpit-live-refresh-filters-drilldown-plus.jsonl"
DEFAULT_INTERACTIVE_INDEX_PATH = DEFAULT_INTERACTIVE_COCKPIT_DIR / "index.html"

_MARKER = "hex-cortex-refresh-plus"
_PATCH = """
<style id="hex-cortex-refresh-plus-style">
#hex-cortex-refresh-plus{display:flex;gap:10px;align-items:center;flex-wrap:wrap;background:#0d1830;border:1px solid #26385f;border-radius:16px;padding:12px 14px;margin:14px 0 18px;box-shadow:0 8px 26px #0005}
#hex-cortex-refresh-plus button{margin:0}#hex-cortex-refresh-plus label{color:#c7d2fe}.refreshState{color:#9fb2d9;font-size:13px;overflow-wrap:anywhere}
</style>
<script id="hex-cortex-refresh-plus">
(function(){
  function ready(fn){document.readyState==='loading'?document.addEventListener('DOMContentLoaded',fn):fn()}
  ready(function(){
    if(document.getElementById('hex-cortex-refresh-plus-bar')) return;
    var top=document.querySelector('.top')||document.body;
    var bar=document.createElement('div');
    bar.id='hex-cortex-refresh-plus-bar';
    bar.innerHTML='<button id="hcxRefresh">Refresh cockpit</button><label><input id="hcxAuto" type="checkbox"> auto refresh</label><span class="refreshState" id="hcxState">embedded data mode</span>';
    top.insertAdjacentElement('afterend',bar);
    var timer=null;
    function refresh(){document.getElementById('hcxState').textContent='refresh requested '+new Date().toLocaleTimeString(); setTimeout(function(){location.reload()},120)}
    document.getElementById('hcxRefresh').addEventListener('click',refresh);
    document.getElementById('hcxAuto').addEventListener('change',function(e){ if(e.target.checked){timer=setInterval(refresh,30000); document.getElementById('hcxState').textContent='auto refresh every 30s'} else {clearInterval(timer); document.getElementById('hcxState').textContent='auto refresh off'} });
  })
})();
</script>
""".strip()


class CortexCockpitLiveRefreshFiltersDrilldownPlusRecord(BaseModel):
    plus_id: str = Field(default_factory=lambda: f"cortex_cockpit_live_refresh_filters_drilldown_plus_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_polish_hash: str | None
    source_index_path: str
    output_index_path: str
    features_enabled: list[str]
    plus_status: str
    plus_decision: str
    plus_allowed: bool
    next_action: str
    blockers: list[str]
    plus_hash: str
    reasons: list[str]


class CortexCockpitLiveRefreshFiltersDrilldownPlusJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexCockpitLiveRefreshFiltersDrilldownPlusRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexCockpitLiveRefreshFiltersDrilldownPlusRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex cockpit refresh plus {line_number}") from exc
        return records

    def save(self, records: list[CortexCockpitLiveRefreshFiltersDrilldownPlusRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_cockpit_live_refresh_filters_drilldown_plus(profile: Path, *, index_path: Path | None = None) -> dict[str, object]:
    index_path = index_path or DEFAULT_INTERACTIVE_INDEX_PATH
    polish = _latest_polish(profile)
    record = _plus_record(profile, index_path, polish)
    if record.plus_allowed:
        markup = index_path.read_text(encoding="utf-8")
        if _MARKER not in markup:
            markup = markup.replace("</body>", f"{_PATCH}\n</body>")
            index_path.write_text(markup, encoding="utf-8")
    path = profile / CORTEX_COCKPIT_LIVE_REFRESH_FILTERS_DRILLDOWN_PLUS_FILENAME
    store = CortexCockpitLiveRefreshFiltersDrilldownPlusJsonlStore(path)
    current = store.load()
    current_hashes = {item.plus_hash for item in current}
    records = [] if record.plus_hash in current_hashes else [record]
    count = store.save([*current, *records])
    return {
        "plus_type": "cortex_cockpit_live_refresh_filters_drilldown_plus",
        "profile_path": str(profile),
        "plus_path": str(path),
        "plus_count": count,
        "plus_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_cockpit_live_refresh_filters_drilldown_plus(path: Path) -> dict[str, object]:
    records = CortexCockpitLiveRefreshFiltersDrilldownPlusJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.plus_allowed]
    return {
        "inspect_type": "cortex_cockpit_live_refresh_filters_drilldown_plus",
        "path": str(path),
        "exists": path.exists(),
        "total_plus_count": len(records),
        "allowed_plus_count": len(allowed),
        "latest_plus_id": latest.plus_id if latest else None,
        "latest_plus_status": latest.plus_status if latest else None,
        "latest_plus_decision": latest.plus_decision if latest else None,
        "latest_plus_allowed": latest.plus_allowed if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_plus_hash": latest.plus_hash if latest else None,
    }


def _latest_polish(profile: Path):
    records = CortexInteractiveCockpitUxPolishJsonlStore(profile / CORTEX_INTERACTIVE_COCKPIT_UX_POLISH_FILENAME).load()
    return records[-1] if records else None


def _plus_record(profile: Path, index_path: Path, polish) -> CortexCockpitLiveRefreshFiltersDrilldownPlusRecord:
    blockers = []
    if polish is None:
        blockers.append("missing_interactive_cockpit_ux_polish")
    elif polish.polish_allowed is not True:
        blockers.append("interactive_cockpit_ux_polish_not_allowed")
    elif polish.next_action != "build_live_refresh_filters_drilldown_plus":
        blockers.append("ux_polish_not_waiting_refresh_plus")
    if not index_path.exists():
        blockers.append("missing_interactive_cockpit_index")
    allowed = not blockers
    features = ["manual_refresh", "optional_auto_refresh", "filter_preserved", "drilldown_preserved", "embedded_mode_fallback"] if allowed else []
    status = "applied" if allowed else "blocked"
    decision = "live_refresh_filters_drilldown_plus_applied" if allowed else "live_refresh_filters_drilldown_plus_blocked"
    next_action = "operate_interactive_cockpit_v1_3" if allowed else "repair_live_refresh_filters_drilldown_plus"
    reasons = ["ux_polish_ready", "refresh_controls_added", "drilldown_preserved"] if allowed else blockers
    plus_hash = _hash(str(profile), str(index_path), polish.polish_hash if polish else "missing_polish", decision, next_action, *features, *reasons)
    return CortexCockpitLiveRefreshFiltersDrilldownPlusRecord(
        profile_path=str(profile),
        source_polish_hash=polish.polish_hash if polish else None,
        source_index_path=str(index_path),
        output_index_path=str(index_path),
        features_enabled=features,
        plus_status=status,
        plus_decision=decision,
        plus_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        plus_hash=plus_hash,
        reasons=reasons,
    )


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
