from __future__ import annotations

import json

from hex_cortex.memory.cortex_bundle import build_cortex_bundle
from hex_cortex.memory.cortex_bundle import build_cortex_bundle_read_plan
from hex_cortex.memory.cortex_bus import list_cortex_units
from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_coding_model_router import build_coding_model_catalog
from hex_cortex.memory.cortex_coding_model_router import route_coding_task
from hex_cortex.memory.cortex_self_correction import build_self_correction_plan
from hex_cortex.memory.cortex_surfaces import audit_cortex_surface
from hex_cortex.memory.cortex_surfaces import build_cortex_surface_manifest
from hex_cortex.memory.cortex_surfaces import list_cortex_surfaces
from hex_cortex.memory.cortex_wiring import audit_cortex_wiring
from hex_cortex.memory.cortex_wiring import list_cortex_runtime_facts


def list_cortex_rpc_tools() -> list[dict[str, object]]:
    empty_schema = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    readonly = {"readOnlyHint": True, "destructiveHint": False}
    return [
        {
            "name": "hex_cortex_units",
            "title": "HEX-CORTEX Units",
            "description": "List registered units and safety metadata.",
            "inputSchema": empty_schema,
            "annotations": readonly,
        },
        {
            "name": "hex_cortex_wiring",
            "title": "HEX-CORTEX Wiring",
            "description": "Audit wiring with optional boolean runtime facts.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "runtime_facts": {
                        "type": "object",
                        "additionalProperties": {"type": "boolean"},
                    }
                },
                "additionalProperties": False,
            },
            "annotations": readonly,
        },
        {
            "name": "hex_cortex_surfaces",
            "title": "HEX-CORTEX Surfaces",
            "description": "List supported deployment surfaces.",
            "inputSchema": empty_schema,
            "annotations": readonly,
        },
        {
            "name": "hex_cortex_surface_audit",
            "title": "HEX-CORTEX Surface Audit",
            "description": "Audit one deployment surface.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "surface_id": {"type": "string", "minLength": 1},
                    "runtime_facts": {
                        "type": "object",
                        "additionalProperties": {"type": "boolean"},
                    },
                },
                "required": ["surface_id"],
                "additionalProperties": False,
            },
            "annotations": readonly,
        },
        {
            "name": "hex_cortex_manifest",
            "title": "HEX-CORTEX Manifest",
            "description": "Build a secret-free surface manifest.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "surface_id": {"type": "string", "minLength": 1}
                },
                "required": ["surface_id"],
                "additionalProperties": False,
            },
            "annotations": readonly,
        },
        {
            "name": "hex_cortex_read_plan",
            "title": "HEX-CORTEX Read Plan",
            "description": "Run the bundled read-only diagnostic plan.",
            "inputSchema": empty_schema,
            "annotations": readonly,
        },
        {
            "name": "hex_cortex_runtime_facts",
            "title": "HEX-CORTEX Runtime Facts",
            "description": "List facts required for operational readiness.",
            "inputSchema": empty_schema,
            "annotations": readonly,
        },
        {
            "name": "hex_cortex_coding_model_catalog",
            "title": "HEX-CORTEX Coding Model Catalog",
            "description": "Describe the local open-weight and remote API coding rails without calling either model.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "local_endpoint": {"type": "string"},
                    "local_model": {"type": "string"},
                    "remote_provider": {"type": "string"},
                    "remote_model": {"type": "string"},
                    "remote_api_key_ref": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "annotations": readonly,
        },
        {
            "name": "hex_cortex_coding_route",
            "title": "HEX-CORTEX Coding Route",
            "description": "Choose an eligible coding model rail under privacy and operator-approval constraints.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_class": {
                        "type": "string",
                        "enum": [
                            "repository_index",
                            "routine_patch",
                            "complex_patch",
                            "critique",
                            "final_review",
                            "test_failure_repair",
                        ],
                    },
                    "context_sensitivity": {
                        "type": "string",
                        "enum": ["public", "private", "secret"],
                    },
                    "complexity": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                    },
                    "local_available": {"type": "boolean"},
                    "remote_available": {"type": "boolean"},
                    "operator_allows_remote": {"type": "boolean"},
                },
                "required": ["task_class"],
                "additionalProperties": False,
            },
            "annotations": readonly,
        },
        {
            "name": "hex_cortex_self_correction_plan",
            "title": "HEX-CORTEX Self-Correction Plan",
            "description": "Build a bounded, non-mutating repair hypothesis plan for an isolated worktree.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "failure_class": {"type": "string", "minLength": 1},
                    "hypothesis": {"type": "string", "minLength": 1},
                    "baseline_ref": {"type": "string", "minLength": 1},
                    "evaluator_ref": {"type": "string", "minLength": 1},
                },
                "required": [
                    "failure_class",
                    "hypothesis",
                    "baseline_ref",
                    "evaluator_ref",
                ],
                "additionalProperties": False,
            },
            "annotations": readonly,
        },
    ]


