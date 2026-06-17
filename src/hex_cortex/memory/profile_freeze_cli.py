"""CLI for construction freeze stamps."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.construction_freeze_stamp import (
    CONSTRUCTION_FREEZE_STAMP_FILENAME,
    build_construction_freeze_stamp,
    summarize_construction_freeze_stamps,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-freeze")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_construction_freeze_stamps(
            args.profile / CONSTRUCTION_FREEZE_STAMP_FILENAME
        )
    else:
        payload = build_construction_freeze_stamp(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
