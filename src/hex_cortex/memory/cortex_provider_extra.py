from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_provider_select import select_cortex_provider
from hex_cortex.memory.cortex_sensor_providers import score_cortex_sensor_provider


def build_cortex_provider_extra_registry() -> dict[str, CortexUnit]:
    return {
        "providers.score": CortexUnit(
            name="providers.score",
            unit=score_cortex_sensor_provider,
            description="Score a provider candidate from static metadata.",
        ),
        "providers.select": CortexUnit(
            name="providers.select",
            unit=select_cortex_provider,
            description="Select a provider candidate for a capability.",
        ),
    }
