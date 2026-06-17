"""CLI for compact profile views."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.profile_panel_snapshot import build_profile_panel_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-view")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    payload = build_profile_panel_snapshot(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
