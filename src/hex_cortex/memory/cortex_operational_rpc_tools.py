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
from hex_cortex.memory.cortex_model_armor import build_model_armor_plan
from hex_cortex.memory.cortex_model_armor import list_coding_protocols
from hex_cortex.memory.cortex_model_armor import propose_protocol_skill_candidates
from hex_cortex.memory.cortex_bandit_router import empty_routing_stats
from hex_cortex.memory.cortex_benchmark_runtime import load_routing_priors
from hex_cortex.memory.cortex_bandit_router import rank_models
from hex_cortex.memory.cortex_bandit_router import update_routing_outcome
from hex_cortex.memory.cortex_confidence_calibration import build_calibration_map
from hex_cortex.memory.cortex_confidence_calibration import calibrate_confidence
from hex_cortex.memory.cortex_model_benchmark import build_benchmark_suite
from hex_cortex.memory.cortex_model_benchmark import score_benchmark_responses
from hex_cortex.memory.cortex_operator_guide import build_operator_guide
from hex_cortex.memory.cortex_operator_guide import build_troubleshooting_guide
from hex_cortex.memory.cortex_operator_guide import list_guide_topics
from hex_cortex.memory.cortex_reflex_brain import classify_task
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
    rows.append(
        {
            "name": "hex_cortex_model_armor",
            "title": "HEX-CORTEX Model Armor",
            "description": (
                "Build the cognitive armor plan for any base model profile: prompt scaffold, "
                "step budgets, mandatory coding protocols, verification, reflection and "
                "escalation contracts, scaled inversely to model capability. Read-only plan; "
                "runs nothing and never weakens base-model guardrails."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["plan", "protocols", "skill_candidates"],
                    },
                    "parameter_scale": {
                        "type": "string",
                        "enum": ["tiny", "small", "medium", "large"],
                    },
                    "context_window_tokens": {"type": "integer"},
                    "supports_tool_calls": {"type": "boolean"},
                    "supports_json_schema": {"type": "boolean"},
                    "task_risk": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                    "python_available": {"type": "boolean"},
                    "large_model_available": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True, "destructiveHint": False},
        }
    )
    rows.append(
        {
            "name": "hex_cortex_operator_guide",
            "title": "HEX-CORTEX Operator Guide",
            "description": (
                "Step-by-step configuration guidance for the operator: local model setup, "
                "fine-tuning, MCP connection, inference server, voice, vision, video "
                "world-model training, GPU admission. Detail scales to experience level; "
                "a troubleshooting action maps symptoms to causes and fixes. Advisory only: "
                "runs nothing, mutates nothing."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["topics", "guide", "troubleshoot"],
                    },
                    "topic": {"type": "string"},
                    "experience_level": {
                        "type": "string",
                        "enum": ["beginner", "intermediate", "expert"],
                    },
                    "symptom": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True, "destructiveHint": False},
        }
    )
    rows.append(
        {
            "name": "hex_cortex_measured_intelligence",
            "title": "HEX-CORTEX Measured Intelligence",
            "description": (
                "Measured-intelligence kit: deterministic model benchmark suite and scoring, "
                "bandit routing that learns from outcome receipts, confidence calibration that "
                "detects bluffing models, and the reflex-brain dry-run classification plan. "
                "Stateless and read-only: callers supply stats/observations; nothing executes."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "benchmark_suite",
                            "benchmark_score",
                            "route",
                            "routing_update",
                            "calibration_map",
                            "calibrate",
                            "reflex_plan",
                        ],
                    },
                    "model_id": {"type": "string"},
                    "responses": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                    "stats": {"type": "object"},
                    "domain": {"type": "string"},
                    "project_root": {"type": "string"},
                    "candidates": {"type": "array", "items": {"type": "string"}},
                    "benchmark_priors": {
                        "type": "object",
                        "additionalProperties": {"type": "number"},
                    },
                    "exploration_weight": {"type": "number"},
                    "success": {"type": "boolean"},
                    "observations": {"type": "array", "items": {"type": "object"}},
                    "bucket_count": {"type": "integer"},
                    "claimed_confidence": {"type": "number"},
                    "calibration_map": {"type": "object"},
                    "task_text": {"type": "string"},
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

    if name == "hex_cortex_model_armor":
        try:
            payload = _call_model_armor(arguments)
        except (TypeError, ValueError):
            return _blocked("model_armor_arguments_invalid"), True
        return payload, False

    if name == "hex_cortex_operator_guide":
        try:
            payload = _call_operator_guide(arguments)
        except (TypeError, ValueError):
            return _blocked("operator_guide_arguments_invalid"), True
        return payload, False

    if name == "hex_cortex_measured_intelligence":
        try:
            payload = _call_measured_intelligence(arguments)
        except (TypeError, ValueError, KeyError):
            return _blocked("measured_intelligence_arguments_invalid"), True
        return payload, False

    return call_legacy_tool(name, arguments)


def _call_measured_intelligence(arguments: dict[str, object]) -> dict[str, object]:
    action = arguments.get("action")
    if action == "benchmark_suite":
        if any(key != "action" for key in arguments):
            raise ValueError("benchmark_suite arguments invalid")
        return build_benchmark_suite()
    if action == "benchmark_score":
        if any(key not in {"action", "model_id", "responses"} for key in arguments):
            raise ValueError("benchmark_score arguments invalid")
        responses = arguments.get("responses")
        if not isinstance(responses, dict):
            raise ValueError("responses must be an object")
        return score_benchmark_responses(
            model_id=str(arguments.get("model_id", "")),
            responses={str(key): str(value) for key, value in responses.items()},
        )
    if action == "route":
        allowed = {
            "action",
            "stats",
            "domain",
            "candidates",
            "benchmark_priors",
            "exploration_weight",
            "project_root",
        }
        if any(key not in allowed for key in arguments):
            raise ValueError("route arguments invalid")
        stats = arguments.get("stats") or empty_routing_stats()
        if not isinstance(stats, dict):
            raise ValueError("route arguments invalid")
        domain = str(arguments.get("domain", ""))
        priors = arguments.get("benchmark_priors")
        if priors is not None and not isinstance(priors, dict):
            raise ValueError("benchmark_priors must be an object")
        prior_map = (
            {str(key): float(value) for key, value in priors.items()} if priors else None
        )
        if prior_map is None and "project_root" in arguments:
            # Measured fingerprints become routing priors without the caller
            # having to copy them by hand.
            project_root = arguments.get("project_root")
            if not isinstance(project_root, str) or not project_root.strip():
                raise ValueError("project_root invalid")
            registry = (Path(project_root) / "receipts" / "model_fingerprints.jsonl").resolve()
            if not registry.is_relative_to(Path(project_root).resolve()):
                raise ValueError("registry escapes project root")
            prior_map = load_routing_priors(registry, domain=domain) or None
        candidates = arguments.get("candidates")
        if candidates is None and prior_map:
            candidates = sorted(prior_map)
        if not isinstance(candidates, list):
            raise ValueError("route arguments invalid")
        return rank_models(
            stats,
            domain=domain,
            candidates=[str(candidate) for candidate in candidates],
            benchmark_priors=prior_map,
            exploration_weight=float(arguments.get("exploration_weight", 1.0)),
        )
    if action == "routing_update":
        allowed = {"action", "stats", "model_id", "domain", "success"}
        if any(key not in allowed for key in arguments):
            raise ValueError("routing_update arguments invalid")
        stats = arguments.get("stats") or empty_routing_stats()
        if not isinstance(stats, dict) or not isinstance(arguments.get("success"), bool):
            raise ValueError("routing_update arguments invalid")
        return update_routing_outcome(
            stats,
            model_id=str(arguments.get("model_id", "")),
            domain=str(arguments.get("domain", "")),
            success=arguments["success"] is True,
        )
    if action == "calibration_map":
        if any(key not in {"action", "observations", "bucket_count"} for key in arguments):
            raise ValueError("calibration_map arguments invalid")
        observations = arguments.get("observations", [])
        if not isinstance(observations, list):
            raise ValueError("observations must be an array")
        return build_calibration_map(
            [dict(row) for row in observations],
            bucket_count=int(arguments.get("bucket_count", 5)),
        )
    if action == "calibrate":
        if any(key not in {"action", "claimed_confidence", "calibration_map"} for key in arguments):
            raise ValueError("calibrate arguments invalid")
        calibration_map = arguments.get("calibration_map")
        if not isinstance(calibration_map, dict):
            raise ValueError("calibration_map must be an object")
        return calibrate_confidence(float(arguments.get("claimed_confidence", -1.0)), calibration_map)
    if action == "reflex_plan":
        if any(key not in {"action", "task_text", "model_id"} for key in arguments):
            raise ValueError("reflex_plan arguments invalid")
        return classify_task(
            str(arguments.get("task_text", "")),
            model=str(arguments.get("model_id", "qwen2.5:1.5b")),
        )
    raise ValueError("measured intelligence action invalid")


def _call_operator_guide(arguments: dict[str, object]) -> dict[str, object]:
    action = arguments.get("action", "topics")
    if action == "topics":
        if any(key != "action" for key in arguments):
            raise ValueError("topics arguments invalid")
        return {"topics": list_guide_topics()}
    topic = arguments.get("topic")
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("topic required")
    if action == "guide":
        allowed = {"action", "topic", "experience_level"}
        if any(key not in allowed for key in arguments):
            raise ValueError("guide arguments invalid")
        return build_operator_guide(
            topic=topic,
            experience_level=str(arguments.get("experience_level", "beginner")),
        )
    if action == "troubleshoot":
        allowed = {"action", "topic", "symptom"}
        if any(key not in allowed for key in arguments):
            raise ValueError("troubleshoot arguments invalid")
        symptom = arguments.get("symptom")
        if symptom is not None and not isinstance(symptom, str):
            raise ValueError("symptom must be a string")
        return build_troubleshooting_guide(topic=topic, symptom=symptom)
    raise ValueError("operator guide action invalid")


def _call_model_armor(arguments: dict[str, object]) -> dict[str, object]:
    action = arguments.get("action", "plan")
    if action == "protocols":
        if any(key != "action" for key in arguments):
            raise ValueError("protocols arguments invalid")
        return {"protocols": list_coding_protocols()}
    if action == "skill_candidates":
        if any(key != "action" for key in arguments):
            raise ValueError("skill_candidates arguments invalid")
        return {"skill_candidates": propose_protocol_skill_candidates()}
    if action != "plan":
        raise ValueError("model armor action invalid")
    allowed = {
        "action",
        "parameter_scale",
        "context_window_tokens",
        "supports_tool_calls",
        "supports_json_schema",
        "task_risk",
        "python_available",
        "large_model_available",
    }
    if any(key not in allowed for key in arguments):
        raise ValueError("plan arguments invalid")
    return build_model_armor_plan(
        parameter_scale=str(arguments.get("parameter_scale", "small")),
        context_window_tokens=int(arguments.get("context_window_tokens", 8_000)),
        supports_tool_calls=arguments.get("supports_tool_calls") is True,
        supports_json_schema=arguments.get("supports_json_schema") is True,
        task_risk=str(arguments.get("task_risk", "medium")),
        python_available=arguments.get("python_available", True) is True,
        large_model_available=arguments.get("large_model_available") is True,
    )


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
