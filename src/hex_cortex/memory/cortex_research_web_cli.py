from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from hex_cortex.memory.cortex_searxng import build_cortex_searxng_searcher
from hex_cortex.memory.cortex_web import build_cortex_web_search
from hex_cortex.memory.cortex_web import describe_cortex_web


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-research")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("describe")

    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--endpoint", default="http://127.0.0.1:8888/search")
    search.add_argument("--timeout-seconds", type=float, default=8.0)
    search.add_argument("--max-results", type=int, default=8)
    search.add_argument("--operator-approved", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "describe":
        _emit(describe_cortex_web())
        return 0

    if not args.operator_approved:
        _emit(
            {
                "status": "blocked",
                "summary": "live web search requires --operator-approved",
                "citations": [],
                "network_call_performed": False,
            }
        )
        return 2

    try:
        searcher = build_cortex_searxng_searcher(
            endpoint=args.endpoint,
            timeout_seconds=args.timeout_seconds,
            max_results=args.max_results,
        )
    except ValueError as exc:
        _emit(
            {
                "status": "blocked",
                "summary": str(exc),
                "citations": [],
                "network_call_performed": False,
            }
        )
        return 2

    guarded = build_cortex_web_search(searcher)
    payload = {**guarded(args.query), "network_call_performed": True}
    _emit(payload)
    return 0 if payload.get("status") == "ok" else 2


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
