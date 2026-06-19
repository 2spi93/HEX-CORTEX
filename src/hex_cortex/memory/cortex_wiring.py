from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_route import list_cortex_routes

_STAGE_UNITS = {
    "local_model": {
        "lc.build",
        "a.build",
        "b.build",
        "c.build",
        "r.describe",
    },
    "perception_and_state": {
        "modal.list",
        "sensor.receipt",
        "providers.list",
        "providers.score",
        "providers.select",
        "seen.build",
        "state.build",
    },
    "world_model_loop": {
        "transition.build",
        "surprise.build",
        "seq.build",
        "goal.build",
        "cost.evaluate",
        "action.propose",
        "action.pick",
        "action.route",
    },
    "effect_receipts": {
        "asset.receipt",
        "account.receipt",
        "output.receipt",
        "tool.receipt",
        "voice.receipt",
        "visual.receipt",
        "encode.receipt",
    },
    "execution_gateway": {
        "exec.catalog",
        "exec.call",
    },
    "knowledge_and_integrations": {
        "domains.list",
        "outputs.list",
        "channels.list",
        "channels.evaluate",
        "asset.list",
        "encode.list",
        "links.list",
        "preferences.profile",
        "web.describe",
        "stability.compute",
    },
}

_RUNTIME_FACTS = {
    "runtime_orchestration_available": "runtime_model_orchestration_not_available",
    "research_social_credentials_available": "research_social_credentials_not_available",
    "server_federation_audit_available": "server_federation_audit_not_available",
    "media_runtime_contract_available": "media_runtime_contract_not_available",
    "latent_world_model_lab_available": "latent_world_model_lab_not_available",
    "world_model_training_evaluation_available": "world_model_training_evaluation_not_available",
    "web_search_adapter_configured": "real_web_search_not_configured",
    "mcp_server_available": "native_mcp_server_not_available",
    "local_model_runtime_available": "local_model_runtime_not_available",
    "media_runtime_available": "media_runtime_not_available",
    "service_packaging_available": "service_packaging_not_available",
    "hardware_adapter_available": "hardware_adapter_not_available",
    "project_adapter_available": "project_adapter_not_available",
    "learned_world_model_available": "learned_world_model_not_available",
}


def audit_cortex_wiring(
    registry: dict[str, CortexUnit],
    *,
    runtime_facts: dict[str, bool] | None = None,
) -> dict[str, object]:
    rows = []
    missing_all = []
    present_count = 0
    required_count = 0
    for stage, required in _STAGE_UNITS.items():
        present = sorted(required.intersection(registry))
        missing = sorted(required.difference(registry))
        present_count += len(present)
        required_count += len(required)
        missing_all.extend(missing)
        rows.append(
            {
                "stage": stage,
                "required_count": len(required),
                "present_count": len(present),
                "missing_count": len(missing),
                "present_units": present,
                "missing_units": missing,
                "stage_ready": not missing,
            }
        )
    route_rows = list_cortex_routes()
    missing_route_units = sorted(
        {
            row["next_unit"]
            for row in route_rows
            if row["next_unit"] not in registry
        }
    )
    facts = dict(runtime_facts or {})
    runtime_blockers = [
        blocker
        for fact, blocker in _RUNTIME_FACTS.items()
        if facts.get(fact) is not True
    ]
    architecture_ready = not missing_all and not missing_route_units
    operational_ready = architecture_ready and not runtime_blockers
    coverage = round(present_count / required_count, 4) if required_count else 0.0
    return {
        "audit_type": "cortex_wiring_audit",
        "registry_unit_count": len(registry),
        "required_unit_count": required_count,
        "present_unit_count": present_count,
        "coverage": coverage,
        "architecture_ready": architecture_ready,
        "operational_ready": operational_ready,
        "stage_rows": rows,
        "missing_units": sorted(set(missing_all)),
        "route_count": len(route_rows),
        "missing_route_units": missing_route_units,
        "runtime_facts": facts,
        "runtime_blockers": runtime_blockers,
        "next_action": "operate_cortex" if operational_ready else "configure_remaining_runtime_adapters",
    }


def list_cortex_wiring_stages() -> list[dict[str, object]]:
    return [
        {
            "stage": stage,
            "required_units": sorted(units),
        }
        for stage, units in _STAGE_UNITS.items()
    ]


def list_cortex_runtime_facts() -> list[dict[str, str]]:
    return [
        {"fact": fact, "blocker_when_false": blocker}
        for fact, blocker in _RUNTIME_FACTS.items()
    ]
