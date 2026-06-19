from __future__ import annotations

import argparse
import json
from pathlib import Path

from hex_cortex.memory.cortex_bundle import build_cortex_bundle
from hex_cortex.memory.cortex_runtime_health import probe_cortex_runtime_targets
from hex_cortex.memory.cortex_runtime_probe import probe_cortex_runtime
from hex_cortex.memory.cortex_runtime_select import select_cortex_runtime_target
from hex_cortex.memory.cortex_runtime_targets import CortexRuntimeTarget
from hex_cortex.memory.cortex_runtime_targets import build_cortex_runtime_targets
from hex_cortex.memory.cortex_runtime_targets import list_cortex_runtime_targets
from hex_cortex.memory.cortex_wiring import audit_cortex_wiring


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("targets", "health", "select"):
        command = subparsers.add_parser(name)
        command.add_argument("--linux-endpoint")
        if name != "targets":
            command.add_argument("--timeout", type=float, default=2.0)
        if name == "select":
            command.add_argument("--platform")
            command.add_argument("--model")
    wiring = subparsers.add_parser("wiring-auto")
    wiring.add_argument("--project-root", default=".")
    wiring.add_argument("--overrides-json", default="{}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "wiring-auto":
        overrides = _boolean_object(args.overrides_json)
        if overrides is None:
            _emit({"status": "blocked", "blockers": ["overrides_json_invalid"]})
            return 2
        probe = probe_cortex_runtime(Path(args.project_root), overrides=overrides)
        payload = audit_cortex_wiring(
            build_cortex_bundle(),
            runtime_facts=probe["runtime_facts"],
        )
        payload["runtime_probe"] = {
            "project_root": probe["project_root"],
            "network_probe_performed": probe["network_probe_performed"],
            "process_probe_performed": probe["process_probe_performed"],
        }
        _emit(payload)
        return 0 if payload["architecture_ready"] is True else 2
    registry = _registry(args.linux_endpoint)
    if args.command == "targets":
        _emit(
            {
                "command": "targets",
                "targets": list_cortex_runtime_targets(registry),
            }
        )
        return 0
    health = probe_cortex_runtime_targets(
        registry,
        timeout_seconds=args.timeout,
    )
    if args.command == "health":
        _emit(health)
        return 0 if health["healthy_count"] > 0 else 2
    payload = select_cortex_runtime_target(
        health["target_records"],
        preferred_platform=args.platform,
        required_model=args.model,
    )
    payload["health_summary"] = {
        "target_count": health["target_count"],
        "healthy_count": health["healthy_count"],
    }
    _emit(payload)
    return 0 if payload["selection_allowed"] is True else 2


def _registry(linux_endpoint: str | None):
    rows = [
        CortexRuntimeTarget(
            target_id="windows-ollama",
            kind="ollama",
            endpoint="http://127.0.0.1:11434",
            platform="windows",
            priority=90,
        )
    ]
    if linux_endpoint:
        rows.append(
            CortexRuntimeTarget(
                target_id="linux-llama-server",
                kind="openai_compatible",
                endpoint=linux_endpoint,
                platform="linux",
                priority=100,
            )
        )
    return build_cortex_runtime_targets(*rows)


def _boolean_object(raw: str) -> dict[str, bool] | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, bool)
        for key, value in payload.items()
    ):
        return None
    return dict(payload)


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
