"""CLI for profile dispatch history summaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.profile_dispatch_history import (
    DISPATCH_HISTORY_FILENAME,
    summarize_profile_dispatch_history,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-dispatch-history")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    payload = summarize_profile_dispatch_history(args.profile / DISPATCH_HISTORY_FILENAME)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
