from __future__ import annotations

import hashlib
import json
import platform
from collections.abc import Callable
from time import monotonic
from urllib.parse import urlparse
from urllib.request import Request, urlopen

RuntimeTransport = Callable[[str, str, dict[str, object] | None, float], dict[str, object]]

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def build_runtime_descriptors(
    *,
    system_name: str | None = None,
    ollama_endpoint: str = "http://127.0.0.1:11434",
    llama_server_endpoint: str = "http://127.0.0.1:8080",
) -> list[dict[str, object]]:
    system = (system_name or platform.system()).strip().lower()
    windows = system.startswith("win")
    linux = system.startswith("linux")
    descriptors = [
        {
            "runtime_id": "windows.ollama",
            "runtime_kind": "ollama",
            "platform_role": "windows_development",
            "preferred": windows,
            "priority": 0 if windows else 20,
            "base_url": _validated_local_base_url(ollama_endpoint),
            "inventory_path": "/api/tags",
            "loaded_models_path": "/api/ps",
            "generation_path": "/api/generate",
            "protocol": "ollama",
        },
        {
            "runtime_id": "linux.llama_server",
            "runtime_kind": "llama_server",
            "platform_role": "linux_server",
            "preferred": linux,
            "priority": 0 if linux else 20,
            "base_url": _validated_local_base_url(llama_server_endpoint),
            "inventory_path": "/v1/models",
            "loaded_models_path": None,
            "generation_path": "/v1/chat/completions",
            "protocol": "openai_compatible",
        },
    ]
    return sorted(descriptors, key=lambda item: (int(item["priority"]), str(item["runtime_id"])))


