from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime


def build_hermes_fleet_certificate(
    *,
    node_certificates: list[dict[str, object]],
    operator_approved: bool,
) -> dict[str, object]:
    blockers: list[str] = []
    if not operator_approved:
        blockers.append("operator_approval_required")
    by_role = {
        role: [row for row in node_certificates if row.get("role") == role]
        for role in ("server_primary", "kali_vm")
    }
    for role, rows in by_role.items():
        if len(rows) != 1:
            blockers.append(f"{role}_certificate_count_invalid")
    selected = [rows[0] for rows in by_role.values() if len(rows) == 1]
    hashes = [row.get("node_id_hash") for row in selected]
    if len(hashes) != len(set(hashes)):
        blockers.append("hermes_node_identity_collision")
    for row in selected:
        role = str(row.get("role"))
        for ready, blocker in (
            (row.get("status") == "ready", f"{role}_not_ready"),
            (row.get("transport_private") is True, f"{role}_transport_not_private"),
            (row.get("doctor_passed") is True, f"{role}_doctor_not_passed"),
            (row.get("mcp_configured") is True, f"{role}_mcp_not_configured"),
            (row.get("hex_cortex_tools_visible") is True, f"{role}_tools_not_visible"),
            (row.get("peer_reachable") is True, f"{role}_peer_not_reachable"),
            (row.get("memory_policy") == "separate_no_merge", f"{role}_memory_policy_invalid"),
            (row.get("raw_secret_persisted") is False, f"{role}_secret_persistence_invalid"),
        ):
            if not ready:
                blockers.append(blocker)
    ready = not blockers
    payload = {
        "receipt_type": "hermes_fleet_certificate_v1",
        "status": "ready" if ready else "blocked",
        "fleet_id": "hex_cortex_hermes_dual_node_v1",
        "node_count": len(selected),
        "node_id_hashes": sorted(str(value) for value in hashes if value),
        "server_primary_ready": len(by_role["server_primary"]) == 1 and by_role["server_primary"][0].get("status") == "ready",
        "kali_vm_ready": len(by_role["kali_vm"]) == 1 and by_role["kali_vm"][0].get("status") == "ready",
        "dual_node_ready": ready,
        "private_transport_ready": ready,
        "hermes_adapter_ready": ready,
        "memory_policy": "separate_no_merge",
        "raw_memory_persisted": False,
        "raw_secret_persisted": False,
        "operator_approved": operator_approved,
        "certified_at": datetime.now(UTC).isoformat(),
        "blockers": sorted(set(blockers)),
        "next_action": "operate_hermes_fleet" if ready else "repair_hermes_fleet",
    }
    payload["receipt_hash"] = _stable_hash(payload)
    return payload


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
