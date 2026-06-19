import pytest

from hex_cortex.memory.cortex_gateway import build_cortex_adapter_registry
from hex_cortex.memory.cortex_gateway import list_cortex_adapters
from hex_cortex.memory.cortex_ollama_link import build_cortex_ollama_adapter


def test_ollama_adapter_is_local_tool_binding() -> None:
    adapter = build_cortex_ollama_adapter()
    registry = build_cortex_adapter_registry(adapter)
    row = list_cortex_adapters(registry)[0]

    assert row["name"] == "local.ollama"
    assert row["lane"] == "tool"
    assert row["network_capable"] is True
    assert row["auto_safe_capable"] is True
    assert row["handler_exposed"] is False


def test_ollama_adapter_rejects_non_local_endpoint() -> None:
    with pytest.raises(ValueError, match="localhost"):
        build_cortex_ollama_adapter(
            endpoint="http://example.com:11434/api/generate"
        )


def test_ollama_adapter_rejects_invalid_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        build_cortex_ollama_adapter(timeout_seconds=0)
