from hex_cortex.memory.cortex_hermes_fleet_certificate import (
    build_hermes_fleet_certificate,
)
from hex_cortex.memory.cortex_hermes_node_certificate import (
    build_hermes_node_certificate,
)


def _node(role: str, node_id: str) -> dict[str, object]:
    return build_hermes_node_certificate(
        node_id=node_id,
        role=role,
        hermes_version="0.17.0",
        transport="tailscale",
        doctor_passed=True,
        mcp_configured=True,
        tools_visible=True,
        peer_reachable=True,
        memory_separation_confirmed=True,
        operator_approved=True,
    )


def test_dual_node_hermes_fleet_is_ready() -> None:
    payload = build_hermes_fleet_certificate(
        node_certificates=[
            _node("server_primary", "srv-hermes"),
            _node("kali_vm", "kali-hermes"),
        ],
        operator_approved=True,
    )

    assert payload["status"] == "ready"
    assert payload["dual_node_ready"] is True
    assert payload["private_transport_ready"] is True
    assert payload["memory_policy"] == "separate_no_merge"
    assert payload["raw_secret_persisted"] is False


def test_hermes_fleet_requires_distinct_nodes() -> None:
    payload = build_hermes_fleet_certificate(
        node_certificates=[
            _node("server_primary", "same-node"),
            _node("kali_vm", "same-node"),
        ],
        operator_approved=True,
    )

    assert payload["status"] == "blocked"
    assert "hermes_node_identity_collision" in payload["blockers"]


def test_hermes_node_requires_memory_separation() -> None:
    payload = build_hermes_node_certificate(
        node_id="kali-hermes",
        role="kali_vm",
        hermes_version="0.17.0",
        transport="private_lan",
        doctor_passed=True,
        mcp_configured=True,
        tools_visible=True,
        peer_reachable=True,
        memory_separation_confirmed=False,
        operator_approved=True,
    )

    assert payload["status"] == "blocked"
    assert "hermes_memory_separation_not_confirmed" in payload["blockers"]
