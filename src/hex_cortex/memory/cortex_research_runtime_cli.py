from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_searxng import audit_searxng_runtime
from hex_cortex.memory.cortex_searxng import build_searxng_searcher


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-research")
    commands = parser.add_subparsers(dest="command", required=True)

    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--endpoint", default="http://127.0.0.1:8888/search")
    search.add_argument("--max-items", type=int, default=8)
    search.add_argument("--timeout-seconds", type=float, default=10.0)
    search.add_argument("--network", action="store_true")
    search.add_argument("--output")
    search.add_argument("--pretty", action="store_true")

    audit = commands.add_parser("audit")
    audit.add_argument("query")
    audit.add_argument("--endpoint", default="http://127.0.0.1:8888/search")
    audit.add_argument("--max-items", type=int, default=8)
    audit.add_argument("--timeout-seconds", type=float, default=10.0)
    audit.add_argument("--network", action="store_true")
    audit.add_argument("--output")
    audit.add_argument("--pretty", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.network:
        payload = {
            "status": "planned",
            "command": args.command,
            "endpoint": args.endpoint,
            "query_hash": _hash_text(args.query),
            "query_persisted": False,
            "network_call_performed": False,
            "operational_ready": False,
            "blockers": ["network_execution_not_authorized"],
            "next_action": "rerun_with_network_after_operator_review",
        }
        _write_and_emit(payload, output=args.output, pretty=args.pretty)
        return 2
    try:
        searcher = build_searxng_searcher(
            endpoint=args.endpoint,
            max_items=args.max_items,
            timeout_seconds=args.timeout_seconds,
        )
        search_result = searcher(args.query)
    except ValueError as exc:
        payload = {
            "status": "blocked",
            "network_call_performed": False,
            "blockers": [str(exc)],
            "next_action": "repair_research_runtime_inputs",
        }
        _write_and_emit(payload, output=args.output, pretty=args.pretty)
        return 2
    payload = search_result if args.command == "search" else audit_searxng_runtime(search_result)
    _write_and_emit(payload, output=args.output, pretty=args.pretty)
    success_statuses = {"ok", "operational"}
    return 0 if payload.get("status") in success_statuses else 2


def _write_and_emit(
    payload: dict[str, object],
    *,
    output: str | None,
    pretty: bool,
) -> None:
    text = json.dumps(payload, sort_keys=True, indent=2 if pretty else None)
    if output:
        path = Path(output).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)


def _hash_text(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
