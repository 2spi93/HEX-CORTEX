from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_interactive_cockpit_shell import DEFAULT_INTERACTIVE_COCKPIT_DIR

CORTEX_INTERACTIVE_COCKPIT_UX_POLISH_FILENAME = "cortex-interactive-cockpit-ux-polish.jsonl"
DEFAULT_INTERACTIVE_INDEX_PATH = DEFAULT_INTERACTIVE_COCKPIT_DIR / "index.html"

_CSS_MARKER = "hex-cortex-ux-polish"
_CSS = """
<style id="hex-cortex-ux-polish">
.card,.value,.muted,td,th,.tag,pre{overflow-wrap:anywhere;word-break:normal;min-width:0}
.value{font-size:clamp(20px,2.2vw,28px);line-height:1.12;max-width:100%}
.card{overflow:hidden}.grid{align-items:stretch}.muted{line-height:1.45}
table{table-layout:auto}td,th{max-width:360px}pre{max-height:520px;overflow:auto;white-space:pre-wrap}
</style>
""".strip()


class CortexInteractiveCockpitUxPolishRecord(BaseModel):
    polish_id: str = Field(default_factory=lambda: f"cortex_interactive_cockpit_ux_polish_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_index_path: str
    output_index_path: str
    fixes_applied: list[str]
    polish_status: str
    polish_decision: str
    polish_allowed: bool
    next_action: str
    blockers: list[str]
    polish_hash: str
    reasons: list[str]


class CortexInteractiveCockpitUxPolishJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexInteractiveCockpitUxPolishRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexInteractiveCockpitUxPolishRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex interactive cockpit UX polish {line_number}") from exc
        return records

    def save(self, records: list[CortexInteractiveCockpitUxPolishRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_interactive_cockpit_ux_polish(profile: Path, *, index_path: Path | None = None) -> dict[str, object]:
    index_path = index_path or DEFAULT_INTERACTIVE_INDEX_PATH
    record = _polish_record(profile, index_path)
    if record.polish_allowed:
        markup = index_path.read_text(encoding="utf-8")
        if _CSS_MARKER not in markup:
            markup = markup.replace("</head>", f"{_CSS}\n</head>")
            index_path.write_text(markup, encoding="utf-8")
    path = profile / CORTEX_INTERACTIVE_COCKPIT_UX_POLISH_FILENAME
    store = CortexInteractiveCockpitUxPolishJsonlStore(path)
    current = store.load()
    current_hashes = {item.polish_hash for item in current}
    records = [] if record.polish_hash in current_hashes else [record]
    count = store.save([*current, *records])
    return {
        "polish_type": "cortex_interactive_cockpit_ux_polish",
        "profile_path": str(profile),
        "polish_path": str(path),
        "polish_count": count,
        "polish_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_interactive_cockpit_ux_polishes(path: Path) -> dict[str, object]:
    records = CortexInteractiveCockpitUxPolishJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.polish_allowed]
    return {
        "inspect_type": "cortex_interactive_cockpit_ux_polish",
        "path": str(path),
        "exists": path.exists(),
        "total_polish_count": len(records),
        "allowed_polish_count": len(allowed),
        "latest_polish_id": latest.polish_id if latest else None,
        "latest_polish_status": latest.polish_status if latest else None,
        "latest_polish_decision": latest.polish_decision if latest else None,
        "latest_polish_allowed": latest.polish_allowed if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_polish_hash": latest.polish_hash if latest else None,
    }


def _polish_record(profile: Path, index_path: Path) -> CortexInteractiveCockpitUxPolishRecord:
    blockers = []
    if not index_path.exists():
        blockers.append("missing_interactive_cockpit_index")
    allowed = not blockers
    fixes = ["long_value_wrapping", "compact_cards", "pre_wrap_drilldown"] if allowed else []
    decision = "interactive_cockpit_ux_polish_applied" if allowed else "interactive_cockpit_ux_polish_blocked"
    status = "applied" if allowed else "blocked"
    next_action = "build_live_refresh_filters_drilldown_plus" if allowed else "repair_interactive_cockpit_ux_polish"
    reasons = ["interactive_index_found", "card_overflow_fixed"] if allowed else blockers
    polish_hash = _hash(str(profile), str(index_path), decision, next_action, *fixes, *reasons)
    return CortexInteractiveCockpitUxPolishRecord(
        profile_path=str(profile),
        source_index_path=str(index_path),
        output_index_path=str(index_path),
        fixes_applied=fixes,
        polish_status=status,
        polish_decision=decision,
        polish_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        polish_hash=polish_hash,
        reasons=reasons,
    )


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
