"""CLI for operator runtime readiness markers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.operator_runtime_ready import OPERATOR_RUNTIME_READY_FILENAME
from hex_cortex.memory.operator_runtime_ready import build_operator_runtime_ready
from hex_cortex.memory.operator_runtime_ready import summarize_operator_runtime_ready


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="operator-runtime-ready")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_operator_runtime_ready(
            args.profile / OPERATOR_RUNTIME_READY_FILENAME
        )
    else:
        payload = build_operator_runtime_ready(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
