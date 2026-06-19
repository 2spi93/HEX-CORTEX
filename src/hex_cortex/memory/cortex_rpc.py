from __future__ import annotations

from dataclasses import dataclass

from hex_cortex.memory.cortex_rpc_tools import build_cortex_rpc_tool_result
from hex_cortex.memory.cortex_rpc_tools import call_cortex_rpc_tool
from hex_cortex.memory.cortex_rpc_tools import list_cortex_rpc_tools

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "hex-cortex"
SERVER_VERSION = "1.0.0"
SERVER_INSTRUCTIONS = (
    "HEX-CORTEX read-only diagnostics. Inspect units, wiring, deployment surfaces, "
    "runtime requirements, and secret-free manifests. This server exposes no adapter "
    "execution, shell command, network request, secret access, or repository mutation."
)


@dataclass
class CortexRpcSession:
    initialized: bool = False
    client_initialized: bool = False


def handle_cortex_rpc_message(
    message: dict[str, object],
    *,
    session: CortexRpcSession,
) -> dict[str, object] | None:
    request_id = message.get("id")
    method = message.get("method")
    if message.get("jsonrpc") != "2.0" or not isinstance(method, str):
        return rpc_error(request_id, -32600, "Invalid Request")
    if method == "initialize":
        params = message.get("params")
        if not isinstance(params, dict):
            return rpc_error(request_id, -32602, "Invalid initialize params")
        session.initialized = True
        return rpc_result(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": SERVER_NAME,
                    "title": "HEX-CORTEX Read-Only Diagnostics",
                    "version": SERVER_VERSION,
                },
                "instructions": SERVER_INSTRUCTIONS,
            },
        )
    if method == "notifications/initialized":
        if session.initialized:
            session.client_initialized = True
        return None
    if method == "ping":
        return rpc_result(request_id, {})
    if not session.initialized:
        return rpc_error(request_id, -32002, "Server not initialized")
    if method == "tools/list":
        return rpc_result(request_id, {"tools": list_cortex_rpc_tools()})
    if method == "tools/call":
        params = message.get("params")
        if not isinstance(params, dict):
            return rpc_error(request_id, -32602, "Invalid tool call params")
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return rpc_error(request_id, -32602, "Invalid tool call params")
        payload, is_error = call_cortex_rpc_tool(name, arguments)
        return rpc_result(
            request_id,
            build_cortex_rpc_tool_result(payload, is_error=is_error),
        )
    return rpc_error(request_id, -32601, f"Method not found: {method}")


def rpc_result(request_id: object, payload: dict[str, object]) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": payload,
    }


def rpc_error(
    request_id: object,
    code: int,
    message: str,
) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
