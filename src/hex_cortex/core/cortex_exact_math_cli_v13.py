"""Operator-facing exact MathCell command, offline and side-effect free."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from hex_cortex.core.cortex_exact_math_v13 import calculate_exact


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hexcortex-math",
        description="Bounded exact-rational mathematics without an LLM",
    )
    parser.add_argument("--expression", required=True, help="integer rational expression")
    parser.add_argument(
        "--approve-calculate", action="store_true",
        help="Explicitly authorize exact calculation of the given expression",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    report = calculate_exact(args.expression, approved=args.approve_calculate)
    print(json.dumps(report, sort_keys=True, indent=2 if args.pretty else None))
    return 0 if report["status"] == "verified_exact_arithmetic" else 2


if __name__ == "__main__":
    raise SystemExit(main())
