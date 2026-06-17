"""CLI for planner packet statistics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.planner_packet_stats import (
    PLANNER_STATS_FILENAME,
    build_planner_packet_stats,
    summarize_planner_packet_stats,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-stats")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_planner_packet_stats(args.profile / PLANNER_STATS_FILENAME)
    else:
        payload = build_planner_packet_stats(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
