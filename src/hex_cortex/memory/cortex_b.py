from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_B_FILENAME = "cortex-b.jsonl"
SOURCE_FILENAME = "cortex-a.jsonl"
APPROVAL = "OPERATOR_APPROVE_A1"
Runner = Callable[[dict[str, object]], dict[str, object]]


def build_cortex_b(profile: Path, *, approval: str, runner: Runner | None = None) -> dict[str, object]:
    source = _latest(profile / SOURCE_FILENAME)
    blockers = _blockers(source, approval, runner)
    allowed = not blockers
    shape = source.get("shape") if source and isinstance(source.get("shape"), dict) else {}
    observed = runner(shape) if allowed and runner is not None else {}
    observed_summary = _summary(observed) if observed else None
    observed_hash = _stable_hash(observed) if observed else None
    next_action = "inspect_b_receipt" if allowed else "repair_b"
    b_hash = _hash(
        str(profile),
        _text(source.get("a_hash") if source else None) or "missing_source",
        observed_hash or "missing_observed_hash",
        next_action,
        *blockers,
    )
    record = {
        "b_id": f"cortex_b_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_a_hash": source.get("a_hash") if source else None,
        "b_status": "ready" if allowed else "blocked",
        "b_allowed": allowed,
        "kind": source.get("kind") if source else None,
        "model": source.get("model") if source else None,
        "approval_phrase_matched": approval == APPROVAL,
        "runtime_binding": "operator_runner_injected",
        "model_call_performed": allowed,
        "network_call_performed": allowed,
        "repo_mutation_performed": False,
        "shell_execution_performed": False,
        "raw_output_saved": False,
        "observed_summary": observed_summary,
        "observed_hash": observed_hash,
        "next_action": next_action,
        "blockers": blockers,
        "b_hash": b_hash,
    }
    path = profile / CORTEX_B_FILENAME
    rows = _load(path)
    if not any(row.get("b_hash") == b_hash for row in rows):
        rows.append(record)
    _write(path, rows)
    return {
        "b_type": "cortex_b",
        "profile_path": str(profile),
        "b_path": str(path),
        "b_count": len(rows),
        "b_records": [record],
    }


def summarize_cortex_b(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_b",
        "path": str(path),
        "exists": path.exists(),
        "total_b_count": len(rows),
        "latest_b_allowed": latest.get("b_allowed") if latest else None,
        "latest_kind": latest.get("kind") if latest else None,
        "latest_model": latest.get("model") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_observed_hash": latest.get("observed_hash") if latest else None,
    }


def _blockers(source: dict[str, object] | None, approval: str, runner: Runner | None) -> list[str]:
    blockers = []
    if not source:
        return ["missing_a"]
    if source.get("a_allowed") is not True:
        blockers.append("a_not_allowed")
    if source.get("next_action") != "go_a1":
        blockers.append("a_not_ready")
    if source.get("needs_operator") is not True:
        blockers.append("operator_not_required_by_source")
    if approval != APPROVAL:
        blockers.append("approval_phrase_mismatch")
    if runner is None:
        blockers.append("missing_runner")
    for flag in (
        "did_model",
        "did_net",
        "did_repo",
        "did_cmd",
        "saved_output",
    ):
        if source.get(flag) is not False:
            blockers.append(f"a_{flag}_not_false")
    return blockers


def _summary(observed: dict[str, object]) -> dict[str, object]:
    status = observed.get("status")
    summary = observed.get("summary")
    return {
        "status": status if isinstance(status, str) else "unknown",
        "summary_length": len(summary) if isinstance(summary, str) else 0,
        "schema_keys": sorted(str(key) for key in observed.keys()),
    }


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _latest(path: Path) -> dict[str, object] | None:
    rows = _load(path)
    return rows[-1] if rows else None


def _load(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _stable_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
