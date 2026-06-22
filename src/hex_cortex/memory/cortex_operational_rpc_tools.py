from __future__ import annotations

from pathlib import Path

from hex_cortex.memory.cortex_cognitive_genome import audit_cognitive_genome
from hex_cortex.memory.cortex_cognitive_genome import build_homeostasis_decision
from hex_cortex.memory.cortex_cognitive_genome import build_profile_council
from hex_cortex.memory.cortex_operational_audit_v2 import build_operational_audit
from hex_cortex.memory.cortex_operational_intelligence_tools import (
    call_operational_intelligence_tool,
)
from hex_cortex.memory.cortex_operational_intelligence_tools import (
    list_operational_intelligence_tools,
)
from hex_cortex.memory.cortex_rpc_tools import build_cortex_rpc_tool_result
from hex_cortex.memory.cortex_rpc_tools import call_cortex_rpc_tool as call_legacy_tool
from hex_cortex.memory.cortex_rpc_tools import list_cortex_rpc_tools as list_legacy_tools


def list_cortex_operational_rpc_tools() -> list[dict[str, object]]:
    rows = [dict(row) for row in list_legacy_tools()]
    for row in rows:
        if row.get("name") == "hex_cortex_wiring":
            row["description"] = (
                "Audit wiring from canonical operational truth. When runtime_facts are omitted, "
                "localhost runtimes are probed automatically."
            )
            row["inputSchema"] = {
                "type": "object",
                "properties": {
                    "project_root": {"type": "string"},
                    "network": {"type": "boolean"},
                    "include_research": {"type": "boolean"},
                    "runtime_facts": {
                        "type": "object",
                        "additionalProperties": {"type": "boolean"},
                    },
                },
                "additionalProperties": False,
            }
            break
    rows.append(
        {
            "name": "hex_cortex_operational_audit",
            "title": "HEX-CORTEX Operational Audit",
            "description": (
                "Build one canonical readiness snapshot across code, runtimes, models, research, "
                "media, world model, cognitive genome, security, and server evidence."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_root": {"type": "string"},
                    "network": {"type": "boolean"},
                    "include_research": {"type": "boolean"},
                    "research_query": {"type": "string"},
                    "comfyui_endpoint": {"type": "string"},
                    "searxng_endpoint": {"type": "string"},
                    "runtime_facts": {
                        "type": "object",
                        "additionalProperties": {"type": "boolean"},
                    },
                },
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True, "destructiveHint": False},
        }
    )
    rows.append(
        {
            "name": "hex_cortex_cognitive_genome",
            "title": "HEX-CORTEX Cognitive Genome",
            "description": (
                "Audit the immutable genome or build a read-only profile council and cognitive "
                "homeostasis decision."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_root": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": ["audit", "council", "homeostasis"],
                    },
                    "failure_class": {"type": "string"},
                    "novelty": {"type": "number"},
                    "uncertainty": {"type": "number"},
                    "mutation_requested": {"type": "boolean"},
                    "recurrence_count": {"type": "integer"},
                    "deterministic_verification_available": {"type": "boolean"},
                    "local_verification_failed": {"type": "boolean"},
                    "cost_pressure": {"type": "number"},
                    "regression_risk": {"type": "number"},
                },
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True, "destructiveHint": False},
        }
    )
    rows.extend(list_operational_intelligence_tools())
    return rows


def call_cortex_operational_rpc_tool(
    name: str,
    arguments: dict[str, object],
) -> tuple[dict[str, object], bool]:
    intelligence_result = call_operational_intelligence_tool(name, arguments)
    if intelligence_result is not None:
        return intelligence_result

    if name == "hex_cortex_wiring":
        error = _validate_arguments(
            arguments,
            allowed={"project_root", "network", "include_research", "runtime_facts"},
        )
        if error is not None:
            return error, True
        manual_facts = _boolean_facts(arguments.get("runtime_facts", {}))
        if manual_facts is None:
            return _blocked("runtime_facts_invalid"), True
        if manual_facts:
            return call_legacy_tool(name, {"runtime_facts": manual_facts})
        snapshot = _build_snapshot(
            arguments,
            default_network=True,
            default_include_research=False,
        )
        if snapshot is None:
            return _blocked("operational_audit_arguments_invalid"), True
        wiring = snapshot.get("wiring")
        if not isinstance(wiring, dict):
            return _blocked("operational_wiring_missing"), True
        payload = dict(wiring)
        payload["truth_source"] = "hex_cortex_operational_truth_v1"
        payload["operational_snapshot"] = _compact_snapshot(snapshot)
        return payload, payload.get("architecture_ready") is not True

    if name == "hex_cortex_operational_audit":
        error = _validate_arguments(
            arguments,
            allowed={
                "project_root",
                "network",
                "include_research",
                "research_query",
                "comfyui_endpoint",
                "searxng_endpoint",
                "runtime_facts",
            },
        )
        if error is not None:
            return error, True
        snapshot = _build_snapshot(
            arguments,
            default_network=False,
            default_include_research=True,
        )
        if snapshot is None:
            return _blocked("operational_audit_arguments_invalid"), True
        return snapshot, False

    if name == "hex_cortex_cognitive_genome":
        try:
            payload = _call_cognitive_genome(arguments)
        except (TypeError, ValueError):
            return _blocked("cognitive_genome_arguments_invalid"), True
        return payload, bool(payload.get("blockers"))

    return call_legacy_tool(name, arguments)


