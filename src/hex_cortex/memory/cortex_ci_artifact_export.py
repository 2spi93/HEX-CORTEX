from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

CORTEX_CI_ARTIFACT_EXPORT_FILENAME = "cortex-ci-artifact-export.json"
_DEFAULT_OUTPUT_DIR = Path("artifacts") / "hex-cortex-ci"
_SOURCES = {
    "readiness_seal": "cortex-memory-first-readiness-seal.jsonl",
    "active_skill_index": "cortex-active-skill-index.jsonl",
    "controlled_skill_use": "cortex-controlled-skill-use.jsonl",
    "guidance": "cortex-controlled-skill-guidance-renderer.jsonl",
    "guidance_receipt": "cortex-guidance-receipt.jsonl",
    "guidance_outcome": "cortex-guidance-outcome.jsonl",
    "loop_close_report": "cortex-loop-close-report.jsonl",
}


class CortexCiArtifactExportRecord(BaseModel):
    export_id: str = Field(default_factory=lambda: f"cortex_ci_artifact_export_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    output_path: str
    export_status: str
    export_decision: str
    export_allowed: bool
    active_skill_count: int = Field(ge=0)
    latest_skill_key: str | None
    latest_use_status: str | None
    latest_guidance_status: str | None
    latest_outcome_status: str | None
    latest_report_status: str | None
    exported_sources: list[str]
    blockers: list[str]
    next_action: str
    export_hash: str
    reasons: list[str]


def build_cortex_ci_artifact_export(profile: Path, output_dir: Path | None = None) -> dict[str, object]:
    output_dir = output_dir or _DEFAULT_OUTPUT_DIR
    latest = {name: _latest_jsonl(profile / filename) for name, filename in _SOURCES.items()}
    blockers = _blockers(latest)
    allowed = not blockers
    status = "exported" if allowed else "blocked"
    decision = "ci_artifact_export_ready" if allowed else "ci_artifact_export_blocked"
    next_action = "publish_ci_artifact" if allowed else "repair_ci_artifact_sources"
    reasons = ["memory_first_loop_closed", "ci_export_materialized"] if allowed else blockers
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / CORTEX_CI_ARTIFACT_EXPORT_FILENAME
    active_skill_count = _int(latest["active_skill_index"], "active_skill_count")
    latest_skill_key = _latest_skill_key(latest)
    export_hash = _hash(
        str(profile),
        str(output_path),
        str(active_skill_count),
        latest_skill_key or "missing_skill_key",
        decision,
        next_action,
        *reasons,
    )
    record = CortexCiArtifactExportRecord(
        profile_path=str(profile),
        output_path=str(output_path),
        export_status=status,
        export_decision=decision,
        export_allowed=allowed,
        active_skill_count=active_skill_count,
        latest_skill_key=latest_skill_key,
        latest_use_status=_str(latest["controlled_skill_use"], "use_status"),
        latest_guidance_status=_str(latest["guidance"], "guidance_status"),
        latest_outcome_status=_str(latest["guidance_outcome"], "outcome_status"),
        latest_report_status=_str(latest["loop_close_report"], "report_status"),
        exported_sources=[name for name, row in latest.items() if row is not None],
        blockers=blockers,
        next_action=next_action,
        export_hash=export_hash,
        reasons=reasons,
    )
    payload = {
        "artifact_type": "hex_cortex_ci_artifact_export",
        "record": record.model_dump(mode="json"),
        "latest": latest,
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def summarize_cortex_ci_artifact_export(output_path: Path | None = None) -> dict[str, object]:
    output_path = output_path or (_DEFAULT_OUTPUT_DIR / CORTEX_CI_ARTIFACT_EXPORT_FILENAME)
    if not output_path.exists():
        return {
            "inspect_type": "cortex_ci_artifact_export",
            "path": str(output_path),
            "exists": False,
        }
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    record = payload.get("record", {})
    return {
        "inspect_type": "cortex_ci_artifact_export",
        "path": str(output_path),
        "exists": True,
        "latest_export_status": record.get("export_status"),
        "latest_export_decision": record.get("export_decision"),
        "latest_export_allowed": record.get("export_allowed"),
        "latest_active_skill_count": record.get("active_skill_count"),
        "latest_skill_key": record.get("latest_skill_key"),
        "latest_next_action": record.get("next_action"),
        "latest_export_hash": record.get("export_hash"),
    }


def _latest_jsonl(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows[-1] if rows else None


def _blockers(latest: dict[str, dict[str, object] | None]) -> list[str]:
    blockers = []
    if not _ok(latest["readiness_seal"], "seal_allowed"):
        blockers.append("missing_or_blocked_readiness_seal")
    if not _ok(latest["active_skill_index"], "index_allowed"):
        blockers.append("missing_or_blocked_active_skill_index")
    if not _ok(latest["controlled_skill_use"], "use_allowed"):
        blockers.append("missing_or_blocked_controlled_skill_use")
    if not _ok(latest["guidance"], "guidance_allowed"):
        blockers.append("missing_or_blocked_guidance")
    if not _ok(latest["guidance_receipt"], "receipt_allowed"):
        blockers.append("missing_or_blocked_guidance_receipt")
    if not _ok(latest["guidance_outcome"], "outcome_allowed"):
        blockers.append("missing_or_blocked_guidance_outcome")
    if not _ok(latest["loop_close_report"], "report_allowed"):
        blockers.append("missing_or_blocked_loop_close_report")
    return blockers


def _ok(row: dict[str, object] | None, key: str) -> bool:
    return bool(row and row.get(key) is True)


def _int(row: dict[str, object] | None, key: str) -> int:
    value = row.get(key) if row else 0
    return value if isinstance(value, int) else 0


def _str(row: dict[str, object] | None, key: str) -> str | None:
    value = row.get(key) if row else None
    return value if isinstance(value, str) else None


def _latest_skill_key(latest: dict[str, dict[str, object] | None]) -> str | None:
    for source, key in (
        ("loop_close_report", "selected_skill_key"),
        ("guidance_outcome", "selected_skill_key"),
        ("controlled_skill_use", "selected_skill_key"),
        ("readiness_seal", "latest_skill_key"),
    ):
        value = _str(latest[source], key)
        if value:
            return value
    return None


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