def call_cortex_rpc_tool(
    name: str,
    arguments: dict[str, object],
) -> tuple[dict[str, object], bool]:
    registry = build_cortex_bundle()
    if name == "hex_cortex_units":
        error = _reject_arguments(arguments)
        if error:
            return error, True
        return {
            "status": "ok",
            "unit_count": len(registry),
            "units": list_cortex_units(registry),
        }, False
    if name == "hex_cortex_wiring":
        facts = _boolean_facts(arguments.get("runtime_facts", {}))
        if facts is None:
            return _blocked("runtime_facts_invalid"), True
        return audit_cortex_wiring(registry, runtime_facts=facts), False
    if name == "hex_cortex_surfaces":
        error = _reject_arguments(arguments)
        if error:
            return error, True
        rows = list_cortex_surfaces()
        return {
            "status": "ok",
            "surface_count": len(rows),
            "surfaces": rows,
        }, False
    if name == "hex_cortex_surface_audit":
        surface_id = arguments.get("surface_id")
        facts = _boolean_facts(arguments.get("runtime_facts", {}))
        if not isinstance(surface_id, str) or not surface_id.strip() or facts is None:
            return _blocked("surface_arguments_invalid"), True
        payload = audit_cortex_surface(
            surface_id=surface_id,
            registry=registry,
            runtime_facts=facts,
        )
        return payload, payload.get("contract_ready") is not True
    if name == "hex_cortex_manifest":
        surface_id = arguments.get("surface_id")
        if not isinstance(surface_id, str) or not surface_id.strip():
            return _blocked("surface_id_invalid"), True
        payload = build_cortex_surface_manifest(surface_id)
        return payload, payload.get("state") == "blocked"
    if name == "hex_cortex_read_plan":
        error = _reject_arguments(arguments)
        if error:
            return error, True
        payload = run_cortex_units(registry, build_cortex_bundle_read_plan())
        return payload, payload.get("bus_allowed") is not True
    if name == "hex_cortex_runtime_facts":
        error = _reject_arguments(arguments)
        if error:
            return error, True
        rows = list_cortex_runtime_facts()
        return {
            "status": "ok",
            "fact_count": len(rows),
            "runtime_facts": rows,
        }, False
    if name == "hex_cortex_coding_model_catalog":
        allowed = {
            "local_endpoint",
            "local_model",
            "remote_provider",
            "remote_model",
            "remote_api_key_ref",
        }
        if any(key not in allowed for key in arguments):
            return _blocked("coding_catalog_arguments_invalid"), True
        try:
            payload = build_coding_model_catalog(
                local_endpoint=str(arguments.get("local_endpoint", "http://127.0.0.1:8080")),
                local_model=str(arguments.get("local_model", "Qwen3-Coder-30B-A3B-Instruct")),
                remote_provider=str(arguments.get("remote_provider", "openai")),
                remote_model=str(arguments.get("remote_model", "gpt-5.5")),
                remote_api_key_ref=str(arguments.get("remote_api_key_ref", "env:OPENAI_API_KEY")),
            )
        except ValueError:
            return _blocked("coding_catalog_invalid"), True
        return payload, payload.get("status") != "ready"
    if name == "hex_cortex_coding_route":
        task_class = arguments.get("task_class")
        if not isinstance(task_class, str):
            return _blocked("task_class_invalid"), True
        payload = route_coding_task(
            task_class=task_class,
            context_sensitivity=str(arguments.get("context_sensitivity", "private")),
            complexity=str(arguments.get("complexity", "medium")),
            local_available=arguments.get("local_available", True) is True,
            remote_available=arguments.get("remote_available", False) is True,
            operator_allows_remote=arguments.get("operator_allows_remote", False) is True,
        )
        return payload, payload.get("status") != "ready"
    if name == "hex_cortex_self_correction_plan":
        required = ("failure_class", "hypothesis", "baseline_ref", "evaluator_ref")
        if any(not isinstance(arguments.get(key), str) for key in required):
            return _blocked("self_correction_arguments_invalid"), True
        payload = build_self_correction_plan(
            failure_class=str(arguments["failure_class"]),
            hypothesis=str(arguments["hypothesis"]),
            baseline_ref=str(arguments["baseline_ref"]),
            evaluator_ref=str(arguments["evaluator_ref"]),
        )
        return payload, payload.get("status") != "ready"
    return _blocked("unknown_tool"), True


def build_cortex_rpc_tool_result(
    payload: dict[str, object],
    *,
    is_error: bool,
) -> dict[str, object]:
    serialized = json.dumps(payload, sort_keys=True)
    return {
        "content": [{"type": "text", "text": serialized}],
        "structuredContent": payload,
        "isError": is_error,
    }


def _boolean_facts(value: object) -> dict[str, bool] | None:
    if not isinstance(value, dict):
        return None
    if not all(
        isinstance(key, str) and isinstance(item, bool)
        for key, item in value.items()
    ):
        return None
    return dict(value)


def _reject_arguments(arguments: dict[str, object]) -> dict[str, object] | None:
    return _blocked("unexpected_arguments") if arguments else None


def _blocked(blocker: str) -> dict[str, object]:
    return {"status": "blocked", "blockers": [blocker]}
