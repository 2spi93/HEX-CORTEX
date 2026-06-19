from __future__ import annotations

import re
from collections.abc import Callable

from hex_cortex.memory.cortex_gateway import CortexAdapter

HardwareHandler = Callable[[dict[str, object]], dict[str, object]]


def build_cortex_hardware_adapter(
    *,
    device_id: str,
    handler: HardwareHandler,
    lane: str = "tool",
) -> CortexAdapter:
    if not isinstance(device_id, str) or not re.fullmatch(
        r"[a-z0-9_-]+",
        device_id,
    ):
        raise ValueError("device_id must use lowercase safe characters")
    if lane not in {"tool", "visual", "voice"}:
        raise ValueError("hardware adapter lane is unsupported")
    if not callable(handler):
        raise ValueError("hardware handler must be callable")
    return CortexAdapter(
        name=f"hardware.{device_id}",
        lane=lane,
        handler=handler,
        description=f"Hardware adapter for {device_id}.",
        requires_operator=True,
        local_process_capable=True,
        auto_safe_capable=False,
    )
