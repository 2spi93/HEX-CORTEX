from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_gateway import list_cortex_adapters
from hex_cortex.memory.cortex_gateway import run_cortex_adapter_gateway


def _catalog(**kwargs):
    return list_cortex_adapters(**kwargs)


def _call(**kwargs):
    return run_cortex_adapter_gateway(**kwargs)


def build_cortex_xlink() -> dict[str, CortexUnit]:
    return {
        "exec.catalog": CortexUnit(
            name="exec.catalog",
            unit=_catalog,
            description="List execution bindings.",
        ),
        "exec.call": CortexUnit(
            name="exec.call",
            unit=_call,
            description="Invoke one execution binding.",
            mutates_receipt=True,
        ),
    }
