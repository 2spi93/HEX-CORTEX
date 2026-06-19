import io
import json

from hex_cortex.memory.cortex_stdio import serve_cortex_stdio


def test_stdio_serves_lifecycle_and_tools() -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        },
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "hex_cortex_runtime_facts",
                "arguments": {},
            },
        },
    ]
    source = io.StringIO(
        "".join(json.dumps(message) + "\n" for message in messages)
    )
    target = io.StringIO()

    code = serve_cortex_stdio(source, target)
    rows = [json.loads(line) for line in target.getvalue().splitlines()]

    assert code == 0
    assert len(rows) == 3
    assert rows[0]["id"] == 1
    assert rows[1]["id"] == 2
    assert len(rows[1]["result"]["tools"]) == 7
    assert rows[2]["id"] == 3
    assert rows[2]["result"]["isError"] is False


def test_stdio_returns_parse_and_invalid_request_errors() -> None:
    source = io.StringIO("not-json\n[]\n")
    target = io.StringIO()

    serve_cortex_stdio(source, target)
    rows = [json.loads(line) for line in target.getvalue().splitlines()]

    assert rows[0]["error"]["code"] == -32700
    assert rows[1]["error"]["code"] == -32600


def test_stdio_writes_only_json_rpc_messages() -> None:
    source = io.StringIO(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"})
        + "\n"
    )
    target = io.StringIO()

    serve_cortex_stdio(source, target)
    lines = target.getvalue().splitlines()

    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {},
    }
