"""CLI for controlled execution receipts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.controlled_execution_receipt import (
    CONTROLLED_EXECUTION_RECEIPT_FILENAME,
    build_controlled_execution_receipt,
    summarize_controlled_execution_receipts,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-receipt")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_controlled_execution_receipts(
            args.profile / CONTROLLED_EXECUTION_RECEIPT_FILENAME
        )
    else:
        payload = build_controlled_execution_receipt(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
