from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_operational_audit_v2 import build_operational_audit
from hex_cortex.memory.cortex_operational_audit_v2 import write_operational_audit_receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-audit")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--skip-research", action="store_true")
    parser.add_argument("--research-query", default="HEX-CORTEX operational readiness")
    parser.add_argument("--comfyui-endpoint", default="http://127.0.0.1:8188")
    parser.add_argument("--searxng-endpoint", default="http://127.0.0.1:8888/search")
    parser.add_argument("--model-ref", default="facebook/dinov2-base")
    parser.add_argument("--overrides-json", default="{}")
    parser.add_argument("--write-receipt", default="")
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    overrides = _parse_boolean_object(args.overrides_json)
    if overrides is None:
        return 2
    try:
        payload = build_operational_audit(
            Path(args.project_root),
            execute_network=args.network,
            include_research=not args.skip_research,
            research_query=args.research_query,
            comfyui_endpoint=args.comfyui_endpoint,
            searxng_endpoint=args.searxng_endpoint,
            model_ref=args.model_ref,
            runtime_fact_overrides=overrides,
        )
    except ValueError as exc:
        _emit(
            {
                "audit_type": "hex_cortex_operational_truth_v1",
                "operational_ready": False,
                "branch_ready": False,
                "blockers": [str(exc)],
            },
            pretty=args.pretty,
        )
        return 2
    if args.write_receipt:
        payload["receipt_write"] = write_operational_audit_receipt(
            Path(args.write_receipt),
            payload,
        )
    _emit(payload, pretty=args.pretty)
    return 0 if payload.get("branch_ready") is True else 2


def _parse_boolean_object(raw: str) -> dict[str, bool] | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        _emit({"status": "blocked", "blockers": ["overrides_json_invalid"]}, pretty=False)
        return None
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, bool)
        for key, value in payload.items()
    ):
        _emit(
            {"status": "blocked", "blockers": ["overrides_json_must_be_boolean_object"]},
            pretty=False,
        )
        return None
    return dict(payload)


def _emit(payload: dict[str, object], *, pretty: bool) -> None:
    print(json.dumps(payload, sort_keys=True, indent=2 if pretty else None))


if __name__ == "__main__":
    raise SystemExit(main())
