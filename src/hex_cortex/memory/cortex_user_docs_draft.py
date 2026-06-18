from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_USER_DOCS_DRAFT_FILENAME = "cortex-user-docs-draft.jsonl"
CI_EVIDENCE_EXPORT_PLAN_FILENAME = "cortex-ci-evidence-export-plan.jsonl"
V13_RELEASE_REPORT_FILENAME = "cortex-v13-release-report.jsonl"
DEFAULT_DOC_PATH = Path("docs") / "HEX_CORTEX_USER_GUIDE_V1_3.md"


def build_cortex_user_docs_draft(profile: Path, *, output_path: Path | None = None) -> dict[str, object]:
    output_path = output_path or DEFAULT_DOC_PATH
    ci_plan = _latest_jsonl(profile / CI_EVIDENCE_EXPORT_PLAN_FILENAME)
    release = _latest_jsonl(profile / V13_RELEASE_REPORT_FILENAME)
    blockers = _blockers(ci_plan, release)
    allowed = not blockers
    status = "written" if allowed else "blocked"
    decision = "user_docs_draft_written" if allowed else "user_docs_draft_blocked"
    next_action = "plan_operator_ui_wording_polish" if allowed else "repair_user_docs_draft"
    reasons = ["ci_evidence_plan_ready", "release_report_ready", "user_docs_written"] if allowed else blockers
    docs_hash = _hash(str(profile), str(output_path), str(ci_plan.get("plan_hash") if ci_plan else "missing_plan"), str(release.get("report_hash") if release else "missing_release"), decision, next_action, *reasons)
    if allowed:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(_render_docs(ci_plan, release, docs_hash), encoding="utf-8")
    record = {
        "docs_id": f"cortex_user_docs_draft_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "output_path": str(output_path),
        "source_ci_plan_hash": ci_plan.get("plan_hash") if ci_plan else None,
        "source_release_hash": release.get("report_hash") if release else None,
        "docs_status": status,
        "docs_decision": decision,
        "docs_allowed": allowed,
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "docs_hash": docs_hash,
    }
    path = profile / CORTEX_USER_DOCS_DRAFT_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("docs_hash") == docs_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {"docs_type": "cortex_user_docs_draft", "profile_path": str(profile), "docs_path": str(path), "docs_count": len(records), "docs_records": [record]}


def summarize_cortex_user_docs_drafts(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_user_docs_draft",
        "path": str(path),
        "exists": path.exists(),
        "total_docs_count": len(records),
        "allowed_docs_count": sum(1 for item in records if item.get("docs_allowed") is True),
        "latest_docs_status": latest.get("docs_status") if latest else None,
        "latest_docs_decision": latest.get("docs_decision") if latest else None,
        "latest_docs_allowed": latest.get("docs_allowed") if latest else None,
        "latest_output_path": latest.get("output_path") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_docs_hash": latest.get("docs_hash") if latest else None,
    }


def _blockers(ci_plan: dict[str, object] | None, release: dict[str, object] | None) -> list[str]:
    blockers = []
    if not ci_plan:
        blockers.append("missing_ci_evidence_export_plan")
    elif ci_plan.get("export_allowed") is not True:
        blockers.append("ci_evidence_export_plan_not_allowed")
    if not release:
        blockers.append("missing_v13_release_report")
    elif release.get("release_allowed") is not True:
        blockers.append("v13_release_report_not_allowed")
    return blockers


def _render_docs(ci_plan: dict[str, object], release: dict[str, object], docs_hash: str) -> str:
    evidence_paths = ci_plan.get("evidence_paths", [])
    evidence_list = "\n".join(f"- `{path}`" for path in evidence_paths)
    return f"""# HEX-CORTEX v1.3 User Guide

## Status

- Release report: `{release.get('output_path')}`
- Release tag: `{release.get('tag_name')}`
- Test summary: `{release.get('pytest_summary')}`
- Evidence export workflow: `{ci_plan.get('workflow_path')}`
- Evidence name: `{ci_plan.get('evidence_name')}`
- Docs hash: `{docs_hash}`

## Run the interactive cockpit

1. Run the tests:

```powershell
python -m pytest
```

2. Rebuild the cockpit data API when evidence changes:

```powershell
python -m hex_cortex.memory.cortex_cockpit_data_api_cli .hex-cortex --pretty
```

3. Rebuild or reopen the interactive cockpit:

```powershell
python -m hex_cortex.memory.cortex_interactive_cockpit_shell_cli .hex-cortex --pretty
start .\\artifacts\\hex-cortex-interactive-cockpit\\index.html
```

## Interpret the cockpit

- `Best routed skill` is the skill currently selected as strongest for the latest architecture loop.
- `Feedback score` aggregates routing quality, skill-use success, guidance quality, outcome usefulness, and closeout stability.
- `Active skills` is the count of skills currently available to the controlled skill loop.
- `Evidence drilldown` contains the full embedded evidence payload used by the cockpit.

## Refresh controls

- Use `Refresh cockpit` after regenerating local evidence.
- Use auto-refresh only for short local review sessions.
- The cockpit is static/local-first, so refresh reloads the page rather than starting a server.

## CI evidence export

The CI evidence workflow exports these paths:

{evidence_list}

The exported evidence is intended for release review and audit, not for runtime state mutation.

## Product hardening notes

Generated runtime folders such as `.hex-cortex/` and `artifacts/` should remain local or CI-exported unless a release explicitly decides to track them.

## Next action

`plan_operator_ui_wording_polish`
"""


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
