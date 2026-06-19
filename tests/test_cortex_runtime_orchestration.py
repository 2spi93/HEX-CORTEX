import pytest

from hex_cortex.memory.cortex_runtime_health import probe_cortex_runtime_target
from hex_cortex.memory.cortex_runtime_health import probe_cortex_runtime_targets
from hex_cortex.memory.cortex_runtime_select import build_cortex_runtime_benchmark_plan
from hex_cortex.memory.cortex_runtime_select import select_cortex_runtime_target
from hex_cortex.memory.cortex_runtime_targets import CortexRuntimeTarget
from hex_cortex.memory.cortex_runtime_targets import build_cortex_runtime_targets
from hex_cortex.memory.cortex_runtime_targets import default_cortex_runtime_targets
from hex_cortex.memory.cortex_runtime_targets import list_cortex_runtime_targets


def test_default_runtime_targets_match_windows_and_linux() -> None:
    registry = default_cortex_runtime_targets(
        linux_endpoint="https://llama.example.test"
    )
    rows = list_cortex_runtime_targets(registry)

    assert [row["target_id"] for row in rows] == [
        "linux-llama-server",
        "windows-ollama",
    ]
    assert registry["windows-ollama"].kind == "ollama"
    assert registry["linux-llama-server"].kind == "openai_compatible"
    assert all(row["auth_value_persisted"] is False for row in rows)


def test_runtime_target_rejects_remote_plain_http() -> None:
    with pytest.raises(ValueError, match="https"):
        build_cortex_runtime_targets(
            CortexRuntimeTarget(
                target_id="remote",
                kind="openai_compatible",
                endpoint="http://192.0.2.20:8080",
                platform="linux",
            )
        )


def test_ollama_probe_reads_inventory_and_loaded_models() -> None:
    calls = []

    def getter(url, headers, timeout):
        calls.append((url, headers, timeout))
        if url.endswith("/api/tags"):
            return {"models": [{"name": "qwen3:8b"}, {"name": "coder:7b"}]}
        return {"models": [{"name": "qwen3:8b"}]}

    target = CortexRuntimeTarget(
        target_id="windows-ollama",
        kind="ollama",
        endpoint="http://127.0.0.1:11434",
        platform="windows",
        priority=90,
    )

    payload = probe_cortex_runtime_target(target, http_get=getter)

    assert payload["healthy"] is True
    assert payload["models"] == ["coder:7b", "qwen3:8b"]
    assert payload["loaded_models"] == ["qwen3:8b"]
    assert payload["model_count"] == 2
    assert len(calls) == 2


def test_openai_probe_uses_v1_models_and_auth_reference() -> None:
    observed = {}

    def getter(url, headers, timeout):
        observed["url"] = url
        observed["headers"] = headers
        observed["timeout"] = timeout
        return {"data": [{"id": "qwen3-8b"}]}

    target = CortexRuntimeTarget(
        target_id="linux-llama-server",
        kind="openai_compatible",
        endpoint="https://llama.example.test",
        platform="linux",
        auth_ref="keyring://hex-cortex/llama/main",
    )

    payload = probe_cortex_runtime_target(
        target,
        auth_resolver=lambda ref: "secret-token",
        http_get=getter,
    )

    assert payload["healthy"] is True
    assert payload["models"] == ["qwen3-8b"]
    assert observed["url"] == "https://llama.example.test/v1/models"
    assert observed["headers"]["Authorization"] == "Bearer secret-token"
    assert "secret-token" not in str(payload)


def test_runtime_probe_normalizes_failure() -> None:
    target = CortexRuntimeTarget(
        target_id="windows-ollama",
        kind="ollama",
        endpoint="http://127.0.0.1:11434",
        platform="windows",
    )

    payload = probe_cortex_runtime_target(
        target,
        http_get=lambda url, headers, timeout: (_ for _ in ()).throw(
            RuntimeError("offline")
        ),
    )

    assert payload["healthy"] is False
    assert payload["error_type"] == "RuntimeError"
    assert payload["network_call_performed"] is True


def test_runtime_selection_prefers_platform_then_loaded_model() -> None:
    records = [
        {
            "target_id": "windows-ollama",
            "kind": "ollama",
            "platform": "windows",
            "healthy": True,
            "priority": 90,
            "latency_ms": 80.0,
            "models": ["qwen3:8b"],
            "loaded_model_count": 1,
        },
        {
            "target_id": "linux-llama-server",
            "kind": "openai_compatible",
            "platform": "linux",
            "healthy": True,
            "priority": 100,
            "latency_ms": 25.0,
            "models": ["qwen3:8b"],
            "loaded_model_count": 0,
        },
    ]

    windows = select_cortex_runtime_target(
        records,
        preferred_platform="windows",
        required_model="qwen3:8b",
    )
    linux = select_cortex_runtime_target(
        records,
        preferred_platform="linux",
        required_model="qwen3:8b",
    )

    assert windows["selected_target"]["target_id"] == "windows-ollama"
    assert linux["selected_target"]["target_id"] == "linux-llama-server"


def test_runtime_selection_blocks_when_required_model_missing() -> None:
    payload = select_cortex_runtime_target(
        [
            {
                "target_id": "windows-ollama",
                "healthy": True,
                "models": ["other"],
            }
        ],
        required_model="missing",
    )

    assert payload["selection_allowed"] is False
    assert payload["blockers"] == ["no_healthy_compatible_runtime"]


def test_runtime_probe_batch_and_benchmark_plan() -> None:
    registry = build_cortex_runtime_targets(
        CortexRuntimeTarget(
            target_id="windows-ollama",
            kind="ollama",
            endpoint="http://127.0.0.1:11434",
            platform="windows",
        )
    )
    payload = probe_cortex_runtime_targets(
        registry,
        http_get=lambda url, headers, timeout: {"models": []},
    )
    plan = build_cortex_runtime_benchmark_plan(model="qwen3:8b")

    assert payload["healthy_count"] == 1
    assert plan["execution_performed"] is False
    assert "tokens_per_second" in plan["metrics"]