def probe_runtime_descriptor(
    descriptor: dict[str, object],
    *,
    transport: RuntimeTransport | None = None,
    timeout_seconds: float = 2.0,
) -> dict[str, object]:
    runtime_id = _required_string(descriptor, "runtime_id")
    base_url = _validated_local_base_url(_required_string(descriptor, "base_url"))
    inventory_path = _required_string(descriptor, "inventory_path")
    caller = transport or _http_json
    started = monotonic()
    error_type: str | None = None
    inventory: dict[str, object] = {}
    loaded: dict[str, object] = {}
    try:
        inventory = caller("GET", base_url + inventory_path, None, timeout_seconds)
        loaded_path = descriptor.get("loaded_models_path")
        if isinstance(loaded_path, str) and loaded_path:
            loaded = caller("GET", base_url + loaded_path, None, timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - receipt records only the error type.
        error_type = type(exc).__name__
    elapsed_ms = round((monotonic() - started) * 1000, 3)
    models = _model_inventory(str(descriptor.get("runtime_kind")), inventory)
    loaded_rows = _loaded_inventory(loaded)
    healthy = error_type is None
    return {
        "receipt_type": "runtime_health_probe",
        "runtime_id": runtime_id,
        "runtime_kind": descriptor.get("runtime_kind"),
        "healthy": healthy,
        "latency_ms": elapsed_ms,
        "model_count": len(models),
        "models": models,
        "loaded_model_count": len(loaded_rows),
        "loaded_models": loaded_rows,
        "loaded_vram_bytes": sum(int(row.get("size_vram", 0)) for row in loaded_rows),
        "network_call_performed": True,
        "raw_response_persisted": False,
        "error_type": error_type,
        "probe_hash": _stable_hash({
            "runtime_id": runtime_id,
            "healthy": healthy,
            "models": models,
            "loaded_models": loaded_rows,
            "error_type": error_type,
        }),
    }


def benchmark_runtime_descriptor(
    descriptor: dict[str, object],
    *,
    model: str,
    prompt: str = "Reply with OK.",
    transport: RuntimeTransport | None = None,
    timeout_seconds: float = 8.0,
) -> dict[str, object]:
    if not model.strip():
        raise ValueError("model must be non-empty")
    base_url = _validated_local_base_url(_required_string(descriptor, "base_url"))
    generation_path = _required_string(descriptor, "generation_path")
    protocol = _required_string(descriptor, "protocol")
    caller = transport or _http_json
    if protocol == "ollama":
        request = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 32},
        }
    elif protocol == "openai_compatible":
        request = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0,
            "max_tokens": 32,
        }
    else:
        raise ValueError(f"unsupported protocol: {protocol}")
    started = monotonic()
    error_type: str | None = None
    response: dict[str, object] = {}
    try:
        response = caller("POST", base_url + generation_path, request, timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - benchmark receipt is fail-closed.
        error_type = type(exc).__name__
    elapsed_seconds = max(monotonic() - started, 0.000001)
    generated_tokens = _generated_tokens(protocol, response)
    tokens_per_second = round(generated_tokens / elapsed_seconds, 3) if generated_tokens else 0.0
    return {
        "receipt_type": "runtime_benchmark",
        "runtime_id": descriptor.get("runtime_id"),
        "runtime_kind": descriptor.get("runtime_kind"),
        "model": model,
        "healthy": error_type is None,
        "latency_ms": round(elapsed_seconds * 1000, 3),
        "generated_tokens": generated_tokens,
        "tokens_per_second": tokens_per_second,
        "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_persisted": False,
        "raw_response_persisted": False,
        "network_call_performed": True,
        "model_call_performed": True,
        "error_type": error_type,
    }


def orchestrate_runtime_models(
    *,
    system_name: str | None = None,
    execute_network: bool = False,
    execute_benchmark: bool = False,
    model_overrides: dict[str, str] | None = None,
    transport: RuntimeTransport | None = None,
) -> dict[str, object]:
    descriptors = build_runtime_descriptors(system_name=system_name)
    if not execute_network:
        selected = descriptors[0]
        return {
            "orchestration_type": "runtime_model_orchestration_v1",
            "status": "planned",
            "selected_runtime_id": selected["runtime_id"],
            "fallback_runtime_ids": [row["runtime_id"] for row in descriptors[1:]],
            "service_descriptors": descriptors,
            "health_receipts": [],
            "benchmark_receipt": None,
            "network_call_performed": False,
            "model_call_performed": False,
            "runtime_facts": {
                "runtime_orchestration_available": True,
                "local_model_runtime_available": False,
                "ollama_endpoint_configured": False,
                "llama_server_endpoint_configured": False,
            },
            "next_action": "run_runtime_auto_with_network_probe",
        }
    health = [
        probe_runtime_descriptor(row, transport=transport)
        for row in descriptors
    ]
    healthy_ids = {row["runtime_id"] for row in health if row["healthy"] is True}
    selected = next((row for row in descriptors if row["runtime_id"] in healthy_ids), None)
    benchmark = None
    if selected is not None and execute_benchmark:
        model = (model_overrides or {}).get(str(selected["runtime_id"]))
        if model is None:
            matching = next(row for row in health if row["runtime_id"] == selected["runtime_id"])
            models = matching.get("models", [])
            model = str(models[0]["name"]) if isinstance(models, list) and models else ""
        if model:
            benchmark = benchmark_runtime_descriptor(selected, model=model, transport=transport)
    selected_id = selected.get("runtime_id") if selected else None
    fallback_ids = [
        row["runtime_id"]
        for row in descriptors
        if row["runtime_id"] in healthy_ids and row["runtime_id"] != selected_id
    ]
    return {
        "orchestration_type": "runtime_model_orchestration_v1",
        "status": "ready" if selected else "blocked",
        "selected_runtime_id": selected_id,
        "fallback_runtime_ids": fallback_ids,
        "service_descriptors": descriptors,
        "health_receipts": health,
        "benchmark_receipt": benchmark,
        "network_call_performed": True,
        "model_call_performed": benchmark is not None,
        "runtime_facts": {
            "runtime_orchestration_available": True,
            "local_model_runtime_available": selected is not None,
            "ollama_endpoint_configured": "windows.ollama" in healthy_ids,
            "llama_server_endpoint_configured": "linux.llama_server" in healthy_ids,
        },
        "next_action": "operate_selected_runtime" if selected else "start_local_model_runtime",
    }


def _http_json(
    method: str,
    url: str,
    payload: dict[str, object] | None,
    timeout_seconds: float,
) -> dict[str, object]:
    _validated_local_url(url)
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - localhost only.
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("runtime response must be a JSON object")
    return result


def _validated_local_base_url(value: str) -> str:
    parsed = _validated_local_url(value)
    return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"


def _validated_local_url(value: str):
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in _LOCAL_HOSTS or parsed.port is None:
        raise ValueError("runtime endpoint must be explicit localhost http with port")
    return parsed


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _model_inventory(runtime_kind: str, payload: dict[str, object]) -> list[dict[str, object]]:
    if runtime_kind == "ollama":
        rows = payload.get("models", [])
        return [
            {
                "name": row.get("name") or row.get("model"),
                "size": row.get("size"),
                "parameter_size": (row.get("details") or {}).get("parameter_size")
                if isinstance(row.get("details"), dict)
                else None,
                "quantization": (row.get("details") or {}).get("quantization_level")
                if isinstance(row.get("details"), dict)
                else None,
            }
            for row in rows
            if isinstance(row, dict) and (row.get("name") or row.get("model"))
        ]
    rows = payload.get("data", [])
    return [
        {"name": row.get("id"), "size": None, "parameter_size": None, "quantization": None}
        for row in rows
        if isinstance(row, dict) and row.get("id")
    ]


def _loaded_inventory(payload: dict[str, object]) -> list[dict[str, object]]:
    rows = payload.get("models", [])
    return [
        {
            "name": row.get("name") or row.get("model"),
            "size": row.get("size"),
            "size_vram": row.get("size_vram", 0),
            "context_length": row.get("context_length"),
        }
        for row in rows
        if isinstance(row, dict) and (row.get("name") or row.get("model"))
    ]


def _generated_tokens(protocol: str, response: dict[str, object]) -> int:
    if protocol == "ollama":
        value = response.get("eval_count", 0)
        return int(value) if isinstance(value, int | float) else 0
    usage = response.get("usage", {})
    value = usage.get("completion_tokens", 0) if isinstance(usage, dict) else 0
    return int(value) if isinstance(value, int | float) else 0


def _stable_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
