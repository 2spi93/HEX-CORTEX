"""CLI entrypoint for memory confidence batch confirmations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.confidence_batch import run_memory_confidence_batch_profile


def build_parser() -> argparse.ArgumentParser:
    """Build the memory confidence batch parser."""

    parser = argparse.ArgumentParser(
        prog="memory-confidence-batch",
        description="Preview or apply memory confidence confirmations.",
    )
    parser.add_argument("profile", type=Path)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--reason", default="batch_confirmed")
    parser.add_argument("--delta", type=float, default=0.05)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run memory confidence batch confirmation."""

    args = build_parser().parse_args(argv)
    payload = run_memory_confidence_batch_profile(
        args.profile,
        limit=args.limit,
        reason=args.reason,
        delta=args.delta,
        dry_run=not args.apply,
    )
    indent = 2 if args.pretty else None
    json.dump(payload, sys.stdout, indent=indent, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
