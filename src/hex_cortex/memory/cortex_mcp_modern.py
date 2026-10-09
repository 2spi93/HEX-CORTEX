"""MCP 2026-07-28 stateless stdio adapter.

Keeps the 2025 handshake implementation separate. The caller selects the era
per message through request _meta; modern requests do not require initialize.
This adapter intentionally exposes only the existing read-only tool catalog.
"""

from __future__ import annotations

from hex_cortex.memory.cortex_operational_rpc_tools import (
    build_cortex_rpc_tool_result,
    call_cortex_operational_rpc_tool,
    list_cortex_operational_rpc_tools,
)

MODERN_VERSION = "2026-07-28"
LEGACY_VERSION = "2025-06-18"
_VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
_CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"
_SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"
_SERVER_INFO = {"name": "hex-cortex", "version": "1.2.0"}


def is_modern_request(message: dict[str, object]) -> bool:
    """Route modern messages without treating all old requests as modern."""
    if message.get("method") == "server/discover":
        return True
    params = message.get("params")
    if not isinstance(params, dict):
        return False
    meta = params.get("_meta")
    return isinstance(meta, dict) and _VERSION_KEY in meta


def _error(request_id: object, code: int, message: str, data: object = None) -> dict[str, object]:
    error: dict[str, object] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _result(request_id: object, content: dict[str, object]) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "resultType": "complete",
            **content,
            "_meta": {_SERVER_INFO_KEY: dict(_SERVER_INFO)},
        },
    }


def handle_modern_request(message: dict[str, object]) -> dict[str, object]:
    """Serve supported read-only MCP RPCs independently of session state."""
    request_id = message.get("id")
    method = message.get("method")
    if message.get("jsonrpc") != "2.0" or not isinstance(method, str):
        return _error(request_id, -32600, "Invalid Request")

    params = message.get("params")
    if not isinstance(params, dict):
        return _error(request_id, -32602, "Missing request params")
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        return _error(request_id, -32602, "Missing per-request MCP metadata")
    version = meta.get(_VERSION_KEY)
    if version != MODERN_VERSION:
        return _error(
            request_id,
            -32022,
            "Unsupported protocol version",
            {"supported": [MODERN_VERSION, LEGACY_VERSION], "requested": version},
        )
    if not isinstance(meta.get(_CAPABILITIES_KEY), dict):
        return _error(request_id, -32602, "Client capabilities must be an object")

    if method == "server/discover":
        return _result(
            request_id,
            {
                "supportedVersions": [MODERN_VERSION, LEGACY_VERSION],
                "capabilities": {"tools": {"listChanged": False}},
                "instructions": "HEX-CORTEX read-only diagnostics, planning and measured intelligence.",
                "ttlMs": 60000,
                "cacheScope": "public",
            },
        )
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        if params.get("cursor") not in (None, ""):
            return _error(request_id, -32602, "Invalid cursor")
        return _result(
            request_id,
            {
                "tools": list_cortex_operational_rpc_tools(),
                "ttlMs": 60000,
                "cacheScope": "public",
            },
        )
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(args, dict):
            return _error(request_id, -32602, "Invalid tool call params")
        payload, is_error = call_cortex_operational_rpc_tool(name, args)
        return _result(
            request_id,
            build_cortex_rpc_tool_result(payload, is_error=is_error),
        )
    return _error(request_id, -32601, "Method not found")
