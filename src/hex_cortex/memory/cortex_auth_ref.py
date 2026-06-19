from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_AUTH_REF_FILENAME = "cortex-auth-refs.jsonl"


def build_cortex_auth_ref(
    *,
    provider: str,
    account: str = "main",
    backend: str = "keyring",
) -> str:
    safe_provider = _safe(provider, field="provider")
    safe_account = _safe(account, field="account")
    if backend not in {"keyring", "vault", "environment", "systemd"}:
        raise ValueError("authentication backend is unsupported")
    return f"{backend}://hex-cortex/{safe_provider}/{safe_account}"


def register_cortex_auth_ref(
    profile: Path,
    *,
    provider: str,
    account: str,
    auth_ref: str,
    scopes: list[str] | None = None,
    verified: bool = False,
) -> dict[str, object]:
    expected_prefixes = ("keyring://", "vault://", "environment://", "systemd://")
    if not auth_ref.startswith(expected_prefixes):
        raise ValueError("auth_ref must use a supported external backend")
    normalized_scopes = sorted(
        {scope.strip() for scope in (scopes or []) if scope.strip()}
    )
    receipt_hash = _hash(
        str(profile),
        provider,
        account,
        auth_ref,
        str(verified),
        *normalized_scopes,
    )
    record = {
        "auth_ref_id": f"cortex_auth_ref_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "provider": provider,
        "account": account,
        "auth_ref": auth_ref,
        "scopes": normalized_scopes,
        "verified": verified,
        "value_persisted": False,
        "external_store_required": True,
        "next_action": (
            "verify_provider_connection"
            if verified
            else "store_value_in_external_backend"
        ),
        "auth_ref_hash": receipt_hash,
    }
    path = profile / CORTEX_AUTH_REF_FILENAME
    rows = _load(path)
    existing = next(
        (row for row in rows if row.get("auth_ref_hash") == receipt_hash),
        None,
    )
    if existing is None:
        rows.append(record)
        _write(path, rows)
        selected = record
    else:
        selected = existing
    return {
        "auth_ref_type": "cortex_external_authentication",
        "auth_ref_path": str(path),
        "auth_ref_count": len(rows),
        "auth_ref_records": [selected],
    }


def _safe(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9_-]+", value):
        raise ValueError(f"{field} must use lowercase safe characters")
    return value


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
    content = "".join(
        json.dumps(row, sort_keys=True) + "\n"
        for row in rows
    )
    path.write_text(content, encoding="utf-8")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
