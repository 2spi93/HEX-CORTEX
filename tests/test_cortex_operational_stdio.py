"""End-to-end tests for the cortex operational MCP stdio serve loop."""

from __future__ import annotations

import io
import json

from hex_cortex.memory.cortex_operational_stdio import serve_cortex_operational_stdio


def _serve(lines: list[str]) -> list[dict[str, object]]:
    input_stream = io.StringIO("\n".join(lines) + "\n")
    output_stream = io.StringIO()
    exit_code = serve_cortex_operational_stdio(input_stream, output_stream)
    assert exit_code == 0
    return [json.loads(raw) for raw in output_stream.getvalue().splitlines()]


def _rpc(method: str, request_id: int | None = None, params: dict | None = None) -> str:
    message: dict[str, object] = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        message["id"] = request_id
    if params is not None:
        message["params"] = params
    return json.dumps(message)


def test_stdio_full_session_lists_tools_and_answers_ping() -> None:
    responses = _serve(
        [
            _rpc("initialize", 1, {"protocolVersion": "2025-03-26", "capabilities": {}}),
            _rpc("notifications/initialized"),
            _rpc("tools/list", 2),
            _rpc("ping", 3),
        ]
    )

    assert [response["id"] for response in responses] == [1, 2, 3]

    initialize_result = responses[0]["result"]
    assert initialize_result["serverInfo"]["name"] == "hex-cortex"
    assert "instructions" in initialize_result

    tools = responses[1]["result"]["tools"]
    tool_names = {tool["name"] for tool in tools}
    assert "hex_cortex_wiring" in tool_names
    assert "hex_cortex_cognitive_loop" in tool_names
    assert responses[2]["result"] == {}


def test_stdio_rejects_tool_calls_before_initialize() -> None:
    responses = _serve([_rpc("tools/list", 1)])

    assert responses[0]["error"]["code"] == -32002


def test_stdio_reports_parse_error_and_keeps_serving() -> None:
    responses = _serve(
        [
            "this is not json",
            _rpc("initialize", 1, {"protocolVersion": "2025-03-26", "capabilities": {}}),
        ]
    )

    assert responses[0]["error"]["code"] == -32700
    assert responses[0]["id"] is None
    assert "result" in responses[1]


def test_stdio_rejects_non_object_message_and_unknown_tool() -> None:
    responses = _serve(
        [
            json.dumps(["not", "an", "object"]),
            _rpc("initialize", 1, {"protocolVersion": "2025-03-26", "capabilities": {}}),
            _rpc("tools/call", 2, {"name": "does_not_exist", "arguments": {}}),
        ]
    )

    assert responses[0]["error"]["code"] == -32600
    tool_result = responses[2]["result"]
    assert tool_result["isError"] is True


def test_stdio_skips_blank_lines_without_response() -> None:
    responses = _serve(
        [
            "",
            "   ",
            _rpc("ping", 1),
        ]
    )

    assert len(responses) == 1
    assert responses[0]["id"] == 1
