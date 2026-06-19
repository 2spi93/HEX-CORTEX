from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from hex_cortex.memory.cortex_a import build_cortex_a
from hex_cortex.memory.cortex_b import APPROVAL, build_cortex_b
from hex_cortex.memory.cortex_lc import build_cortex_lc

CORTEX_C_FILENAME = "cortex-c.jsonl"
Runner = Callable[[dict[str, object]], dict[str, object]]


def build_cortex_c(
    profile: Path,
    *,
    kind: str,
    model: str,
    target: str | None,
    approval: str,
    runner: Runner,
) -> dict[str, object]:
    lc_payload = build_cortex_lc(profile, kind=kind, model=model, target=target)
    a_payload = build_cortex_a(profile, expected_kind=kind)
    b_payload = build_cortex_b(profile, approval=approval, runner=runner)
    lc_record = lc_payload["lc_records"][0]
    a_record = a_payload["a_records"][0]
    b_record = b_payload["b_records"][0]
    allowed = bool(
        lc_record.get("lc_allowed") is True
        and a_record.get("a_allowed") is True
        and b_record.get("b_allowed") is True
        and approval == APPROVAL
    )
    blockers = _collect_blockers(lc_record, a_record, b_record, approval)
    c_hash = _hash(
        str(profile),
        str(lc_record.get("lc_hash")),
        str(a_record.get("a_hash")),
        str(b_record.get("b_hash")),
        *blockers,
    )
    record = {
        "c_id": f"cortex_c_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "c_status": "ready" if allowed else "blocked",
        "c_allowed": allowed,
        "kind": kind,
        "model": model,
        "target_redacted": lc_record.get("target_redacted"),
        "lc_hash": lc_record.get("lc_hash"),
        "a_hash": a_record.get("a_hash"),
        "b_hash": b_record.get("b_hash"),
        "observed_hash": b_record.get("observed_hash"),
        "raw_output_saved": False,
        "repo_mutation_performed": False,
        "shell_execution_performed": False,
        "approval_phrase_matched": approval == APPROVAL,
        "next_action": "inspect_c_receipt" if allowed else "repair_c",
        "blockers": blockers,
        "c_hash": c_hash,
    }
    path = profile / CORTEX_C_FILENAME
    rows = _load(path)
    if not any(row.get("c_hash") == c_hash for row in rows):
        rows.append(record)
    _write(path, rows)
    return {
        "c_type": "cortex_c",
        "profile_path": str(profile),
        "c_path": str(path),
        "c_count": len(rows),
        "c_records": [record],
        "lc_records": [lc_record],
        "a_records": [a_record],
        "b_records": [b_record],
    }


def summarize_cortex_c(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_c",
        "path": str(path),
        "exists": path.exists(),
        "total_c_count": len(rows),
        "latest_c_allowed": latest.get("c_allowed") if latest else None,
        "latest_kind": latest.get("kind") if latest else None,
        "latest_model": latest.get("model") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_observed_hash": latest.get("observed_hash") if latest else None,
    }


def _collect_blockers(
    lc_record: dict[str, object],
    a_record: dict[str, object],
    b_record: dict[str, object],
    approval: str,
) -> list[str]:
    blockers = []
    if lc_record.get("lc_allowed") is not True:
        blockers.append("lc_blocked")
    if a_record.get("a_allowed") is not True:
        blockers.append("a_blocked")
    if b_record.get("b_allowed") is not True:
        blockers.append("b_blocked")
    if approval != APPROVAL:
        blockers.append("approval_phrase_mismatch")
    for record_name, record in (("lc", lc_record), ("a", a_record), ("b", b_record)):
        for blocker in record.get("blockers", []):
            blockers.append(f"{record_name}:{blocker}")
    return blockers


def _load(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
