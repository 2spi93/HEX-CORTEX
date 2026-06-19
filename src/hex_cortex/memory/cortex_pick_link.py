from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_pick import build_cortex_pick


def build_cortex_pick_link() -> dict[str, CortexUnit]:
    return {
        "action.pick": CortexUnit(
            name="action.pick",
            unit=build_cortex_pick,
            description="Select one ranked action without executing it.",
            mutates_receipt=True,
            requires_operator=False,
        )
    }
