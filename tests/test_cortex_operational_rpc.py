from __future__ import annotations

from hex_cortex.memory import cortex_operational_rpc_tools as operational_tools
from hex_cortex.memory.cortex_operational_rpc import handle_cortex_operational_rpc_message
from hex_cortex.memory.cortex_operational_rpc_tools import call_cortex_operational_rpc_tool
from hex_cortex.memory.cortex_operational_rpc_tools import list_cortex_operational_rpc_tools
from hex_cortex.memory.cortex_rpc import CortexRpcSession
from hex_cortex.memory.cortex_rpc import PROTOCOL_VERSION


def test_operational_rpc_catalog_extends_legacy_tools() -> None:
    rows = list_cortex_operational_rpc_tools()

    assert len(rows) == 11
    assert {row["name"] for row in rows} >= {
        "hex_cortex_wiring",
        "hex_cortex_operational_audit",
    }
    assert all(row["annotations"]["readOnlyHint"] is True for row in rows)
    assert all(row["annotations"]["destructiveHint"] is False for row in rows)


def test_wiring_uses_canonical_snapshot_when_facts_are_omitted(monkeypatch) -> None:
    monkeypatch.setattr(
        operational_tools,
        "build_operational_audit",
        lambda *args, **kwargs: _snapshot(),
    )

    payload, is_error = call_cortex_operational_rpc_tool("hex_cortex_wiring", {})

    assert is_error is False
    assert payload["operational_ready"] is True
    assert payload["truth_source"] == "hex_cortex_operational_truth_v1"
    assert payload["runtime_facts"]["local_model_runtime_available"] is True
    assert payload["operational_snapshot"]["readiness"]["runtime_ready"] is True


def test_wiring_preserves_explicit_manual_facts() -> None:
    payload, is_error = call_cortex_operational_rpc_tool(
        "hex_cortex_wiring",
        {"runtime_facts": {"local_model_runtime_available": True}},
    )

    assert is_error is False
    assert payload["runtime_facts"] == {"local_model_runtime_available": True}
    assert "truth_source" not in payload


def test_operational_audit_tool_returns_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(
        operational_tools,
        "build_operational_audit",
        lambda *args, **kwargs: _snapshot(),
    )

    payload, is_error = call_cortex_operational_rpc_tool(
        "hex_cortex_operational_audit",
        {"network": True, "include_research": False},
    )

    assert is_error is False
    assert payload["audit_type"] == "hex_cortex_operational_truth_v1"
    assert payload["runtime_ready"] is True


def test_operational_rpc_initializes_and_lists_tools() -> None:
    session = CortexRpcSession()
    initialized = handle_cortex_operational_rpc_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        },
        session=session,
    )
    listing = handle_cortex_operational_rpc_message(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        session=session,
    )

    assert initialized["result"]["serverInfo"]["version"] == "1.1.0"
    assert len(listing["result"]["tools"]) == 11


def _snapshot() -> dict[str, object]:
    facts = {"local_model_runtime_available": True}
    wiring = {
        "audit_type": "cortex_wiring_audit",
        "architecture_ready": True,
        "operational_ready": True,
        "runtime_facts": facts,
        "runtime_blockers": [],
    }
    return {
        "audit_type": "hex_cortex_operational_truth_v1",
        "audit_hash": "a" * 64,
        "code_ready": True,
        "runtime_ready": True,
        "models_ready": True,
        "research_ready": False,
        "media_ready": True,
        "world_model_ready": True,
        "policy_v2_ready": False,
        "self_correction_ready": False,
        "remote_api_ready": False,
        "server_ready": False,
        "security_ready": False,
        "branch_ready": False,
        "operational_ready": False,
        "runtime_facts": facts,
        "category_blockers": {},
        "wiring": wiring,
        "network_call_performed": True,
        "next_action": "run_searxng_live_citation_audit",
    }