def _call_cognitive_genome(arguments: dict[str, object]) -> dict[str, object]:
    action = arguments.get("action", "audit")
    project_root = arguments.get("project_root", ".")
    if not isinstance(project_root, str) or not project_root.strip():
        raise ValueError("project_root invalid")
    if action == "audit":
        allowed = {"project_root", "action"}
        if any(key not in allowed for key in arguments):
            raise ValueError("audit arguments invalid")
        return audit_cognitive_genome(Path(project_root) / "config" / "cognitive_genome_v1.json")
    if action == "council":
        allowed = {
            "project_root",
            "action",
            "failure_class",
            "novelty",
            "uncertainty",
            "mutation_requested",
        }
        if any(key not in allowed for key in arguments):
            raise ValueError("council arguments invalid")
        return build_profile_council(
            failure_class=str(arguments.get("failure_class", "")),
            novelty=float(arguments.get("novelty", 0.0)),
            uncertainty=float(arguments.get("uncertainty", 0.0)),
            mutation_requested=arguments.get("mutation_requested") is True,
        )
    if action == "homeostasis":
        allowed = {
            "project_root",
            "action",
            "uncertainty",
            "recurrence_count",
            "deterministic_verification_available",
            "local_verification_failed",
            "cost_pressure",
            "regression_risk",
        }
        if any(key not in allowed for key in arguments):
            raise ValueError("homeostasis arguments invalid")
        return build_homeostasis_decision(
            uncertainty=float(arguments.get("uncertainty", 0.0)),
            recurrence_count=int(arguments.get("recurrence_count", 0)),
            deterministic_verification_available=(
                arguments.get("deterministic_verification_available") is True
            ),
            local_verification_failed=arguments.get("local_verification_failed") is True,
            cost_pressure=float(arguments.get("cost_pressure", 0.0)),
            regression_risk=float(arguments.get("regression_risk", 0.0)),
        )
    raise ValueError("cognitive genome action invalid")


def _build_snapshot(
    arguments: dict[str, object],
    *,
    default_network: bool,
    default_include_research: bool,
) -> dict[str, object] | None:
    manual_facts = _boolean_facts(arguments.get("runtime_facts", {}))
    if manual_facts is None:
        return None
    project_root = arguments.get("project_root", ".")
    research_query = arguments.get("research_query", "HEX-CORTEX operational readiness")
    comfyui_endpoint = arguments.get("comfyui_endpoint", "http://127.0.0.1:8188")
    searxng_endpoint = arguments.get("searxng_endpoint", "http://127.0.0.1:8888/search")
    if not all(
        isinstance(value, str) and value.strip()
        for value in (project_root, research_query, comfyui_endpoint, searxng_endpoint)
    ):
        return None
    try:
        return build_operational_audit(
            Path(project_root),
            execute_network=arguments.get("network", default_network) is True,
            include_research=arguments.get("include_research", default_include_research) is True,
            research_query=research_query,
            comfyui_endpoint=comfyui_endpoint,
            searxng_endpoint=searxng_endpoint,
            runtime_fact_overrides=manual_facts,
        )
    except ValueError:
        return None


def _compact_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
    category_names = (
        "code_ready",
        "runtime_ready",
        "models_ready",
        "research_ready",
        "media_ready",
        "world_model_ready",
        "policy_v2_ready",
        "self_correction_ready",
        "remote_api_ready",
        "cognitive_genome_ready",
        "server_ready",
        "security_ready",
        "branch_ready",
        "operational_ready",
    )
    return {
        "audit_hash": snapshot.get("audit_hash"),
        "truth_source": snapshot.get("audit_type"),
        "readiness": {name: snapshot.get(name) is True for name in category_names},
        "category_blockers": snapshot.get("category_blockers", {}),
        "next_action": snapshot.get("next_action"),
        "network_call_performed": snapshot.get("network_call_performed") is True,
    }


def _validate_arguments(
    arguments: dict[str, object],
    *,
    allowed: set[str],
) -> dict[str, object] | None:
    if any(key not in allowed for key in arguments):
        return _blocked("operational_arguments_invalid")
    for key in ("network", "include_research"):
        if key in arguments and not isinstance(arguments[key], bool):
            return _blocked(f"{key}_must_be_boolean")
    return None


def _boolean_facts(value: object) -> dict[str, bool] | None:
    if not isinstance(value, dict):
        return None
    if not all(
        isinstance(key, str) and isinstance(item, bool)
        for key, item in value.items()
    ):
        return None
    return dict(value)


def _blocked(blocker: str) -> dict[str, object]:
    return {"status": "blocked", "blockers": [blocker]}


__all__ = [
    "build_cortex_rpc_tool_result",
    "call_cortex_operational_rpc_tool",
    "list_cortex_operational_rpc_tools",
]
