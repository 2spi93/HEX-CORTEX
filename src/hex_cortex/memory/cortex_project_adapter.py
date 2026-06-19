from __future__ import annotations

import re
from collections.abc import Callable

from hex_cortex.memory.cortex_gateway import CortexAdapter

ProjectHandler = Callable[[dict[str, object]], dict[str, object]]
_ALLOWED_LANES = {
    "asset",
    "account",
    "tool",
    "voice",
    "visual",
    "local_output",
}


def build_cortex_project_adapter(
    *,
    project_id: str,
    handler: ProjectHandler,
    lane: str = "tool",
    requires_operator: bool = True,
    auto_safe_capable: bool = False,
) -> CortexAdapter:
    if not isinstance(project_id, str) or not re.fullmatch(
        r"[a-z0-9_-]+",
        project_id,
    ):
        raise ValueError("project_id must use lowercase safe characters")
    if lane not in _ALLOWED_LANES:
        raise ValueError("project adapter lane is unsupported")
    if not callable(handler):
        raise ValueError("project handler must be callable")
    return CortexAdapter(
        name=f"project.{project_id}",
        lane=lane,
        handler=handler,
        description=f"Project adapter for {project_id}.",
        requires_operator=requires_operator,
        local_process_capable=True,
        auto_safe_capable=auto_safe_capable,
    )
