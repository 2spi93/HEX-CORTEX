from __future__ import annotations

from pathlib import Path

from hex_cortex.memory.cortex_cognitive_loop_plan import build_cognitive_loop_plan
from hex_cortex.memory.cortex_repo_graph import build_repo_graph
from hex_cortex.memory.cortex_repo_graph import find_callers
from hex_cortex.memory.cortex_repo_graph import find_symbol
from hex_cortex.memory.cortex_repo_graph import find_tests_for_symbol
from hex_cortex.memory.cortex_repo_graph import summarize_module_contract

_TOOL_NAMES = {"hex_cortex_cognitive_loop", "hex_cortex_repo_intelligence"}
_LEVELS = {"low", "medium", "high", "critical"}
_SENSITIVITY = {"public", "private", "secret"}
_REPO_ACTIONS = {"summary", "find_symbol", "find_callers", "find_tests", "module_contract"}


def list_operational_intelligence_tools() -> list[dict[str, object]]:
    """Read-only MCP descriptors for planning and repository intelligence."""
    readonly = {"readOnlyHint": True, "destructiveHint": False}
    return [
        {
            "name": "hex_cortex_cognitive_loop",
            "title": "HEX-CORTEX Cognitive Loop Plan",
            "description": (
                "Build a cold, read-only execution plan across adaptive compute, GPU admission, "
                "brain routing, self-consistency, and escalation. Performs no model call."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_root": {"type": "string"},
                    "ledger_path": {"type": "string"},
                    "gpu_snapshot": {
                        "type": "object",
                        "properties": {
                            "vram_total_mb": {"type": "number"},
                            "vram_used_mb": {"type": "number"},
                            "temperature_c": {"type": "number"},
                            "gpu_utilization_pct": {"type": "number"},
                            "loaded_model_count": {"type": "integer"},
                            "big_model_loaded": {"type": "boolean"},
                            "queue_depth": {"type": "integer"},
                            "recent_latency_ms": {"type": "number"},
                            "recent_oom_count": {"type": "integer"},
                            "in_cooldown": {"type": "boolean"},
                            "interactive_task_active": {"type": "boolean"},
                        },
                        "required": ["vram_total_mb", "vram_used_mb"],
                        "additionalProperties": False,
                    },
                    "task_domain": {"type": "string"},
                    "context_sensitivity": {
                        "type": "string",
                        "enum": ["public", "private", "secret"],
                    },
                    "difficulty": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                    "risk": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                    "prior_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "maximum_latency_ms": {"type": "number", "exclusiveMinimum": 0},
                    "cost_pressure": {"type": "number", "minimum": 0, "maximum": 1},
                    "remote_allowed": {"type": "boolean"},
                    "target_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "is_benchmark": {"type": "boolean"},
                },
                "required": ["gpu_snapshot", "task_domain", "context_sensitivity"],
                "additionalProperties": False,
            },
            "annotations": readonly,
        },
        {
            "name": "hex_cortex_repo_intelligence",
            "title": "HEX-CORTEX Repository Intelligence",
            "description": (
                "Query a bounded read-only Python AST graph for repository summary, symbols, "
                "callers, tests, or a module public contract. Never returns source bodies."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_root": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": [
                            "summary",
                            "find_symbol",
                            "find_callers",
                            "find_tests",
                            "module_contract",
                        ],
                    },
                    "symbol": {"type": "string"},
                    "module": {"type": "string"},
                },
                "required": ["action"],
                "additionalProperties": False,
            },
            "annotations": readonly,
        },
    ]


def call_operational_intelligence_tool(
    name: str,
    arguments: dict[str, object],
) -> tuple[dict[str, object], bool] | None:
    """Dispatch one extension tool, or return None when the name is not ours."""
    if name not in _TOOL_NAMES:
        return None
    try:
        if name == "hex_cortex_cognitive_loop":
            payload = _call_cognitive_loop(arguments)
        else:
            payload = _call_repo_intelligence(arguments)
    except (OSError, TypeError, ValueError):
        blocker = (
            "cognitive_loop_arguments_invalid"
            if name == "hex_cortex_cognitive_loop"
            else "repo_intelligence_arguments_invalid"
        )
        return {"status": "blocked", "blockers": [blocker]}, True
    return payload, payload.get("status") == "blocked"


