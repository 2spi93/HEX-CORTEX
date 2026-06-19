from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_outputs import list_cortex_outputs
from hex_cortex.memory.cortex_seen import build_cortex_seen
from hex_cortex.memory.cortex_state import build_cortex_state


def build_cortex_world_flow_registry() -> dict[str, CortexUnit]:
    return {
        "seen.build": CortexUnit(
            name="seen.build",
            unit=build_cortex_seen,
            description="Build a compact approved observation receipt.",
            mutates_receipt=True,
            requires_operator=True,
        ),
        "state.build": CortexUnit(
            name="state.build",
            unit=build_cortex_state,
            description="Build a compact world-state snapshot from approved receipts.",
            mutates_receipt=True,
            requires_operator=False,
        ),
        "outputs.list": CortexUnit(
            name="outputs.list",
            unit=list_cortex_outputs,
            description="List governed writing, coding, planning, voice, and visual outputs.",
            mutates_receipt=False,
            requires_operator=False,
        ),
    }
