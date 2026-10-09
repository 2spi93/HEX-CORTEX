"""MCP 2026-07-28 stateless stdio adapter.

Keeps the 2025 handshake implementation separate. The caller selects the era
per message through request _meta; modern requests do not require initialize.
This adapter intentionally exposes only the existing read-only tool catalog.
"""

from __future__ import annotations

import os
from pathlib import Path

from hex_cortex.memory.cortex_mcp_skills import LocalSkillCatalog
from hex_cortex.memory.cortex_mcp_tasks import LocalTaskStore

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


def _extensions() -> dict[str, object]:
    extensions: dict[str, object] = {}
    if os.environ.get("HEX_CORTEX_SKILLS_DIRECTORY"):
        extensions["io.modelcontextprotocol/skills"] = {}
    if os.environ.get("HEX_CORTEX_TASK_STORE"):
        extensions["io.modelcontextprotocol/tasks"] = {}
    return extensions


def _skill_catalog() -> LocalSkillCatalog:
    root = os.environ.get("HEX_CORTEX_SKILLS_DIRECTORY")
    if not root:
        raise ValueError("MCP Skills extension not configured")
    return LocalSkillCatalog(Path(root))


def _task_store() -> LocalTaskStore:
    path = os.environ.get("HEX_CORTEX_TASK_STORE")
    if not path:
        raise ValueError("MCP Tasks extension not configured")
    return LocalTaskStore(Path(path))


def _task_capability(meta: dict[str, object]) -> bool:
    capabilities = meta.get(_CAPABILITIES_KEY, {})
    if not isinstance(capabilities, dict):
        return False
    extensions = capabilities.get("extensions", {})
    return isinstance(extensions, dict) and (
        "io.modelcontextprotocol/tasks" in extensions
    )


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
        capabilities: dict[str, object] = {"tools": {"listChanged": False}}
        extensions = _extensions()
        if extensions:
            capabilities["extensions"] = extensions
        if "io.modelcontextprotocol/skills" in extensions:
            capabilities["resources"] = {}
        return _result(
            request_id,
            {
                "supportedVersions": [MODERN_VERSION, LEGACY_VERSION],
                "capabilities": capabilities,
                "instructions": "HEX-CORTEX local read-only diagnostics, planning and measured intelligence.",
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
    if method in {"skills/list", "skills/get", "resources/read", "resources/list"}:
        try:
            catalog = _skill_catalog()
            if method == "skills/list":
                if params.get("cursor") not in (None, ""):
                    raise ValueError("invalid cursor")
                return _result(request_id, {
                    "skills": catalog.all(), "ttlMs": 300000, "cacheScope": "public",
                })
            if method == "skills/get":
                if not isinstance(params.get("uri"), str):
                    raise ValueError("skill uri required")
                return _result(request_id, {
                    "skill": catalog.get(params["uri"]),
                    "ttlMs": 300000, "cacheScope": "public",
                })
            if method == "resources/list":
                resources = [
                    {
                        "uri": item["uri"],
                        "name": str(item["frontmatter"]["name"]),
                        "description": str(item["frontmatter"]["description"]),
                        "mimeType": "text/markdown",
                    }
                    for item in catalog.all()
                ]
                return _result(request_id, {
                    "resources": resources, "ttlMs": 300000, "cacheScope": "public",
                })
            if not isinstance(params.get("uri"), str):
                raise ValueError("resource uri required")
            return _result(request_id, catalog.read(params["uri"]))
        except (ValueError, OSError, UnicodeError) as exc:
            return _error(request_id, -32602, f"Invalid local skill resource: {exc}")
    if method in {"tasks/get", "tasks/update", "tasks/cancel"}:
        if not _task_capability(meta):
            return _error(request_id, -32021, "Missing required client capability")
        try:
            store = _task_store()
            task_id = params.get("taskId")
            if not isinstance(task_id, str):
                raise ValueError("taskId must be a string")
            if method == "tasks/get":
                return _result(request_id, store.get(task_id))
            if method == "tasks/cancel":
                store.cancel(task_id)
                return _result(request_id, {})
            store.update(task_id, params.get("inputResponses", {}))
            return _result(request_id, {})
        except (ValueError, OSError) as exc:
            return _error(request_id, -32602, f"Invalid local task: {exc}")
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(args, dict):
            return _error(request_id, -32602, "Invalid tool call params")
        payload, is_error = call_cortex_operational_rpc_tool(name, args)
        result = build_cortex_rpc_tool_result(payload, is_error=is_error)
        if _task_capability(meta) and os.environ.get("HEX_CORTEX_TASK_STORE"):
            try:
                task = _task_store().create_completed(result)
            except (OSError, ValueError):
                return _error(request_id, -32603, "Local task persistence failed")
            return {
                "jsonrpc": "2.0", "id": request_id,
                "result": {
                    "resultType": "task", **task,
                    "_meta": {_SERVER_INFO_KEY: dict(_SERVER_INFO)},
                },
            }
        return _result(request_id, result)
    return _error(request_id, -32601, "Method not found")
