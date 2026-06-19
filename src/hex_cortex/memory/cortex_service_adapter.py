from __future__ import annotations

import re
from collections.abc import Callable

from hex_cortex.memory.cortex_gateway import CortexAdapter

ServiceHandler = Callable[[dict[str, object]], dict[str, object]]


def build_cortex_service_adapter(
    *,
    service_id: str,
    handler: ServiceHandler,
    lane: str = "tool",
    requires_operator: bool = True,
    auto_safe_capable: bool = False,
) -> CortexAdapter:
    if not isinstance(service_id, str) or not re.fullmatch(
        r"[a-z0-9_-]+",
        service_id,
    ):
        raise ValueError("service_id must use lowercase safe characters")
    if lane not in {"asset", "account", "tool", "voice", "visual"}:
        raise ValueError("service adapter lane is unsupported")
    if not callable(handler):
        raise ValueError("service handler must be callable")
    return CortexAdapter(
        name=f"service.{service_id}",
        lane=lane,
        handler=handler,
        description=f"Service adapter for {service_id}.",
        requires_operator=requires_operator,
        network_capable=True,
        auto_safe_capable=auto_safe_capable,
    )
