from __future__ import annotations

from hex_cortex.memory.cortex_action import build_cortex_action_proposals
from hex_cortex.memory.cortex_bus import CortexUnit


def build_cortex_action_link() -> dict[str, CortexUnit]:
    return {
        "action.propose": CortexUnit(
            name="action.propose",
            unit=build_cortex_action_proposals,
            description="Rank candidate actions without executing them.",
            mutates_receipt=True,
            requires_operator=False,
        )
    }
