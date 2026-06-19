from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

Signer = Callable[[bytes], str]
Verifier = Callable[[bytes, str], bool]


def build_cortex_exchange_packet(
    *,
    source: str,
    target: str,
    capability: str,
    request: dict[str, object],
    signer: Signer,
    ttl_seconds: int = 300,
) -> dict[str, object]:
    if ttl_seconds < 30 or ttl_seconds > 3600:
        raise ValueError("ttl_seconds must be in [30, 3600]")
    created = datetime.now(UTC)
    body = {
        "packet_id": f"cortex_exchange_{uuid4().hex}",
        "created_at": created.isoformat(),
        "expires_at_epoch": int(created.timestamp()) + ttl_seconds,
        "source": source,
        "target": target,
        "capability": capability,
        "request_hash": _stable_hash(request),
        "memory_shared": False,
        "raw_request_persisted": False,
        "protocol": "hex-cortex-exchange-v1",
    }
    signature = signer(_canonical(body))
    if not isinstance(signature, str) or not signature:
        raise ValueError("signer must return a non-empty signature")
    return {
        **body,
        "signature": signature,
        "signer_state_persisted": False,
    }


def verify_cortex_exchange_packet(
    packet: dict[str, object],
    *,
    verifier: Verifier,
    now_epoch: int | None = None,
) -> dict[str, object]:
    signature = packet.get("signature")
    if not isinstance(signature, str) or not signature:
        return _result(False, "signature_missing")
    body = {
        key: value
        for key, value in packet.items()
        if key not in {"signature", "signer_state_persisted"}
    }
    if not verifier(_canonical(body), signature):
        return _result(False, "signature_invalid")
    expiry = body.get("expires_at_epoch")
    if not isinstance(expiry, int):
        return _result(False, "expiry_invalid")
    current = int(datetime.now(UTC).timestamp()) if now_epoch is None else now_epoch
    if expiry < current:
        return _result(False, "packet_expired")
    if body.get("memory_shared") is not False:
        return _result(False, "memory_boundary_violated")
    return _result(True, None)


def _result(allowed: bool, blocker: str | None) -> dict[str, object]:
    return {
        "verification_type": "cortex_exchange_packet",
        "verification_allowed": allowed,
        "memory_boundary_preserved": allowed,
        "blockers": [] if blocker is None else [blocker],
        "next_action": (
            "dispatch_exchange_packet"
            if allowed
            else "reject_exchange_packet"
        ),
    }


def _stable_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _canonical(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
