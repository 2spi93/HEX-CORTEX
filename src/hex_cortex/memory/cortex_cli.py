from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_bundle import build_cortex_bundle
from hex_cortex.memory.cortex_bundle import build_cortex_bundle_read_plan
from hex_cortex.memory.cortex_bus import list_cortex_units
from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_runtime_probe import probe_cortex_runtime
from hex_cortex.memory.cortex_surfaces import audit_cortex_surface
from hex_cortex.memory.cortex_surfaces import build_cortex_surface_manifest
from hex_cortex.memory.cortex_surfaces import list_cortex_surfaces
from hex_cortex.memory.cortex_wiring import audit_cortex_wiring


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hex-cortex")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("units")
    subparsers.add_parser("wiring")
    subparsers.add_parser("surfaces")
    subparsers.add_parser("read-plan")

    probe_parser = subparsers.add_parser("probe")
    probe_parser.add_argument("--project-root", default=".")
    probe_parser.add_argument("--overrides-json", default="{}")

    surface_parser = subparsers.add_parser("surface")
    surface_parser.add_argument("surface_id")
    surface_parser.add_argument("--facts-json", default="{}")

    auto_parser = subparsers.add_parser("surface-auto")
    auto_parser.add_argument("surface_id")
    auto_parser.add_argument("--project-root", default=".")
    auto_parser.add_argument("--overrides-json", default="{}")

    manifest_parser = subparsers.add_parser("manifest")
    manifest_parser.add_argument("surface_id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry = build_cortex_bundle()
    if args.command == "units":
        _emit(
            {
                "command": "units",
                "unit_count": len(registry),
                "units": list_cortex_units(registry),
            }
        )
        return 0
    if args.command == "wiring":
        payload = audit_cortex_wiring(registry)
        _emit(payload)
        return 0 if payload["architecture_ready"] is True else 2
    if args.command == "surfaces":
        rows = list_cortex_surfaces()
        _emit(
            {
                "command": "surfaces",
                "surface_count": len(rows),
                "surfaces": rows,
            }
        )
        return 0
    if args.command == "read-plan":
        payload = run_cortex_units(
            registry,
            build_cortex_bundle_read_plan(),
        )
        _emit(payload)
        return 0 if payload["bus_allowed"] is True else 2
    if args.command == "probe":
        overrides = _parse_boolean_object(
            args.overrides_json,
            command="probe",
        )
        if overrides is None:
            return 2
        payload = probe_cortex_runtime(
            Path(args.project_root),
            overrides=overrides,
        )
        _emit(payload)
        return 0
    if args.command == "surface":
        facts = _parse_boolean_object(
            args.facts_json,
            command="surface",
        )
        if facts is None:
            return 2
        payload = audit_cortex_surface(
            surface_id=args.surface_id,
            registry=registry,
            runtime_facts=facts,
        )
        _emit(payload)
        return 0 if payload["contract_ready"] is True else 2
    if args.command == "surface-auto":
        overrides = _parse_boolean_object(
            args.overrides_json,
            command="surface-auto",
        )
        if overrides is None:
            return 2
        probe = probe_cortex_runtime(
            Path(args.project_root),
            overrides=overrides,
        )
        payload = audit_cortex_surface(
            surface_id=args.surface_id,
            registry=registry,
            runtime_facts=probe["runtime_facts"],
        )
        payload["runtime_probe"] = {
            "project_root": probe["project_root"],
            "network_probe_performed": probe["network_probe_performed"],
            "process_probe_performed": probe["process_probe_performed"],
        }
        _emit(payload)
        return 0 if payload["contract_ready"] is True else 2
    if args.command == "manifest":
        payload = build_cortex_surface_manifest(args.surface_id)
        _emit(payload)
        return 0 if payload.get("state") != "blocked" else 2
    _emit(
        {
            "status": "blocked",
            "blockers": ["unknown_command"],
        }
    )
    return 2


def _parse_boolean_object(
    raw: str,
    *,
    command: str,
) -> dict[str, bool] | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        _emit(
            {
                "command": command,
                "status": "blocked",
                "blockers": ["facts_json_invalid"],
            }
        )
        return None
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, bool)
        for key, value in payload.items()
    ):
        _emit(
            {
                "command": command,
                "status": "blocked",
                "blockers": ["facts_json_must_be_boolean_object"],
            }
        )
        return None
    return dict(payload)


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
