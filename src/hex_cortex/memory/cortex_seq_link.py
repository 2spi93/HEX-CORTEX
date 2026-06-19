from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_seq import build_cortex_seq


def build_cortex_seq_link() -> dict[str, CortexUnit]:
    return {
        "seq.build": CortexUnit(
            name="seq.build",
            unit=build_cortex_seq,
            description="Build one chained temporal sequence record.",
            mutates_receipt=True,
            requires_operator=False,
        )
    }
