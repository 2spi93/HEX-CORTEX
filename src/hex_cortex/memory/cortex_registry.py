from __future__ import annotations

from pathlib import Path

from hex_cortex.memory.cortex_a import build_cortex_a
from hex_cortex.memory.cortex_b import build_cortex_b
from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_c import build_cortex_c
from hex_cortex.memory.cortex_lc import build_cortex_lc
from hex_cortex.memory.cortex_r import build_cortex_r


def build_cortex_registry() -> dict[str, CortexUnit]:
    return {
        "lc.build": CortexUnit(
            name="lc.build",
            unit=build_cortex_lc,
            description="Build a local target receipt.",
            mutates_receipt=True,
            requires_operator=False,
        ),
        "a.build": CortexUnit(
            name="a.build",
            unit=build_cortex_a,
            description="Build a safe shape receipt from a local target receipt.",
            mutates_receipt=True,
            requires_operator=False,
        ),
        "b.build": CortexUnit(
            name="b.build",
            unit=build_cortex_b,
            description="Build an operator-approved runner receipt with an injected runner.",
            mutates_receipt=True,
            requires_operator=True,
        ),
        "c.build": CortexUnit(
            name="c.build",
            unit=build_cortex_c,
            description="Build the chained lc -> a -> b receipt.",
            mutates_receipt=True,
            requires_operator=True,
        ),
        "r.describe": CortexUnit(
            name="r.describe",
            unit=describe_cortex_r,
            description="Validate and describe a localhost runner adapter without executing it.",
            mutates_receipt=False,
            requires_operator=False,
        ),
    }


def describe_cortex_r(*, endpoint: str, timeout_seconds: float = 8.0) -> dict[str, object]:
    runner = build_cortex_r(endpoint=endpoint, timeout_seconds=timeout_seconds)
    return {
        "adapter_type": "cortex_r",
        "endpoint_redacted": _redact_endpoint(endpoint),
        "timeout_seconds": timeout_seconds,
        "runner_created": callable(runner),
        "runner_executed": False,
        "next_action": "inject_runner_into_b_or_c",
    }


def build_cortex_registry_plan(profile: Path) -> list[dict[str, object]]:
    return [
        {
            "name": "lc.build",
            "kwargs": {
                "profile": profile,
                "kind": "ollama",
                "model": "qwen2.5-coder:7b-instruct",
                "target": "http://127.0.0.1:11434",
            },
        },
        {"name": "a.build", "kwargs": {"profile": profile, "expected_kind": "ollama"}},
        {
            "name": "r.describe",
            "kwargs": {
                "endpoint": "http://127.0.0.1:11434/api/generate",
                "timeout_seconds": 8.0,
            },
        },
    ]


def _redact_endpoint(endpoint: str) -> str:
    if endpoint.startswith("http://127.0.0.1"):
        return "http://127.0.0.1:<redacted>"
    if endpoint.startswith("http://localhost"):
        return "http://localhost:<redacted>"
    return "non-local-redacted"
