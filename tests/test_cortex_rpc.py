from hex_cortex.memory.cortex_rpc import CortexRpcSession
from hex_cortex.memory.cortex_rpc import PROTOCOL_VERSION
from hex_cortex.memory.cortex_rpc import handle_cortex_rpc_message
from hex_cortex.memory.cortex_rpc_tools import call_cortex_rpc_tool
from hex_cortex.memory.cortex_rpc_tools import list_cortex_rpc_tools


def test_rpc_tool_catalog_is_read_only() -> None:
    rows = list_cortex_rpc_tools()

    assert len(rows) == 10
    assert {row["name"] for row in rows} == {
        "hex_cortex_units",
        "hex_cortex_wiring",
        "hex_cortex_surfaces",
        "hex_cortex_surface_audit",
        "hex_cortex_manifest",
        "hex_cortex_read_plan",
        "hex_cortex_runtime_facts",
        "hex_cortex_coding_model_catalog",
        "hex_cortex_coding_route",
        "hex_cortex_self_correction_plan",
    }
    assert all(row["annotations"]["readOnlyHint"] is True for row in rows)
    assert all(row["annotations"]["destructiveHint"] is False for row in rows)


def test_rpc_requires_initialize_before_tools() -> None:
    response = handle_cortex_rpc_message(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        session=CortexRpcSession(),
    )

    assert response["error"]["code"] == -32002


def test_rpc_initialization_and_tool_listing() -> None:
    session = CortexRpcSession()
    initialized = handle_cortex_rpc_message(
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
    notification = handle_cortex_rpc_message(
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
        session=session,
    )
    listing = handle_cortex_rpc_message(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        session=session,
    )

    assert initialized["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert initialized["result"]["capabilities"] == {
        "tools": {"listChanged": False}
    }
    assert notification is None
    assert session.client_initialized is True
    assert len(listing["result"]["tools"]) == 10


def test_rpc_tool_call_returns_structured_and_text_content() -> None:
    session = CortexRpcSession(initialized=True, client_initialized=True)

    response = handle_cortex_rpc_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "hex_cortex_wiring",
                "arguments": {},
            },
        },
        session=session,
    )

    result = response["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["architecture_ready"] is True
    assert result["content"][0]["type"] == "text"


def test_rpc_exposes_coding_route_without_model_call() -> None:
    payload, is_error = call_cortex_rpc_tool(
        "hex_cortex_coding_route",
        {
            "task_class": "routine_patch",
            "context_sensitivity": "private",
            "complexity": "medium",
            "local_available": True,
            "remote_available": False,
            "operator_allows_remote": False,
        },
    )

    assert is_error is False
    assert payload["selected_provider_id"] == "local_open_weight"
    assert payload["model_call_performed"] is False


def test_rpc_exposes_bounded_self_correction_plan() -> None:
    payload, is_error = call_cortex_rpc_tool(
        "hex_cortex_self_correction_plan",
        {
            "failure_class": "test_failure",
            "hypothesis": "Fix the parser without changing its evaluator.",
            "baseline_ref": "main@abc123",
            "evaluator_ref": "pytest",
        },
    )

    assert is_error is False
    assert payload["status"] == "ready"
    assert payload["evaluator_mutation_allowed"] is False
    assert payload["operator_merge_approval_required"] is True


def test_rpc_unknown_tool_is_tool_error() -> None:
    session = CortexRpcSession(initialized=True)

    response = handle_cortex_rpc_message(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "unknown", "arguments": {}},
        },
        session=session,
    )

    assert response["result"]["isError"] is True
    assert response["result"]["structuredContent"]["blockers"] == [
        "unknown_tool"
    ]


def test_rpc_tool_validation_rejects_invalid_facts() -> None:
    payload, is_error = call_cortex_rpc_tool(
        "hex_cortex_wiring",
        {"runtime_facts": {"bad": "not-boolean"}},
    )

    assert is_error is True
    assert payload["blockers"] == ["runtime_facts_invalid"]


def test_rpc_ping_is_available_before_initialize() -> None:
    response = handle_cortex_rpc_message(
        {"jsonrpc": "2.0", "id": 9, "method": "ping"},
        session=CortexRpcSession(),
    )

    assert response == {"jsonrpc": "2.0", "id": 9, "result": {}}
