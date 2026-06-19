from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit

_COMMON_EXECUTION_UNITS = {
    "action.propose",
    "action.pick",
    "action.route",
    "exec.catalog",
    "exec.call",
}

_SURFACES = [
    {
        "surface_id": "claude_code",
        "label": "Claude Code",
        "preferred_transport": "mcp_stdio",
        "fallback_transport": "python_module_cli",
        "required_units": sorted(_COMMON_EXECUTION_UNITS | {"tool.receipt"}),
        "minimum_runtime_facts": [
            "cli_entrypoint_available",
            "claude_project_configured",
        ],
        "native_runtime_facts": ["mcp_server_available"],
        "instruction_file": "CLAUDE.md",
    },
    {
        "surface_id": "codex_cli",
        "label": "Codex CLI",
        "preferred_transport": "mcp_stdio",
        "fallback_transport": "python_module_cli",
        "required_units": sorted(_COMMON_EXECUTION_UNITS | {"tool.receipt"}),
        "minimum_runtime_facts": [
            "cli_entrypoint_available",
            "codex_project_configured",
        ],
        "native_runtime_facts": ["mcp_server_available"],
        "instruction_file": "AGENTS.md",
    },
    {
        "surface_id": "ollama",
        "label": "Ollama local runtime",
        "preferred_transport": "ollama_http",
        "fallback_transport": "python_runner_injection",
        "required_units": [
            "lc.build",
            "a.build",
            "b.build",
            "c.build",
            "r.describe",
            "exec.call",
        ],
        "minimum_runtime_facts": [
            "local_model_runtime_available",
            "ollama_endpoint_configured",
        ],
        "native_runtime_facts": [],
        "instruction_file": None,
    },
    {
        "surface_id": "llama_cpp",
        "label": "llama.cpp server",
        "preferred_transport": "openai_compatible_http",
        "fallback_transport": "python_runner_injection",
        "required_units": [
            "lc.build",
            "a.build",
            "b.build",
            "c.build",
            "exec.call",
        ],
        "minimum_runtime_facts": [
            "local_model_runtime_available",
            "llama_cpp_adapter_available",
        ],
        "native_runtime_facts": [],
        "instruction_file": None,
    },
    {
        "surface_id": "hermes_agent",
        "label": "Hermes Agent",
        "preferred_transport": "tool_protocol_or_cli",
        "fallback_transport": "python_module_cli",
        "required_units": sorted(_COMMON_EXECUTION_UNITS | {"links.list"}),
        "minimum_runtime_facts": ["cli_entrypoint_available"],
        "native_runtime_facts": ["hermes_adapter_available"],
        "instruction_file": None,
    },
    {
        "surface_id": "kali_linux",
        "label": "Kali Linux",
        "preferred_transport": "python_module_cli",
        "fallback_transport": "local_service",
        "required_units": sorted(_COMMON_EXECUTION_UNITS | {"tool.receipt"}),
        "minimum_runtime_facts": ["cli_entrypoint_available"],
        "native_runtime_facts": ["kali_profile_configured"],
        "instruction_file": "AGENTS.md",
    },
    {
        "surface_id": "server",
        "label": "Server or container",
        "preferred_transport": "local_service",
        "fallback_transport": "python_module_cli",
        "required_units": sorted(_COMMON_EXECUTION_UNITS),
        "minimum_runtime_facts": ["cli_entrypoint_available"],
        "native_runtime_facts": ["service_packaging_available"],
        "instruction_file": None,
    },
    {
        "surface_id": "hardware_edge",
        "label": "Edge hardware",
        "preferred_transport": "device_adapter",
        "fallback_transport": "python_module_cli",
        "required_units": sorted(
            _COMMON_EXECUTION_UNITS | {"sensor.receipt", "providers.select"}
        ),
        "minimum_runtime_facts": ["cli_entrypoint_available"],
        "native_runtime_facts": ["hardware_adapter_available"],
        "instruction_file": None,
    },
    {
        "surface_id": "gtixt",
        "label": "GTIXT project",
        "preferred_transport": "project_adapter",
        "fallback_transport": "python_module_cli",
        "required_units": sorted(
            _COMMON_EXECUTION_UNITS
            | {"web.describe", "stability.compute", "preferences.profile"}
        ),
        "minimum_runtime_facts": ["cli_entrypoint_available"],
        "native_runtime_facts": ["project_adapter_available"],
        "instruction_file": "AGENTS.md",
    },
    {
        "surface_id": "generic_project",
        "label": "Generic project",
        "preferred_transport": "project_adapter",
        "fallback_transport": "python_module_cli",
        "required_units": sorted(_COMMON_EXECUTION_UNITS),
        "minimum_runtime_facts": ["cli_entrypoint_available"],
        "native_runtime_facts": ["project_adapter_available"],
        "instruction_file": "AGENTS.md",
    },
]