def _call_cognitive_loop(arguments: dict[str, object]) -> dict[str, object]:
    allowed = {
        "project_root",
        "ledger_path",
        "gpu_snapshot",
        "task_domain",
        "context_sensitivity",
        "difficulty",
        "risk",
        "prior_confidence",
        "maximum_latency_ms",
        "cost_pressure",
        "remote_allowed",
        "target_confidence",
        "is_benchmark",
    }
    _reject_extra(arguments, allowed)
    root = _safe_project_root(arguments.get("project_root", "."))
    ledger = _safe_child(root, arguments.get("ledger_path", ".hex-cortex/cognitive/brain-registry.jsonl"))
    snapshot = arguments.get("gpu_snapshot")
    task_domain = arguments.get("task_domain")
    sensitivity = arguments.get("context_sensitivity")
    difficulty = arguments.get("difficulty", "medium")
    risk = arguments.get("risk", "low")
    if not isinstance(snapshot, dict):
        raise ValueError("gpu_snapshot invalid")
    if not isinstance(task_domain, str) or not task_domain.strip():
        raise ValueError("task_domain invalid")
    if sensitivity not in _SENSITIVITY:
        raise ValueError("context_sensitivity invalid")
    if difficulty not in _LEVELS or risk not in _LEVELS:
        raise ValueError("difficulty or risk invalid")
    prior = arguments.get("prior_confidence")
    if prior is not None and not _unit_interval(prior):
        raise ValueError("prior_confidence invalid")
    latency = _positive_number(arguments.get("maximum_latency_ms", 5000.0))
    cost = _unit_number(arguments.get("cost_pressure", 0.5))
    target = _unit_number(arguments.get("target_confidence", 0.7))
    for key in ("remote_allowed", "is_benchmark"):
        if key in arguments and not isinstance(arguments[key], bool):
            raise ValueError(f"{key} invalid")
    return build_cognitive_loop_plan(
        ledger,
        dict(snapshot),
        task_domain=task_domain,
        context_sensitivity=str(sensitivity),
        difficulty=str(difficulty),
        risk=str(risk),
        prior_confidence=float(prior) if prior is not None else None,
        maximum_latency_ms=latency,
        cost_pressure=cost,
        remote_allowed=arguments.get("remote_allowed") is True,
        target_confidence=target,
        is_benchmark=arguments.get("is_benchmark") is True,
    )


def _call_repo_intelligence(arguments: dict[str, object]) -> dict[str, object]:
    _reject_extra(arguments, {"project_root", "action", "symbol", "module"})
    root = _safe_project_root(arguments.get("project_root", "."))
    action = arguments.get("action")
    if action not in _REPO_ACTIONS:
        raise ValueError("action invalid")
    if action == "module_contract":
        module = arguments.get("module")
        if not isinstance(module, str) or not module.strip():
            raise ValueError("module invalid")
        return summarize_module_contract(root, module)
    symbol = arguments.get("symbol")
    if action != "summary" and (not isinstance(symbol, str) or not symbol.strip()):
        raise ValueError("symbol invalid")
    graph = build_repo_graph(root)
    if action == "summary":
        return {
            "result_type": "cortex_repo_summary_v1",
            "module_count": graph["module_count"],
            "symbol_count": graph["symbol_count"],
            "unparsed_count": graph["unparsed_count"],
            "unparsed": graph["unparsed"],
            "source_bodies_returned": False,
        }
    if action == "find_symbol":
        result = find_symbol(graph, str(symbol))
    elif action == "find_callers":
        result = find_callers(graph, str(symbol))
    else:
        result = find_tests_for_symbol(graph, str(symbol))
    return {
        "result_type": f"cortex_repo_{action}_v1",
        "symbol": symbol,
        "result_count": len(result),
        "results": result,
        "source_bodies_returned": False,
    }


def _safe_project_root(value: object) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("project_root invalid")
    cwd = Path.cwd().resolve()
    root = (cwd / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        root.relative_to(cwd)
    except ValueError as exc:
        raise ValueError("project_root escapes MCP working directory") from exc
    if not root.is_dir():
        raise ValueError("project_root missing")
    return root


def _safe_child(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("relative path invalid")
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("relative path escapes project root") from exc
    return path


def _reject_extra(arguments: dict[str, object], allowed: set[str]) -> None:
    if any(key not in allowed for key in arguments):
        raise ValueError("unexpected argument")


def _unit_interval(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and 0.0 <= float(value) <= 1.0


def _unit_number(value: object) -> float:
    if not _unit_interval(value):
        raise ValueError("number outside unit interval")
    return float(value)


def _positive_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or float(value) <= 0.0:
        raise ValueError("positive number required")
    return float(value)
