from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

_PRIVATE_TRANSPORTS = {"tailscale", "wireguard", "ssh_tunnel", "private_lan"}
_ROLES = {"server_primary", "kali_vm"}


def build_hermes_node_certificate(
    *,
    node_id: str,
    role: str,
    hermes_version: str,
    transport: str,
    doctor_passed: bool,
    mcp_configured: bool,
    tools_visible: bool,
    peer_reachable: bool,
    memory_separation_confirmed: bool,
    operator_approved: bool,
) -> dict[str, object]:
    blockers: list[str] = []
    if role not in _ROLES:
        blockers.append("hermes_node_role_invalid")
    if transport not in _PRIVATE_TRANSPORTS:
        blockers.append("private_transport_invalid")
    if not node_id.strip():
        blockers.append("node_id_missing")
    if not hermes_version.strip():
        blockers.append("hermes_version_missing")
    for ready, blocker in (
        (doctor_passed, "hermes_doctor_not_passed"),
        (mcp_configured, "hex_cortex_mcp_not_configured"),
        (tools_visible, "hex_cortex_tools_not_confirmed"),
        (peer_reachable, "hermes_peer_not_reachable"),
        (memory_separation_confirmed, "hermes_memory_separation_not_confirmed"),
        (operator_approved, "operator_approval_required"),
    ):
        if not ready:
            blockers.append(blocker)
    ready = not blockers
    payload = {
        "receipt_type": "hermes_node_certificate_v1",
        "status": "ready" if ready else "blocked",
        "node_id_hash": _hash_text(node_id.strip()) if node_id.strip() else None,
        "role": role,
        "hermes_version": hermes_version.strip()[:200],
        "transport": transport,
        "transport_private": transport in _PRIVATE_TRANSPORTS,
        "doctor_passed": doctor_passed,
        "mcp_configured": mcp_configured,
        "hex_cortex_tools_visible": tools_visible,
        "peer_reachable": peer_reachable,
        "memory_policy": "separate_no_merge",
        "memory_separation_confirmed": memory_separation_confirmed,
        "raw_output_persisted": False,
        "raw_memory_persisted": False,
        "raw_secret_persisted": False,
        "operator_approved": operator_approved,
        "certified_at": datetime.now(UTC).isoformat(),
        "blockers": sorted(set(blockers)),
        "next_action": "retain_hermes_node_certificate" if ready else "repair_hermes_node",
    }
    payload["receipt_hash"] = _stable_hash(payload)
    return payload


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
