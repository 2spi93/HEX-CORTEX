from __future__ import annotations

from hex_cortex.memory.cortex_gateway import CortexAdapter
from hex_cortex.memory.cortex_r import build_cortex_r


def build_cortex_openai_local_adapter(
    *,
    endpoint: str = "http://127.0.0.1:8080/v1/chat/completions",
    timeout_seconds: float = 8.0,
) -> CortexAdapter:
    runner = build_cortex_r(
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        protocol="openai_compatible",
    )
    return CortexAdapter(
        name="local.openai_compatible",
        lane="tool",
        handler=runner,
        description="Local OpenAI-compatible advisory adapter.",
        network_capable=True,
        auto_safe_capable=True,
        timeout_seconds=timeout_seconds,
    )
