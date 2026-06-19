from __future__ import annotations

from hex_cortex.memory.cortex_gateway import CortexAdapter
from hex_cortex.memory.cortex_r import build_cortex_r


def build_cortex_ollama_adapter(
    *,
    endpoint: str = "http://127.0.0.1:11434/api/generate",
    timeout_seconds: float = 8.0,
) -> CortexAdapter:
    runner = build_cortex_r(
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
    )
    return CortexAdapter(
        name="local.ollama",
        lane="tool",
        handler=runner,
        description="Local Ollama advisory adapter.",
        network_capable=True,
        auto_safe_capable=True,
        timeout_seconds=timeout_seconds,
    )