def list_cortex_surfaces() -> list[dict[str, object]]:
    return [dict(item) for item in _SURFACES]


def get_cortex_surface(surface_id: str) -> dict[str, object]:
    for item in _SURFACES:
        if item["surface_id"] == surface_id:
            return dict(item)
    return {
        "surface_id": surface_id,
        "state": "blocked",
        "blocker": "unknown_surface",
    }


def audit_cortex_surface(
    *,
    surface_id: str,
    registry: dict[str, CortexUnit],
    runtime_facts: dict[str, bool] | None = None,
) -> dict[str, object]:
    surface = get_cortex_surface(surface_id)
    if surface.get("state") == "blocked":
        return {
            "surface_audit_type": "cortex_surface_audit",
            "surface_id": surface_id,
            "contract_ready": False,
            "usable_ready": False,
            "native_ready": False,
            "blockers": ["unknown_surface"],
        }
    required_units = set(surface.get("required_units", []))
    missing_units = sorted(required_units.difference(registry))
    facts = dict(runtime_facts or {})
    minimum_facts = list(surface.get("minimum_runtime_facts", []))
    native_facts = list(surface.get("native_runtime_facts", []))
    missing_minimum = sorted(
        fact for fact in minimum_facts if facts.get(fact) is not True
    )
    missing_native = sorted(
        fact for fact in native_facts if facts.get(fact) is not True
    )
    contract_ready = not missing_units
    usable_ready = contract_ready and not missing_minimum
    native_ready = usable_ready and not missing_native
    blockers = [f"missing_unit:{name}" for name in missing_units]
    blockers.extend(f"missing_runtime_fact:{name}" for name in missing_minimum)
    blockers.extend(f"missing_native_fact:{name}" for name in missing_native)
    return {
        "surface_audit_type": "cortex_surface_audit",
        "surface_id": surface_id,
        "label": surface.get("label"),
        "preferred_transport": surface.get("preferred_transport"),
        "fallback_transport": surface.get("fallback_transport"),
        "instruction_file": surface.get("instruction_file"),
        "contract_ready": contract_ready,
        "usable_ready": usable_ready,
        "native_ready": native_ready,
        "missing_units": missing_units,
        "missing_minimum_facts": missing_minimum,
        "missing_native_facts": missing_native,
        "blockers": blockers,
        "next_action": _next_action(
            contract_ready=contract_ready,
            usable_ready=usable_ready,
            native_ready=native_ready,
        ),
    }


def build_cortex_surface_manifest(surface_id: str) -> dict[str, object]:
    surface = get_cortex_surface(surface_id)
    if surface.get("state") == "blocked":
        return surface
    return {
        "manifest_type": "cortex_surface_manifest",
        "surface_id": surface_id,
        "preferred_transport": surface.get("preferred_transport"),
        "fallback_transport": surface.get("fallback_transport"),
        "instruction_file": surface.get("instruction_file"),
        "required_units": surface.get("required_units"),
        "minimum_runtime_facts": surface.get("minimum_runtime_facts"),
        "native_runtime_facts": surface.get("native_runtime_facts"),
        "secrets_must_use_environment_or_secret_store": True,
        "raw_secrets_in_manifest": False,
        "next_action": "configure_surface_runtime",
    }


def _next_action(
    *,
    contract_ready: bool,
    usable_ready: bool,
    native_ready: bool,
) -> str:
    if not contract_ready:
        return "repair_surface_contract"
    if not usable_ready:
        return "configure_surface_fallback"
    if not native_ready:
        return "configure_surface_native_transport"
    return "use_surface"
