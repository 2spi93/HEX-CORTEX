"""CLI for construction status reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.construction_status_report import (
    CONSTRUCTION_STATUS_REPORT_FILENAME,
    build_construction_status_report,
    summarize_construction_status_reports,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-status")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_construction_status_reports(
            args.profile / CONSTRUCTION_STATUS_REPORT_FILENAME
        )
    else:
        payload = build_construction_status_report(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
