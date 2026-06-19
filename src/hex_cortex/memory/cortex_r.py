from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

Runner = Callable[[dict[str, object]], dict[str, object]]


def build_cortex_r(*, endpoint: str, timeout_seconds: float = 8.0) -> Runner:
    _assert_local_endpoint(endpoint)
    if timeout_seconds <= 0 or timeout_seconds > 30:
        raise ValueError("timeout_seconds must be in (0, 30]")

    def run(shape: dict[str, object]) -> dict[str, object]:
        model = shape.get("model")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("shape.model must be a non-empty string")
        payload = {
            "model": model,
            "prompt": "Return JSON: {\"status\": \"ok\", \"summary\": \"ready\"}.",
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except URLError as exc:
            return {"status": "blocked", "summary": f"local request failed: {exc.reason}"}
        return _extract(raw)

    return run


def _assert_local_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != "http":
        raise ValueError("endpoint must use http")
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("endpoint must be localhost")
    if parsed.port is None:
        raise ValueError("endpoint must include an explicit port")


def _extract(raw: str) -> dict[str, object]:
    try:
        payload: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "blocked", "summary": "invalid json response"}
    response = payload.get("response")
    if isinstance(response, str):
        try:
            nested = json.loads(response)
        except json.JSONDecodeError:
            nested = {"summary": response}
        if isinstance(nested, dict):
            status = nested.get("status")
            summary = nested.get("summary")
            return {
                "status": status if isinstance(status, str) else "ok",
                "summary": summary if isinstance(summary, str) else response[:160],
            }
    status = payload.get("status")
    summary = payload.get("summary")
    return {
        "status": status if isinstance(status, str) else "ok",
        "summary": summary if isinstance(summary, str) else "local response received",
    }
