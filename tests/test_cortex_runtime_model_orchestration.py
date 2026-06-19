import pytest

from hex_cortex.memory.cortex_runtime_model_orchestration import benchmark_runtime_descriptor
from hex_cortex.memory.cortex_runtime_model_orchestration import build_runtime_descriptors
from hex_cortex.memory.cortex_runtime_model_orchestration import orchestrate_runtime_models
from hex_cortex.memory.cortex_runtime_model_orchestration import probe_runtime_descriptor


def test_runtime_descriptors_prefer_windows_ollama() -> None:
    rows = build_runtime_descriptors(system_name="Windows")

    assert rows[0]["runtime_id"] == "windows.ollama"
    assert rows[0]["preferred"] is True
    assert rows[1]["runtime_id"] == "linux.llama_server"


def test_runtime_descriptors_prefer_linux_llama_server() -> None:
    rows = build_runtime_descriptors(system_name="Linux")

    assert rows[0]["runtime_id"] == "linux.llama_server"
    assert rows[0]["preferred"] is True


def test_runtime_descriptor_rejects_remote_endpoint() -> None:
    with pytest.raises(ValueError, match="localhost"):
        build_runtime_descriptors(ollama_endpoint="https://example.com:11434")


def test_probe_ollama_inventory_and_vram() -> None:
    descriptor = build_runtime_descriptors(system_name="Windows")[0]

    def transport(method, url, payload, timeout):
        assert method == "GET"
        assert payload is None
        assert timeout == 2.0
        if url.endswith("/api/tags"):
            return {
                "models": [
                    {
                        "name": "qwen3:8b",
                        "size": 5_000,
                        "details": {"parameter_size": "8B", "quantization_level": "Q4_K_M"},
                    }
                ]
            }
        return {
            "models": [
                {"name": "qwen3:8b", "size": 5_000, "size_vram": 4_000, "context_length": 32768}
            ]
        }

    receipt = probe_runtime_descriptor(descriptor, transport=transport)

    assert receipt["healthy"] is True
    assert receipt["model_count"] == 1
    assert receipt["models"][0]["quantization"] == "Q4_K_M"
    assert receipt["loaded_vram_bytes"] == 4_000
    assert receipt["raw_response_persisted"] is False


def test_orchestrator_falls_back_to_healthy_runtime() -> None:
    def transport(method, url, payload, timeout):
        if "11434" in url:
            raise ConnectionError("offline")
        if url.endswith("/v1/models"):
            return {"data": [{"id": "qwen3-8b.gguf"}]}
        raise AssertionError(url)

    payload = orchestrate_runtime_models(
        system_name="Windows",
        execute_network=True,
        transport=transport,
    )

    assert payload["status"] == "ready"
    assert payload["selected_runtime_id"] == "linux.llama_server"
    assert payload["runtime_facts"]["local_model_runtime_available"] is True
    assert payload["runtime_facts"]["ollama_endpoint_configured"] is False


def test_benchmark_receipt_does_not_persist_prompt_or_response() -> None:
    descriptor = build_runtime_descriptors(system_name="Linux")[0]

    def transport(method, url, payload, timeout):
        assert method == "POST"
        assert payload["model"] == "qwen3-8b.gguf"
        return {"usage": {"completion_tokens": 8}, "choices": [{"message": {"content": "OK"}}]}

    receipt = benchmark_runtime_descriptor(
        descriptor,
        model="qwen3-8b.gguf",
        transport=transport,
    )

    assert receipt["healthy"] is True
    assert receipt["generated_tokens"] == 8
    assert receipt["model_call_performed"] is True
    assert receipt["prompt_persisted"] is False
    assert receipt["raw_response_persisted"] is False
