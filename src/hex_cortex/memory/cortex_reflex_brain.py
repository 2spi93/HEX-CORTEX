"""Reflex brain — the kernel's own tiny advisory model (autonomy ladder step 4).

A micro local model (0.5-3B) classifies incoming tasks for the kernel itself:
domain, novelty, uncertainty, risk. Its verdict is advisory only — it feeds
the router and the armor, it never executes or mutates anything.

Operator-approved first real advisory call, with hard rails baked in:
localhost endpoints only, structured JSON-schema output at temperature 0,
bounded timeout, and no raw prompt or raw response persistence — the parsed
fields plus a hash of the raw body are all that ever leaves this module.
Without a transport the module stays fully cold and returns a dry-run plan.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from urllib.parse import urlparse

_REQUEST_TYPE = "cortex_reflex_request_v1"
_VERDICT_TYPE = "cortex_reflex_verdict_v1"
_DOMAINS = (
    "coding",
    "debugging",
    "research",
    "math",
    "writing",
    "configuration",
    "planning",
    "other",
)
_RISKS = ("low", "medium", "high", "critical")
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "task_domain": {"type": "string", "enum": list(_DOMAINS)},
        "novelty": {"type": "number", "minimum": 0, "maximum": 1},
        "uncertainty": {"type": "number", "minimum": 0, "maximum": 1},
        "risk": {"type": "string", "enum": list(_RISKS)},
    },
    "required": ["task_domain", "novelty", "uncertainty", "risk"],
}

Transport = Callable[[str, bytes, float], str]


def build_reflex_request(
    task_text: str,
    *,
    model: str = "qwen2.5:1.5b",
    endpoint: str = "http://127.0.0.1:11434",
    timeout_seconds: float = 15.0,
) -> dict[str, object]:
    """Build the advisory classification request for the reflex model."""

    if not task_text.strip():
        raise ValueError("task_text must not be empty")
    if not model.strip():
        raise ValueError("model must not be empty")
    if not 1.0 <= timeout_seconds <= 60.0:
        raise ValueError("timeout_seconds must be within [1, 60]")
    host = urlparse(endpoint).hostname
    if host not in _LOCAL_HOSTS:
        raise ValueError("reflex brain only calls localhost endpoints")

    prompt = (
        "Classify this task for a routing kernel. Respond with JSON only.\n"
        f"Task: {task_text.strip()}"
    )
    return {
        "request_type": _REQUEST_TYPE,
        "url": f"{endpoint.rstrip('/')}/api/chat",
        "timeout_seconds": timeout_seconds,
        "payload": {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "format": _RESPONSE_SCHEMA,
            "options": {"temperature": 0.0},
            "stream": False,
        },
        "advisory_only": True,
        "mutation_allowed": False,
    }


def parse_reflex_response(raw_body: str) -> dict[str, object]:
    """Validate the reflex model's reply into a bounded verdict.

    Only parsed fields and a hash of the raw body survive; the raw text is
    never returned, so nothing upstream can persist it by accident.
    """

    body_hash = hashlib.sha256(raw_body.encode("utf-8")).hexdigest()
    try:
        envelope = json.loads(raw_body)
        content = envelope["message"]["content"]
        verdict = json.loads(content)
    except (json.JSONDecodeError, KeyError, TypeError):
        return _invalid_verdict(body_hash, "response_not_parseable")

    domain = verdict.get("task_domain")
    risk = verdict.get("risk")
    novelty = verdict.get("novelty")
    uncertainty = verdict.get("uncertainty")
    if domain not in _DOMAINS or risk not in _RISKS:
        return _invalid_verdict(body_hash, "enum_out_of_contract")
    if not all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0.0 <= float(value) <= 1.0
        for value in (novelty, uncertainty)
    ):
        return _invalid_verdict(body_hash, "score_out_of_bounds")

    return {
        "verdict_type": _VERDICT_TYPE,
        "valid": True,
        "task_domain": domain,
        "novelty": round(float(novelty), 10),
        "uncertainty": round(float(uncertainty), 10),
        "risk": risk,
        "raw_response_hash": body_hash,
        "raw_response_persisted": False,
        "advisory_only": True,
        "next_action": "feed_router_and_armor",
    }


def _invalid_verdict(body_hash: str, reason: str) -> dict[str, object]:
    return {
        "verdict_type": _VERDICT_TYPE,
        "valid": False,
        "invalid_reason": reason,
        "raw_response_hash": body_hash,
        "raw_response_persisted": False,
        "advisory_only": True,
        "next_action": "fallback_to_deterministic_routing",
    }


def classify_task(
    task_text: str,
    *,
    model: str = "qwen2.5:1.5b",
    endpoint: str = "http://127.0.0.1:11434",
    timeout_seconds: float = 15.0,
    transport: Transport | None = None,
) -> dict[str, object]:
    """Classify one task with the reflex brain.

    Without a transport this is a cold dry run returning the exact request
    that would be sent. With a transport (injected by the runtime), the call
    happens and the parsed verdict comes back — advisory only.
    """

    request = build_reflex_request(
        task_text,
        model=model,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
    )
    if transport is None:
        return {
            "verdict_type": _VERDICT_TYPE,
            "valid": False,
            "dry_run": True,
            "request": request,
            "model_call_performed": False,
            "advisory_only": True,
            "next_action": "provide_transport_to_execute",
        }

    body = json.dumps(request["payload"]).encode("utf-8")
    raw = transport(str(request["url"]), body, float(request["timeout_seconds"]))
    verdict = parse_reflex_response(raw)
    verdict["model_call_performed"] = True
    verdict["dry_run"] = False
    return verdict


def default_local_transport(url: str, body: bytes, timeout_seconds: float) -> str:
    """Minimal localhost-only HTTP transport for runtimes that want one."""

    import urllib.request

    host = urlparse(url).hostname
    if host not in _LOCAL_HOSTS:
        raise ValueError("default transport refuses non-localhost URLs")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return response.read().decode("utf-8")
