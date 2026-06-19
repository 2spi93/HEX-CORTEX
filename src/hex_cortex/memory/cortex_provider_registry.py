from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_sensor_providers import list_cortex_sensor_providers


def build_cortex_provider_registry() -> dict[str, CortexUnit]:
    return {
        "providers.list": CortexUnit(
            name="providers.list",
            unit=list_cortex_sensor_providers,
            description="List candidate screen, camera, and voice providers.",
            mutates_receipt=False,
            requires_operator=False,
        )
    }
