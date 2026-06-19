from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_transition import build_cortex_transition


def build_cortex_transition_registry() -> dict[str, CortexUnit]:
    return {
        "transition.build": CortexUnit(
            name="transition.build",
            unit=build_cortex_transition,
            description="Predict a deterministic next state from state and action context.",
            mutates_receipt=True,
            requires_operator=False,
        )
    }
