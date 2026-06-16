"""CLI entrypoint for temporal memory confidence decay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.confidence_decay import run_memory_confidence_decay_profile


def build_parser() -> argparse.ArgumentParser:
    """Build the memory confidence decay parser."""

    parser = argparse.ArgumentParser(
        prog="memory-confidence-decay",
        description="Preview or apply temporal memory confidence decay.",
    )
    parser.add_argument("profile", type=Path)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--stale-after-days", type=int, default=30)
    parser.add_argument("--decay-amount", type=float, default=0.05)
    parser.add_argument("--minimum-confidence", type=float, default=0.3)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run temporal memory confidence decay."""

    args = build_parser().parse_args(argv)
    payload = run_memory_confidence_decay_profile(
        args.profile,
        limit=args.limit,
        stale_after_days=args.stale_after_days,
        decay_amount=args.decay_amount,
        minimum_confidence=args.minimum_confidence,
        dry_run=not args.apply,
    )
    indent = 2 if args.pretty else None
    json.dump(payload, sys.stdout, indent=indent, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
