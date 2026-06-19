from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_ACCOUNT_FILENAME = "cortex-account.jsonl"


def build_cortex_account_receipt(
    profile: Path,
    *,
    candidate: dict[str, object],
    account_ref_hash: str,
    scopes: list[str],
    callback_mode: str = "none",
) -> dict[str, object]:
    canonical_scopes = sorted(set(scopes))
    blockers = []
    if candidate.get("candidate_ready") is not True:
        blockers.append("account_candidate_not_ready")
    if not _text(candidate.get("channel_id")):
        blockers.append("missing_account_channel_id")
    if candidate.get("mode") not in {"read", "write"}:
        blockers.append("account_mode_invalid")
    if not _text(account_ref_hash):
        blockers.append("missing_account_reference_hash")
    if not canonical_scopes or not all(
        isinstance(scope, str) and scope.strip()
        for scope in canonical_scopes
    ):
        blockers.append("account_scopes_invalid")
    if callback_mode not in {"none", "polling", "webhook"}:
        blockers.append("account_callback_mode_invalid")
    if candidate.get("network_call_allowed") is not False:
        blockers.append("account_network_gate_not_false")
    allowed = not blockers
    receipt_hash = _hash(
        str(profile),
        str(candidate.get("channel_id")),
        str(candidate.get("mode")),
        account_ref_hash,
        *canonical_scopes,
        callback_mode,
        *blockers,
    )
    record = {
        "account_receipt_id": f"cortex_account_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "account_status": "ready" if allowed else "blocked",
        "account_allowed": allowed,
        "channel_id": candidate.get("channel_id"),
        "mode": candidate.get("mode"),
        "auth_mode": candidate.get("auth_mode"),
        "account_ref_hash": account_ref_hash,
        "scopes": canonical_scopes,
        "callback_mode": callback_mode,
        "credential_persisted": False,
        "secret_persisted": False,
        "network_call_performed": False,
        "content_published": False,
        "messages_read": False,
        "next_action": _next_action(candidate, allowed),
        "blockers": blockers,
        "account_receipt_hash": receipt_hash,
    }
    path = profile / CORTEX_ACCOUNT_FILENAME
    rows = _load(path)
    existing = next(
        (
            row
            for row in rows
            if row.get("account_receipt_hash") == receipt_hash
        ),
        None,
    )
    if existing is None:
        rows.append(record)
        _write(path, rows)
        selected = record
    else:
        selected = existing
    return {
        "account_type": "cortex_account_receipt",
        "account_path": str(path),
        "account_count": len(rows),
        "account_records": [selected],
    }


def summarize_cortex_account_receipts(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_account_receipt",
        "path": str(path),
        "exists": path.exists(),
        "total_account_count": len(rows),
        "latest_account_allowed": (
            latest.get("account_allowed") if latest else None
        ),
        "latest_channel_id": latest.get("channel_id") if latest else None,
        "latest_mode": latest.get("mode") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
    }


def _next_action(candidate: dict[str, object], allowed: bool) -> str:
    if not allowed:
        return "repair_account_receipt"
    if candidate.get("mode") == "write":
        return "prepare_account_write_adapter"
    return "run_account_read_probe"


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _load(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(row, sort_keys=True) + "\n"
        for row in rows
    )
    path.write_text(text, encoding="utf-8")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
