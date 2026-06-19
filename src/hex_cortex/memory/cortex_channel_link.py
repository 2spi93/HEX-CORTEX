from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_channels import evaluate_cortex_channel_candidate
from hex_cortex.memory.cortex_channels import list_cortex_channels


def build_cortex_channel_link() -> dict[str, CortexUnit]:
    return {
        "channels.list": CortexUnit(
            name="channels.list",
            unit=list_cortex_channels,
            description="List cold external channel candidates.",
            mutates_receipt=False,
            requires_operator=False,
        ),
        "channels.evaluate": CortexUnit(
            name="channels.evaluate",
            unit=evaluate_cortex_channel_candidate,
            description="Evaluate a cold channel candidate without network access.",
            mutates_receipt=False,
            requires_operator=False,
        ),
    }
