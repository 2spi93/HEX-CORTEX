from __future__ import annotations

import json
from collections.abc import Callable
from time import monotonic
from urllib.error import URLError
from urllib.request import Request, urlopen

from hex_cortex.memory.cortex_runtime_targets import CortexRuntimeTarget

HttpGet = Callable[[str, dict[str, str], float], dict[str, object]]
AuthResolver = Callable[[str], str | None]


def probe_cortex_runtime_target(
    target: CortexRuntimeTarget,
    *,
    timeout_seconds: float = 2.0,
    auth_resolver: AuthResolver | None = None,
    http_get: HttpGet | None = None,
) -> dict[str, object]:
    if timeout_seconds <= 0 or timeout_seconds > 15:
        raise ValueError("timeout_seconds must be in (0, 15]")
    if not target.enabled:
        return _blocked(target, "runtime_target_disabled")
    headers = {"Accept": "application/json"}
    if target.auth_ref is not None:
        if auth_resolver is None:
            return _blocked(target, "runtime_auth_resolver_missing")
        token = auth_resolver(target.auth_ref)
        if not token:
            return _blocked(target, "runtime_auth_value_missing")
        headers["Authorization"] = f"Bearer {token}"
    getter = http_get or _get_json
    started = monotonic()
    try:
        if target.kind == "ollama":
            inventory = getter(
                f"{target.endpoint.rstrip('/')}/api/tags",
                headers,
                timeout_seconds,
            )
            loaded = getter(
                f"{target.endpoint.rstrip('/')}/api/ps",
                headers,
                timeout_seconds,
            )
            models = _ollama_models(inventory)
            loaded_models = _ollama_models(loaded)
        else:
            inventory = getter(
                _openai_models_url(target.endpoint),
                headers,
                timeout_seconds,
            )
            models = _openai_models(inventory)
            loaded_models = []
    except Exception as exc:  # noqa: BLE001 - normalized into a health receipt.
        elapsed_ms = round((monotonic() - started) * 1000, 3)
        return {
            **_base(target),
            "healthy": False,
            "latency_ms": elapsed_ms,
            "models": [],
            "model_count": 0,
            "loaded_models": [],
            "loaded_model_count": 0,
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:160],
            "network_call_performed": True,
            "auth_value_persisted": False,
            "next_action": "repair_runtime_target",
        }
    elapsed_ms = round((monotonic() - started) * 1000, 3)
    return {
        **_base(target),
        "healthy": True,
        "latency_ms": elapsed_ms,
        "models": models,
        "model_count": len(models),
        "loaded_models": loaded_models,
        "loaded_model_count": len(loaded_models),
        "error_type": None,
        "error_message": None,
        "network_call_performed": True,
        "auth_value_persisted": False,
        "next_action": "benchmark_runtime_target",
    }


def probe_cortex_runtime_targets(
    registry: dict[str, CortexRuntimeTarget],
    *,
    timeout_seconds: float = 2.0,
    auth_resolver: AuthResolver | None = None,
    http_get: HttpGet | None = None,
) -> dict[str, object]:
    rows = [
        probe_cortex_runtime_target(
            target,
            timeout_seconds=timeout_seconds,
            auth_resolver=auth_resolver,
            http_get=http_get,
        )
        for target in registry.values()
    ]
    return {
        "probe_type": "cortex_runtime_health",
        "target_count": len(rows),
        "healthy_count": sum(row["healthy"] is True for row in rows),
        "network_call_performed": bool(rows),
        "target_records": rows,
        "next_action": (
            "select_runtime_target"
            if any(row["healthy"] is True for row in rows)
            else "repair_runtime_targets"
        ),
    }


def _get_json(
    url: str,
    headers: dict[str, str],
    timeout_seconds: float,
) -> dict[str, object]:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except URLError as exc:
        raise RuntimeError(f"runtime request failed: {exc.reason}") from exc
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("runtime response must be an object")
    return payload


def _ollama_models(payload: dict[str, object]) -> list[str]:
    rows = payload.get("models")
    if not isinstance(rows, list):
        return []
    names = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name") or row.get("model")
        if isinstance(name, str) and name:
            names.append(name)
    return sorted(set(names))


def _openai_models(payload: dict[str, object]) -> list[str]:
    rows = payload.get("data")
    if not isinstance(rows, list):
        return []
    names = []
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            names.append(str(row["id"]))
    return sorted(set(names))


def _openai_models_url(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/models"
    return f"{base}/v1/models"


def _base(target: CortexRuntimeTarget) -> dict[str, object]:
    return {
        "target_id": target.target_id,
        "kind": target.kind,
        "endpoint": target.endpoint,
        "platform": target.platform,
        "priority": target.priority,
        "auth_ref": target.auth_ref,
    }


def _blocked(
    target: CortexRuntimeTarget,
    blocker: str,
) -> dict[str, object]:
    return {
        **_base(target),
        "healthy": False,
        "latency_ms": None,
        "models": [],
        "model_count": 0,
        "loaded_models": [],
        "loaded_model_count": 0,
        "error_type": blocker,
        "error_message": blocker,
        "network_call_performed": False,
        "auth_value_persisted": False,
        "next_action": "repair_runtime_target",
    }
