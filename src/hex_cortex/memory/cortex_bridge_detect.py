from __future__ import annotations

_TRANSPORT_ORDER = [
    "mcp",
    "openai_compatible",
    "declared_api",
    "cli_stdio",
]


def list_cortex_bridge_transports() -> list[dict[str, object]]:
    return [
        {
            "transport": transport,
            "priority": index + 1,
            "shared_memory": False,
        }
        for index, transport in enumerate(_TRANSPORT_ORDER)
    ]


def detect_cortex_bridge_transport(
    observations: dict[str, object],
) -> dict[str, object]:
    availability = {
        "mcp": observations.get("mcp_available") is True,
        "openai_compatible": observations.get("openai_models_available") is True,
        "declared_api": observations.get("declared_api_available") is True,
        "cli_stdio": observations.get("cli_stdio_available") is True,
    }
    selected = next(
        (
            transport
            for transport in _TRANSPORT_ORDER
            if availability[transport]
        ),
        None,
    )
    return {
        "detection_type": "cortex_bridge_transport",
        "transport_order": list(_TRANSPORT_ORDER),
        "availability": availability,
        "selected_transport": selected,
        "detection_allowed": selected is not None,
        "shared_memory": False,
        "next_action": (
            "build_bridge_exchange_plan"
            if selected is not None
            else "configure_bridge_transport"
        ),
        "blockers": [] if selected is not None else ["no_bridge_transport_available"],
    }
