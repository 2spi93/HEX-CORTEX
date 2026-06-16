"""CLI entrypoint for memory confidence recovery."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.confidence_recovery import run_memory_confidence_recovery_profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="memory-confidence-recovery")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--recovery-amount", type=float, default=0.02)
    parser.add_argument("--recovery-ceiling", type=float, default=0.7)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    payload = run_memory_confidence_recovery_profile(
        args.profile,
        limit=args.limit,
        recovery_amount=args.recovery_amount,
        recovery_ceiling=args.recovery_ceiling,
        dry_run=not args.apply,
    )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
