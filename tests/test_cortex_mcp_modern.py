"""Protocol-era regression tests: MCP 2026-07-28 + 2025 legacy in one stdio process."""

from __future__ import annotations

import io
import json

from hex_cortex.memory.cortex_mcp_modern import handle_modern_request
from hex_cortex.memory.cortex_operational_stdio import serve_cortex_operational_stdio


def modern(method: str, request_id: int, **params: object) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
            },
            **params,
        },
    }


def test_discover_is_stateless_and_advertises_read_only_tools() -> None:
    result = handle_modern_request(modern("server/discover", 1))["result"]
    assert result["resultType"] == "complete"
    assert result["supportedVersions"][0] == "2026-07-28"
    assert result["capabilities"]["tools"]["listChanged"] is False
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "hex-cortex"


def test_tools_list_without_initialize_has_cache_metadata() -> None:
    result = handle_modern_request(modern("tools/list", 2))["result"]
    assert result["ttlMs"] >= 0
    assert result["cacheScope"] == "public"
    assert "hex_cortex_measured_intelligence" in {
        item["name"] for item in result["tools"]
    }


def test_read_only_tool_call_without_initialize() -> None:
    result = handle_modern_request(
        modern(
            "tools/call",
            3,
            name="hex_cortex_measured_intelligence",
            arguments={"action": "benchmark_suite"},
        )
    )["result"]
    assert result["resultType"] == "complete"
    assert result["isError"] is False
    assert "benchmark_suite" in result["content"][0]["text"]


def test_missing_capabilities_fail_closed() -> None:
    request = modern("tools/list", 4)
    del request["params"]["_meta"]["io.modelcontextprotocol/clientCapabilities"]
    error = handle_modern_request(request)["error"]
    assert error["code"] == -32602


def test_unknown_version_reports_compatible_versions() -> None:
    request = modern("tools/list", 5)
    request["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"] = "2099-01-01"
    error = handle_modern_request(request)["error"]
    assert error["code"] == -32022
    assert "2026-07-28" in error["data"]["supported"]


def test_modern_and_legacy_stdio_same_process() -> None:
    legacy_initialize = {
        "jsonrpc": "2.0",
        "id": 9,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
    }
    requests = [
        modern("server/discover", 1),
        modern("tools/list", 2),
        legacy_initialize,
        {"jsonrpc": "2.0", "id": 10, "method": "tools/list"},
    ]
    stdin = io.StringIO("\n".join(json.dumps(item) for item in requests) + "\n")
    stdout = io.StringIO()
    assert serve_cortex_operational_stdio(stdin, stdout) == 0
    output = [json.loads(row) for row in stdout.getvalue().splitlines()]
    assert [row["id"] for row in output] == [1, 2, 9, 10]
    assert output[0]["result"]["resultType"] == "complete"
    assert output[2]["result"]["protocolVersion"] == "2025-06-18"
    assert "resultType" not in output[3]["result"]
