"""CLI for profile status summaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.receipt_summary import (
    RECEIPT_SUMMARY_FILENAME,
    build_receipt_summary,
    summarize_receipt_summaries,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-status-summary")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_receipt_summaries(args.profile / RECEIPT_SUMMARY_FILENAME)
    else:
        payload = build_receipt_summary(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
