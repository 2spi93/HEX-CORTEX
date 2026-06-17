"""CLI for review closeout reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.review_closeout_report import (
    REVIEW_CLOSEOUT_REPORT_FILENAME,
    build_review_closeout_report,
    summarize_review_closeout_reports,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-closeout")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_review_closeout_reports(
            args.profile / REVIEW_CLOSEOUT_REPORT_FILENAME
        )
    else:
        payload = build_review_closeout_report(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
