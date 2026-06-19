from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_surprise import build_cortex_surprise


def build_cortex_surprise_registry() -> dict[str, CortexUnit]:
    return {
        "surprise.build": CortexUnit(
            name="surprise.build",
            unit=build_cortex_surprise,
            description=(
                "Compare predicted and observed state features and build "
                "a prediction-error receipt."
            ),
            mutates_receipt=True,
            requires_operator=False,
        )
    }
