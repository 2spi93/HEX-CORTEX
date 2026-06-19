from __future__ import annotations

from hex_cortex.memory.cortex_sensor_providers import list_cortex_sensor_providers


def select_cortex_provider(
    *,
    capability_id: str,
    prefer_local: bool = True,
) -> dict[str, object]:
    candidates = [
        item
        for item in list_cortex_sensor_providers()
        if item.get("capability_id") == capability_id
    ]
    if not candidates:
        return {
            "selection_type": "cortex_provider_selection",
            "selected": False,
            "capability_id": capability_id,
            "blockers": ["no_provider_for_capability"],
        }
    ranked = sorted(
        candidates,
        key=lambda item: (
            0
            if prefer_local
            and str(item.get("provider_id", "")).startswith("local_")
            else 1,
            str(item.get("provider_id", "")),
        ),
    )
    selected = ranked[0]
    return {
        "selection_type": "cortex_provider_selection",
        "selected": True,
        "capability_id": capability_id,
        "provider_id": selected.get("provider_id"),
        "permission_mode": selected.get("permission_mode"),
        "secure_context_required": selected.get("secure_context_required"),
        "raw_input_persistence_allowed": selected.get(
            "raw_input_persistence_allowed"
        ),
        "candidate_count": len(candidates),
    }
