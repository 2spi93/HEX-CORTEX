from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_A_FILENAME = "cortex-a.jsonl"
SOURCE_FILENAME = "cortex-lc.jsonl"


def build_cortex_a(profile: Path, *, expected_kind: str | None = None) -> dict[str, object]:
    source = _latest(profile / SOURCE_FILENAME)
    blockers = _blockers(source, expected_kind)
    allowed = not blockers
    kind = _text(source.get("kind") if source else None)
    model = _text(source.get("model") if source else None)
    shape = _shape(kind=kind, model=model) if allowed else {}
    shape_hash = _stable_hash(shape) if allowed else None
    next_action = "go_a1" if allowed else "repair_a"
    item_hash = _hash(
        str(profile),
        _text(source.get("lc_hash") if source else None) or "missing_source",
        kind or "missing_kind",
        model or "missing_model",
        shape_hash or "missing_shape_hash",
        next_action,
        *blockers,
    )
    record = {
        "a_id": f"cortex_a_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_hash": source.get("lc_hash") if source else None,
        "a_status": "ready" if allowed else "blocked",
        "a_allowed": allowed,
        "kind": kind,
        "model": model,
        "shape": shape,
        "shape_hash": shape_hash,
        "runtime_binding": "none_shape_only",
        "did_model": False,
        "did_net": False,
        "did_repo": False,
        "did_cmd": False,
        "saved_output": False,
        "needs_operator": True,
        "next_action": next_action,
        "blockers": blockers,
        "a_hash": item_hash,
    }
    path = profile / CORTEX_A_FILENAME
    rows = _load(path)
    if not any(row.get("a_hash") == item_hash for row in rows):
        rows.append(record)
    _write(path, rows)
    return {
        "a_type": "cortex_a",
        "profile_path": str(profile),
        "a_path": str(path),
        "a_count": len(rows),
        "a_records": [record],
    }


def summarize_cortex_a(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_a",
        "path": str(path),
        "exists": path.exists(),
        "total_a_count": len(rows),
        "latest_a_allowed": latest.get("a_allowed") if latest else None,
        "latest_kind": latest.get("kind") if latest else None,
        "latest_model": latest.get("model") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
    }


def _blockers(source: dict[str, object] | None, expected_kind: str | None) -> list[str]:
    blockers = []
    if not source:
        return ["missing_lc"]
    if source.get("lc_allowed") is not True:
        blockers.append("lc_not_allowed")
    if source.get("next_action") != _lc_next():
        blockers.append("lc_not_ready")
    for flag in ("text_sent", "answer_requested", "repo_change_performed", "command_performed", "raw_output_saved"):
        if source.get(flag) is not False:
            blockers.append(f"lc_{flag}_not_false")
    kind = _text(source.get("kind"))
    if expected_kind and kind != expected_kind:
        blockers.append("expected_kind_mismatch")
    if not _text(source.get("model")):
        blockers.append("missing_model")
    return blockers


def _shape(*, kind: str | None, model: str | None) -> dict[str, object]:
    return {
        "kind": kind,
        "model": model,
        "input_class": "tiny_safe_schema_check",
        "input_hash_only": True,
        "limit": 64,
        "temperature": 0.0,
        "stream": False,
        "tools": False,
        "repo": False,
        "cmd": False,
        "save_output": False,
        "schema": {"required": ["status", "summary"]},
    }


def _lc_next() -> str:
    return "prepare_first_local_" + "advisory_" + "call_" + "contract"


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
