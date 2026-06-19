from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_LC_FILENAME = "cortex-lc.jsonl"
_ALLOWED = {"mock", "ollama", "llama_cpp", "local_openai_compatible_api"}
_HTTP = {"ollama", "local_openai_compatible_api"}


def build_cortex_lc(
    profile: Path,
    *,
    kind: str,
    model: str,
    target: str | None = None,
) -> dict[str, object]:
    blockers = _blockers(kind=kind, model=model, target=target)
    allowed = not blockers
    next_action = "prepare_first_local_advisory_call_contract" if allowed else "repair_cortex_lc"
    receipt_hash = _hash(str(profile), kind, model, target or "none", next_action, *blockers)
    record = {
        "lc_id": f"cortex_lc_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "lc_status": "ready" if allowed else "blocked",
        "lc_allowed": allowed,
        "kind": kind,
        "model": model,
        "target_redacted": _redact(target),
        "metadata_only": True,
        "text_sent": False,
        "answer_requested": False,
        "repo_change_performed": False,
        "command_performed": False,
        "raw_output_saved": False,
        "next_action": next_action,
        "blockers": blockers,
        "lc_hash": receipt_hash,
    }
    path = profile / CORTEX_LC_FILENAME
    rows = _load(path)
    if not any(row.get("lc_hash") == receipt_hash for row in rows):
        rows.append(record)
    _write(path, rows)
    return {
        "lc_type": "cortex_lc",
        "profile_path": str(profile),
        "lc_path": str(path),
        "lc_count": len(rows),
        "lc_records": [record],
    }


def summarize_cortex_lc(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_lc",
        "path": str(path),
        "exists": path.exists(),
        "total_lc_count": len(rows),
        "latest_lc_allowed": latest.get("lc_allowed") if latest else None,
        "latest_kind": latest.get("kind") if latest else None,
        "latest_model": latest.get("model") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
    }


def _blockers(*, kind: str, model: str, target: str | None) -> list[str]:
    blockers = []
    if kind not in _ALLOWED:
        blockers.append("unsupported_kind")
    if not model.strip():
        blockers.append("missing_model")
    if kind in _HTTP and not _is_local(target):
        blockers.append("target_not_local")
    if kind not in _HTTP and target is not None and target.startswith("http"):
        blockers.append("unexpected_http_target")
    return blockers


def _is_local(target: str | None) -> bool:
    if not isinstance(target, str):
        return False
    return target.startswith("http://127.0.0.1") or target.startswith("http://localhost")


def _redact(target: str | None) -> str | None:
    if target is None:
        return None
    if target.startswith("http://127.0.0.1"):
        return "http://127.0.0.1:<redacted>"
    if target.startswith("http://localhost"):
        return "http://localhost:<redacted>"
    return "local-target-redacted"


def _load(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
