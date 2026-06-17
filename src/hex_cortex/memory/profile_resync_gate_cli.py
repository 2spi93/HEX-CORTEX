"""CLI for profile resync gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.profile_resync_gate import (
    PROFILE_RESYNC_GATE_FILENAME,
    build_profile_resync_gate,
    summarize_profile_resync_gates,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-resync-gate")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_profile_resync_gates(args.profile / PROFILE_RESYNC_GATE_FILENAME)
    else:
        payload = build_profile_resync_gate(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
